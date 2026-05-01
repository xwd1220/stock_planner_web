from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from .models import BuyPlanInput, SellPlanInput, Symbol
from .services.buy_plan import calculate_buy_plan
from .services.sell_plan import calculate_sell_plan
from .storage import PlannerStore
from .web import run_server


def bootstrap_demo(db_path: str = ".runtime/stock_planner.db") -> dict[str, object]:
    store = PlannerStore(db_path)
    store.init_schema()

    symbol = Symbol(symbol_code="NVDA", symbol_name="NVIDIA", asset_type="stock")
    symbol_id = store.save_symbol(symbol)

    buy_input = BuyPlanInput(
        symbol_code="NVDA",
        initial_price=100,
        planned_capital=500000,
        buy_frequency_pct=0.05,
        buy_count=6,
        base_quantity=200,
        multipliers=[1, 1, 1.5, 1.5, 2, 2],
    )
    buy_result = calculate_buy_plan(buy_input)
    buy_plan_id = store.save_buy_plan(symbol_id, buy_input, buy_result)

    sell_input = SellPlanInput(
        symbol_code="NVDA",
        average_cost=buy_result.average_cost,
        total_position_quantity=buy_result.total_quantity,
        intended_sell_quantity=1673,
        target_capital_recovery=404282.75,
        initial_sell_price=94.28,
        initial_capital_plan_price=157.19,
        sell_frequency_pct=0.30,
        sell_count=4,
        multipliers=[2, 3, 3, 2],
    )
    sell_result = calculate_sell_plan(sell_input)
    sell_plan_id = store.save_sell_plan(symbol_id, sell_input, sell_result)
    store.close()

    return {
        "memory_fallback": store.memory_fallback,
        "symbol_id": symbol_id,
        "buy_plan_id": buy_plan_id,
        "sell_plan_id": sell_plan_id,
        "buy_result": _serialize_result(asdict(buy_result)),
        "sell_result": _serialize_result(asdict(sell_result)),
    }


def _serialize_result(payload: dict[str, object]) -> dict[str, object]:
    return json.loads(json.dumps(payload, ensure_ascii=False, default=str))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="股票交易计划工具")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("demo", help="生成演示数据并打印结果")

    serve_parser = subparsers.add_parser("serve", help="启动本地 Web 服务")
    serve_parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    serve_parser.add_argument("--port", type=int, default=8008, help="监听端口")
    serve_parser.add_argument("--db-path", default=".runtime/stock_planner.db", help="SQLite 路径")

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.command == "serve":
        run_server(host=args.host, port=args.port, db_path=args.db_path)
    else:
        print(json.dumps(bootstrap_demo(), ensure_ascii=False, indent=2))
