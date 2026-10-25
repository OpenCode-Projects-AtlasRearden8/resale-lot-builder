"""Fee-rate configs and the profit math.

Each platform is one JSON config file: its final-value fee percentage,
fixed per-order fee, assumed shipping cost, and a few pricing helpers.
The numbers shipped with this project are EXAMPLES ONLY — run
`resale-lot-builder fees init` to copy them into ./fees/ and set rates
that match your own marketplace accounts.
"""

from __future__ import annotations

import json
import math
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .store import CONDITIONS, Item, condition_label

BUNDLED_CONFIG_DIR = Path(__file__).parent / "configs"
LOCAL_FEES_DIR = Path("fees")

DEFAULT_CONDITION_MULTIPLIERS = {
    "NEW": 1.0, "LN": 0.9, "VG": 0.8, "G": 0.7, "A": 0.6,
}


@dataclass
class PlatformConfig:
    key: str
    name: str
    final_value_fee_pct: float
    fixed_fee_per_order: float
    shipping_cost_per_lot: float
    shipping_cost_per_item: float
    markup_multiplier: float
    condition_multipliers: Dict[str, float] = field(
        default_factory=DEFAULT_CONDITION_MULTIPLIERS.copy
    )
    notes: str = ""
    source: str = "bundled"

    @property
    def fee_fraction(self) -> float:
        return self.final_value_fee_pct / 100.0


def load_platform_file(path: Path) -> PlatformConfig:
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    mult = DEFAULT_CONDITION_MULTIPLIERS.copy()
    mult.update({
        k: float(v)
        for k, v in raw.get("condition_multipliers", {}).items()
        if k in CONDITIONS
    })
    return PlatformConfig(
        key=path.stem.lower(),
        name=str(raw.get("platform") or path.stem),
        final_value_fee_pct=float(raw.get("final_value_fee_pct", 10.0)),
        fixed_fee_per_order=float(raw.get("fixed_fee_per_order", 0.0)),
        shipping_cost_per_lot=float(raw.get("shipping_cost_per_lot", 0.0)),
        shipping_cost_per_item=float(raw.get("shipping_cost_per_item", 0.0)),
        markup_multiplier=float(raw.get("default_markup_multiplier", 3.0)),
        condition_multipliers=mult,
        notes=str(raw.get("notes", "")),
        source="customized" if path.parent.name == "fees" else "bundled",
    )


def available_platforms(fees_dir: Optional[Path] = None) -> Tuple[List[Path], Path]:
    """Return (config paths in priority order, the directory in use)."""
    local = Path(fees_dir) if fees_dir else LOCAL_FEES_DIR
    if local.exists() and any(local.glob("*.json")):
        return sorted(local.glob("*.json")), local
    return sorted(BUNDLED_CONFIG_DIR.glob("*.json")), BUNDLED_CONFIG_DIR


def resolve_platform(key: str, fees_dir: Optional[Path] = None) -> PlatformConfig:
    paths, _dir = available_platforms(fees_dir)
    for path in paths:
        if path.stem.lower() == key.lower():
            return load_platform_file(path)
    names = ", ".join(p.stem for p in paths) or "(none)"
    raise ValueError(
        f"No platform config named {key!r}. Available: {names}. "
        f"Put your own JSON files in ./fees/ (see `fees init`)."
    )


def init_fees_dir(dest: Optional[Path] = None) -> List[Path]:
    target = Path(dest) if dest else LOCAL_FEES_DIR
    target.mkdir(parents=True, exist_ok=True)
    copied = []
    for path in sorted(BUNDLED_CONFIG_DIR.glob("*.json")):
        out = target / path.name
        shutil.copyfile(path, out)
        copied.append(out)
    return copied


def estimate_item_price(item: Item, cfg: PlatformConfig) -> float:
    """Per-unit asking price estimate for one item.

    If you supplied --price when adding the item, we trust you and use it.
    Otherwise: unit cost x markup multiplier x condition factor.
    """
    if item.price:
        return round(item.price, 2)
    factor = cfg.condition_multipliers.get(item.condition, 0.75)
    return round(max(float(item.cost), 0.0) * cfg.markup_multiplier * factor, 2)


