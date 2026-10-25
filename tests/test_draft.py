import pytest

from resale_lot_builder.draft import (
    TITLE_LIMIT,
    compare_line,
    make_title,
    render_description,
    render_lot_draft,
    write_draft,
)
from resale_lot_builder.grouping import LotSuggestion, suggest_lots
from resale_lot_builder.pricing import lot_economics, resolve_platform
from tests.conftest import make_item


@pytest.fixture
def tcg_suggestion(sample_items):
    groups, _ = suggest_lots(sample_items, by="theme")
    return groups[0]


def test_make_title_shape_and_limit(tcg_suggestion):
    title = make_title(tcg_suggestion)
    assert title.startswith("Lot of 3 TCG items")
    assert "Pokemon bulk card pile" in title
    assert len(title) <= 80 == TITLE_LIMIT


def test_make_title_clips_long_lists():
    items = [
        make_item(i, f"Long item name number {i} of eleven", 1, theme="misc")
        for i in range(1, 12)
    ]
    suggestion = LotSuggestion("misc lot", "theme", "misc", items)
    assert suggestion.units == 11
    title = make_title(suggestion)
    assert len(title) <= 80
    assert title.endswith("…")


def test_description_lists_items_and_conditions(tcg_suggestion):
    text = render_description(tcg_suggestion)
    assert "Lot of 3 TCG items" in text
    assert "- Pokemon bulk card pile — Very good" in text
    assert "Kindle" not in text, "only this lot's items belong here"
    assert "Acceptable." in text  # spells out the grading scale


def test_compare_line_both_directions(shop):
    cfg = resolve_platform("ebay")
    healthy = lot_economics(
        [   # two units share one shipment -> bundling wins
            make_item(1, "Bundle me", 5, condition="G", theme="x"),
            make_item(2, "And me", 4, condition="VG", theme="x"),
        ],
        cfg,
    )
    under = lot_economics(
        [make_item(2, "Underwater", 30, condition="A", theme="y", price=10)],
        cfg,
    )
    assert "bundling looks better" in compare_line(healthy)
    assert "selling separately looks better" in compare_line(under)


def test_render_lot_draft_sections(shop, tcg_suggestion):
    cfg = resolve_platform("ebay")
    text = render_lot_draft("L1", tcg_suggestion, cfg)
    assert text.startswith("# Listing draft — L1: tcg lot (eBay)")
    assert "## Title (paste this)" in text
    assert "## Description (paste this)" in text
    assert "## Pricing ladder (for you — keep off the listing)" in text
    assert "Day 0 — list at" in text
    assert "Day 14 — reprice" in text
    assert "Day 30 — floor" in text
    assert "Break-even for this lot" in text
    assert "Bundle vs. separate" in text
    assert selling_separately_shown(text)


def selling_separately_shown(text) -> bool:  # pragma: no cover - helper
    return "Selling every unit separately" in text


def test_underwater_draft_gets_warning(shop):
    cfg = resolve_platform("amazon")
    suggestion = LotSuggestion(
        "y lot", "theme", "y",
        [make_item(1, "Underwater", 30, condition="A", theme="y", price=10)],
    )
    text = render_lot_draft("L2", suggestion, cfg)
    assert "Heads up" in text


def test_write_draft_saves_file(shop, tcg_suggestion):
    cfg = resolve_platform("ebay")
    text = render_lot_draft("L1", tcg_suggestion, cfg)
    out = write_draft("L1", text)
    assert out.resolve() == (shop / "listings" / "L1.md").resolve()
    saved = out.read_text(encoding="utf-8")
    assert saved == text
