"""Group loose items into lot suggestions by theme or brand."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from .store import Item


@dataclass
class LotSuggestion:
    name: str
    grouping: str  # "theme" or "brand"
    key: str
    items: List[Item]

    @property
    def units(self) -> int:
        return sum(it.qty for it in self.items)

    @property
    def total_cost(self) -> float:
        return round(sum(it.total_cost for it in self.items), 2)


SUGGEST_RETURN = Tuple[List[LotSuggestion], int]


def _key_of(item: Item, by: str) -> str:
    return (item.brand if by == "brand" else item.theme).strip()


def suggest_lots(
    items: List[Item], by: str = "theme", min_items: int = 2
) -> SUGGEST_RETURN:
    """Group items sharing the same theme (or brand).

    Returns (suggestions sorted biggest-first, count of items left over)
    where "left over" means either no matching key or a group smaller
    than min_items.
    """
    if by not in ("theme", "brand"):
        raise ValueError("--by must be 'theme' or 'brand'.")
    buckets: Dict[str, List[Item]] = {}
    leftover = 0
    for item in items:
        key = _key_of(item, by)
        if not key:
            leftover += 1
            continue
        buckets.setdefault(key, []).append(item)
    suggestions: List[LotSuggestion] = []
    for key in sorted(buckets):
        group = sorted(buckets[key], key=lambda it: it.id)
        if len(group) < min_items:
            leftover += 1
            continue
        suggestions.append(
            LotSuggestion(name=f"{key} lot", grouping=by, key=key, items=group)
        )
    suggestions.sort(key=lambda s: (-s.units, s.name.lower()))
    return suggestions, leftover
