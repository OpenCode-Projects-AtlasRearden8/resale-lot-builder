import pytest

from resale_lot_builder.grouping import suggest_lots
from tests.conftest import make_item


def test_group_by_theme(sample_items):
    groups, leftover = suggest_lots(sample_items, by="theme", min_items=2)
    assert leftover == 0
    names = [g.name for g in groups]
    assert names == ["tcg lot", "tech lot"]  # tied on units -> name order
    tcg = groups[0]
    assert [it.id for it in tcg.items] == [1, 2, 3]
    assert tcg.units == 3
    assert tcg.total_cost == pytest.approx(6 + 5 + 4)


def test_group_by_brand(sample_items):
    groups, leftover = suggest_lots(sample_items, by="brand")
    # every sample brand appears once -> nothing clears min_items=2
    assert groups == []
    assert leftover == len(sample_items)
    singles, leftover = suggest_lots(sample_items, by="brand", min_items=1)
    assert {g.key for g in singles} == {
        "Pokemon", "Konami", "Dragon Shield", "Logitech", "Anker", "Amazon"}
    assert leftover == 0


def test_untagged_and_small_groups_are_left_over():
    items = [
        make_item(1, "Tagged A", 1, theme="toys"),
        make_item(2, "Tagged B", 1, theme="toys"),
        make_item(3, "No tag", 1, theme=""),
        make_item(4, "Lone brand", 1, brand="Unix ◎"),
    ]
    groups, leftover = suggest_lots(items, by="theme")
    assert [g.key for g in groups] == ["toys"]
    assert leftover == 2  # untagged + lone brand


def test_qty_counts_units_and_cost():
    items = [
        make_item(1, "Plush", 2, theme="toys", qty=2),
        make_item(2, "Posters", 1, theme="toys"),
    ]
    (group,), leftover = suggest_lots(items, by="theme")
    assert leftover == 0
    assert group.units == 3
    assert group.total_cost == pytest.approx(5.0)


def test_invalid_by_raises(sample_items):
    with pytest.raises(ValueError):
        suggest_lots(sample_items, by="vibes")
