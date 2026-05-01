import json
from io import BytesIO

from stock_planner_project.stock_planner.web import PlannerWebApp


def _call_app(app: PlannerWebApp, method: str, path: str, payload: dict[str, object] | None = None) -> tuple[str, bytes]:
    body = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8") if payload is not None else b""
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": BytesIO(body),
    }
    captured: dict[str, object] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured["status"] = status
        captured["headers"] = headers

    response = b"".join(app(environ, start_response))
    return str(captured["status"]), response


def test_health_endpoint_returns_ok() -> None:
    app = PlannerWebApp(db_path=":memory:")
    status, response = _call_app(app, "GET", "/health")

    assert status == "200 OK"
    assert json.loads(response.decode("utf-8")) == {"status": "ok"}


def test_symbol_buy_and_sell_endpoints_work_together() -> None:
    app = PlannerWebApp(db_path=":memory:")

    save_status, save_response = _call_app(
        app,
        "POST",
        "/api/symbols",
        {
            "symbol_code": "NVDA",
            "symbol_name": "NVIDIA",
            "asset_type": "stock",
            "currency": "USD",
        },
    )
    saved_symbol = json.loads(save_response.decode("utf-8"))

    buy_status, buy_response = _call_app(
        app,
        "POST",
        "/api/buy-plans/calculate",
        {
            "symbol_code": "NVDA",
            "initial_price": 100,
            "planned_capital": 500000,
            "buy_frequency_pct": 0.05,
            "buy_count": 3,
            "base_quantity": 200,
            "multipliers": [1, 1, 1.5],
        },
    )
    buy_payload = json.loads(buy_response.decode("utf-8"))

    sell_status, sell_response = _call_app(
        app,
        "POST",
        "/api/sell-plans/calculate",
        {
            "symbol_code": "NVDA",
            "average_cost": buy_payload["average_cost"],
            "total_position_quantity": buy_payload["total_quantity"],
            "intended_sell_quantity": 200,
            "target_capital_recovery": 20000,
            "initial_sell_price": 95,
            "initial_capital_plan_price": 120,
            "sell_frequency_pct": 0.20,
            "sell_count": 2,
            "multipliers": [2, 3],
        },
    )
    sell_payload = json.loads(sell_response.decode("utf-8"))

    assert save_status == "201 Created"
    assert saved_symbol["symbol_code"] == "NVDA"
    assert buy_status == "200 OK"
    assert buy_payload["total_quantity"] == "700"
    assert sell_status == "200 OK"
    assert sell_payload["remaining_quantity"] == "500"


def test_saved_plans_appear_in_history_and_can_be_loaded() -> None:
    app = PlannerWebApp(db_path=":memory:")

    save_symbol_status, save_symbol_response = _call_app(
        app,
        "POST",
        "/api/symbols",
        {
            "symbol_code": "NVDA",
            "symbol_name": "NVIDIA",
            "asset_type": "stock",
            "currency": "USD",
        },
    )
    symbol_payload = json.loads(save_symbol_response.decode("utf-8"))
    symbol_id = symbol_payload["id"]

    buy_save_status, buy_save_response = _call_app(
        app,
        "POST",
        "/api/buy-plans",
        {
            "symbol_id": symbol_id,
            "plan": {
                "symbol_code": "NVDA",
                "initial_price": 100,
                "planned_capital": 500000,
                "buy_frequency_pct": 0.05,
                "buy_count": 3,
                "base_quantity": 200,
                "multipliers": [1, 1, 1.5],
            },
        },
    )
    buy_plan_id = json.loads(buy_save_response.decode("utf-8"))["config_id"]

    sell_save_status, sell_save_response = _call_app(
        app,
        "POST",
        "/api/sell-plans",
        {
            "symbol_id": symbol_id,
            "plan": {
                "symbol_code": "NVDA",
                "average_cost": 94.39,
                "total_position_quantity": 700,
                "intended_sell_quantity": 200,
                "target_capital_recovery": 20000,
                "initial_sell_price": 95,
                "initial_capital_plan_price": 120,
                "sell_frequency_pct": 0.20,
                "sell_count": 2,
                "multipliers": [2, 3],
            },
        },
    )
    sell_plan_id = json.loads(sell_save_response.decode("utf-8"))["config_id"]

    buy_history_status, buy_history_response = _call_app(app, "GET", "/api/buy-plans")
    sell_history_status, sell_history_response = _call_app(app, "GET", "/api/sell-plans")
    buy_detail_status, buy_detail_response = _call_app(app, "GET", f"/api/buy-plans/{buy_plan_id}")
    sell_detail_status, sell_detail_response = _call_app(app, "GET", f"/api/sell-plans/{sell_plan_id}")

    buy_history = json.loads(buy_history_response.decode("utf-8"))
    sell_history = json.loads(sell_history_response.decode("utf-8"))
    buy_detail = json.loads(buy_detail_response.decode("utf-8"))
    sell_detail = json.loads(sell_detail_response.decode("utf-8"))

    assert save_symbol_status == "201 Created"
    assert buy_save_status == "201 Created"
    assert sell_save_status == "201 Created"
    assert buy_history_status == "200 OK"
    assert sell_history_status == "200 OK"
    assert buy_history["items"][0]["config_id"] == buy_plan_id
    assert buy_history["items"][0]["symbol_code"] == "NVDA"
    assert sell_history["items"][0]["config_id"] == sell_plan_id
    assert sell_history["items"][0]["symbol_code"] == "NVDA"
    assert buy_detail_status == "200 OK"
    assert buy_detail["config"]["buy_count"] == 3
    assert buy_detail["nodes"][0]["price"] == "100.00"
    assert sell_detail_status == "200 OK"
    assert sell_detail["config"]["sell_count"] == 2
    assert sell_detail["nodes"][-1]["remaining_quantity"] == "500"


def test_buy_plan_endpoint_returns_validation_error() -> None:
    app = PlannerWebApp(db_path=":memory:")

    status, response = _call_app(
        app,
        "POST",
        "/api/buy-plans/calculate",
        {
            "symbol_code": "",
            "initial_price": 100,
            "planned_capital": 500000,
            "buy_frequency_pct": 0.05,
            "buy_count": 3,
            "base_quantity": 200,
            "multipliers": [1, 1, 1.5],
        },
    )

    assert status == "400 Bad Request"
    assert json.loads(response.decode("utf-8"))["error"] == "标的代码不能为空。"
