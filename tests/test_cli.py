import json
import os
import pathlib
import subprocess
import sys

from resale_lot_builder.cli import main

HERE = pathlib.Path(__file__).parents[1]


def run(capsys, argv):
    """Run the CLI in-process and capture what it printed."""
    rc = main(argv)
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


def test_version_module_subprocess(tmp_path):
    proc = subprocess.run(
        [sys.executable, "-m", "resale_lot_builder", "--version"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(HERE)},
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == "resale-lot-builder 0.1.0"
    assert proc.stderr == ""


def test_no_args_shows_help(shop, capsys):
    rc, out, _err = run(capsys, [])
    assert rc == 0
    assert "usage: resale-lot-builder" in out
    assert "Bundle your resale stash" in out


def test_demo_seeds_then_refluses(shop, capsys):
    rc, out, _err = run(capsys, ["demo"])
    assert rc == 0
    assert "Seeded 6 demo items into stash.csv" in out
    assert "Pokemon bulk card pile (50)" in out
    assert "6 items" in out
    rc, out, _err = run(capsys, ["demo"])
    assert rc == 1
    assert "isn't empty" in out


def test_add_and_list(shop, capsys):
    rc, out, err = run(
        capsys,
        ["add", "Mario plush", "--cost", "4", "--theme", "toys", "--qty", "2"],
    )
    assert rc == 0
    assert "Added item #1: Mario plush" in out
    assert "auto estimate $9.60" in out  # 4.00 x 3.0 markup x 0.8 (VG)
    assert "2 units" in out
    rc, out, _err = run(capsys, ["list"])
    assert rc == 0
    assert "Mario plush" in out
    assert "2 units total" in out
    assert pathlib.Path("stash.csv").exists()


def test_add_rejects_bad_input(shop, capsys):
    rc, _out, err = run(capsys, ["add", "X", "--cost", "abc"])
    assert rc == 1
    assert "Could not read cost" in err
    rc, _out, err = run(
        capsys, ["add", "X", "--cost", "5", "--condition", "junk"])
    assert rc == 1
    assert "Unknown condition" in err
    rc, _out, err = run(capsys, ["add", "X", "--cost", "5", "--qty", "0"])
    assert rc == 1
    assert "qty" in err
    rc, _out, err = run(capsys, ["add", "   ", "--cost", "5"])
    assert rc == 1


def test_add_with_known_price_is_used_as_is(shop, capsys):
    rc, out, err = run(
        capsys,
        ["add", "Kindle", "--cost", "18", "--price", "35", "--condition", "A"],
    )
    assert rc == 0
    assert "your price $35.00" in out


def test_remove(shop, capsys):
    run(capsys, ["add", "A", "--cost", "1"])
    rc, out, _err = run(capsys, ["remove", "1"])
    assert rc == 0
    assert "Removed item #1: A" in out
    assert "0 items left" in out
    rc, _out, err = run(capsys, ["remove", "1"])
    assert rc == 1
    assert "No item with id 1" in err


def test_empty_stash_messages(shop, capsys):
    rc, out, _err = run(capsys, ["list"])
    assert rc == 0
    assert "stash is empty" in out
    rc, out, _err = run(capsys, ["suggest"])
    assert rc == 0
    assert "nothing to suggest" in out
    rc, out, _err = run(capsys, ["lots"])
    assert rc == 0
    assert "No saved lots yet" in out


def test_full_flow(shop, capsys):
    """add -> suggest --save -> lots -> forecast -> draft --write."""
    run(capsys, ["add", "Pokemon pile A", "--cost", "6", "--brand",
                 "Pokemon", "--theme", "tcg"])
    run(capsys, ["add", "Pokemon pile B", "--cost", "5", "--brand",
                 "Pokemon", "--theme", "tcg"])
    run(capsys, ["add", "Logitech mouse", "--cost", "7", "--brand",
                 "Logitech", "--theme", "tech"])
    run(capsys, ["add", "Anker charger", "--cost", "6", "--brand",
                 "Anker", "--theme", "tech"])

    rc, out, _err = run(capsys, ["suggest", "--by", "theme"])
    assert rc == 0
    assert "Lot idea: tcg lot" in out and "Pokemon pile A" in out
    assert "--save" in out  # the "keep these" hint

    rc, out, _err = run(capsys, ["suggest", "--save"])
    assert rc == 0
    assert "Saved 2 lot(s) to lots.csv (L1, L2)" in out
    assert "replaces" in out

    rc, out, _err = run(capsys, ["lots"])
    assert rc == 0
    assert "L1" in out and "tcg lot" in out

    rc, out, _err = run(capsys, ["forecast", "-p", "ebay"])
    assert rc == 0
    assert "Lot L1 — tcg lot" in out
    assert "Pricing ladder" in out
    assert "Day 30 — floor" in out
    assert "Verdict" in out
    assert "bundled EXAMPLE rates" in out

    rc, out, _err = run(capsys, ["forecast", "L2", "-p", "amazon"])
    assert rc == 0
    assert "tech lot" in out and "15.0% of sale" in out

    rc, out, _err = run(capsys, ["forecast", "--by", "brand",
                                 "--min-items", "1"])
    assert rc == 0
    assert "ad-hoc brand groupings" in out

    rc, out, _err = run(capsys, ["draft", "L1", "--write"])
    assert rc == 0
    draft_file = pathlib.Path("listings") / "L1.md"
    assert draft_file.exists()
    text = draft_file.read_text(encoding="utf-8")
    assert "## Title (paste this)" in text
    assert "Pokemon" in text
    assert "Day 14 — reprice" in text


def test_forecast_without_saved_lots_hints_next_move(shop, capsys):
    run(capsys, ["add", "A", "--cost", "1", "--theme", "x"])
    rc, out, _err = run(capsys, ["forecast"])
    assert rc == 0
    assert "No saved lots yet" in out
    assert "forecast --by theme" in out


def test_missing_lot_reference(shop, capsys):
    rc, _out, err = run(capsys, ["draft", "L9"])
    assert rc == 1
    assert "No saved lot" in err


def test_removed_items_are_skipped_in_lots(shop, capsys):
    run(capsys, ["add", "A", "--cost", "1", "--theme", "x"])
    run(capsys, ["add", "B", "--cost", "1", "--theme", "x"])
    run(capsys, ["suggest", "--save"])
    rc, out, _err = run(capsys, ["remove", "1"])
    assert rc == 0
    rc, out, _err = run(capsys, ["forecast", "L1"])
    assert rc == 0
    assert "removed from the stash and are skipped" in out
    assert "Lot L1 — x lot" in out


def test_fees_list_print_and_unknown(shop, capsys):
    rc, out, _err = run(capsys, ["fees"])
    assert rc == 0
    assert "eBay" in out and "Amazon" in out
    assert "bundled" in out
    rc, out, _err = run(capsys, ["fees", "ebay"])
    assert rc == 0
    assert '"final_value_fee_pct": 13.25' in out
    rc, _out, err = run(capsys, ["fees", "nope"])
    assert rc == 1
    assert "No platform config named 'nope'" in err
    assert "amazon, ebay" in err


def test_fees_init_uses_customized_rates(shop, capsys):
    rc, out, _err = run(capsys, ["fees", "--init"])
    assert rc == 0
    assert "fees/ebay.json" in out
    assert (pathlib.Path("fees") / "ebay.json").exists()

    run(capsys, ["demo"])
    run(capsys, ["suggest", "--save"])
    rc, out, _err = run(capsys, ["forecast"])
    assert rc == 0
    assert "customized rates" in out

    # Edit your own copy with numbers from your actual dashboard:
    (pathlib.Path("fees") / "ebay.json").write_text(
        json.dumps({"platform": "eBay", "final_value_fee_pct": 9.0}),
        encoding="utf-8",
    )
    rc, out, _err = run(capsys, ["forecast", "L1"])
    assert rc == 0
    assert "9.0% of sale" in out


def test_forecast_adhoc_never_touches_lots_csv(shop, capsys):
    run(capsys, ["add", "A", "--cost", "1", "--theme", "x"])
    rc, out, _err = run(capsys, ["forecast", "--by", "theme"])
    assert rc == 0
    assert "ad-hoc theme groupings" in out
    assert not pathlib.Path("lots.csv").exists()