def price_99(price: float) -> float:
    """Round UP to the next ".99-style" charming price (10 -> 10.99, 10.98 -> 10.99)."""
    if price <= 0:
        return 0.0
    whole = int(math.ceil(price - 0.99))
    if whole < 1:
        whole = 1
    value = round(whole + 0.99, 2)
    if value < price:
        value = round(whole + 0.99 + 1.0, 2)
    return value


def net_for_lot(price: float, cfg: PlatformConfig) -> float:
    """What you keep from one lot sale, before costs of goods."""
    return price * (1 - cfg.fee_fraction) - cfg.fixed_fee_per_order \
        - cfg.shipping_cost_per_lot


def net_for_items_separate(unit_prices: List[float], cfg: PlatformConfig) -> float:
    """Net proceeds if each unit sells on its own (each pays its own shipping)."""
    total = 0.0
    for price in unit_prices:
        total += price * (1 - cfg.fee_fraction) - cfg.fixed_fee_per_order \
            - cfg.shipping_cost_per_item
    return round(total, 2)


@dataclass
class LotEconomics:
    item_estimates: List[Tuple[Item, float]]  # (item, per-unit estimate)
    lot_cost: float
    lot_retail: float
    list_price: float
    break_even_price: float
    floor_price: float
    rungs: List[Tuple[str, float, float]]  # (label, price, profit at that price)
    lot_profit_start: float
    sep_gross: float
    sep_net: float
    sep_profit: float
    warning: str


def _round(rung: float) -> float:
    return round(rung, 2)


def lot_economics(items: List[Item], cfg: PlatformConfig) -> LotEconomics:
    """All the money math for one candidate lot, on one platform."""
    item_estimates = [(it, estimate_item_price(it, cfg)) for it in items]
    lot_cost = _round(sum(it.total_cost for it, _ in item_estimates))
    lot_retail = _round(
        sum(est * it.qty for it, est in item_estimates)
    )
    list_price = price_99(lot_retail)

    fee = cfg.fee_fraction
    if fee >= 1:  # paranoid guard; nobody lists on a 100%+ fee platform
        fee = 0.9999
    break_even = (lot_cost + cfg.fixed_fee_per_order
                  + cfg.shipping_cost_per_lot) / (1 - fee)
    floor_price = price_99(break_even)

    rung2_price = price_99(list_price * 0.9)
    if rung2_price < floor_price:
        rung2_price = floor_price

    def profit_at(price: float) -> float:
        return _round(net_for_lot(price, cfg) - lot_cost)

    rungs = [
        ("Day 0 — list at", list_price, profit_at(list_price)),
        ("Day 14 — reprice", _round(rung2_price), profit_at(rung2_price)),
        ("Day 30 — floor", _round(floor_price), profit_at(floor_price)),
    ]
    warning = ""
    if floor_price > list_price:
        warning = (
            f"Break-even ({break_even:.2f} -> ${floor_price:.2f} rounded) is ABOVE "
            f"the estimated asking price — lower your cost basis, assign higher "
            f"prices, or expect a loss if you must sell."
        )
    unit_prices = []
    for it, est in item_estimates:
        unit_prices.extend([est] * it.qty)
    sep_net = net_for_items_separate(unit_prices, cfg)
    sep_gross = _round(sum(unit_prices))
    sep_profit = _round(sep_net - lot_cost)

    return LotEconomics(
        item_estimates=item_estimates,
        lot_cost=lot_cost,
        lot_retail=lot_retail,
        list_price=list_price,
        break_even_price=_round(break_even),
        floor_price=_round(floor_price),
        rungs=rungs,
        lot_profit_start=rungs[0][2],
        sep_gross=sep_gross,
        sep_net=sep_net,
        sep_profit=sep_profit,
        warning=warning,
    )


def roi(profit: float, cost: float) -> str:
    if cost <= 0:
        return "n/a"
    return f"{profit / cost * 100:.0f}%"


def condition_scale_line() -> str:
    return ", ".join(f"{c} = {condition_label(c)}" for c in CONDITIONS)
