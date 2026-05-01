from stock_planner_project.stock_planner.models import BuyPlanInput, SellPlanInput, Symbol
from stock_planner_project.stock_planner.services.buy_plan import calculate_buy_plan
from stock_planner_project.stock_planner.services.sell_plan import calculate_sell_plan
from stock_planner_project.stock_planner.storage import PlannerStore


def test_storage_can_save_and_reload_buy_and_sell_plans() -> None:
    store = PlannerStore(":memory:")
    store.init_schema()

    symbol_id = store.save_symbol(Symbol(symbol_code="NVDA", symbol_name="NVIDIA"))

    buy_plan = BuyPlanInput(
        symbol_code="NVDA",
        initial_price=100,
        planned_capital=500000,
        buy_frequency_pct=0.05,
        buy_count=3,
        base_quantity=200,
        multipliers=[1, 1, 1.5],
    )
    buy_result = calculate_buy_plan(buy_plan)
    buy_config_id = store.save_buy_plan(symbol_id, buy_plan, buy_result)

    sell_plan = SellPlanInput(
        symbol_code="NVDA",
        average_cost=buy_result.average_cost,
        total_position_quantity=buy_result.total_quantity,
        intended_sell_quantity=200,
        target_capital_recovery=20000,
        initial_sell_price=95,
        initial_capital_plan_price=120,
        sell_frequency_pct=0.20,
        sell_count=2,
        multipliers=[2, 3],
    )
    sell_result = calculate_sell_plan(sell_plan)
    sell_config_id = store.save_sell_plan(symbol_id, sell_plan, sell_result)

    saved_buy = store.get_buy_plan(buy_config_id)
    saved_sell = store.get_sell_plan(sell_config_id)
    store.close()

    assert saved_buy.symbol_id == symbol_id
    assert len(saved_buy.nodes) == 3
    assert saved_buy.nodes[0]["price"] == "100.00"

    assert saved_sell.symbol_id == symbol_id
    assert len(saved_sell.nodes) == 2
    assert saved_sell.nodes[-1]["remaining_quantity"] == "500"
