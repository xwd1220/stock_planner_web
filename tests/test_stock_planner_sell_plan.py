from decimal import Decimal

import pytest

from stock_planner_project.stock_planner.models import SellPlanInput
from stock_planner_project.stock_planner.services.sell_plan import calculate_sell_plan


def test_sell_plan_allocates_quantities_by_weight_and_reconciles_rounding() -> None:
    plan = SellPlanInput(
        symbol_code="NVDA",
        average_cost=72.52,
        total_position_quantity=5575,
        intended_sell_quantity=1673,
        target_capital_recovery=404282.75,
        initial_sell_price=94.28,
        initial_capital_plan_price=157.19,
        sell_frequency_pct=0.30,
        sell_count=4,
        multipliers=[2, 3, 3, 2],
    )

    result = calculate_sell_plan(plan)

    assert [node.sell_price for node in result.nodes] == [
        Decimal("94.28"),
        Decimal("122.56"),
        Decimal("159.33"),
        Decimal("207.13"),
    ]
    assert [node.capital_plan_price for node in result.nodes] == [
        Decimal("157.19"),
        Decimal("204.35"),
        Decimal("265.66"),
        Decimal("345.36"),
    ]
    assert [node.quantity for node in result.nodes] == [
        Decimal("334"),
        Decimal("501"),
        Decimal("501"),
        Decimal("337"),
    ]
    assert result.total_recovered_capital == Decimal("242519.22")
    assert result.total_planned_capital == Decimal("404362.79")
    assert result.remaining_quantity == Decimal("3902")
    assert result.recovery_gap == Decimal("161763.53")
    assert result.warnings == ["预计回收资金比目标少 161763.53 美元。"]


def test_sell_plan_rejects_quantity_above_total_position() -> None:
    plan = SellPlanInput(
        symbol_code="NVDA",
        average_cost=72.52,
        total_position_quantity=100,
        intended_sell_quantity=101,
        target_capital_recovery=1000,
        initial_sell_price=90,
        initial_capital_plan_price=120,
        sell_frequency_pct=0.30,
        sell_count=2,
        multipliers=[1, 1],
    )

    with pytest.raises(ValueError, match="计划卖出数量不能超过总持仓数量。"):
        calculate_sell_plan(plan)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"symbol_code": ""}, "标的代码不能为空。"),
        ({"sell_count": 0}, "卖出次数必须大于 0。"),
        ({"multipliers": [1]}, "卖单倍数数量必须与卖出次数一致。"),
        ({"sell_frequency_pct": 1}, "卖出频率必须在 0 到 1 之间。"),
    ],
)
def test_sell_plan_validation(overrides: dict[str, object], message: str) -> None:
    payload = {
        "symbol_code": "NVDA",
        "average_cost": 72.52,
        "total_position_quantity": 100,
        "intended_sell_quantity": 50,
        "target_capital_recovery": 1000,
        "initial_sell_price": 90,
        "initial_capital_plan_price": 120,
        "sell_frequency_pct": 0.30,
        "sell_count": 2,
        "multipliers": [1, 1],
    }
    payload.update(overrides)

    with pytest.raises(ValueError, match=message):
        calculate_sell_plan(SellPlanInput(**payload))
