from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import BuyPlanInput, BuyPlanResult, SavedPlan, SellPlanInput, SellPlanResult, Symbol


class PlannerStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self.memory_fallback = False
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            self._configure_connection()
        except sqlite3.OperationalError as exc:
            if "disk I/O error" not in str(exc):
                raise
            self.memory_fallback = True
            self.conn = sqlite3.connect(":memory:")
            self.conn.row_factory = sqlite3.Row
            self._configure_connection()

    def init_schema(self) -> None:
        try:
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS symbols (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol_code TEXT NOT NULL UNIQUE,
                    symbol_name TEXT NOT NULL DEFAULT '',
                    asset_type TEXT NOT NULL DEFAULT 'stock',
                    currency TEXT NOT NULL DEFAULT 'USD',
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS buy_plan_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol_id INTEGER NOT NULL,
                    initial_price TEXT NOT NULL,
                    planned_capital TEXT NOT NULL,
                    buy_frequency_pct TEXT NOT NULL,
                    buy_count INTEGER NOT NULL,
                    base_quantity TEXT NOT NULL,
                    multipliers_json TEXT NOT NULL,
                    quantity_precision INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(symbol_id) REFERENCES symbols(id)
                );

                CREATE TABLE IF NOT EXISTS buy_plan_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    buy_plan_config_id INTEGER NOT NULL,
                    node_index INTEGER NOT NULL,
                    price TEXT NOT NULL,
                    quantity TEXT NOT NULL,
                    multiplier TEXT NOT NULL,
                    capital_used TEXT NOT NULL,
                    cumulative_capital TEXT NOT NULL,
                    cumulative_quantity TEXT NOT NULL,
                    average_cost TEXT NOT NULL,
                    FOREIGN KEY(buy_plan_config_id) REFERENCES buy_plan_configs(id)
                );

                CREATE TABLE IF NOT EXISTS sell_plan_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol_id INTEGER NOT NULL,
                    average_cost TEXT NOT NULL,
                    total_position_quantity TEXT NOT NULL,
                    intended_sell_quantity TEXT NOT NULL,
                    target_capital_recovery TEXT NOT NULL,
                    initial_sell_price TEXT NOT NULL,
                    initial_capital_plan_price TEXT NOT NULL,
                    sell_frequency_pct TEXT NOT NULL,
                    sell_count INTEGER NOT NULL,
                    multipliers_json TEXT NOT NULL,
                    quantity_precision INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(symbol_id) REFERENCES symbols(id)
                );

                CREATE TABLE IF NOT EXISTS sell_plan_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sell_plan_config_id INTEGER NOT NULL,
                    node_index INTEGER NOT NULL,
                    sell_price TEXT NOT NULL,
                    capital_plan_price TEXT NOT NULL,
                    quantity TEXT NOT NULL,
                    multiplier TEXT NOT NULL,
                    recovered_capital TEXT NOT NULL,
                    planned_capital TEXT NOT NULL,
                    cumulative_recovered_capital TEXT NOT NULL,
                    cumulative_planned_capital TEXT NOT NULL,
                    remaining_quantity TEXT NOT NULL,
                    FOREIGN KEY(sell_plan_config_id) REFERENCES sell_plan_configs(id)
                );
                """
            )
            self.conn.commit()
        except sqlite3.OperationalError as exc:
            if self.memory_fallback or "disk I/O error" not in str(exc):
                raise
            self.memory_fallback = True
            self.conn.close()
            self.conn = sqlite3.connect(":memory:")
            self.conn.row_factory = sqlite3.Row
            self._configure_connection()
            self.init_schema()

    def save_symbol(self, symbol: Symbol) -> int:
        cursor = self.conn.execute(
            """
            INSERT INTO symbols (symbol_code, symbol_name, asset_type, currency, notes)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(symbol_code) DO UPDATE SET
                symbol_name = excluded.symbol_name,
                asset_type = excluded.asset_type,
                currency = excluded.currency,
                notes = excluded.notes,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id
            """,
            (symbol.symbol_code, symbol.symbol_name, symbol.asset_type, symbol.currency, symbol.notes),
        )
        row = cursor.fetchone()
        self.conn.commit()
        return int(row["id"])

    def list_symbols(self) -> list[Symbol]:
        rows = self.conn.execute(
            """
            SELECT id, symbol_code, symbol_name, asset_type, currency, notes
            FROM symbols
            ORDER BY symbol_code
            """
        ).fetchall()
        return [
            Symbol(
                id=int(row["id"]),
                symbol_code=row["symbol_code"],
                symbol_name=row["symbol_name"],
                asset_type=row["asset_type"],
                currency=row["currency"],
                notes=row["notes"],
            )
            for row in rows
        ]

    def get_symbol(self, symbol_id: int) -> Symbol:
        row = self.conn.execute(
            """
            SELECT id, symbol_code, symbol_name, asset_type, currency, notes
            FROM symbols
            WHERE id = ?
            """,
            (symbol_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"未找到标的 {symbol_id}")
        return Symbol(
            id=int(row["id"]),
            symbol_code=row["symbol_code"],
            symbol_name=row["symbol_name"],
            asset_type=row["asset_type"],
            currency=row["currency"],
            notes=row["notes"],
        )

    def save_buy_plan(self, symbol_id: int, plan: BuyPlanInput, result: BuyPlanResult) -> int:
        cursor = self.conn.execute(
            """
            INSERT INTO buy_plan_configs (
                symbol_id, initial_price, planned_capital, buy_frequency_pct, buy_count,
                base_quantity, multipliers_json, quantity_precision
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                symbol_id,
                str(plan.initial_price),
                str(plan.planned_capital),
                str(plan.buy_frequency_pct),
                plan.buy_count,
                str(plan.base_quantity),
                json.dumps([str(value) for value in plan.multipliers], ensure_ascii=False),
                plan.quantity_precision,
            ),
        )
        config_id = int(cursor.lastrowid)
        self.conn.executemany(
            """
            INSERT INTO buy_plan_results (
                buy_plan_config_id, node_index, price, quantity, multiplier,
                capital_used, cumulative_capital, cumulative_quantity, average_cost
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    config_id,
                    node.node_index,
                    str(node.price),
                    str(node.quantity),
                    str(node.multiplier),
                    str(node.capital_used),
                    str(node.cumulative_capital),
                    str(node.cumulative_quantity),
                    str(node.average_cost),
                )
                for node in result.nodes
            ],
        )
        self.conn.commit()
        return config_id

    def save_sell_plan(self, symbol_id: int, plan: SellPlanInput, result: SellPlanResult) -> int:
        cursor = self.conn.execute(
            """
            INSERT INTO sell_plan_configs (
                symbol_id, average_cost, total_position_quantity, intended_sell_quantity,
                target_capital_recovery, initial_sell_price, initial_capital_plan_price,
                sell_frequency_pct, sell_count, multipliers_json, quantity_precision
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                symbol_id,
                str(plan.average_cost),
                str(plan.total_position_quantity),
                str(plan.intended_sell_quantity),
                str(plan.target_capital_recovery),
                str(plan.initial_sell_price),
                str(plan.initial_capital_plan_price),
                str(plan.sell_frequency_pct),
                plan.sell_count,
                json.dumps([str(value) for value in plan.multipliers], ensure_ascii=False),
                plan.quantity_precision,
            ),
        )
        config_id = int(cursor.lastrowid)
        self.conn.executemany(
            """
            INSERT INTO sell_plan_results (
                sell_plan_config_id, node_index, sell_price, capital_plan_price, quantity,
                multiplier, recovered_capital, planned_capital, cumulative_recovered_capital,
                cumulative_planned_capital, remaining_quantity
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    config_id,
                    node.node_index,
                    str(node.sell_price),
                    str(node.capital_plan_price),
                    str(node.quantity),
                    str(node.multiplier),
                    str(node.recovered_capital),
                    str(node.planned_capital),
                    str(node.cumulative_recovered_capital),
                    str(node.cumulative_planned_capital),
                    str(node.remaining_quantity),
                )
                for node in result.nodes
            ],
        )
        self.conn.commit()
        return config_id

    def list_buy_plans(self) -> list[dict[str, str | int]]:
        rows = self.conn.execute(
            """
            SELECT
                b.id AS config_id,
                b.symbol_id,
                s.symbol_code,
                s.symbol_name,
                b.initial_price,
                b.planned_capital,
                b.buy_frequency_pct,
                b.buy_count,
                b.base_quantity,
                b.created_at
            FROM buy_plan_configs b
            JOIN symbols s ON s.id = b.symbol_id
            ORDER BY b.id DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def list_sell_plans(self) -> list[dict[str, str | int]]:
        rows = self.conn.execute(
            """
            SELECT
                splan.id AS config_id,
                splan.symbol_id,
                sym.symbol_code,
                sym.symbol_name,
                splan.average_cost,
                splan.total_position_quantity,
                splan.intended_sell_quantity,
                splan.target_capital_recovery,
                splan.sell_count,
                splan.created_at
            FROM sell_plan_configs splan
            JOIN symbols sym ON sym.id = splan.symbol_id
            ORDER BY splan.id DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def get_buy_plan(self, config_id: int) -> SavedPlan:
        config_row = self.conn.execute(
            "SELECT * FROM buy_plan_configs WHERE id = ?",
            (config_id,),
        ).fetchone()
        if config_row is None:
            raise KeyError(f"未找到买入计划 {config_id}")
        node_rows = self.conn.execute(
            "SELECT * FROM buy_plan_results WHERE buy_plan_config_id = ? ORDER BY node_index",
            (config_id,),
        ).fetchall()
        return SavedPlan(
            config_id=config_id,
            symbol_id=int(config_row["symbol_id"]),
            config=dict(config_row),
            nodes=[dict(row) for row in node_rows],
        )

    def get_sell_plan(self, config_id: int) -> SavedPlan:
        config_row = self.conn.execute(
            "SELECT * FROM sell_plan_configs WHERE id = ?",
            (config_id,),
        ).fetchone()
        if config_row is None:
            raise KeyError(f"未找到卖出计划 {config_id}")
        node_rows = self.conn.execute(
            "SELECT * FROM sell_plan_results WHERE sell_plan_config_id = ? ORDER BY node_index",
            (config_id,),
        ).fetchall()
        return SavedPlan(
            config_id=config_id,
            symbol_id=int(config_row["symbol_id"]),
            config=dict(config_row),
            nodes=[dict(row) for row in node_rows],
        )

    def close(self) -> None:
        self.conn.close()

    def _configure_connection(self) -> None:
        self.conn.execute("PRAGMA temp_store = MEMORY;")
        try:
            self.conn.execute("PRAGMA journal_mode = MEMORY;")
            self.conn.execute("PRAGMA synchronous = OFF;")
        except sqlite3.OperationalError:
            pass
