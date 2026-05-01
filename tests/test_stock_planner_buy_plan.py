from decimal import Decimal

import pytest

from stock_planner_project.stock_planner.models import BuyPlanInput
from stock_planner_project.stock_planner.services.buy_plan import calculate_buy_plan


def test_buy_plan_calculates_price_ladder_and_compounded_quantities() -> None:
    plan = BuyPlanInput(
        symbol_code="NVDA",
        initial_price=100,
        planned_capital=500000,
        buy_frequency_pct=0.05,
        buy_count=6,
        base_quantity=200,
        multipliers=[1, 1, 1.5, 1.5, 2, 2],
    )

    result = calculate_buy_plan(plan)

    assert [node.price for node in result.nodes] == [
        Decimal("100.00"),
        Decimal("95.00"),
        Decimal("90.25"),
        Decimal("85.74"),
        Decimal("81.45"),
        Decimal("77.38"),
    ]
    assert [node.quantity for node in result.nodes] == [
        Decimal("200"),
        Decimal("200"),
        Decimal("300"),
        Decimal("450"),
        Decimal("900"),
        Decimal("1800"),
    ]
    assert result.total_quantity == Decimal("3850")
    assert result.total_capital == Decimal("317247.00")
    assert result.average_cost == Decimal("82.40")
    assert result.over_budget is False
    assert result.budget_gap == Decimal("182753.00")


def test_buy_plan_marks_over_budget() -> None:
    plan = BuyPlanInput(
        symbol_code="QQQ",
        initial_price=100,
        planned_capital=1000,
        buy_frequency_pct=0.05,
        buy_count=2,
        base_quantity=10,
        multipliers=[1, 2],
    )

    result = calculate_buy_plan(plan)

    assert result.over_budget is True
    assert result.budget_gap == Decimal("-1900.00")
    assert result.warnings


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"symbol_code": ""}, "标的代码不能为空。"),
        ({"buy_count": 0}, "买入次数必须大于 0。"),
        ({"multipliers": [1]}, "买单倍数数量必须与买入次数一致。"),
        ({"buy_frequency_pct": 1}, "买入频率必须在 0 到 1 之间。"),
    ],
)
def test_buy_plan_validation(overrides: dict[str, object], message: str) -> None:
    payload = {
        "symbol_code": "NVDA",
        "initial_price": 100,
        "planned_capital": 1000,
        "buy_frequency_pct": 0.05,
        "buy_count": 2,
        "base_quantity": 10,
        "multipliers": [1, 1],
    }
    payload.update(overrides)

    with pytest.raises(ValueError, match=message):
        calculate_buy_plan(BuyPlanInput(**payload))
