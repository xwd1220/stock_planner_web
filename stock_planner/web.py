from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Callable
from wsgiref.simple_server import make_server

from .models import BuyPlanInput, SellPlanInput, Symbol
from .services.buy_plan import calculate_buy_plan
from .services.sell_plan import calculate_sell_plan
from .storage import PlannerStore


class PlannerWebApp:
    def __init__(self, db_path: str = ".runtime/stock_planner.db") -> None:
        self.store = PlannerStore(db_path)
        self.store.init_schema()
        self.static_dir = Path(__file__).with_name("static")
        self.index_html = (self.static_dir / "index.html").read_text(encoding="utf-8")

    def __call__(self, environ: dict[str, object], start_response: Callable[..., object]) -> list[bytes]:
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        path = str(environ.get("PATH_INFO", "/"))
        try:
            status_code, content_type, payload = self.dispatch(
                method=method,
                path=path,
                body=self._read_body(environ),
            )
        except Exception as exc:  # pragma: no cover
            status_code = 500
            content_type = "application/json; charset=utf-8"
            payload = self._to_json_bytes({"error": str(exc)})

        status_text = {
            200: "200 OK",
            201: "201 Created",
            400: "400 Bad Request",
            404: "404 Not Found",
            500: "500 Internal Server Error",
        }[status_code]
        start_response(status_text, [("Content-Type", content_type), ("Content-Length", str(len(payload)))])
        return [payload]

    def dispatch(self, method: str, path: str, body: bytes = b"") -> tuple[int, str, bytes]:
        if method == "GET" and path == "/":
            return 200, "text/html; charset=utf-8", self.index_html.encode("utf-8")
        if method == "GET" and path == "/health":
            return 200, "application/json; charset=utf-8", self._to_json_bytes({"status": "ok"})
        if method == "GET" and path == "/api/symbols":
            return 200, "application/json; charset=utf-8", self._to_json_bytes({"items": [asdict(s) for s in self.store.list_symbols()]})
        if method == "POST" and path == "/api/symbols":
            return self._handle_save_symbol(body)
        if method == "POST" and path == "/api/buy-plans/calculate":
            return self._handle_calculate_buy_plan(body)
        if method == "POST" and path == "/api/sell-plans/calculate":
            return self._handle_calculate_sell_plan(body)
        if method == "GET" and path == "/api/buy-plans":
            return 200, "application/json; charset=utf-8", self._to_json_bytes({"items": self.store.list_buy_plans()})
        if method == "GET" and path == "/api/sell-plans":
            return 200, "application/json; charset=utf-8", self._to_json_bytes({"items": self.store.list_sell_plans()})
        if method == "POST" and path == "/api/buy-plans":
            return self._handle_save_buy_plan(body)
        if method == "POST" and path == "/api/sell-plans":
            return self._handle_save_sell_plan(body)
        if method == "GET" and path.startswith("/api/buy-plans/"):
            return self._handle_get_buy_plan(path)
        if method == "GET" and path.startswith("/api/sell-plans/"):
            return self._handle_get_sell_plan(path)
        return 404, "application/json; charset=utf-8", self._to_json_bytes({"error": "未找到接口。"})

    def _handle_save_symbol(self, body: bytes) -> tuple[int, str, bytes]:
        payload = self._read_json(body)
        symbol = Symbol(
            symbol_code=str(payload.get("symbol_code", "")).strip().upper(),
            symbol_name=str(payload.get("symbol_name", "")).strip(),
            asset_type=str(payload.get("asset_type", "stock")).strip() or "stock",
            currency=str(payload.get("currency", "USD")).strip() or "USD",
            notes=str(payload.get("notes", "")).strip(),
        )
        if not symbol.symbol_code:
            return 400, "application/json; charset=utf-8", self._to_json_bytes({"error": "标的代码不能为空。"})
        symbol_id = self.store.save_symbol(symbol)
        return 201, "application/json; charset=utf-8", self._to_json_bytes(asdict(self.store.get_symbol(symbol_id)))

    def _handle_calculate_buy_plan(self, body: bytes) -> tuple[int, str, bytes]:
        try:
            result = calculate_buy_plan(self._build_buy_plan(self._read_json(body)))
        except ValueError as exc:
            return 400, "application/json; charset=utf-8", self._to_json_bytes({"error": str(exc)})
        return 200, "application/json; charset=utf-8", self._to_json_bytes(asdict(result))

    def _handle_calculate_sell_plan(self, body: bytes) -> tuple[int, str, bytes]:
        try:
            result = calculate_sell_plan(self._build_sell_plan(self._read_json(body)))
        except ValueError as exc:
            return 400, "application/json; charset=utf-8", self._to_json_bytes({"error": str(exc)})
        return 200, "application/json; charset=utf-8", self._to_json_bytes(asdict(result))

    def _handle_save_buy_plan(self, body: bytes) -> tuple[int, str, bytes]:
        payload = self._read_json(body)
        symbol_id = int(payload.get("symbol_id", 0))
        if symbol_id <= 0:
            return 400, "application/json; charset=utf-8", self._to_json_bytes({"error": "symbol_id 无效。"})
        try:
            plan = self._build_buy_plan(payload.get("plan", {}))
            result = calculate_buy_plan(plan)
        except ValueError as exc:
            return 400, "application/json; charset=utf-8", self._to_json_bytes({"error": str(exc)})
        config_id = self.store.save_buy_plan(symbol_id, plan, result)
        return 201, "application/json; charset=utf-8", self._to_json_bytes({"config_id": config_id})

    def _handle_save_sell_plan(self, body: bytes) -> tuple[int, str, bytes]:
        payload = self._read_json(body)
        symbol_id = int(payload.get("symbol_id", 0))
        if symbol_id <= 0:
            return 400, "application/json; charset=utf-8", self._to_json_bytes({"error": "symbol_id 无效。"})
        try:
            plan = self._build_sell_plan(payload.get("plan", {}))
            result = calculate_sell_plan(plan)
        except ValueError as exc:
            return 400, "application/json; charset=utf-8", self._to_json_bytes({"error": str(exc)})
        config_id = self.store.save_sell_plan(symbol_id, plan, result)
        return 201, "application/json; charset=utf-8", self._to_json_bytes({"config_id": config_id})

    def _handle_get_buy_plan(self, path: str) -> tuple[int, str, bytes]:
        try:
            config_id = int(path.rsplit("/", 1)[-1])
            plan = self.store.get_buy_plan(config_id)
        except (ValueError, KeyError) as exc:
            return 404, "application/json; charset=utf-8", self._to_json_bytes({"error": str(exc)})
        return 200, "application/json; charset=utf-8", self._to_json_bytes(asdict(plan))

    def _handle_get_sell_plan(self, path: str) -> tuple[int, str, bytes]:
        try:
            config_id = int(path.rsplit("/", 1)[-1])
            plan = self.store.get_sell_plan(config_id)
        except (ValueError, KeyError) as exc:
            return 404, "application/json; charset=utf-8", self._to_json_bytes({"error": str(exc)})
        return 200, "application/json; charset=utf-8", self._to_json_bytes(asdict(plan))

    @staticmethod
    def _build_buy_plan(payload: dict[str, object]) -> BuyPlanInput:
        return BuyPlanInput(
            symbol_code=str(payload.get("symbol_code", "")).strip().upper(),
            initial_price=payload.get("initial_price", 0),
            planned_capital=payload.get("planned_capital", 0),
            buy_frequency_pct=payload.get("buy_frequency_pct", 0),
            buy_count=int(payload.get("buy_count", 0)),
            base_quantity=payload.get("base_quantity", 0),
            multipliers=payload.get("multipliers", []),
            quantity_precision=int(payload.get("quantity_precision", 0)),
        )

    @staticmethod
    def _build_sell_plan(payload: dict[str, object]) -> SellPlanInput:
        return SellPlanInput(
            symbol_code=str(payload.get("symbol_code", "")).strip().upper(),
            average_cost=payload.get("average_cost", 0),
            total_position_quantity=payload.get("total_position_quantity", 0),
            intended_sell_quantity=payload.get("intended_sell_quantity", 0),
            target_capital_recovery=payload.get("target_capital_recovery", 0),
            initial_sell_price=payload.get("initial_sell_price", 0),
            initial_capital_plan_price=payload.get("initial_capital_plan_price", 0),
            sell_frequency_pct=payload.get("sell_frequency_pct", 0),
            sell_count=int(payload.get("sell_count", 0)),
            multipliers=payload.get("multipliers", []),
            quantity_precision=int(payload.get("quantity_precision", 0)),
        )

    @staticmethod
    def _read_body(environ: dict[str, object]) -> bytes:
        body_stream = environ.get("wsgi.input")
        if body_stream is None:
            return b""
        content_length = int(environ.get("CONTENT_LENGTH") or 0)
        return body_stream.read(content_length) if content_length > 0 else b""

    @staticmethod
    def _read_json(body: bytes) -> dict[str, object]:
        if not body:
            return {}
        return json.loads(body.decode("utf-8"))

    @staticmethod
    def _to_json_bytes(payload: object) -> bytes:
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")


def run_server(host: str = "127.0.0.1", port: int = 8008, db_path: str = ".runtime/stock_planner.db") -> None:
    app = PlannerWebApp(db_path=db_path)
    with make_server(host, port, app) as server:
        print(f"Stock Planner 已启动: http://{host}:{port}")
        if app.store.memory_fallback:
            print("当前环境无法写入 SQLite 文件，已自动切换到内存库。")
        server.serve_forever()
