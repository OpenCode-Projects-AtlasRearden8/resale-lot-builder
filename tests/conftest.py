from pathlib import Path
import pytest

from resale_lot_builder.store import Item

ROOT = Path(__file__).parents[1]


@pytest.fixture
def shop(tmp_path, monkeypatch):
    """An empty, isolated "shop folder" as the current working directory."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def make_item(
    item_id,
    name,
    cost,
    condition="VG",
    brand="",
    theme="",
    qty=1,
    price=None,
    notes="",
):
    return Item(
        id=item_id,
        name=name,
        brand=brand,
        theme=theme,
        condition=condition,
        cost=cost,
        qty=qty,
        price=price,
        notes=notes,
        added="2026-10-25",
    )


@pytest.fixture
def sample_items():
    """Mixed stash: a tcg pile, a tech pile, one item with a known price."""
    return [
        make_item(1, "Pokemon bulk card pile", 6.00, condition="VG",
                  brand="Pokemon", theme="tcg"),
        make_item(2, "Yu-Gi-Oh card bundle", 5.00, condition="G",
                  brand="Konami", theme="tcg"),
        make_item(3, "Dragon Shield sleeves", 4.00, condition="LN",
                  brand="Dragon Shield", theme="tcg"),
        make_item(4, "Logitech wireless mouse", 7.00, condition="VG",
                  brand="Logitech", theme="tech"),
        make_item(5, "Anker wall charger", 6.00, condition="G",
                  brand="Anker", theme="tech"),
        make_item(6, "Kindle Paperwhite", 18.00, condition="A",
                  brand="Amazon", theme="tech", price=35.00),
    ]
