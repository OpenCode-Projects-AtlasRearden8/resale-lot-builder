import json

import pytest

from resale_lot_builder.pricing import (
    estimate_item_price,
    init_fees_dir,
    load_platform_file,
    lot_economics,
    net_for_items_separate,
    net_for_lot,
    price_99,
    resolve_platform,
)
from tests.conftest import make_item


def test_bundled_configs_load(shop):
    cfg = resolve_platform("eBAY")
    assert cfg.name == "eBay"
    assert cfg.key == "ebay"
    assert cfg.source == "bundled"
    assert cfg.final_value_fee_pct == 13.25
    assert cfg.fixed_fee_per_order == 0.30
    assert cfg.shipping_cost_per_lot == 7.00
    assert cfg.shipping_cost_per_item == 5.00
    assert cfg.markup_multiplier == 3.0
    assert cfg.condition_multipliers["A"] == 0.6
    amazon = resolve_platform("amazon")
    assert amazon.name == "Amazon"
    assert amazon.final_value_fee_pct == 15.0


def test_resolve_unknown_platform_lists_available(shop):
    with pytest.raises(ValueError) as info:
        resolve_platform("grubhub")
    assert "amazon, ebay" in str(info.value)  # sorted listing of options


def test_custom_fees_dir_overrides_bundled(shop):
    fees = shop / "fees"
    fees.mkdir()
    (fees / "posh.json").write_text(json.dumps({
        "platform": "Poshmark",
        "final_value_fee_pct": 20.0,
    }), encoding="utf-8")
    cfg = resolve_platform("posh")
    assert cfg.name == "Poshmark"
    assert cfg.source == "customized"          # fees/ dir ⇒ customized
    assert cfg.final_value_fee_pct == 20.0
    assert cfg.fixed_fee_per_order == 0.0      # defaults fill the gaps
    assert cfg.markup_multiplier == 3.0
    assert cfg.condition_multipliers["VG"] == 0.8
    with pytest.raises(ValueError):
        resolve_platform("ebay", fees_dir=fees)  # local dir wins, so no ebay


def test_fees_init_copies_bundled_defaults(shop):
    copied = init_fees_dir()
    names = sorted(p.name for p in copied)
    assert names == ["amazon.json", "ebay.json"]
    cfg = load_platform_file(shop / "fees" / "ebay.json")
    assert cfg.final_value_fee_pct == 13.25
    assert cfg.source == "customized"


def test_estimate_item_price(shop, sample_items):
    cfg = resolve_platform("ebay")
    pile = sample_items[0]          # cost 6.00, VG, no known price
    assert estimate_item_price(pile, cfg) == pytest.approx(6.0 * 3.0 * 0.8)
    kindle = sample_items[5]        # explicit -- price wins, multiplier skipped
    assert estimate_item_price(kindle, cfg) == 35.00
    odd = make_item(9, "Odd", 8.00, condition="ZZ")  # unknown condition code
    assert estimate_item_price(odd, cfg) == pytest.approx(8.0 * 3.0 * 0.75)


def test_price_99_rounds_up_charmingly():
    assert price_99(10) == 10.99
    assert price_99(10.99) == 10.99
    assert price_99(10.98) == 10.99
    assert price_99(11.00) == 11.99
    assert price_99(0.2) == 1.99
    assert price_99(0) == 0.0
    assert price_99(39.8) == 39.99


def test_net_math_exact(shop):
    cfg = resolve_platform("ebay")
    # one lot sale of $100: 100 * 86.75% - 0.30 fixed - 7.00 lot shipping
    assert net_for_lot(100.0, cfg) == pytest.approx(100 * 0.8675 - 0.30 - 7.00)
    # selling one unit separately: fee + fixed + its own shipping
    assert net_for_items_separate([100.0], cfg) == pytest.approx(
        100 * 0.8675 - 0.30 - 5.00)
    # two units, each shipping alone
    assert net_for_items_separate([10.0, 10.0], cfg) == pytest.approx(
        2 * (10 * 0.8675 - 0.30 - 5.00), abs=0.01)


def test_lot_economics_walkthrough(shop):
    """Hand-checked numbers, from cost basis to floor price."""
    cfg = resolve_platform("ebay")
    items = [
        make_item(1, "Pile A", 2.00, condition="VG"),   # est 2*3*0.8 = 4.80
        make_item(2, "Kindle", 18.00, condition="A", price=35.00),
    ]
    eco = lot_economics(items, cfg)
    assert eco.lot_cost == 20.00
    assert eco.lot_retail == 39.80               # 4.80 + 35.00
    assert eco.list_price == 39.99               # charming .99 rounding
    assert eco.break_even_price == pytest.approx(
        (20 + 0.30 + 7.00) / 0.8675, abs=0.01)
    assert eco.floor_price == 31.99              # next .99 above break-even
    assert eco.rungs[0] == ("Day 0 — list at", 39.99, pytest.approx(
        39.99 * 0.8675 - 0.30 - 7.00 - 20.0, abs=0.01))
    assert eco.rungs[1][0].startswith("Day 14")
    assert eco.rungs[1][1] == 36.99              # 39.99 * 0.9 -> charming
    assert eco.rungs[2] == ("Day 30 — floor", 31.99, pytest.approx(
        31.99 * 0.8675 - 0.30 - 7.00 - 20.0, abs=0.01))
    assert eco.rungs[2][2] >= 0.0                # the floor is break-even+
    # separate: each unit pays full per-item shipping
    assert eco.sep_net == pytest.approx(
        (4.8 * 0.8675 - 0.30 - 5.00) + (35.0 * 0.8675 - 0.30 - 5.00), abs=0.01)
    assert eco.sep_profit == pytest.approx(eco.sep_net - 20.0, abs=0.01)
    assert eco.warning == ""


def test_lot_economics_flags_underwater_pricing(shop):
    """When break-even sits above the asking price, the user must be warned."""
    cfg = resolve_platform("ebay")
    items = [make_item(1, "Underwater", 30.00, condition="A", price=10.00)]
    eco = lot_economics(items, cfg)
    assert eco.list_price == 10.99
    assert eco.floor_price > eco.list_price      # 43.99ish vs 10.99
    assert "ABOVE" in eco.warning


def test_qty_multiplies_estimates_and_costs(shop):
    cfg = resolve_platform("ebay")
    items = [make_item(1, "Plush", 2.00, condition="VG", qty=2)]
    eco = lot_economics(items, cfg)
    assert eco.lot_cost == 4.00
    assert eco.lot_retail == 9.60                # (2*3*0.8) * 2 units
    # separately, each unit ships on its own
    assert eco.sep_gross == 9.60
    assert eco.sep_net == pytest.approx(
        2 * (4.80 * 0.8675 - 0.30 - 5.00), abs=0.01)
