import pytest

from resale_lot_builder import store
from resale_lot_builder.store import (
    Lot,
    LotStore,
    Stash,
    condition_code,
    condition_label,
)


def test_condition_aliases_and_defaults():
    assert condition_code("vg") == "VG"
    assert condition_code("Like New") == "LN"
    assert condition_code("very good") == "VG"
    assert condition_code("acceptable") == "A"
    assert condition_code("") == "VG"
    assert condition_label("A") == "Acceptable"


def test_condition_invalid_lists_options():
    with pytest.raises(ValueError) as info:
        condition_code("scratched")
    assert "NEW" in str(info.value) and "VG" in str(info.value)


def test_stash_round_trip(shop, sample_items):
    stash = Stash(shop / "stash.csv")
    for it in sample_items:
        stash.add(it)
    loaded = stash.load()
    assert [it.id for it in loaded] == list(range(1, 7))
    assert loaded[5].price == 35.00
    assert loaded[1].condition == "G"
    assert loaded[2].total_cost == 4.0
    row = open(shop / "stash.csv", encoding="utf-8").read().strip()
    assert row.startswith(
        "id,name,brand,theme,condition,cost,qty,price,notes,added")
    assert ",4.00," in row  # money stored with 2 decimals


def test_stash_next_id_and_remove(shop):
    stash = Stash(shop / "stash.csv")
    assert stash.next_id([]) == 1
    a = stash.add(store.Item(0, "A", "", "", "VG", 1.0, 1, None, "", ""))
    b = stash.add(store.Item(0, "B", "", "", "G", 2.0, 3, None, "", ""))
    assert (a.id, b.id) == (1, 2)
    stash.remove(1)
    assert [it.id for it in stash.load()] == [2]
    with pytest.raises(ValueError):
        stash.remove(99)


def test_item_total_cost_with_qty():
    assert store.Item(
        1, "x", "", "", "VG", 2.50, 4, None, "", ""
    ).total_cost == 10.0


def test_lot_store_find_normalizes_ids(shop):
    lot_store = LotStore(shop / "lots.csv")
    lot_store.save([
        Lot("L1", "tcg lot", "theme", "tcg", "1;2;3", "2026-10-25"),
        Lot("L2", "tech lot", "theme", "tech", "4;5;6", "2026-10-25"),
    ])
    assert lot_store.find("1").key == "tcg"
    assert lot_store.find("l2").key == "tech"
    assert lot_store.find("L2").id == "L2"
    with pytest.raises(ValueError):
        lot_store.find("L9")


def test_lot_next_id(shop):
    existing = [Lot("L4", "n", "theme", "k", "1", "")]
    assert LotStore.next_id([]) == "L1"
    assert LotStore.next_id(existing) == "L5"
