# STATUS — resale-lot-builder

Date: 2026-10-25
Owner: Asdale Dynamics, LLC (MIT licensed — see `LICENSE`)

## What was built

A local-first command line tool that turns a reseller's itemized stash into
profitable bundles ("lots"), with numbers the seller controls.

- **Itemize a stash** (`add` / `list` / `remove`): name, per-unit cost,
  condition (`NEW`/`LN`/`VG`/`G`/`A`, aliases accepted), brand, theme, qty,
  optional known price, notes. Stored in plain `stash.csv`, one row per item.
- **Lot suggestions** (`suggest --by theme|brand [--min-items N] [--save]`):
  groups items sharing a theme or brand, biggest groups first, shows exact
  membership; `--save` writes `lots.csv` (ids `L1`, `L2`, …).
- **Profit forecasting** (`forecast [-p platform] [L1] [--by theme]`): per
  saved lot (or ad-hoc grouping), shows estimated asking price, a three-rung
  **pricing ladder** (Day 0 list → Day 14 ~10% off → Day 30 break-even floor,
  `.99`-style price endings), profit + ROI at every rung, and a side-by-side
  **bundle vs. selling-everything-separately** verdict that accounts for one
  shared shipment vs. per-item shipments. Underwater lots (break-even above
  the asking price) are flagged explicitly.
- **Listing drafts** (`draft L1 [-p platform] [--write]`): paste-ready title
  (clipped to eBay's 80-char limit with a character count), a plain-English
  description with an itemized condition rundown, then a clearly separated
  seller-only section (ladder, break-even, bundle-vs-separate).
  `--write` saves `listings/L1.md`.
- **Fee-rate config files** (`fees`, `fees init`, `fees ebay`): each platform
  is one JSON file you own — final-value fee %, fixed per-order fee, assumed
  shipping (per lot and per item), markup multiplier, condition multipliers.
  Bundled `ebay.json` / `amazon.json` ship as **example placeholders**;
  `fees init` copies them to `./fees/`, where they override the bundled
  defaults. Any new JSON (e.g. `mercari.json`) becomes a new platform via
  `-p`.
- **`demo`**: seeds six sample items into an empty folder so the tool can be
  tried safely (refuses non-empty stashes).

Privacy posture: no accounts, no scraping, no network calls, no telemetry.
All data is CSV/JSON/Markdown on the user's disk. No secrets or personal
data anywhere in the repo (runtime files are gitignored).

## Project layout

```
resale_lot_builder/
  cli.py        command parsing + friendly output
  store.py      stash.csv / lots.csv models and I/O
  pricing.py    fee configs + profit math + pricing ladder
  grouping.py   theme/brand lot suggestion logic
  draft.py      listing drafts (title/description/ladder)
  configs/      bundled eBay/Amazon example fee configs
  __main__.py   python -m resale_lot_builder entry
tests/          44 pytest tests (unit + CLI end-to-end)
pyproject.toml  installable package (console script), pytest config
README.md       full beginner-friendly guide
LICENSE         MIT — Copyright (c) 2026 Asdale Dynamics, LLC
```

## How to run it

```bash
pip install -e .[dev]            # or: pip install -e .
resale-lot-builder demo          # in any empty folder — that's the shop folder
resale-lot-builder list
resale-lot-builder suggest --save
resale-lot-builder forecast
resale-lot-builder draft L1 --write
resale-lot-builder fees init     # get editable fee configs in ./fees/
```

Python >= 3.9. No runtime dependencies beyond the standard library; pytest
for development only. Works without install via `python -m resale_lot_builder`
from the project folder.

## Verification results (this folder, 2026-10-25)

- `python -m pytest -q` → **44 passed** (unit tests + CLI end-to-end flows,
  each in an isolated temporary shop folder).
- `flake8 resale_lot_builder tests` (max line 100) → **clean**.
- `pip install -e .` in a fresh venv → console script works:
  `resale-lot-builder --version` → `resale-lot-builder 0.1.0`;
  `pip install .` re-verified bundled configs resolve from installed package.
- Manual end-to-end smoke run in a scratch folder: `demo` → `list` →
  `suggest --save` → `fees` → `forecast` → `fees init` → `forecast`
  (customized rates) → `draft L1 --write` → inspected `listings/L1.md`.
- Hand-checked math: fee/net formulas and `.99`-rounding verified against
  independent expectations in `tests/test_pricing.py` (e.g. $100 eBay sale
  nets $79.45; break-even = (cost + fixed + shipping) / (1 − fee%)).

## Design notes

- Estimates are arithmetic over your own cost/price data — **not** market
  data. The tool never scrapes or "knows" real sheet prices, and the output
  says so wherever estimates appear.
- `suggest --save` **replaces** `lots.csv` (predictable re-runs); item ids
  removed from the stash are skipped in lots with a printed note, so lots
  never break after edits.
- Fee JSON files can carry any platform name; `break-even` uses the lot
  shipping cost, separate-selling uses per-item shipping — that's what makes
  the comparison honest.

## Known gaps / honest limits

- No marketplace/sales data integration (by design — that would need scraping
  or API accounts); price estimates are only as good as your cost basis and
  your fee numbers.
- Fee configs are examples, not policy: users must set their own percentages
  (category, store level, promotions, regional fees vary).
- Currency is unspecified (prints `$`); no multi-currency.
- Lots can't be hand-edited after `--save` (re-run `suggest --save`, or edit
  `lots.csv` — ids are stable-ish but item membership is the semicolon list).
- No GUI/web UI; CSVs open fine in any spreadsheet, but a spreadsheet view
  is not built-in.
- Listing drafts are text; no direct listing-slide upload or photo handling.
- Encoding: develops/tests with UTF-8 (em dashes in output); Windows
  terminals with legacy code pages may need `chcp 65001` or
  `PYTHONIOENCODING=utf-8`.
