# Resale Lot Builder

Turn a shoebox of inventory into sellable bundles — locally, in plain CSV, with
numbers you control.

You itemize what you picked (name, cost, condition), the tool suggests
**lots** — bundles grouped by theme or brand — then forecasts whether a lot
nets you more money than selling piece by piece, and writes a ready-to-paste
listing draft (title, description, pricing ladder) for each one.

No accounts. No scraping. No internet. Everything lives in CSV files in your
folder.

Built for beginners, in plain English — it's a small, practical tool from
**Asdale Dynamics, LLC**: [dylanasdale.github.io](https://dylanasdale.github.io)
explains AI the same way this tool explains itself — like a friend would.

## What it does

- **Itemize a stash** — name, cost, condition (NEW / LN / VG / G / A), brand,
  theme/tag, quantity, optional known price.
- **Suggest lots** — groups items sharing a theme (`--by theme`) or a brand
  (`--by brand`), biggest groups first.
- **Forecast profit** — lot vs. selling separately, using **fee-rate config
  files you set** (eBay/Amazon style percentages, fixed fees, shipping
  assumptions). Includes a pricing ladder: list price → day-14 reprice →
  break-even floor, with estimated profit at each rung.
- **Draft listings** — paste-ready title (under eBay's 80-char limit),
  description, and a pricing ladder you keep for yourself.

## Quickstart

You need Python 3.9+.

```bash
cd anywhere/you/like          # your "shop folder" — data stays right here
pip install -e /path/to/resale-lot-builder

resale-lot-builder demo       # optional: seed six sample items
resale-lot-builder list
resale-lot-builder suggest --save
resale-lot-builder forecast
resale-lot-builder draft L1 --write
```

Or without installing, from the project folder:

```bash
python -m resale_lot_builder list
```

All data appears in your current folder:

| File/folder | What it is |
| --- | --- |
| `stash.csv` | one row per item you own |
| `lots.csv` | saved lot suggestions (created by `suggest --save`) |
| `fees/` | your editable fee-rate configs (created by `fees init`) |
| `listings/` | saved listing drafts (created by `draft --write`) |

## The commands

| Command | What it does |
| --- | --- |
| `add "Name" --cost 8.00 ...` | log an item (`--condition VG`, `--brand`, `--theme`, `--qty`, `--notes`, `--price`) |
| `list` | show the whole stash + totals |
| `remove <id>` | drop an item by id |
| `suggest [--by theme\|brand] [--min-items 2] [--save]` | grouping ideas; `--save` (re)writes `lots.csv` |
| `lots` | list saved lots |
| `forecast [-p ebay] [L1] [--by theme]` | pricing ladder + profit math per lot |
| `draft L1 [-p amazon] [--write]` | paste-ready listing draft |
| `fees` | show every fee config |
| `fees ebay` | print one config's contents |
| `fees init` | copy the bundled configs into `./fees/` so you can edit them |
| `demo` | seed six sample items in an empty folder |

Conditions: `NEW` (New), `LN` (Like new), `VG` (Very good), `G` (Good),
`A` (Acceptable). Longer spellings like `--condition "very good"` work too.

## Fee rates: set your own (important)

The percentages in this repo are **example placeholders** — real fees vary by
category, store level, and any sales you run. Easy fixes:

```bash
resale-lot-builder fees init     # copies ebay.json + amazon.json into ./fees/
# edit fees/ebay.json — set what YOUR account actually charges
```

Each config looks like:

```json
{
  "platform": "eBay",
  "final_value_fee_pct": 13.25,
  "fixed_fee_per_order": 0.30,
  "shipping_cost_per_lot": 7.00,
  "shipping_cost_per_item": 5.00,
  "default_markup_multiplier": 3.0,
  "condition_multipliers": { "NEW": 1.0, "LN": 0.9, "VG": 0.8, "G": 0.7, "A": 0.6 },
  "notes": "Set the rates your account actually charges."
}
```

- Files in `./fees/` override the bundled defaults — use any platform name you
  like (`poshmark.json`, `mercari.json`, `inperson.json`).
- `-p <key>` picks one, e.g. `forecast -p ebay`, `draft L2 -p amazon`.
- `condition_multipliers` scale an item's estimated price by condition.
- `default_markup_multiplier` is the rule of thumb the estimates start with
  (cost × multiplier × condition factor).
- If you set `--price` when adding an item, that price is used as-is — no
  multiplier applied.

## How the money math works

Per item (unless you gave a price): `estimate = cost × markup × condition factor`.

For a lot:

- **Break-even price** covers your cost basis, the fixed per-order fee and one
  lot shipment: `break_even = (total_cost + fixed_fee + lot_shipping) / (1 - fee%)`.
- **Pricing ladder** — Day 0 list at a `.99` price near your total estimates;
  Day 14 drop ~10%; Day 30 sit at the next `.99` above break-even. Estimated
  profit is shown at every rung.
- **Separate-sales comparison** — every unit pays its own fee and its own
  shipping (`shipping_cost_per_item`), so bundling usually wins when the
  single-buyer assumption holds. The output states the trade-off either way.

Two honest limits, printed right in the output when they matter: it never
worries about lots whose break-even lands above the asking price, and it
reminds you that bundling only wins if one buyer takes everything.

## Local-first, private

Data is CSV you own and can open in any spreadsheet. No accounts, no web
requests, no telemetry, no scraping — "market data" is deliberately out of
scope; prices come from your costs and your text.

## Development

```bash
git clone <this repo>      # local repo; no remote is used
pip install -e .[dev]
pytest
```

Project layout:

```
resale_lot_builder/
  cli.py       command parsing + output
  store.py     stash.csv / lots.csv (plain CSV)
  pricing.py   fee configs + profit math + pricing ladder
  grouping.py  theme/brand lot suggestions
  draft.py     listing drafts
  configs/     bundled eBay/Amazon example fee configs
tests/         pytest suite
```

## Credits

Built by **Asdale Dynamics, LLC** — Dylan Asdale's plain-English AI education
shop ([dylanasdale.github.io](https://dylanasdale.github.io)).

Licensed under the MIT License — see `LICENSE`
(`Copyright (c) 2026 Asdale Dynamics, LLC`).
