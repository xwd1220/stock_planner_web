from __future__ import annotations

from decimal import Decimal

from ..models import SellPlanInput, SellPlanNode, SellPlanResult
from .rounding import round_money, round_price, round_quantity, to_decimal


def calculate_sell_plan(plan: SellPlanInput) -> SellPlanResult:
    _validate_sell_plan(plan)

    frequency = to_decimal(plan.sell_frequency_pct)
    multipliers = [to_decimal(value) for value in plan.multipliers]
    target_capital_recovery = round_money(plan.target_capital_recovery)
    total_position_quantity = round_quantity(plan.total_position_quantity, plan.quantity_precision)
    intended_sell_quantity = round_quantity(plan.intended_sell_quantity, plan.quantity_precision)
    total_multiplier = sum(multipliers, start=Decimal("0"))

    nodes: list[SellPlanNode] = []
    current_sell_price = round_price(plan.initial_sell_price)
    current_capital_plan_price = round_price(plan.initial_capital_plan_price)
    allocated_quantity = Decimal("0")
    cumulative_recovered_capital = Decimal("0")
    cumulative_planned_capital = Decimal("0")

    for index in range(plan.sell_count):
        multiplier = multipliers[index]
        if index > 0:
            current_sell_price = round_price(current_sell_price * (Decimal("1") + frequency))
            current_capital_plan_price = round_price(current_capital_plan_price * (Decimal("1") + frequency))

        if index == plan.sell_count - 1:
            node_quantity = round_quantity(intended_sell_quantity - allocated_quantity, plan.quantity_precision)
        else:
            raw_quantity = intended_sell_quantity * (multiplier / total_multiplier)
            node_quantity = round_quantity(raw_quantity, plan.quantity_precision)
            allocated_quantity = round_quantity(allocated_quantity + node_quantity, plan.quantity_precision)

        recovered_capital = round_money(current_sell_price * node_quantity)
        planned_capital = round_money(current_capital_plan_price * node_quantity)
        cumulative_recovered_capital = round_money(cumulative_recovered_capital + recovered_capital)
        cumulative_planned_capital = round_money(cumulative_planned_capital + planned_capital)
        sold_quantity = round_quantity(sum(item.quantity for item in nodes) + node_quantity, plan.quantity_precision)
        remaining_quantity = round_quantity(total_position_quantity - sold_quantity, plan.quantity_precision)

        nodes.append(
            SellPlanNode(
                node_index=index + 1,
                sell_price=current_sell_price,
                capital_plan_price=current_capital_plan_price,
                quantity=node_quantity,
                multiplier=multiplier,
                recovered_capital=recovered_capital,
                planned_capital=planned_capital,
                cumulative_recovered_capital=cumulative_recovered_capital,
                cumulative_planned_capital=cumulative_planned_capital,
                remaining_quantity=remaining_quantity,
            )
        )

    recovery_gap = round_money(target_capital_recovery - cumulative_recovered_capital)
    warnings: list[str] = []
    if recovery_gap > 0:
        warnings.append(f"预计回收资金比目标少 {recovery_gap} 美元。")
    elif recovery_gap < 0:
        warnings.append(f"预计回收资金比目标多 {abs(recovery_gap)} 美元。")

    return SellPlanResult(
        symbol_code=plan.symbol_code,
        nodes=nodes,
        total_position_quantity=total_position_quantity,
        intended_sell_quantity=intended_sell_quantity,
        total_recovered_capital=cumulative_recovered_capital,
        total_planned_capital=cumulative_planned_capital,
        remaining_quantity=nodes[-1].remaining_quantity,
        average_cost=round_money(plan.average_cost),
        target_capital_recovery=target_capital_recovery,
        recovery_gap=recovery_gap,
        warnings=warnings,
    )


def _validate_sell_plan(plan: SellPlanInput) -> None:
    if not plan.symbol_code.strip():
        raise ValueError("标的代码不能为空。")
    if plan.sell_count <= 0:
        raise ValueError("卖出次数必须大于 0。")
    if len(plan.multipliers) != plan.sell_count:
        raise ValueError("卖单倍数数量必须与卖出次数一致。")
    if to_decimal(plan.average_cost) <= 0:
        raise ValueError("持仓成本必须大于 0。")
    if to_decimal(plan.total_position_quantity) <= 0:
        raise ValueError("总持仓数量必须大于 0。")
    if to_decimal(plan.intended_sell_quantity) <= 0:
        raise ValueError("计划卖出数量必须大于 0。")
    if to_decimal(plan.intended_sell_quantity) > to_decimal(plan.total_position_quantity):
        raise ValueError("计划卖出数量不能超过总持仓数量。")
    if to_decimal(plan.target_capital_recovery) <= 0:
        raise ValueError("目标回收资金必须大于 0。")
    if to_decimal(plan.initial_sell_price) <= 0:
        raise ValueError("初始卖出价格必须大于 0。")
    if to_decimal(plan.initial_capital_plan_price) <= 0:
        raise ValueError("初始执行价格必须大于 0。")
    if not Decimal("0") < to_decimal(plan.sell_frequency_pct) < Decimal("1"):
        raise ValueError("卖出频率必须在 0 到 1 之间。")
    for multiplier in plan.multipliers:
        if to_decimal(multiplier) <= 0:
            raise ValueError("卖单倍数必须大于 0。")
