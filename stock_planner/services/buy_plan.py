from __future__ import annotations

from decimal import Decimal

from ..models import BuyPlanInput, BuyPlanNode, BuyPlanResult
from .rounding import round_money, round_price, round_quantity, to_decimal


def calculate_buy_plan(plan: BuyPlanInput) -> BuyPlanResult:
    _validate_buy_plan(plan)

    frequency = to_decimal(plan.buy_frequency_pct)
    multipliers = [to_decimal(value) for value in plan.multipliers]
    planned_capital = round_money(plan.planned_capital)

    nodes: list[BuyPlanNode] = []
    current_price = round_price(plan.initial_price)
    current_quantity = round_quantity(plan.base_quantity, plan.quantity_precision)
    cumulative_capital = Decimal("0")
    cumulative_quantity = Decimal("0")

    for index in range(plan.buy_count):
        multiplier = multipliers[index]
        if index > 0:
            current_price = round_price(current_price * (Decimal("1") - frequency))
            current_quantity = round_quantity(nodes[-1].quantity * multiplier, plan.quantity_precision)

        capital_used = round_money(current_price * current_quantity)
        cumulative_capital = round_money(cumulative_capital + capital_used)
        cumulative_quantity = round_quantity(cumulative_quantity + current_quantity, plan.quantity_precision)
        average_cost = round_money(cumulative_capital / cumulative_quantity)
        nodes.append(
            BuyPlanNode(
                node_index=index + 1,
                price=current_price,
                quantity=current_quantity,
                multiplier=multiplier,
                capital_used=capital_used,
                cumulative_capital=cumulative_capital,
                cumulative_quantity=cumulative_quantity,
                average_cost=average_cost,
            )
        )

    budget_gap = round_money(planned_capital - cumulative_capital)
    over_budget = cumulative_capital > planned_capital
    warnings: list[str] = []
    if over_budget:
        warnings.append(f"买入计划超出预算 {abs(budget_gap)} 美元。")

    return BuyPlanResult(
        symbol_code=plan.symbol_code,
        nodes=nodes,
        total_capital=cumulative_capital,
        total_quantity=cumulative_quantity,
        average_cost=nodes[-1].average_cost,
        planned_capital=planned_capital,
        over_budget=over_budget,
        budget_gap=budget_gap,
        warnings=warnings,
    )


def _validate_buy_plan(plan: BuyPlanInput) -> None:
    if not plan.symbol_code.strip():
        raise ValueError("标的代码不能为空。")
    if plan.buy_count <= 0:
        raise ValueError("买入次数必须大于 0。")
    if len(plan.multipliers) != plan.buy_count:
        raise ValueError("买单倍数数量必须与买入次数一致。")
    if to_decimal(plan.initial_price) <= 0:
        raise ValueError("初始买入价格必须大于 0。")
    if to_decimal(plan.planned_capital) <= 0:
        raise ValueError("计划资金必须大于 0。")
    if not Decimal("0") < to_decimal(plan.buy_frequency_pct) < Decimal("1"):
        raise ValueError("买入频率必须在 0 到 1 之间。")
    if to_decimal(plan.base_quantity) <= 0:
        raise ValueError("首单数量必须大于 0。")
    for multiplier in plan.multipliers:
        if to_decimal(multiplier) <= 0:
            raise ValueError("买单倍数必须大于 0。")
