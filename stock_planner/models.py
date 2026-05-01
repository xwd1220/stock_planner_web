from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


DecimalLike = Decimal | int | float | str


@dataclass(slots=True)
class Symbol:
    symbol_code: str
    symbol_name: str = ""
    asset_type: str = "stock"
    currency: str = "USD"
    notes: str = ""
    id: int | None = None


@dataclass(slots=True)
class BuyPlanInput:
    symbol_code: str
    initial_price: DecimalLike
    planned_capital: DecimalLike
    buy_frequency_pct: DecimalLike
    buy_count: int
    base_quantity: DecimalLike
    multipliers: list[DecimalLike]
    quantity_precision: int = 0


@dataclass(slots=True)
class BuyPlanNode:
    node_index: int
    price: Decimal
    quantity: Decimal
    multiplier: Decimal
    capital_used: Decimal
    cumulative_capital: Decimal
    cumulative_quantity: Decimal
    average_cost: Decimal


@dataclass(slots=True)
class BuyPlanResult:
    symbol_code: str
    nodes: list[BuyPlanNode]
    total_capital: Decimal
    total_quantity: Decimal
    average_cost: Decimal
    planned_capital: Decimal
    over_budget: bool
    budget_gap: Decimal
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SellPlanInput:
    symbol_code: str
    average_cost: DecimalLike
    total_position_quantity: DecimalLike
    intended_sell_quantity: DecimalLike
    target_capital_recovery: DecimalLike
    initial_sell_price: DecimalLike
    initial_capital_plan_price: DecimalLike
    sell_frequency_pct: DecimalLike
    sell_count: int
    multipliers: list[DecimalLike]
    quantity_precision: int = 0


@dataclass(slots=True)
class SellPlanNode:
    node_index: int
    sell_price: Decimal
    capital_plan_price: Decimal
    quantity: Decimal
    multiplier: Decimal
    recovered_capital: Decimal
    planned_capital: Decimal
    cumulative_recovered_capital: Decimal
    cumulative_planned_capital: Decimal
    remaining_quantity: Decimal


@dataclass(slots=True)
class SellPlanResult:
    symbol_code: str
    nodes: list[SellPlanNode]
    total_position_quantity: Decimal
    intended_sell_quantity: Decimal
    total_recovered_capital: Decimal
    total_planned_capital: Decimal
    remaining_quantity: Decimal
    average_cost: Decimal
    target_capital_recovery: Decimal
    recovery_gap: Decimal
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SavedPlan:
    config_id: int
    symbol_id: int
    config: dict[str, Any]
    nodes: list[dict[str, Any]]
