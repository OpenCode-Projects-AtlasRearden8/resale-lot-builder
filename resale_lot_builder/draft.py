"""Listing drafts: title, description, and pricing ladder for one lot."""

from __future__ import annotations

from pathlib import Path
from typing import List

from .grouping import LotSuggestion
from .pricing import (
    LotEconomics,
    PlatformConfig,
    condition_scale_line,
    lot_economics,
    roi,
)
from .store import condition_label

TITLE_LIMIT = 80
LISTINGS_DIR = Path("listings")


def _title_case(key: str) -> str:
    trimmed = key.strip()
    if not trimmed:
        return "Stash"
    if len(trimmed) <= 4:
        return trimmed.upper()
    return trimmed.title()


def _clip(title: str, limit: int = TITLE_LIMIT) -> str:
    if len(title) <= limit:
        return title
    cut = title[: limit - 1].rstrip()
    while cut and cut.endswith((",", "-", "—", "(")):
        cut = cut[:-1].rstrip()
    return cut + "…"


def make_title(suggestion: LotSuggestion) -> str:
    key_disp = _title_case(suggestion.key)
    base = f"Lot of {suggestion.units} {key_disp} items"
    names = [it.name for it in suggestion.items]
    if names:
        shown = ", ".join(names[:3])
        title = f"{base} — includes {shown}"
        if len(names) > 3:
            title += f", +{len(names) - 3} more"
    else:
        title = base
    return _clip(title)


def render_description(suggestion: LotSuggestion) -> str:
    key_disp = _title_case(suggestion.key)
    lines = [
        f"Lot of {suggestion.units} {key_disp} items, sold together as one "
        f"bundle. One payment, one box, no need to dig through my other "
        f"listings.",
        "",
        "What's inside:",
    ]
    for it in suggestion.items:
        qty = f" (x{it.qty})" if it.qty > 1 else ""
        label = condition_label(it.condition)
        lines.append(f"- {it.name} — {label}{qty}")
    lines += [
        "",
        "Condition: graded honestly. Scale used: "
        + condition_scale_line() + ".",
        "Shipping: packed together in one box, handled with care.",
        "Message me with any questions. Thanks for looking!",
    ]
    return "\n".join(lines)


def _ladder_lines(eco: LotEconomics, cost: float) -> List[str]:
    return [
        f"    {label} ${price:,.2f} -> est. profit ${profit:,.2f} "
        f"(ROI {roi(profit, cost)})"
        for label, price, profit in eco.rungs
    ]


def compare_line(eco: LotEconomics) -> str:
    diff = round(eco.lot_profit_start - eco.sep_profit, 2)
    if abs(diff) < 0.01:
        return ("Verdict: it's a coin flip — bundling and separate sales "
                "net about the same.")
    if diff > 0:
        return (f"Verdict: bundling looks better by ${diff:,.2f} per lot — "
                f"but only if a single buyer takes everything.")
    return (f"Verdict: selling separately looks better by ${abs(diff):,.2f} "
            f"— worth it only if they move fast and you're okay shipping "
            f"more boxes.")


def suggestion_economics(
    suggestion: LotSuggestion, cfg: PlatformConfig
) -> LotEconomics:
    return lot_economics(suggestion.items, cfg)


def lot_block(
    lot_label: str,
    suggestion: LotSuggestion,
    cfg: PlatformConfig,
) -> List[str]:
    """Console-facing summary of one lot's numbers (used by `forecast`)."""
    eco = suggestion_economics(suggestion, cfg)
    lines = [
        f"Lot {lot_label} — {suggestion.name} "
        f"({suggestion.units} items, cost ${eco.lot_cost:,.2f})",
        f"  {cfg.name} rates: {cfg.final_value_fee_pct}% of sale "
        f"+ ${cfg.fixed_fee_per_order:,.2f} fixed + "
        f"${cfg.shipping_cost_per_lot:,.2f} shipping per lot",
    ]
    if eco.warning:
        lines.append(f"  ! {eco.warning}")
    lines.append("  Pricing ladder:")
    lines.extend(_ladder_lines(eco, eco.lot_cost))
    lines.append(
        "  Selling separately instead: est. gross "
        f"${eco.sep_gross:,.2f} -> net ${eco.sep_net:,.2f} -> "
        f"profit ${eco.sep_profit:,.2f}"
    )
    lines.append("  " + compare_line(eco))
    lines.append("")
    return lines


def render_lot_draft(
    lot_label: str,
    suggestion: LotSuggestion,
    cfg: PlatformConfig,
) -> str:
    """Full markdown listing draft: paste-ready title/description + seller notes."""
    eco = suggestion_economics(suggestion, cfg)
    title = make_title(suggestion)
    description = render_description(suggestion)

    lines = [
        f"# Listing draft — {lot_label}: {suggestion.name} ({cfg.name})",
        "",
        f"*Estimated from your cost data with {cfg.name} rates — "
        f"arithmetic, not a market appraisal.*",
        "",
        "## Title (paste this)",
        "",
        "```",
        title,
        "```",
        "",
        f"*_{len(title)} of {TITLE_LIMIT} allowed characters._",
        "",
        "## Description (paste this)",
        "",
        "```",
        description,
        "```",
        "",
        "## Pricing ladder (for you — keep off the listing)",
        "",
    ]
    lines.extend(_ladder_lines(eco, eco.lot_cost))
    lines += [
        "",
        f"Break-even for this lot: ${eco.break_even_price:,.2f} — that's the "
        f"price where {cfg.final_value_fee_pct}% fees, "
        f"${cfg.fixed_fee_per_order:,.2f} fixed fee, and "
        f"${cfg.shipping_cost_per_lot:,.2f} lot shipping exactly eat your "
        f"${eco.lot_cost:,.2f} cost basis.",
        "",
        "## Bundle vs. separate",
        "",
        f"    Selling as one lot (day-0 price): profit ${eco.lot_profit_start:,.2f}",
        f"    Selling every unit separately:    profit ${eco.sep_profit:,.2f}",
        "",
        "    " + compare_line(eco),
        "",
    ]
    if eco.warning:
        lines += [f"> **Heads up:** {eco.warning}", ""]
    return "\n".join(lines)


def write_draft(
    lot_label: str, text: str, listings_dir: Path = LISTINGS_DIR
) -> Path:
    out_dir = Path(listings_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{lot_label}.md"
    out.write_text(text, encoding="utf-8")
    return out
