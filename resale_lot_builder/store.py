"""CSV storage for your stash and saved lots.

Everything is plain CSV, stored in your current folder:
  stash.csv  — one row per item you own
  lots.csv   — saved bundle suggestions (only created if you --save)

No accounts, no network, nothing leaves your machine.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List, Optional

STASH_FILE = "stash.csv"
LOTS_FILE = "lots.csv"

CONDITIONS = ("NEW", "LN", "VG", "G", "A")
CONDITION_LABELS = {
    "NEW": "New",
    "LN": "Like new",
    "VG": "Very good",
    "G": "Good",
    "A": "Acceptable",
}
_CONDITION_ALIASES = {
    "NEW": "NEW",
    "N": "NEW",
    "LIKE NEW": "LN",
    "LN": "LN",
    "VERY GOOD": "VG",
    "VG": "VG",
    "GOOD": "G",
    "G": "G",
    "ACCEPTABLE": "A",
    "ACC": "A",
    "A": "A",
}

ITEM_FIELDS = [
    "id", "name", "brand", "theme", "condition",
    "cost", "qty", "price", "notes", "added",
]
LOT_FIELDS = ["id", "name", "grouping", "key", "item_ids", "created"]


def condition_code(value: str) -> str:
    """Validate/normalize a condition code. Raises ValueError if unknown."""
    key = str(value).strip().upper()
    if not key:
        key = "VG"
    code = _CONDITION_ALIASES.get(key)
    if code is None:
        valid = ", ".join(
            f"{c} ({CONDITION_LABELS[c]})" for c in CONDITIONS
        )
        raise ValueError(
            f"Unknown condition {value!r}. Use one of: {valid} "
            f"(e.g. --condition VG)."
        )
    return code


def condition_label(code: str) -> str:
    return CONDITION_LABELS.get(code, code)


@dataclass
class Item:
    id: int
    name: str
    brand: str
    theme: str
    condition: str
    cost: float
    qty: int
    price: Optional[float]  # your own asking price per unit, if you know it
    notes: str
    added: str

    @property
    def total_cost(self) -> float:
        return round(self.cost * self.qty, 2)


@dataclass
class Lot:
    id: str  # like "L1"
    name: str
    grouping: str  # "theme" or "brand"
    key: str  # the theme/brand value this lot shares
    item_ids: str  # semicolon-separated item ids
    created: str

    def id_parts(self) -> List[int]:
        return [int(x) for x in self.item_ids.split(";") if x]


def _write_csv(path: Path, fields: List[str], rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class Stash:
    """Your item list, backed by stash.csv."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> List[Item]:
        if not self.path.exists():
            return []
        items: List[Item] = []
        with open(self.path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                items.append(
                    Item(
                        id=int(row["id"]),
                        name=row["name"],
                        brand=row.get("brand", ""),
                        theme=row.get("theme", ""),
                        condition=row.get("condition", "VG"),
                        cost=float(row["cost"] or 0.0),
                        qty=int(row.get("qty") or 1),
                        price=float(row["price"]) if row.get("price") else None,
                        notes=row.get("notes", ""),
                        added=row.get("added", ""),
                    )
                )
        return items

    def save(self, items: List[Item]) -> None:
        rows = []
        for it in items:
            rows.append({
                "id": it.id,
                "name": it.name,
                "brand": it.brand,
                "theme": it.theme,
                "condition": it.condition,
                "cost": f"{it.cost:.2f}",
                "qty": it.qty,
                "price": f"{it.price:.2f}" if it.price else "",
                "notes": it.notes,
                "added": it.added,
            })
        _write_csv(self.path, ITEM_FIELDS, rows)

    def add(self, item: Item) -> Item:
        items = self.load()
        item.id = self.next_id(items)
        item.added = item.added or date.today().isoformat()
        items.append(item)
        self.save(items)
        return item

    def remove(self, item_id: int) -> Item:
        items = self.load()
        for i, it in enumerate(items):
            if it.id == item_id:
                removed = items.pop(i)
                self.save(items)
                return removed
        raise ValueError(f"No item with id {item_id} in your stash.")

    @staticmethod
    def next_id(items: List[Item]) -> int:
        return max((it.id for it in items), default=0) + 1


class LotStore:
    """Saved lot suggestions, backed by lots.csv."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> List[Lot]:
        if not self.path.exists():
            return []
        lots: List[Lot] = []
        with open(self.path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                lots.append(
                    Lot(
                        id=row["id"],
                        name=row["name"],
                        grouping=row.get("grouping", "theme"),
                        key=row.get("key", ""),
                        item_ids=row.get("item_ids", ""),
                        created=row.get("created", ""),
                    )
                )
        return lots

    def save(self, lots: List[Lot]) -> None:
        rows = [
            {
                "id": lot.id,
                "name": lot.name,
                "grouping": lot.grouping,
                "key": lot.key,
                "item_ids": lot.item_ids,
                "created": lot.created,
            }
            for lot in lots
        ]
        _write_csv(self.path, LOT_FIELDS, rows)

    def find(self, lot_ref: str) -> Lot:
        lots = self.load()
        wanted = lot_ref.strip()
        if wanted.isdigit():
            wanted = f"L{wanted}"
        for lot in lots:
            if lot.id.upper() == wanted.upper():
                return lot
        raise ValueError(
            f"No saved lot {lot_ref!r}. Run `resale-lot-builder lots` to see ids."
        )

    @staticmethod
    def next_id(lots: List[Lot]) -> str:
        numbers = []
        for lot in lots:
            digits = "".join(ch for ch in lot.id if ch.isdigit())
            if digits:
                numbers.append(int(digits))
        return f"L{max(numbers, default=0) + 1}"


def item_by_id(items: List[Item], item_id: int) -> Optional[Item]:
    for it in items:
        if it.id == item_id:
            return it
    return None
