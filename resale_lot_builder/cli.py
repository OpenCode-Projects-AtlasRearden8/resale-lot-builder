"""Command-line interface for Resale Lot Builder.

All commands operate in your CURRENT FOLDER (local-first):
  stash.csv   your items
  lots.csv    saved lot suggestions
  fees/       your editable fee-rate configs (after `fees init`)
  listings/   saved listing drafts

Type `resale-lot-builder --help` or `<command> --help` for details.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from . import __version__
from .draft import lot_block, render_lot_draft, write_draft
from .grouping import LotSuggestion, suggest_lots
from .pricing import (
    available_platforms,
    estimate_item_price,
    init_fees_dir,
    load_platform_file,
    resolve_platform,
)
from .store import (
    LOTS_FILE,
    STASH_FILE,
    Item,
    Lot,
    Stash,
    LotStore,
    condition_code,
    condition_label,
)

PROG = "resale-lot-builder"


# ---------------------------------------------------------------- helpers


def money(amount: float) -> str:
    style = f"{abs(amount):,.2f}"
    return f"-${style}" if amount < 0 else f"${style}"


def render_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    if not rows:
        return "  ".join(headers)
    widths = [
        max(len(h), *(len(str(r[i])) for r in rows))
        for i, h in enumerate(headers)
    ]
    lines = [
        "  ".join(
            str(h).ljust(w) for h, w in zip(headers, widths)
        )
    ]
    lines.append("  ".join("-" * w for w in widths))
    for row in rows:
        lines.append(
            "  ".join(str(cell).ljust(w) for cell, w in zip(row, widths))
        )
    return "\n".join(line.rstrip() for line in lines)


def _stash() -> Stash:
    return Stash(Path(STASH_FILE))


def _lots() -> LotStore:
    return LotStore(Path(LOTS_FILE))


def _parse_money(value: str, what: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(
            f"Could not read {what} {value!r} — use a plain number like 8.50."
        )
    if number < 0:
        raise ValueError(f"{what.capitalize()} can't be negative.")
    return round(number, 2)


def _next_steps(*hints: str) -> None:
    if hints:
        print()
        print("Next steps: " + "  |  ".join(hints))


# ---------------------------------------------------------------- commands


def _cmd_add(args: argparse.Namespace) -> int:
    stash = _stash()
    items = stash.load()
    cost = _parse_money(args.cost, "cost")
    if args.qty < 1:
        raise ValueError("--qty must be at least 1.")
    price = _parse_money(args.price, "price") if args.price else None
    if price is not None and price == 0:
        raise ValueError("--price must be more than $0 (omit it to auto-estimate).")
    item = Item(
        id=0,
        name=args.name.strip(),
        brand=(args.brand or "").strip(),
        theme=(args.theme or "").strip(),
        condition=condition_code(args.condition),
        cost=cost,
        qty=args.qty,
        price=price,
        notes=(args.notes or "").strip(),
        added=date.today().isoformat(),
    )
    if not item.name:
        raise ValueError("Give the item a name, e.g. add \"Tetris DS cart\" ...")
    stash.add(item)
    total_est = estimate_item_price(item, resolve_platform(
        args.platform, args.fees_dir))
    print(
        f"Added item #{item.id}: {item.name} — "
        f"{condition_label(item.condition)}, cost {money(item.cost)}, "
        f"qty {item.qty}"
        + (f", your price {money(item.price)}" if item.price else
           f", auto estimate {money(total_est)}")
    )
    items = stash.load()
    print(
        f"Stash now: {len(items)} items, {sum(i.qty for i in items)} units, "
        f"total cost {money(sum(i.total_cost for i in items))}"
    )
    _next_steps(f"{PROG} list", f"{PROG} suggest")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    stash = _stash()
    items = stash.load()
    if not items:
        print("Your stash is empty — add your first item:")
        print(f'  {PROG} add "Handheld game" --cost 5.00 --condition VG '
              f'--theme tech')
        return 0
    rows = []
    for it in items:
        rows.append([
            it.id, it.name, it.brand or "—", it.theme or "—",
            f"{it.condition} ({condition_label(it.condition)})",
            money(it.cost), it.qty,
            money(it.price) if it.price else "auto",
            (it.notes or "—"),
        ])
    del args
    print(render_table(
        ["ID", "Name", "Brand", "Theme", "Condition", "Cost", "Qty",
         "Price", "Notes"],
        rows,
    ))
    print()
    print(
        f"{len(items)} items, "
        f"{sum(it.qty for it in items)} units total, "
        f"total cost {money(sum(it.total_cost for it in items))}"
    )
    _next_steps(f"{PROG} suggest", f"{PROG} remove <id>")
    return 0


def _cmd_remove(args: argparse.Namespace) -> int:
    stash = _stash()
    removed = stash.remove(args.id)
    print(f"Removed item #{removed.id}: {removed.name}")
    remaining = stash.load()
    print(
        f"{len(remaining)} items left, total cost "
        f"{money(sum(i.total_cost for i in remaining))}"
    )
    return 0


def _suggestions_from_args(
    args: argparse.Namespace
) -> Tuple[object, List[LotSuggestion], int]:
    """Return (stash, suggestions, leftover_count).

    (None, [], 0) when the stash is empty — callers handle that.
    """
    stash = _stash()
    items = stash.load()
    if not items:
        print("Your stash is empty — nothing to suggest yet. Add items first:")
        print(f'  {PROG} add "Mario plush" --cost 4.00 --theme toys --qty 2')
        return None, [], 0
    suggestions, leftover = suggest_lots(
        items, by=args.by, min_items=args.min_items
    )
    return stash, suggestions, leftover


def _show_suggestion(
    suggestion: LotSuggestion, cfg
) -> None:
    est_retail = round(
        sum(estimate_item_price(it, cfg) * it.qty for it in suggestion.items), 2
    )
    print(
        f"Lot idea: {suggestion.name} — {suggestion.units} units "
        f"({len(suggestion.items)} items), cost "
        f"{money(suggestion.total_cost)}, est. retail "
        f"{money(est_retail)} at {cfg.name} rates"
    )
    for it in suggestion.items:
        qty = f" (x{it.qty})" if it.qty > 1 else ""
        est = estimate_item_price(it, cfg)
        print(f"   #{it.id:>3}  {it.name} — {condition_label(it.condition)}"
              f"{qty} est. {money(est)}")
    print()


def _cmd_suggest(args: argparse.Namespace) -> int:
    _stash_, suggestions, leftover = _suggestions_from_args(args)
    del _stash_
    if args.by not in ("theme", "brand"):
        raise ValueError("--by must be 'theme' or 'brand'.")
    cfg = resolve_platform(args.platform, args.fees_dir)
    print(
        f"Lot ideas by {args.by} (groups need {args.min_items}+ items): "
        f"{len(suggestions)} idea(s), {leftover} item(s) left over\n"
    )
    if not suggestions:
        print(
            "No groups made the cut. Try lowering --min-items or tagging "
            "more items with a common theme/brand."
        )
        return 0
    for suggestion in suggestions:
        _show_suggestion(suggestion, cfg)
    if args.save:
        lot_store = _lots()
        saved = []
        for idx, suggestion in enumerate(suggestions, start=1):
            saved.append(Lot(
                id=f"L{idx}",
                name=suggestion.name,
                grouping=suggestion.grouping,
                key=suggestion.key,
                item_ids=";".join(str(it.id) for it in suggestion.items),
                created=date.today().isoformat(),
            ))
        lot_store.save(saved)
        print(
            f"Saved {len(saved)} lot(s) to {LOTS_FILE} "
            f"({', '.join(lot.id for lot in saved)})."
        )
        print("Note: re-running --save replaces the saved list.")
        _next_steps(f"{PROG} lots", f"{PROG} forecast",
                    f"{PROG} draft L1 --write")
    else:
        _next_steps(f"{PROG} suggest --save (to keep these)",
                    f"{PROG} suggest --by brand")
    return 0


def _cmd_lots(args: argparse.Namespace) -> int:
    del args
    lot_store = _lots()
    lots = lot_store.load()
    if not lots:
        print("No saved lots yet. Create some from your stash:")
        print(f"  {PROG} suggest --save")
        return 0
    stash = _stash()
    items = stash.load()
    rows = []
    for lot in lots:
        members = [it for it in items if it.id in lot.id_parts()]
        rows.append([
            lot.id, lot.name, lot.grouping, len(lot.id_parts()),
            sum(it.qty for it in members),
            money(sum(it.total_cost for it in members)),
            lot.created,
        ])
    print(render_table(
        ["ID", "Lot", "Grouped by", "Items", "Units", "Cost", "Saved"],
        rows,
    ))
    _next_steps(f"{PROG} forecast", f"{PROG} draft L1 --write")
    return 0


def _suggestion_for_lot(lot, items: List[Item]) -> Optional[LotSuggestion]:
    wanted = lot.id_parts()
    index = {it.id: it for it in items}
    members = [index[i] for i in wanted if i in index]
    missing = [i for i in wanted if i not in index]
    if missing:
        print(
            f"Note: item(s) {', '.join('#' + str(m) for m in missing)} were "
            f"removed from the stash and are skipped in this lot."
        )
    if not members:
        print(f"Lot {lot.id} has no items left in the stash — skipping.")
        return None
    return LotSuggestion(
        name=lot.name, grouping=lot.grouping, key=lot.key, items=members
    )


def resolve_platform_with_note(
    args: argparse.Namespace
) -> Tuple[object, List[Path], bool]:
    paths, source_dir = available_platforms(args.fees_dir)
    customized = source_dir.name == "fees"
    cfg = resolve_platform(args.platform, args.fees_dir)
    return cfg, paths, customized


def _cmd_forecast(args: argparse.Namespace) -> int:
    cfg, paths, customized = resolve_platform_with_note(args)
    use = "customized rates in ./fees/" if customized else \
        "bundled EXAMPLE rates (run `fees init` to set your own)"
    lot_store = _lots()
    stash = _stash()
    items = stash.load()
    if args.by:
        suggestions, leftover = suggest_lots(
            items, by=args.by, min_items=args.min_items
        )
        label = f"ad-hoc {args.by} groupings ({len(suggestions)} found, " \
                f"{leftover} item(s) left over)"
        pairs = [
            (f"idea {idx}", s) for idx, s in enumerate(suggestions, start=1)
        ]
        hints = (
            f"{PROG} suggest --save (to keep these as lots)",
            f"{PROG} fees (see/edit rates)",
        )
    else:
        lots = lot_store.load()
        if not lots:
            print("No saved lots yet — but your stash may have ideas.")
            print(f"  {PROG} suggest --save    (keep groupings)")
            print(f"  {PROG} forecast --by theme    (just preview them)")
            return 0
        label = f"saved lots ({len(lots)})"
        pairs = []
        for lot in lots:
            sugg = _suggestion_for_lot(lot, items)
            if sugg:
                pairs.append((lot.id, sugg))
        hints = (
            f"{PROG} draft {pairs[0][0]} --write",
            f"{PROG} fees (see/edit rates)",
        )
    print(f"Forecast — {cfg.name}, {use}\n{label}\n")
    if not pairs:
        print("Nothing to forecast (no lots with items left).")
        return 0
    for lot_id, sugg in pairs:
        for line in lot_block(str(lot_id), sugg, cfg):
            print(line)
    _next_steps(*hints)
    return 0


def _cmd_draft(args: argparse.Namespace) -> int:
    cfg, _paths, _customized = resolve_platform_with_note(args)
    lot = _lots().find(args.lot)
    sugg = _suggestion_for_lot(lot, _stash().load())
    if sugg is None:
        return 1
    text = render_lot_draft(str(lot.id), sugg, cfg)
    if args.write:
        out = write_draft(str(lot.id), text)
        print(f"Wrote listing draft to {out}")
        print(f"{PROG} forecast {lot.id} if you want the numbers first.")
    else:
        print(text)
        print()
        print("Next: add --write to save this as "
              f"listings/{lot.id}.md — then copy-paste into your listing.")
    return 0


def _cmd_fees(args: argparse.Namespace) -> int:
    wants_init = bool(args.init) or (args.platform or "").lower() == "init"
    if wants_init:
        copied = init_fees_dir(args.fees_dir)
        print(f"Copied {len(copied)} fee config(s) into ./fees/:")
        for path in copied:
            print(f"  {path}")
        print()
        print("Open each file and set the percentages YOUR marketplace "
              "account actually charges.")
        print("Real rates vary by category, store level, and promotions — "
              "check your seller dashboard.")
        return 0
    paths, source = available_platforms(args.fees_dir)
    if args.platform:
        matches = [p for p in paths if p.stem.lower() == args.platform.lower()]
        if not matches:
            names = ", ".join(p.stem for p in paths) or "(none)"
            raise ValueError(
                f"No platform config named {args.platform!r}. "
                f"Available: {names}."
            )
        origin = ("customized" if matches[0].parent.name == "fees"
                  else "bundled default")
        print(f"{matches[0]} ({origin}):")
        print()
        print(matches[0].read_text(encoding="utf-8").strip())
        print()
        print("To customize: fees init, then edit ./fees/ "
              f"{matches[0].name}")
        return 0
    rows = []
    for path in paths:
        cfg = load_platform_file(path)
        rows.append([
            cfg.key, cfg.name, f"{cfg.final_value_fee_pct}%",
            money(cfg.fixed_fee_per_order),
            money(cfg.shipping_cost_per_lot),
            money(cfg.shipping_cost_per_item),
            f"{cfg.markup_multiplier}x",
            cfg.source,
        ])
    print("Fee-rate configs on record "
          f"(loaded from {sources_dir_name(source)}):")
    print()
    print(render_table(
        ["Key", "Platform", "Fee %", "Fixed", "Ship/lot", "Ship/item",
         "Markup", "Source"],
        rows,
    ))
    print()
    print("Set your own: fees init + edit the JSON in ./fees/")
    print("Use: forecast -p <key>, e.g. forecast -p ebay")
    return 0


def sources_dir_name(path: Path) -> str:
    return str(path)


def _cmd_demo(args: argparse.Namespace) -> int:
    del args
    stash = _stash()
    items = stash.load()
    if items:
        print(
            f"Stash isn't empty ({len(items)} items) — demo refuses to "
            f"pollute it. Run me in an empty folder instead."
        )
        return 1
    samples = [
        ("Pokemon bulk card pile (50)", "Pokemon", "tcg", 6.00, "VG", 1, None),
        ("Yu-Gi-Oh card bundle", "Konami", "tcg", 5.00, "G", 1, None),
        ("Dragon Shield sleeves box (100)", "Dragon Shield", "tcg",
         4.00, "LN", 1, None),
        ("Logitech M510 wireless mouse", "Logitech", "tech", 7.00, "VG", 1, None),
        ("Anker wall charger", "Anker", "tech", 6.00, "G", 1, None),
        ("Kindle Paperwhite 7th gen", "Amazon", "tech",
         18.00, "A", 1, 35.00),
    ]
    for name, brand, theme, cost, cond, qty, price in samples:
        stash.add(Item(
            id=0, name=name, brand=brand, theme=theme,
            condition=condition_code(cond), cost=cost, qty=qty,
            price=price, notes="demo item", added=date.today().isoformat(),
        ))
    print(f"Seeded {len(samples)} demo items into stash.csv.")
    print()
    _cmd_list(argparse.Namespace())
    return 0


# ---------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description=(
            "Bundle your resale stash into profitable lots — locally, in "
            "plain CSV, with fee numbers YOU control.\n"
            "No accounts, no scraping, no internet."
        ),
        epilog=(
            "Examples:\n"
            f'  {PROG} add "Mario plush" --cost 4.00 --condition VG '
            f'--theme toys --qty 2\n'
            f"  {PROG} suggest --by theme --save\n"
            f"  {PROG} forecast -p ebay\n"
            f"  {PROG} draft L1 --write\n"
            f"  {PROG} fees init\n"
            "\n"
            "Data lives in your current folder: stash.csv, lots.csv, "
            "fees/, listings/.\n"
            "Copy this project anywhere you keep a shop folder and run "
            "it there.\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version", action="version",
        version=f"%(prog)s {__version__}",
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    def fees_flags(p, need_platform=False):
        p.add_argument(
            "-p", "--platform", default="ebay" if not need_platform else None,
            help="platform config key (file name in fees/, e.g. ebay)",
        )
        p.add_argument(
            "--fees-dir", default=None,
            help="folder with fee-rate JSON configs (default ./fees or built-ins)",
        )

    p_add = sub.add_parser(
        "add", help="itemize one item of stock",
        description="Add an item to stash.csv. aka the shoebox intake.",
    )
    p_add.add_argument("name", help='item name, e.g. "Tetris DS cart"')
    p_add.add_argument("--cost", required=True,
                       help="what you paid per unit, e.g. 8.00")
    p_add.add_argument("--condition", default="VG",
                       help="NEW LN VG G or A (default VG)")
    p_add.add_argument("--brand", default="",
                       help="brand/maker, for brand-bundled lots")
    p_add.add_argument("--theme", default="",
                       help="any theme/tag, for themed lots")
    p_add.add_argument("--qty", type=int, default=1,
                       help="how many identical units (default 1)")
    p_add.add_argument("--price", default=None,
                       help="your own asking price per unit (skip to "
                            "auto-estimate)")
    p_add.add_argument("--notes", default="", help="free text storage note")
    fees_flags(p_add)
    p_add.set_defaults(func=_cmd_add)

    p_list = sub.add_parser(
        "list", help="show your whole stash",
        description="Print every item in stash.csv with a cost summary.",
    )
    fees_flags(p_list)
    p_list.set_defaults(func=_cmd_list)

    p_rm = sub.add_parser(
        "remove", help="drop one item from stash",
        description="Remove an item by id (see list).",
    )
    p_rm.add_argument("id", type=int, help="item id to drop")
    p_rm.set_defaults(func=_cmd_remove)

    p_sug = sub.add_parser(
        "suggest", help="suggest lot groupings by theme or brand",
        description="Group stash items sharing a theme or brand into lot "
                    "ideas, biggest groups first.",
    )
    p_sug.add_argument("--by", choices=("theme", "brand"), default="theme",
                       help="group key (default theme)")
    p_sug.add_argument("--min-items", type=int, default=2,
                       help="minimum items per lot (default 2)")
    p_sug.add_argument("--save", action="store_true",
                       help=f"write the realized idea list to {LOTS_FILE} "
                            f"(replaces any saved list)")
    fees_flags(p_sug)
    p_sug.set_defaults(func=_cmd_suggest)

    p_all = sub.add_parser(
        "lots", help="list saved lots",
        description="Show lots in lots.csv.",
    )
    p_all.set_defaults(func=_cmd_lots)

    p_fc = sub.add_parser(
        "forecast", help="lot profit vs. selling separately",
        description="Forecast each lot: pricing ladder, profit at each "
                    "rung, and bundle-vs-separate verdict.",
    )
    p_fc.add_argument("lot", nargs="?", default=None,
                      help="one saved lot, e.g. L1 (default: all)")
    p_fc.add_argument("--by", choices=("theme", "brand"), default=None,
                      help="forecast ad-hoc groupings without saving")
    p_fc.add_argument("--min-items", type=int, default=2,
                      help="min items per ad-hoc lot (default 2)")
    fees_flags(p_fc)
    p_fc.set_defaults(func=_cmd_forecast)

    p_dr = sub.add_parser(
        "draft", help="ready-to-paste listing draft per lot",
        description="Print a paste-ready title + description + pricing "
                    "ladder for one saved lot.",
    )
    p_dr.add_argument("lot", help="saved lot id, e.g. L1")
    p_dr.add_argument("--write", action="store_true",
                      help="also save as listings/<lot>.md")
    fees_flags(p_dr)
    p_dr.set_defaults(func=_cmd_draft)

    p_fe = sub.add_parser(
        "fees", help="show/init fee-rate config files",
        description="Show fee-rate configs, copy the bundled ones into "
                    "./fees/ for editing (pass `init`), or print one config.",
    )
    p_fe.add_argument("platform", nargs="?", default=None,
                      help="`init` copies bundled configs into ./fees/; "
                           "otherwise print that platform's config, e.g. ebay")
    p_fe.add_argument("--init", action="store_true",
                      help="copy bundled configs into ./fees/ to edit")
    p_fe.add_argument("--fees-dir", default=None,
                      help="folder with fee-rate JSON configs")
    p_fe.set_defaults(func=_cmd_fees)

    p_de = sub.add_parser(
        "demo", help="seed six demo items in an empty folder",
        description="Fill an EMPTY stash with six sample items so you can "
                    "poke around safely.",
    )
    p_de.set_defaults(func=_cmd_demo)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    try:
        return int(args.func(args) or 0)
    except (ValueError, KeyError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
