"""
Master Dashboard -- HTML Builder (Phase 4 + 16-Fix Rewrite)
==========================================================
Generates index.html with all technical tabs + SSEM + Valuation.
Implements FIX-1 through FIX-16 from 23-Apr-26 V3 review.

NO ES6 in output: var, function(){}, string concatenation only.
No const, let, arrow functions, template literals, spread operators.

Usage:
  python build_dashboard.py
"""

import json
import os
import shutil
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
OUTPUT_PATH = PROJECT_DIR / "index.html"

COWORK_ROOT = PROJECT_DIR.parent
POSITIONS_PATH = COWORK_ROOT / "positions.json"


def safe_json_load(path):
    """Load JSON, handling files with multiple concatenated docs."""
    with open(path) as f:
        content = f.read()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        dec = json.JSONDecoder()
        obj, _ = dec.raw_decode(content)
        return obj


def load_data():
    prices = safe_json_load(DATA_DIR / "prices.json")
    filters = safe_json_load(DATA_DIR / "filter-results.json")
    universe = safe_json_load(DATA_DIR / "universe.json")
    ticker_mapping = safe_json_load(DATA_DIR / "ticker_mapping.json")

    # SSEM
    ssem = None
    ssem_path = DATA_DIR / "factset-ssem.json"
    if ssem_path.exists():
        ssem = safe_json_load(ssem_path)

    # Valuation
    valuation = None
    val_path = DATA_DIR / "factset-valuation.json"
    if val_path.exists():
        valuation = safe_json_load(val_path)

    # Positions
    positions = None
    if POSITIONS_PATH.exists():
        positions = safe_json_load(POSITIONS_PATH)

    master = {
        "meta": {
            "generated": prices["_meta"]["generated"],
            "source": prices["_meta"]["source"],
            "stock_count": prices["_meta"]["count"],
        },
        "universe": universe["stocks"],
        "prices": prices["stocks"],
        "filters": filters["stocks"],
        "ticker_mapping": ticker_mapping["stocks"],
    }
    if positions:
        master["positions"] = positions
    if ssem:
        ssem_data = {k: v for k, v in ssem.items() if k != "_meta"}
        master["ssem"] = ssem_data
    if valuation:
        val_data = {k: v for k, v in valuation.items() if k != "_meta"}
        master["valuation"] = val_data

    # Qualitative ratings (from IC Ratings Dashboard memos)
    qual_path = DATA_DIR / "qualitative.json"
    if qual_path.exists():
        qual = safe_json_load(qual_path)
        master["qualitative"] = qual

    data_js = "var MASTER_DATA = " + json.dumps(master, separators=(",", ":")) + ";\n"

    # Chart data is NO LONGER embedded — lazy-loaded from charts/<TICKER>.js files
    # (was 185MB+ embedded, now ~200KB per ticker loaded on demand)
    data_js += "var CHART_DATA = {};\n"  # kept for backward compat — empty object

    return data_js


# FIX-6: Each tab gets a unique accent colour
# Tab order: Group 1 = Technical filters, Group 2 = Data/Reference
TABS = [
    # Group 1: Technical filter tabs
    {"id": "bp",        "label": "Basing Plateau",   "accent": "#276749"},
    {"id": "pb",        "label": "Probing Bet",      "accent": "#6b46c1"},
    {"id": "mm99",      "label": "MM 99",            "accent": "#1b3d5c"},
    {"id": "vcp",       "label": "VCP",              "accent": "#9c4221"},
    {"id": "utr",       "label": "Uptrend Retest",   "accent": "#744210"},
    # Group 2: Data / reference tabs
    {"id": "tech",      "label": "Technical Data",   "accent": "#2c5282"},
    {"id": "ssem",      "label": "SSEM",             "accent": "#2b6cb0"},
    {"id": "val",       "label": "Valuation",        "accent": "#38a169"},
    {"id": "combos",    "label": "Combinations",     "accent": "#dd6b20"},
    {"id": "positions", "label": "Live Investments",  "accent": "#319795"},
]

IMPLEMENTED_TABS = [
    "mm99", "bp", "pb", "utr", "vcp", "tech", "combos", "positions",
    "ssem", "val",
]


def build_html(data_js):
    # FIX-6: Build tab buttons with per-tab accent colour as inline style
    def hex_to_rgba(hex_color, alpha):
        """Convert hex like #6366f1 to rgba(99,102,241,0.1)"""
        h = hex_color.lstrip('#')
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"rgba({r},{g},{b},{alpha})"

    # FIX-S4-HDR: Two visual groups of tabs with border grouping
    TECHNICAL_TABS = {"bp", "pb", "vcp", "mm99", "utr"}
    tab_buttons = '<div class="tab-group" style="border:1.5px solid rgba(200,50,50,0.25);border-radius:6px;padding:2px 4px;display:inline-flex;gap:2px">'
    for t in TABS:
        # Switch group when we hit the first data/reference tab (Tech Data)
        if t["id"] not in TECHNICAL_TABS and t["id"] == "tech":
            tab_buttons += '</div><div class="tab-group" style="border:1.5px solid rgba(120,80,200,0.25);border-radius:6px;padding:2px 4px;display:inline-flex;gap:2px;margin-left:6px">'
        active = ' tab-active' if t["id"] == "mm99" else ''
        bg_tint = hex_to_rgba(t["accent"], 0.1)
        border_tint = hex_to_rgba(t["accent"], 0.3)
        tab_buttons += (
            '<button class="tab-btn' + active + '" data-tab="' + t["id"] + '" '
            'style="--tab-accent:' + t["accent"] + ';background:' + bg_tint + ';border-color:' + border_tint + '" '
            'onclick="switchTab(\'' + t["id"] + '\')">' + t["label"] + '</button>'
        )
    tab_buttons += '</div>'

    tab_containers = ""
    for t in TABS:
        display = "block" if t["id"] == "mm99" else "none"
        tab_containers += '<div id="tab-' + t["id"] + '" class="tab-content" style="display:' + display + '"></div>\n    '

    tab_ids_js = ",".join(['"' + t["id"] + '"' for t in TABS])
    tab_labels_js = ",".join(['"' + t["label"] + '"' for t in TABS])
    tab_accents_js = ",".join(['"' + t["accent"] + '"' for t in TABS])

    # ---- CSS ----
    css = r"""
*,*::before,*::after{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#f7f5ef;--card:#fbfaf5;--card-hover:#f0ede3;--border:#e8e3d4;
  --text:#333333;--text-dim:#6b6b6b;--text-bright:#1a1a1a;
  --green:#2e7d32;--green-dim:#e8f5e9;--red:#c62828;--red-dim:#ffebee;
  --amber:#8d6e00;--amber-dim:#fff8e1;--blue:#1565c0;--purple:#7955bf;
  --header-height:145px;
  --font:'Aptos','Segoe UI',system-ui,-apple-system,sans-serif
}
body{font-family:var(--font);background:var(--bg);color:var(--text);font-size:13px;line-height:1.4;overflow-x:hidden}
.header{position:fixed;top:0;left:0;right:0;height:var(--header-height);background:var(--card);border-bottom:1px solid var(--border);z-index:100;display:flex;flex-direction:column}
/* FIX-5 Row 1: title + stats + Key + Chart */
.header-top{display:flex;align-items:center;padding:6px 16px;gap:16px}
.header-title{font-size:16px;font-weight:600;color:var(--text-bright);white-space:nowrap}
.header-stats{display:flex;gap:20px;font-size:12px;color:var(--text-dim)}
.header-stats .stat-value{color:var(--text-bright);font-weight:600}
/* FIX-1: Key + Chart pushed right */
.header-right-btns{display:flex;gap:6px;margin-left:auto}
.header-right-btns .ctrl-btn{background:var(--card);border:1px solid var(--border);color:var(--text-dim);font-family:var(--font);font-size:11px;padding:3px 10px;border-radius:4px;cursor:pointer;white-space:nowrap}
.header-right-btns .ctrl-btn:hover{color:var(--text);border-color:#bbb}
/* FIX-5 Row 2: TABS label + tab nav */
.header-tabs-row{display:flex;align-items:center;padding:0 16px 2px;gap:8px}
.header-tabs-row .row-label{font-size:12px;font-weight:700;color:var(--text-bright);text-transform:uppercase;letter-spacing:.5px;white-space:nowrap}
.tab-nav{display:flex;gap:2px;overflow-x:auto;-webkit-overflow-scrolling:touch}
/* FIX-6: Tab buttons with colour edging */
.tab-btn{background:var(--card);border:1px solid var(--border);border-left:3px solid var(--tab-accent,#1b3d5c);color:var(--text-dim);font-family:var(--font);font-size:11px;font-weight:500;padding:4px 10px;border-radius:4px;cursor:pointer;white-space:nowrap;transition:background .15s,color .15s}
.tab-btn:hover{background:var(--card-hover);color:var(--text)}
.tab-btn.tab-active{background:var(--tab-accent,#1b3d5c);color:#fff;font-weight:600;border-left-color:var(--tab-accent,#1b3d5c)}
/* FIX-5 Row 3: toggles label + controls */
.header-controls-row{display:flex;gap:6px;padding:0 16px 4px;align-items:center;flex-wrap:wrap}
.header-controls-row .row-label{font-size:12px;font-weight:700;color:var(--text-bright);text-transform:uppercase;letter-spacing:.5px;white-space:nowrap;min-width:80px}
.header-controls-row .ctrl-btn{background:var(--card);border:1px solid var(--border);color:var(--text-dim);font-family:var(--font);font-size:11px;padding:3px 10px;border-radius:4px;cursor:pointer;white-space:nowrap}
.header-controls-row .ctrl-btn:hover{color:var(--text);border-color:#bbb}
.header-controls-row .ctrl-btn.active{background:#1b3d5c;color:#fff;border-color:#1b3d5c}
.header-controls-row .anchor-links{display:flex;gap:4px;margin-left:auto;align-items:center}
.header-controls-row .anchor-link{color:var(--text-dim);font-size:11px;text-decoration:none;cursor:pointer;padding:3px 8px;border:1px solid var(--border);border-radius:4px;background:var(--card)}
.header-controls-row .anchor-link:hover{color:var(--text-bright);border-color:#bbb;background:var(--card-hover)}
#header-tab-controls{display:inline-flex;gap:6px;align-items:center;flex-wrap:wrap}
.main{margin-top:var(--header-height);padding:12px 16px}
.tab-content{animation:fadeIn .2s ease}
@keyframes fadeIn{from{opacity:0}to{opacity:1}}
.summary-tile{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:12px}
.summary-tile h3{font-size:14px;font-weight:600;color:var(--text-bright);margin-bottom:8px}
.summary-tile .sub{font-size:12px;color:var(--text-dim);margin-bottom:8px}
.summary-stats{display:flex;gap:24px;flex-wrap:wrap}
.summary-stat{display:flex;flex-direction:column}
.summary-stat .label{font-size:11px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.5px}
.summary-stat .value{font-size:20px;font-weight:700;color:var(--text-bright)}
.summary-stat .value.green{color:var(--green)}.summary-stat .value.red{color:var(--red)}.summary-stat .value.amber{color:var(--amber)}
.score-filter,.group-toggles{display:flex;gap:4px;flex-wrap:wrap}
.score-btn,.group-toggle{background:var(--card);border:1px solid var(--border);color:var(--text-dim);font-family:var(--font);font-size:11px;padding:4px 10px;border-radius:4px;cursor:pointer}
.score-btn:hover,.group-toggle:hover{border-color:#bbb;color:var(--text)}
.score-btn.active{background:#1b3d5c;color:#fff;border-color:#1b3d5c;font-weight:600}
.group-toggle.active{background:#1b3d5c;color:#fff;border-color:#1b3d5c;font-weight:600}

/* FIX-11: Fixed table layout, no horizontal scroll */
.data-table-wrap{overflow-x:hidden;border-radius:8px;border:1px solid var(--border)}
table.data-table{width:100%;border-collapse:collapse;font-size:12px;table-layout:auto}
table.data-table th{background:#f0ede3;color:#6b6b6b;font-weight:600;font-size:10px;text-transform:uppercase;letter-spacing:.3px;padding:4px 4px;text-align:left;border-bottom:2px solid var(--border);position:sticky;top:0;z-index:5;cursor:pointer;white-space:nowrap;user-select:none;-webkit-user-select:none;overflow:hidden;text-overflow:ellipsis}
table.data-table th:hover{color:var(--text)}
table.data-table th .sort-arrow{margin-left:2px;opacity:.4}
table.data-table th.sorted .sort-arrow{opacity:1;color:var(--amber)}
table.data-table td{padding:3px 4px;border-bottom:1px solid #e8e3d4;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
table.data-table tr:hover{background:var(--card-hover)}
/* FIX-9: Consistent text alignment */
.col-num{text-align:right}
.col-txt{text-align:left}
table.data-table th.col-num{text-align:right}
table.data-table th.col-txt{text-align:left}

/* FIX-4: Group header row above column headers */
/* FIX-SORT: Group header row sticks at top:0; column header row sticks below it at top:20px */
table.data-table .group-header-row th{background:#f5f3ec;font-size:9px;font-weight:600;padding:2px 4px;text-align:center;border-bottom:1px solid var(--border);cursor:default;letter-spacing:.4px;z-index:6;top:0;pointer-events:none}
table.data-table .col-header-row th{top:20px;z-index:8}

/* Column group borders */
.grp-lt-first{border-left:2px solid rgba(200,50,50,0.25)}
.grp-lt-last{border-right:2px solid rgba(200,50,50,0.25)}
th.grp-lt-first,th.grp-lt-last{border-top:2px solid rgba(200,50,50,0.25)}
.grp-mt-first{border-left:2px solid rgba(200,150,0,0.25)}
.grp-mt-last{border-right:2px solid rgba(200,150,0,0.25)}
th.grp-mt-first,th.grp-mt-last{border-top:2px solid rgba(200,150,0,0.25)}
.grp-st-first{border-left:2px solid rgba(50,150,50,0.25)}
.grp-st-last{border-right:2px solid rgba(50,150,50,0.25)}
th.grp-st-first,th.grp-st-last{border-top:2px solid rgba(50,150,50,0.25)}
.grp-lead-first{border-left:2px solid rgba(50,100,200,0.25)}
.grp-lead-last{border-right:2px solid rgba(50,100,200,0.25)}
th.grp-lead-first,th.grp-lead-last{border-top:2px solid rgba(50,100,200,0.25)}
.grp-rs-first{border-left:2px solid rgba(120,80,200,0.25)}
.grp-rs-last{border-right:2px solid rgba(120,80,200,0.25)}
th.grp-rs-first,th.grp-rs-last{border-top:2px solid rgba(120,80,200,0.25)}
.grp-eps-first{border-left:2px solid rgba(50,150,50,0.25)}
.grp-eps-last{border-right:2px solid rgba(50,150,50,0.25)}
th.grp-eps-first,th.grp-eps-last{border-top:2px solid rgba(50,150,50,0.25)}
.grp-ebitda-first{border-left:2px solid rgba(50,100,200,0.25)}
.grp-ebitda-last{border-right:2px solid rgba(50,100,200,0.25)}
th.grp-ebitda-first,th.grp-ebitda-last{border-top:2px solid rgba(50,100,200,0.25)}
.grp-sales-first{border-left:2px solid rgba(200,150,0,0.25)}
.grp-sales-last{border-right:2px solid rgba(200,150,0,0.25)}
th.grp-sales-first,th.grp-sales-last{border-top:2px solid rgba(200,150,0,0.25)}
.grp-tp-first{border-left:2px solid rgba(120,80,200,0.25)}
.grp-tp-last{border-right:2px solid rgba(120,80,200,0.25)}
th.grp-tp-first,th.grp-tp-last{border-top:2px solid rgba(120,80,200,0.25)}
.grp-buy-first{border-left:2px solid rgba(200,50,50,0.25)}
.grp-buy-last{border-right:2px solid rgba(200,50,50,0.25)}
th.grp-buy-first,th.grp-buy-last{border-top:2px solid rgba(200,50,50,0.25)}
.grp-pe-first{border-left:2px solid rgba(50,150,50,0.25)}
.grp-pe-last{border-right:2px solid rgba(50,150,50,0.25)}
th.grp-pe-first,th.grp-pe-last{border-top:2px solid rgba(50,150,50,0.25)}
.grp-loose-first{border-left:2px solid rgba(50,100,200,0.25)}
.grp-loose-last{border-right:2px solid rgba(50,100,200,0.25)}
th.grp-loose-first,th.grp-loose-last{border-top:2px solid rgba(50,100,200,0.25)}
.grp-med-first{border-left:2px solid rgba(200,150,0,0.25)}
.grp-med-last{border-right:2px solid rgba(200,150,0,0.25)}
th.grp-med-first,th.grp-med-last{border-top:2px solid rgba(200,150,0,0.25)}
.grp-tight-first{border-left:2px solid rgba(50,150,50,0.25)}
.grp-tight-last{border-right:2px solid rgba(50,150,50,0.25)}
th.grp-tight-first,th.grp-tight-last{border-top:2px solid rgba(50,150,50,0.25)}

table.data-table th.col-num,table.data-table td.col-num{text-align:right}
table.data-table th.col-txt,table.data-table td.col-txt{text-align:left}
table.data-table th.col-filter,table.data-table td.col-filter{text-align:center}
table.data-table th.col-rs,table.data-table td.col-rs{text-align:center}
table.data-table th.col-ref,table.data-table td.col-ref{text-align:center}
table.data-table th.col-ratings,table.data-table td.col-ratings{text-align:center}
table.data-table th.col-price,table.data-table td.col-price{text-align:right}
/* FIX-S4-COLW-V4: table-layout:auto — browser auto-sizes by content */
table.data-table td.col-identity{white-space:nowrap}
.col-price{background:rgba(21,101,192,.03)}.col-filter{background:rgba(141,110,0,.03)}.col-rs{background:rgba(121,85,191,.03)}.col-green{background:rgba(46,125,50,.03)}.col-ref{background:rgba(21,101,192,.03)}
.pass{color:var(--green)}.fail{color:var(--red)}.amber{color:var(--amber)}.neutral{color:var(--text-dim)}
.badge{display:inline-block;padding:2px 6px;border-radius:3px;font-size:10px;font-weight:600;text-transform:uppercase}
.badge-pass{background:var(--green-dim);color:var(--green)}.badge-fail{background:var(--red-dim);color:var(--red)}.badge-amber{background:var(--amber-dim);color:var(--amber)}
.badge-capital{background:#e8f5e9;color:var(--green);border:1px solid rgba(46,125,50,.3)}
.badge-late{background:#fff8e1;color:var(--amber);border:1px solid rgba(141,110,0,.3)}
.badge-early{background:#e3f2fd;color:var(--blue);border:1px solid rgba(21,101,192,.3)}
.tick{color:var(--green)}.cross{color:var(--red)}
.score-bar{display:inline-flex;gap:1px;vertical-align:middle}
.score-bar .pip{width:6px;height:12px;border-radius:2px}
.pip-on{background:var(--green)}.pip-off{background:#e0ddd3}
.pip-amber{background:var(--amber)}
.signal-bar{display:inline-flex;gap:1px;vertical-align:middle}
.signal-bar .seg{width:12px;height:16px;border-radius:2px}
.seg-pass{background:var(--green)}.seg-fail{background:var(--red-dim)}.seg-amber{background:var(--amber-dim)}
.combo-cell{text-align:center;font-weight:600}

/* Industry/Sector tiles */
.ind-sec-wrap{display:flex;gap:12px;margin-bottom:12px}
.ind-sec-wrap .half-table{flex:1;min-width:0;height:480px;display:flex;flex-direction:column}
.half-table .half-title{font-size:13px;font-weight:600;color:var(--text-bright);margin-bottom:6px;flex-shrink:0}
.half-table .data-table-wrap{flex:1;overflow-y:auto;overflow-x:hidden;max-height:450px}
.half-table table.data-table th{font-size:11px;text-transform:none;letter-spacing:0;white-space:normal;word-wrap:break-word}

.qual-tile{padding:12px 0;margin-bottom:8px;margin-top:24px}
.qual-tile h4{font-size:13px;font-weight:600;color:var(--text-bright);margin-bottom:8px}
.qualified-title{margin-top:20px}
.chart-panel{position:fixed;top:var(--header-height);right:0;bottom:0;width:25%;background:var(--card);border-left:1px solid var(--border);z-index:90;transform:translateX(100%);transition:transform .3s ease,width .3s ease;overflow-y:auto;padding:16px}
.chart-panel.open{transform:translateX(0)}
.chart-open .main{margin-right:25%;transition:margin-right .3s ease}
.chart-panel .close-btn{position:absolute;top:8px;right:8px;background:var(--card-hover);border:1px solid var(--border);color:var(--text);width:28px;height:28px;border-radius:4px;cursor:pointer;font-size:16px}
.chart-width-btns{display:flex;gap:4px;margin-bottom:12px}
.chart-width-btn{background:var(--card);border:1px solid var(--border);color:var(--text-dim);font-family:var(--font);font-size:11px;padding:3px 8px;border-radius:3px;cursor:pointer}
.chart-width-btn.active{background:#1b3d5c;color:#fff;border-color:#1b3d5c}

/* FIX-16: graduated colours including grey neutral */
.grad-green{color:#2e7d32}.grad-lgreen{color:#558b2f}.grad-neutral{color:#6b6b6b}.grad-red{color:#c62828}.grad-dred{color:#b71c1c}
.sparkline-cell{vertical-align:middle}
.range-bar-cell{vertical-align:middle}

/* Key: floating tooltips near column headers */
.key-panel{display:none}
table.data-table th .key-tip{display:none;position:absolute;top:100%;left:0;z-index:20;background:#fbfaf5;border:1px solid #e8e3d4;border-radius:4px;padding:6px 10px;font-size:10px;font-weight:400;color:#6b6b6b;white-space:normal;min-width:160px;max-width:300px;box-shadow:0 2px 8px rgba(0,0,0,.08);text-transform:none;letter-spacing:0;line-height:1.35;pointer-events:none}
table.data-table.show-keys th .key-tip{display:block}
table.data-table.show-keys th{overflow:visible}
table.data-table th{position:relative}

/* FIX-3: Ratings columns toggle */
.ratings-hidden .col-ratings{display:none}

/* FIX-2: Qualified Stocks heading */
.qualified-title{font-size:14px;font-weight:600;color:var(--text-bright);margin:12px 0 8px;padding-left:4px}

/* UTR V2: Stage group borders (MM99 pattern) */
.utr-e-first{border-left:2px solid rgba(200,170,0,0.30)}
.utr-e-last{border-right:2px solid rgba(200,170,0,0.30)}
th.utr-e-first,th.utr-e-last{border-top:2px solid rgba(200,170,0,0.30)}
.utr-l-first{border-left:2px solid rgba(230,100,0,0.30)}
.utr-l-last{border-right:2px solid rgba(230,100,0,0.30)}
th.utr-l-first,th.utr-l-last{border-top:2px solid rgba(230,100,0,0.30)}
.utr-c-first{border-left:2px solid rgba(46,125,50,0.30)}
.utr-c-last{border-right:2px solid rgba(46,125,50,0.30)}
th.utr-c-first,th.utr-c-last{border-top:2px solid rgba(46,125,50,0.30)}
/* UTR key description row above headers */
.utr-key-row td{font-size:9px;color:#8b8680;font-weight:400;font-style:italic;text-align:center;padding:1px 3px;white-space:normal;line-height:1.2;vertical-align:bottom;border-bottom:none;max-width:64px;overflow:hidden;text-overflow:ellipsis}
/* UTR: hide inputs columns */
.utr-inputs-hidden .col-input{display:none}
/* UTR: Test MA colour coding */
.ma-50d{color:#ff8c00;font-weight:700}.ma-100d{color:#2ca02c;font-weight:700}.ma-150d{color:#1a5276;font-weight:700}.ma-200d{color:#4a3d9e;font-weight:700}

@media(max-width:768px){.header-stats{display:none}.ind-sec-wrap{flex-direction:column}}
/* FEAT-5: Industry/sector filter highlight */
.ind-sec-highlight td.col-sector,.ind-sec-highlight td.col-industry{background:rgba(46,125,50,0.08)}
.filter-pill{transition:opacity 0.2s}.filter-pill:hover{opacity:0.8}
"""

    # ---- JavaScript ----
    js = r"""
(function(){
"use strict";
var D=MASTER_DATA;
var priceMap={},filterMap={},tmMap=D.ticker_mapping||{};
var currentTab="mm99",currentSort={col:"mm99_score",dir:"desc"};
var mm99MinScore=0;
var utrMinCap=0;
var utrFailedFilter="";  // ""=off, "L1W"=last 1 week, "L1M"=last 1 month
var utrShowInputs=false;  // default hidden
var displayMode="ticker";
var valueMode="tick";
var showRatings=false;
var TAB_IDS=[""" + tab_ids_js + r"""];
var TAB_LABELS=[""" + tab_labels_js + r"""];
var TAB_ACCENTS=[""" + tab_accents_js + r"""];
var activeGroups={};
// FEAT-5: Industry/sector filter state (resets on tab switch)
var indFilter={};  // {industry_name: true, ...}
var secFilter={};  // {sector_name: true, ...}
window.toggleIndFilter=function(ind){
  if(indFilter[ind])delete indFilter[ind];else indFilter[ind]=true;
  renderTab(currentTab);
};
window.toggleSecFilter=function(sec){
  if(secFilter[sec])delete secFilter[sec];else secFilter[sec]=true;
  renderTab(currentTab);
};
window.clearIndSecFilter=function(){
  indFilter={};secFilter={};renderTab(currentTab);
};
function hasIndSecFilter(){
  for(var k in indFilter)if(indFilter.hasOwnProperty(k))return true;
  for(var k in secFilter)if(secFilter.hasOwnProperty(k))return true;
  return false;
}
function passIndSecFilter(r){
  var hasInd=false,hasSec=false;
  for(var k in indFilter)if(indFilter.hasOwnProperty(k)){hasInd=true;break}
  for(var k in secFilter)if(secFilter.hasOwnProperty(k)){hasSec=true;break}
  if(!hasInd&&!hasSec)return true;
  var indOk=!hasInd||indFilter[r._tax_industry];
  var secOk=!hasSec||secFilter[r._tax_sector];
  return indOk&&secOk;
}
function applyIndSecFilter(rows){var out=[];for(var j=0;j<rows.length;j++){if(passIndSecFilter(rows[j]))out.push(rows[j])}return out}
function indSecFilterPills(){
  if(!hasIndSecFilter())return"";
  var h='<span class="filter-pill" onclick="clearIndSecFilter()" style="margin-left:12px;cursor:pointer;background:#e74c3c;color:#fff;padding:2px 10px;border-radius:12px;font-size:11px;font-weight:600">';
  var parts=[];
  for(var k in indFilter)if(indFilter.hasOwnProperty(k))parts.push(k);
  for(var k in secFilter)if(secFilter.hasOwnProperty(k))parts.push(k);
  h+=parts.join(" + ")+' &times;</span>';
  return h;
}
// FIX-S4-PBEXCL: Exclude toggles for PB tab
var pbExcludes={ex_mm99:false,ex_vcp:false,ex_utr:false};
window.togglePbExclude=function(k){pbExcludes[k]=!pbExcludes[k];renderTab("pb")};

var CANONICAL_INDUSTRIES=[
  "A. Consumer staples","B. Healthcare","C. Telecoms",
  "E. Utilities","F. Defence",
  "G. Financials","H. Consumer discretionary",
  "I. Transportation","J. Technology",
  "K. Professional, business and consumer services",
  "L. Media","M. Materials","N. Real assets",
  "O. Industrials and capital goods",
  "P. Energy, commodities and metals mining"
];

var i;
for(i=0;i<D.prices.length;i++)priceMap[D.prices[i].ticker]=D.prices[i];
for(i=0;i<D.filters.length;i++)filterMap[D.filters[i].ticker]=D.filters[i];

// BUG-1-FIX: Build position ticker set + ensure all positions have filter stubs
var positionTickerSet={};
if(D.positions&&D.positions.investments){
  for(i=0;i<D.positions.investments.length;i++){
    var pt=D.positions.investments[i].ticker;
    positionTickerSet[pt]=true;
    // Create stub filter entry if missing
    if(!filterMap[pt]){
      filterMap[pt]={ticker:pt,mm99:{score_11:0,stage:"",group_a:{pass:false,tests:{T1:false,T2:false},ma200_months_rising:0},group_b:{pass:false,tests:{T3:false,T4:false}},group_c:{pass:false,tests:{T5:false,T6:false}},group_d:{pass:false,tests:{T7:false,T8:false}},group_e:{pass:false,tests:{T9:false,T10:false,T11:false},rs_vs_sector:null,rs_excess_sector:null,rs_excess_industry:null,rs_excess_market:null}},basing_plateau:{stage:"",group_a:{pass:false,tests:{T1:false,T2:false}},group_b:{pass:false,tests:{T3:false,T4:false,T5:false}},group_c:{pass:false,tests:{T6:false,T7:false,T8:false}}},probing_bet:{stage:"",group_a:{pass:false,tests:{T1:false,T2:false,T3:false,T4:false,T5:false}},group_b:{pass:false,tests:{T6:false,T7:false}},group_c:{pass:false,tests:{T8:false}},group_d:{pass:false,tests:{T9:false,T10:false}},group_e:{pass:false,tests:{T11:false,T12:false}}},uptrend_retest:{composite:0,signals:[]},vcp:{stage2:false}};
    }
    // Create stub price entry if missing
    if(!priceMap[pt]){
      var tax=getTaxonomy?getTaxonomy(pt):{industry:"",sector:""};
      D.prices.push({ticker:pt,company_name:pt,sector:tax.sector||"",industry:tax.industry||"",price:null,price_prev:null,high_52w:null,low_52w:null,mas:null,rs_percentile:null,rs_vs_sector:null,rs_composite:null,adv_1m:null,adv_3m:null,swing_high:null});
      priceMap[pt]=D.prices[D.prices.length-1];
    }
  }
}

document.getElementById("stat-count").textContent=D.meta.stock_count;
document.getElementById("stat-source").textContent=D.meta.source;
document.getElementById("stat-updated").textContent=D.meta.generated;

// ---- Key panel column descriptions per tab ----
var KEY_DEFS={
  mm99:[
    ["Ticker","Stock ticker symbol"],["Sector","Industry sector classification"],["Price","Current stock price"],
    ["52W High","52-week high price (or % from high in % mode)"],["52W Low","52-week low price (or % from low in % mode)"],["RS","Relative Strength percentile (0-100)"],
    ["Score","Minervini 8-point technical score"],["Stage","Capital / Late / Early stage classification"],
    ["P>200D","Price above 200-day MA"],["200D Up","200-day MA trending upward (month count)"],
    ["P>150D","Price above 150-day MA"],["150>200","150-day MA above 200-day MA"],
    ["50>150","50-day MA above 150-day MA"],["P>50D","Price above 50-day MA"],
    ["P>20%L","Price at least 20% above 52-week low"],["P<25%H","Price within 25% of 52-week high"],
    ["Sector","Relative strength vs sector"],["Industry","Relative strength vs industry"],["Market","Relative strength vs market"]
  ],
  bp:[
    ["Ticker","Stock ticker symbol"],["Sector","Industry sector classification"],["Price","Current stock price"],
    ["Stage","Basing Plateau stage: Tight=Capital, Medium=Late, Loose=Early"],
    ["MA Map","Visual position of Price, 200D, 150D, 50D MAs"],
    ["T1-T2","Loose tests: Price and 50D within 15% of 200D"],
    ["T3-T5","Medium tests: Price, 50D, 150D within 10% of 200D"],
    ["T6-T8","Tight tests: Price, 50D, 150D within 5% of 200D"]
  ],
  pb:[
    ["Ticker","Stock ticker symbol"],["Stage","Probing Bet stage"],
    ["T1-T5","Group A: rising MAs (P, 5D, 10D, 20D, 50D)"],
    ["T6-T7","Group B: 20D and 50D rising"],
    ["Dead Cat","Group C: 30%+ below 52W high"],
    ["PB1/PB2","Capital entry: price above rising 20D/50D"]
  ],
  utr:[
    ["Ticker","Stock ticker symbol"],["Score","Composite pullback quality score (max 8)"],
    ["Depth-RS","8 signal assessments: pass/amber/fail"],
    ["EWS","Early warning signals count (5 max)"]
  ],
  vcp:[
    ["Ticker","Stock ticker symbol"],["Stage 2","In Stage 2 uptrend (Groups A+B pass)"],
    ["MM Score","Minervini 8-point score"]
  ],
  tech:[
    ["MAs","Moving averages at various periods"],["52W","52-week high and low"],["ADV","Average daily volume"]
  ],
  ssem:[
    ["EPS/EBITDA/Sales","Consensus revision % over 1M/3M/6M/12M"],
    ["TP","Target price revision %"],["Buy","% of analysts with Buy rating"],["Momentum","Composite momentum count"]
  ],
  val:[
    ["P/E","Current price-to-earnings ratio"],["Pctile","P/E percentile vs 10Y history (0=cheapest)"],
    ["Range","Visual: 10Y P/E range bar (green=below median, red=above)"],["EPS 24MF","24-month forward EPS estimate"]
  ]
};

// ---- Shared Utilities ----
function getTaxonomy(ticker){
  var m=tmMap[ticker];
  if(m)return{industry:m.industry||"",sector:m.sector||""};
  var p=priceMap[ticker];
  if(p)return{industry:p.industry||"",sector:p.sector||""};
  return{industry:"",sector:""};
}

window.switchTab=function(id){
  var b=document.querySelectorAll(".tab-btn");
  for(var j=0;j<b.length;j++){b[j].classList.remove("tab-active");if(b[j].getAttribute("data-tab")===id)b[j].classList.add("tab-active")}
  var c=document.querySelectorAll(".tab-content");
  for(var j=0;j<c.length;j++){c[j].style.display="none"}
  var el=document.getElementById("tab-"+id);
  if(el){
    el.style.display="block";
    currentTab=id;
    // Only render if tab is empty (first visit) or needs refresh
    if(!el.innerHTML||el.getAttribute("data-stale")==="1"){
      el.removeAttribute("data-stale");
      renderTab(id);
    } else {
      // Always refresh header controls even on cached tabs
      buildHeaderControls(id);
    }
  }
  // FIX-5: update toggles label
  var tl=document.getElementById("toggles-label");
  if(tl){
    for(var j=0;j<TAB_IDS.length;j++){if(TAB_IDS[j]===id){tl.textContent=TAB_LABELS[j]+" Filters";break}}
  }
  // Close key panel on tab switch
  var kp=document.getElementById("key-panel");
  if(kp)kp.classList.remove("open");
};
window.closeChart=function(){
  document.getElementById("chart-panel").classList.remove("open");
  document.body.classList.remove("chart-open");
  document.querySelector(".main").style.marginRight="0";
};
window.setChartWidth=function(p){
  var pn=document.getElementById("chart-panel");
  pn.style.width=p+"%";
  document.querySelector(".main").style.marginRight=p+"%";
  var b=document.querySelectorAll(".chart-width-btn");
  for(var j=0;j<b.length;j++)b[j].classList.remove("active");
  if(event&&event.target)event.target.classList.add("active");
  // Redraw chart at new panel width after transition
  if(chartTicker)setTimeout(function(){drawMasterChart(chartTicker)},350);
};
// FIX-S4-CHART-V2: Faithful port of pullback-monitor.html drawChart
var chartZoom="2Y";
var chartTicker="";
// Default: 5D+10D off (except on PB tab where short MAs matter)
var chartVis={ma5:false,ma10:false,ma20:true,ma50:true,ma100:true,ma150:true,ma200:true,obv:true,vol:true,vol20:true,vol50:true};
function fmtVol(v){if(v>=1000000)return(v/1000000).toFixed(1)+"M";if(v>=1000)return(v/1000).toFixed(0)+"K";return v.toFixed(0)}
function getChartSlice(chart,zoom){
  var n=chart.length;
  var days={"1M":Math.min(n,22),"3M":Math.min(n,63),"6M":Math.min(n,125),"12M":Math.min(n,252),"2Y":Math.min(n,504),"3Y":Math.min(n,756),"5Y":Math.min(n,1260)};
  var count=days[zoom]||days["6M"];
  return chart.slice(Math.max(0,n-count));
}
window.toggleChartLayer=function(layer){
  chartVis[layer]=!chartVis[layer];
  drawMasterChart(chartTicker);
  // Update legend opacity
  var el=document.getElementById("legend-"+layer);
  if(el)el.style.opacity=chartVis[layer]?"1":"0.3";
};
// === LAZY CHART LOADER ===
// Chart data lives in charts/<TICKER>.js files (~200KB each).
// Each file self-registers: var CHART_REGISTRY=CHART_REGISTRY||{};CHART_REGISTRY["TICKER"]=[...];
// Data is compact array format: [date, o, h, l, c, v, ma5, ma10, ma20, ma50, ma100, ma150, ma200]
var CHART_REGISTRY = CHART_REGISTRY || {};
var _chartLoading = {};

function _safeTickerFile(t){
  return t.replace(/[.\/]/g,"_");
}

function _expandChartRows(rows){
  // Convert compact [d,o,h,l,c,v,ma5,...,ma200] back to object format
  var maKeys=["ma5","ma10","ma20","ma50","ma100","ma150","ma200"];
  var out=[];
  for(var i=0;i<rows.length;i++){
    var r=rows[i];
    var obj={d:r[0],o:r[1],h:r[2],l:r[3],c:r[4],v:r[5]};
    for(var m=0;m<maKeys.length;m++){
      if(r[6+m]!=null)obj[maKeys[m]]=r[6+m];
    }
    out.push(obj);
  }
  return out;
}

function loadChartData(ticker, callback){
  // Already loaded?
  if(CHART_REGISTRY[ticker]){
    callback(_expandChartRows(CHART_REGISTRY[ticker]));
    return;
  }
  // Already loading?
  if(_chartLoading[ticker]){
    _chartLoading[ticker].push(callback);
    return;
  }
  _chartLoading[ticker]=[callback];
  var url="charts/"+_safeTickerFile(ticker)+".js";
  // Try XHR first (works from file:// and http://), fall back to script injection
  var xhr=new XMLHttpRequest();
  xhr.open("GET",url,true);
  xhr.onreadystatechange=function(){
    if(xhr.readyState!==4)return;
    var cbs=_chartLoading[ticker]||[];
    delete _chartLoading[ticker];
    if(xhr.status===200||(xhr.status===0&&xhr.responseText)){
      try{eval(xhr.responseText)}catch(e){}
    }
    var data=CHART_REGISTRY[ticker]?_expandChartRows(CHART_REGISTRY[ticker]):null;
    for(var i=0;i<cbs.length;i++)cbs[i](data);
  };
  try{xhr.send()}catch(e){
    // XHR blocked — fall back to script injection (works from http://)
    delete _chartLoading[ticker];
    _chartLoading[ticker]=[callback];
    var s=document.createElement("script");
    s.src=url;
    s.onload=function(){
      var cbs2=_chartLoading[ticker]||[];
      delete _chartLoading[ticker];
      var data2=CHART_REGISTRY[ticker]?_expandChartRows(CHART_REGISTRY[ticker]):null;
      for(var i=0;i<cbs2.length;i++)cbs2[i](data2);
    };
    s.onerror=function(){
      var cbs2=_chartLoading[ticker]||[];
      delete _chartLoading[ticker];
      for(var i=0;i<cbs2.length;i++)cbs2[i](null);
    };
    document.head.appendChild(s);
  }
}
// === END LAZY CHART LOADER ===

function drawMasterChart(ticker){
  var canvas=document.getElementById("chart-canvas");
  if(!canvas)return;
  // Use lazy-loaded registry data, fall back to legacy CHART_DATA for compatibility
  var chartAll=null;
  if(CHART_REGISTRY[ticker]){
    chartAll=_expandChartRows(CHART_REGISTRY[ticker]);
  }else if(typeof CHART_DATA!=="undefined"&&CHART_DATA[ticker]){
    chartAll=CHART_DATA[ticker];
  }
  if(!chartAll||chartAll.length===0){
    // Try lazy-loading — show loading message, then redraw on completion
    document.getElementById("chart-container").innerHTML='<div style="text-align:center;padding:40px;color:var(--text-dim)">Loading chart data for '+ticker+'...</div>';
    loadChartData(ticker,function(data){
      if(data&&data.length>0){drawMasterChart(ticker)}
      else{document.getElementById("chart-container").innerHTML='<div style="text-align:center;padding:40px;color:var(--text-dim)">No chart data for '+ticker+'</div>'}
    });
    return;
  }
  var vis=chartVis;
  var chart=getChartSlice(chartAll,chartZoom);
  var fullChart=chartAll;
  // FIX-S4-CHART-V3: Use canvas.getBoundingClientRect for true rendered size
  var dpr=window.devicePixelRatio||1;
  var rect=canvas.getBoundingClientRect();
  var W=Math.round(rect.width);
  var H=Math.max(400,Math.round(window.innerHeight-rect.top-20));
  canvas.style.height=H+"px";
  // Internal resolution = CSS size * DPI
  canvas.width=W*dpr;
  canvas.height=H*dpr;
  var ctx=canvas.getContext("2d");
  ctx.scale(dpr,dpr);
  var pad={t:22,r:68,b:62,l:78};
  var plotW=W-pad.l-pad.r;
  var plotH=H-pad.t-pad.b;
  var n=chart.length;
  var barW=Math.max(4,plotW/n);
  var candleW=Math.max(3,barW*0.78);

  var monthFull=["JANUARY","FEBRUARY","MARCH","APRIL","MAY","JUNE","JULY","AUGUST","SEPTEMBER","OCTOBER","NOVEMBER","DECEMBER"];
  var monthShort=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  var dayNames=["Su","Mo","Tu","We","Th","Fr","Sa"];
  var dates=[];
  var i;for(i=0;i<chart.length;i++)dates.push(new Date(chart[i].d+"T00:00:00"));

  // Price range
  var allVals=[];var j,p;
  var maPeriods=[5,10,20,50,100,150,200];
  for(j=0;j<chart.length;j++){
    allVals.push(chart[j].h);allVals.push(chart[j].l);
    for(p=0;p<maPeriods.length;p++){var mk="ma"+maPeriods[p];if(chart[j][mk])allVals.push(chart[j][mk])}
  }
  var priceMin=Math.min.apply(null,allVals)*0.98;
  var priceMax=Math.max.apply(null,allVals)*1.02;
  var priceRange=priceMax-priceMin||1;

  // Volume
  var vols=[];for(j=0;j<chart.length;j++)vols.push(chart[j].v);
  var volMax=Math.max.apply(null,vols)||1;
  var volZoneH=plotH*0.50;

  // Volume MAs (20D + 50D)
  var fullVols=[];for(j=0;j<fullChart.length;j++)fullVols.push(fullChart[j].v);
  var visStart=fullChart.length-n;
  var volMA20=[],volMA50=[];
  for(j=0;j<n;j++){
    var ai=visStart+j;
    var s20=Math.max(0,ai-19);var sl20=fullVols.slice(s20,ai+1);
    volMA20.push(sl20.reduce(function(a,b){return a+b},0)/sl20.length);
    var s50=Math.max(0,ai-49);var sl50=fullVols.slice(s50,ai+1);
    volMA50.push(sl50.reduce(function(a,b){return a+b},0)/sl50.length);
  }
  var avgVol50=volMA50.length>0?volMA50[volMA50.length-1]:volMax*0.5;

  // OBV
  var obv=[0];
  for(j=1;j<chart.length;j++){
    if(chart[j].c>chart[j-1].c)obv.push(obv[j-1]+chart[j].v);
    else if(chart[j].c<chart[j-1].c)obv.push(obv[j-1]-chart[j].v);
    else obv.push(obv[j-1]);
  }
  var obvMin=Math.min.apply(null,obv);var obvMax=Math.max.apply(null,obv);var obvRange=obvMax-obvMin||1;

  // Coordinate functions
  function priceY(v){return pad.t+plotH*(1-(v-priceMin)/priceRange)}
  function volY(v){return pad.t+plotH-(v/volMax)*volZoneH}
  function volMALineY(v){return pad.t+plotH-(v/volMax)*volZoneH}
  var obvZoneTop=pad.t+plotH*0.75;var obvZoneBot=pad.t+plotH;var obvZoneH2=obvZoneBot-obvZoneTop;
  function obvY(v){return obvZoneBot-((v-obvMin)/obvRange)*obvZoneH2}
  function xPos(i){return pad.l+i*barW+barW/2}

  // Light theme colours
  var bgCol="#ffffff";var gridCol="rgba(180,190,200,0.6)";var gridColMonth="rgba(140,150,160,0.7)";var gridColWeek="rgba(200,210,220,0.5)";
  var textCol="#4a5568";var textColBright="#1f2328";
  var candleUpStroke="#26a641";var candleDnFill="#da3633";var candleDnStroke="#da3633";
  var maColors={5:"#8b0000",10:"#e88a9a",20:"#e74c3c",50:"#ff8c00",100:"#2ca02c",150:"#1a5276",200:"#4a3d9e"};
  var maWidths={200:5,150:3,100:2.5,50:2.2,20:1.8,10:1.5,5:1.5};

  // Clear
  ctx.fillStyle=bgCol;ctx.fillRect(0,0,W,H);

  // Price grid
  var gridCount=H>500?10:6;
  for(var g=0;g<=gridCount;g++){
    var gy=pad.t+plotH*g/gridCount;
    ctx.strokeStyle=gridCol;ctx.lineWidth=0.8;
    ctx.beginPath();ctx.moveTo(pad.l,gy);ctx.lineTo(W-pad.r,gy);ctx.stroke();
    var gv=priceMax-(priceRange*g/gridCount);
    ctx.fillStyle=textCol;ctx.font="13px monospace";ctx.textAlign="left";
    ctx.fillText(gv.toFixed(gv<10?2:gv<100?1:0),W-pad.r+6,gy+4);
  }

  // Monthly + weekly gridlines
  var lastMonth2=-1;
  for(j=0;j<dates.length;j++){
    var x=xPos(j);var m=dates[j].getMonth();var dow=dates[j].getDay();
    if(m!==lastMonth2&&j>0){ctx.strokeStyle=gridColMonth;ctx.lineWidth=1.2;ctx.beginPath();ctx.moveTo(x,pad.t);ctx.lineTo(x,pad.t+plotH+52);ctx.stroke()}
    lastMonth2=m;
    if(dow===1&&j>0){ctx.strokeStyle=gridColWeek;ctx.lineWidth=0.6;ctx.beginPath();ctx.moveTo(x,pad.t);ctx.lineTo(x,pad.t+plotH+20);ctx.stroke()}
  }

  // Volume axis
  function niceVolMax(v){if(v<=0)return 1;var mag=Math.pow(10,Math.floor(Math.log10(v)));var lead=v/mag;var nice;if(lead<=1)nice=1;else if(lead<=2)nice=2;else if(lead<=3)nice=3;else if(lead<=5)nice=5;else nice=10;return nice*mag}
  var volTickMax=niceVolMax(volMax);
  ctx.fillStyle=textCol;ctx.font="12px monospace";ctx.textAlign="right";
  for(var vg=0;vg<=3;vg++){var vVal=volTickMax*vg/3;var vy=volY(vVal);ctx.fillText(fmtVol(vVal),pad.l-8,vy+4)}
  ctx.save();ctx.translate(14,pad.t+plotH-volZoneH/2);ctx.rotate(-Math.PI/2);
  ctx.fillStyle=textCol;ctx.font="12px sans-serif";ctx.textAlign="center";ctx.fillText("Volume",0,0);ctx.restore();

  // Volume bars — 4-colour (up/down x high/low vol)
  if(vis.vol){for(j=0;j<chart.length;j++){
    var vx=xPos(j)-candleW/2;var bh=(chart[j].v/volMax)*volZoneH;
    var upDay=j>0?chart[j].c>=chart[j-1].c:true;var highVol=chart[j].v>=avgVol50;
    if(upDay&&highVol)ctx.fillStyle="rgba(63,185,80,0.50)";
    else if(upDay)ctx.fillStyle="rgba(63,185,80,0.20)";
    else if(highVol)ctx.fillStyle="rgba(248,81,73,0.50)";
    else ctx.fillStyle="rgba(248,81,73,0.20)";
    ctx.fillRect(vx,pad.t+plotH-bh,candleW,bh);
  }}

  // Volume % labels inside bars (when bars wide enough)
  if(barW>16&&vis.vol){ctx.textAlign="center";
    for(j=0;j<chart.length;j++){var x2=xPos(j);var barBottom=pad.t+plotH;
      var pct50v=volMA50[j]>0?Math.round((chart[j].v/volMA50[j]-1)*100):0;
      var pct20v=volMA20[j]>0?Math.round((chart[j].v/volMA20[j]-1)*100):0;
      ctx.fillStyle="#9a6700";ctx.font="9px monospace";ctx.fillText((pct50v>=0?"+":"")+pct50v+"%",x2,barBottom-20);
      ctx.fillStyle="#0969da";ctx.fillText((pct20v>=0?"+":"")+pct20v+"%",x2,barBottom-10);
    }
  }

  // 50D volume MA line
  if(vis.vol50){ctx.strokeStyle="#9a6700";ctx.lineWidth=1.5;ctx.beginPath();
    for(j=0;j<volMA50.length;j++){var vx2=xPos(j),vy2=volMALineY(volMA50[j]);if(j===0)ctx.moveTo(vx2,vy2);else ctx.lineTo(vx2,vy2)}ctx.stroke()}
  // 20D volume MA line
  if(vis.vol20){ctx.strokeStyle="#0969da";ctx.lineWidth=1.5;ctx.beginPath();
    for(j=0;j<volMA20.length;j++){var vx3=xPos(j),vy3=volMALineY(volMA20[j]);if(j===0)ctx.moveTo(vx3,vy3);else ctx.lineTo(vx3,vy3)}ctx.stroke()}

  // OBV line
  if(vis.obv){ctx.strokeStyle="rgba(188,140,255,0.5)";ctx.lineWidth=1.2;ctx.beginPath();
    for(j=0;j<obv.length;j++){var ox=xPos(j),oy=obvY(obv[j]);if(j===0)ctx.moveTo(ox,oy);else ctx.lineTo(ox,oy)}ctx.stroke()}

  // Candlesticks (thicker wicks + bodies)
  for(j=0;j<chart.length;j++){
    var cx2=xPos(j);var upD=chart[j].c>=chart[j].o;
    var bTop=priceY(Math.max(chart[j].o,chart[j].c));var bBot=priceY(Math.min(chart[j].o,chart[j].c));var bH2=Math.max(1,bBot-bTop);
    ctx.strokeStyle=upD?candleUpStroke:candleDnStroke;ctx.lineWidth=1.5;
    ctx.beginPath();ctx.moveTo(cx2,priceY(chart[j].h));ctx.lineTo(cx2,priceY(chart[j].l));ctx.stroke();
    if(upD){ctx.fillStyle=bgCol;ctx.fillRect(cx2-candleW/2,bTop,candleW,bH2);ctx.strokeStyle=candleUpStroke;ctx.lineWidth=1.5;ctx.strokeRect(cx2-candleW/2,bTop,candleW,bH2)}
    else{ctx.fillStyle=candleDnFill;ctx.fillRect(cx2-candleW/2,bTop,candleW,bH2)}
  }

  // MA lines (graduated widths, 100D dashed)
  ctx.textAlign="left";
  for(p=0;p<maPeriods.length;p++){
    var per=maPeriods[p];if(!vis["ma"+per])continue;
    var mk2="ma"+per;ctx.strokeStyle=maColors[per];ctx.lineWidth=maWidths[per];
    ctx.setLineDash(per===100?[6,4]:[]);ctx.beginPath();var started=false;
    for(j=0;j<chart.length;j++){var mv=chart[j][mk2];if(mv){var mx=xPos(j),my=priceY(mv);if(!started){ctx.moveTo(mx,my);started=true}else ctx.lineTo(mx,my)}}
    ctx.stroke();ctx.setLineDash([]);
    var lastMaVal=null;for(j=chart.length-1;j>=0;j--){if(chart[j][mk2]){lastMaVal=chart[j][mk2];break}}
    if(lastMaVal!==null){var ly=priceY(lastMaVal);ctx.fillStyle=maColors[per];ctx.font="bold 12px monospace";ctx.textAlign="left";ctx.fillText(lastMaVal.toFixed(lastMaVal<100?2:1),W-pad.r+6,ly+4)}
  }

  // Current price label (bold, RHS)
  if(chart.length>0){var lastC=chart[chart.length-1].c;var lcy2=priceY(lastC);ctx.fillStyle=textColBright;ctx.font="bold 13px monospace";ctx.textAlign="left";ctx.fillText(lastC.toFixed(lastC<100?2:1),W-pad.r+6,lcy2+4)}

  // X-axis: centred month labels with overlap guard
  var monthSpans2=[];var curMS=0,curM2=dates[0]?dates[0].getMonth():-1;
  for(j=0;j<dates.length;j++){var m3=dates[j].getMonth();if(m3!==curM2){if(curM2>=0)monthSpans2.push({m:curM2,start:curMS,end:j-1});curMS=j;curM2=m3}}
  if(curM2>=0)monthSpans2.push({m:curM2,start:curMS,end:n-1});
  ctx.font="bold 12px sans-serif";ctx.fillStyle=textColBright;ctx.textAlign="center";
  var lastMR=-999;
  for(j=0;j<monthSpans2.length;j++){var sp=monthSpans2[j];var mcx=(xPos(sp.start)+xPos(sp.end))/2;var mw2=ctx.measureText(monthFull[sp.m]).width;
    if((mcx-mw2/2)>(lastMR+8)){ctx.fillText(monthFull[sp.m],mcx,pad.t+plotH+48);lastMR=mcx+mw2/2}}

  // Date labels (day-month format, spaced)
  var labelEvery=1;if(n>60)labelEvery=5;else if(n>25)labelEvery=2;
  var lastLabelX=-999;ctx.font="12px sans-serif";ctx.fillStyle=textCol;ctx.textAlign="center";
  for(j=0;j<dates.length;j++){if(j%labelEvery===0){var x3=xPos(j);if(x3-lastLabelX>34){
    var dateStr=dates[j].getDate()+"-"+monthShort[dates[j].getMonth()];ctx.fillText(dateStr,x3,pad.t+plotH+16);lastLabelX=x3}}}
}

// Clickable legend HTML with toggle
function chartLegendHTML(){
  var items=[
    {key:"ma5",label:"MA-5D",color:"#8b0000"},{key:"ma10",label:"MA-10D",color:"#e88a9a"},
    {key:"ma20",label:"MA-20D",color:"#e74c3c"},{key:"ma50",label:"MA-50D",color:"#ff8c00"},
    {key:"ma100",label:"MA-100D",color:"#2ca02c"},{key:"ma150",label:"MA-150D",color:"#1a5276"},
    {key:"ma200",label:"MA-200D",color:"#4a3d9e"},{key:"obv",label:"OBV",color:"#bc8cff"},
    {key:"vol",label:"Volume",color:"rgba(204,180,0,0.6)"},{key:"vol50",label:"Vol 50D MA",color:"#9a6700"},
    {key:"vol20",label:"Vol 20D MA",color:"#0969da"}
  ];
  var h="";
  for(var j=0;j<items.length;j++){
    var it=items[j];var on=chartVis[it.key];
    h+='<span id="legend-'+it.key+'" onclick="toggleChartLayer(\''+it.key+'\')" style="cursor:pointer;opacity:'+(on?"1":"0.3")+';display:inline-flex;align-items:center;gap:2px;padding:1px 4px;border-radius:3px;border:1px solid '+(on?"var(--border)":"transparent")+';user-select:none">';
    h+='<span style="display:inline-block;width:12px;height:2px;background:'+it.color+';border-radius:1px"></span>';
    h+='<span style="font-size:10px;font-weight:600;color:'+it.color+';text-decoration:'+(on?"none":"line-through")+'">'+it.label+'</span></span>';
  }
  return h;
}

window.openChart=function(t){
  chartTicker=t;
  var p=document.getElementById("chart-panel");
  // Default chart width: 50%
  p.style.width="50%";
  p.classList.add("open");
  document.body.classList.add("chart-open");
  document.querySelector(".main").style.marginRight="50%";
  // FIX-S4-CHARTLAYOUT: Compact layout — one row for width+zoom, smaller legend, ticker inline
  // On PB tab, enable 5D+10D MAs by default
  if(currentTab==="pb"){chartVis.ma5=true;chartVis.ma10=true}else{chartVis.ma5=false;chartVis.ma10=false}
  var cont=document.getElementById("chart-container");
  var company="";
  for(var j=0;j<D.universe.length;j++){if(D.universe[j].ticker===t){company=D.universe[j].company_name||"";break}}
  // Row 1: ticker + width toggles + zoom toggles
  var h='<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;flex-wrap:wrap">';
  h+='<span style="font-size:14px;font-weight:700;color:var(--text-bright)">'+t+'</span>';
  h+='<span style="font-size:12px;color:var(--text-dim)">'+company+'</span>';
  h+='<span style="margin-left:auto;display:flex;gap:2px">';
  var widths=[{p:25,l:"\u00bc"},{p:33,l:"\u2153"},{p:50,l:"\u00bd"},{p:100,l:"Full"}];
  for(var w2=0;w2<widths.length;w2++){
    var wAct=parseInt(p.style.width)===widths[w2].p?" active":"";
    h+='<button class="chart-width-btn'+wAct+'" onclick="setChartWidth('+widths[w2].p+')">'+widths[w2].l+'</button>';
  }
  h+='</span>';
  h+='<span style="display:flex;gap:2px">';
  var zooms=["1M","3M","6M","12M","2Y","3Y","5Y"];
  for(var z=0;z<zooms.length;z++){
    var act=zooms[z]===chartZoom?" active":"";
    h+='<button class="chart-width-btn'+act+'" onclick="setChartZoom(\''+zooms[z]+'\')">'+zooms[z]+'</button>';
  }
  h+='</span>';
  h+='<button class="close-btn" onclick="closeChart()" style="margin-left:4px">&times;</button>';
  h+='</div>';
  // Row 2: compact legend (smaller text, single row)
  h+='<div style="display:flex;flex-wrap:wrap;gap:1px;margin-bottom:4px;line-height:1.4">'+chartLegendHTML()+'</div>';
  // Canvas (fills remaining space)
  h+='<div id="chart-canvas-wrap" style="width:100%;position:relative"><canvas id="chart-canvas" style="width:100%;display:block"></canvas></div>';
  cont.innerHTML=h;
  // Pre-load chart data, then draw after CSS transition finishes (300ms)
  loadChartData(t,function(){
    setTimeout(function(){drawMasterChart(t)},350);
  });
};
window.setChartZoom=function(z){
  chartZoom=z;
  if(chartTicker)openChart(chartTicker);
};

// Key: toggle floating tooltips near column headers
var keysVisible=false;
window.openKey=function(){
  keysVisible=!keysVisible;
  var tables=document.querySelectorAll("table.data-table");
  for(var j=0;j<tables.length;j++){
    if(keysVisible)tables[j].classList.add("show-keys");
    else tables[j].classList.remove("show-keys");
  }
  var btn=document.querySelector("[onclick*='openKey']");
  if(btn){
    if(keysVisible){btn.textContent="Hide Key";btn.classList.add("active")}
    else{btn.textContent="Key";btn.classList.remove("active")}
  }
};
window.closeKey=function(){keysVisible=false;var t=document.querySelectorAll("table.data-table");for(var j=0;j<t.length;j++)t[j].classList.remove("show-keys")};

window.toggleDisplayMode=function(){var cc=document.querySelectorAll(".tab-content");for(var ci=0;ci<cc.length;ci++)cc[ci].setAttribute("data-stale","1");
  displayMode=(displayMode==="ticker")?"company":"ticker";
  var btn=document.getElementById("btn-display-mode");
  if(btn)btn.textContent=(displayMode==="ticker")?"Ticker":"Company";
  var main=document.querySelector(".main");
  if(main){
    if(displayMode==="company")main.classList.add("company-mode");
    else main.classList.remove("company-mode");
  }
  renderTab(currentTab);
};

// FIX-8: Rename "% Thr" to "%"
window.toggleValueMode=function(){var cc=document.querySelectorAll(".tab-content");for(var ci=0;ci<cc.length;ci++)cc[ci].setAttribute("data-stale","1");
  valueMode=(valueMode==="tick")?"pct":"tick";
  var btn=document.getElementById("btn-value-mode");
  if(btn){
    if(valueMode==="tick"){btn.textContent="\u2713\u2717";btn.classList.remove("active")}
    else{btn.textContent="% Distance";btn.classList.add("active")}
  }
  renderTab(currentTab);
};

// FIX-3: Ratings columns toggle
window.toggleRatings=function(){var cc=document.querySelectorAll(".tab-content");for(var ci=0;ci<cc.length;ci++)cc[ci].setAttribute("data-stale","1");
  showRatings=!showRatings;
  var btn=document.getElementById("btn-ratings");
  if(btn){
    if(showRatings){btn.classList.add("active");btn.textContent="Hide case ratings"}
    else{btn.classList.remove("active");btn.textContent="Show case ratings"}
  }
  var main=document.querySelector(".main");
  if(main){
    if(showRatings)main.classList.remove("ratings-hidden");
    else main.classList.add("ratings-hidden");
  }
};

// FIX-S4-JUMPTO: Find element within active tab to avoid duplicate ID conflicts
window.scrollToSection=function(id){
  var tabEl=document.getElementById("tab-"+currentTab);
  var el=tabEl?tabEl.querySelector("#"+id):document.getElementById(id);
  if(!el)el=document.getElementById(id);
  if(el)el.scrollIntoView({behavior:"smooth",block:"start"});
};

window.toggleGroup=function(grp){
  if(activeGroups[grp]){delete activeGroups[grp]}else{activeGroups[grp]=true}
  renderTab(currentTab);
};

function _sigRank(v){return v==="pass"?3:v==="amber"?2:v==="fail"?1:0}
function sortData(data,col,dir){
  return data.slice().sort(function(a,b){
    var av=gnv(a,col),bv=gnv(b,col);
    var an=av===null||av===undefined,bn=bv===null||bv===undefined;
    if(an&&bn)return 0;if(an)return 1;if(bn)return-1;
    // Sort pass/amber/fail signals numerically
    if(av==="pass"||av==="amber"||av==="fail"||bv==="pass"||bv==="amber"||bv==="fail"){av=_sigRank(av);bv=_sigRank(bv);return dir==="asc"?av-bv:bv-av}
    // Sort stage badges: Capital > Late > Early > None
    var stgMap={"Capital":4,"Late":3,"Early":2};if(stgMap[av]||stgMap[bv]){av=stgMap[av]||0;bv=stgMap[bv]||0;return dir==="asc"?av-bv:bv-av}
    if(typeof av==="string")return dir==="asc"?av.localeCompare(bv):bv.localeCompare(av);
    if(typeof av==="boolean"){av=av?1:0;bv=bv?1:0}
    return dir==="asc"?av-bv:bv-av;
  });
}
function gnv(o,p){var k=p.split(".");var v=o;for(var j=0;j<k.length;j++){if(v==null)return null;v=v[k[j]]}return v}
window.handleSort=function(c){if(currentSort.col===c)currentSort.dir=currentSort.dir==="asc"?"desc":"asc";else{currentSort.col=c;currentSort.dir="desc"}renderTab(currentTab)};

function tick(v){return v?'<span class="tick">&#10003;</span>':'<span class="cross">&#10007;</span>'}
function badge(s){if(!s)return'<span class="badge badge-fail">&mdash;</span>';if(s==="Capital")return'<span class="badge badge-capital">Capital</span>';if(s==="Late")return'<span class="badge badge-late">Late</span>';if(s==="Early")return'<span class="badge badge-early">Early</span>';return'<span class="badge badge-fail">'+s+'</span>'}
function scorePips(s,m){var h='<div class="score-bar">';for(var j=0;j<m;j++)h+='<div class="pip '+(j<s?'pip-on':'pip-off')+'"></div>';return h+'</div>'}
// Score pips mapped to individual test results (each pip = one test)
function testPips(tests){var h='<div class="score-bar">';for(var j=0;j<tests.length;j++)h+='<div class="pip '+(tests[j]?'pip-on':'pip-off')+'"></div>';return h+'</div>'}
function signalBar(sigs){var h='<div class="signal-bar">';for(var j=0;j<sigs.length;j++){var c=sigs[j]==="pass"?"seg-pass":sigs[j]==="amber"?"seg-amber":"seg-fail";h+='<div class="seg '+c+'"></div>'}return h+'</div>'}

function addCommas(s){var p=s.split(".");var i=p[0];var d=p.length>1?"."+p[1]:"";var r="";var c=0;for(var j=i.length-1;j>=0;j--){if(c>0&&c%3===0)r=","+r;r=i.charAt(j)+r;c++}return r+d}
function fp(v){
  if(v==null)return"&mdash;";
  var n=Number(v);
  var s;
  if(n>100)s=n.toFixed(0);
  else if(n>20)s=n.toFixed(1);
  else s=n.toFixed(2);
  return addCommas(s);
}
function fpc(v){
  if(v==null)return"&mdash;";
  var n=v*100;
  if(n<0)return"("+Math.abs(n).toFixed(0)+"%)";
  return n.toFixed(0)+"%";
}
// FIX-S4-0DP: All percentages at 0 decimal places
function fpc1(v){
  if(v==null)return"&mdash;";
  var n=v*100;
  if(n<0)return"("+Math.abs(n).toFixed(0)+"%)";
  return n.toFixed(0)+"%";
}
function fpcRaw(v){
  if(v==null)return"&mdash;";
  if(v<0)return"("+Math.abs(v).toFixed(0)+"%)";
  return Number(v).toFixed(0)+"%";
}
function pf(v){if(v==null)return"&mdash;";return fpc(v)}
function nf(v,d){if(v==null)return"&mdash;";return addCommas(Number(v).toFixed(d||0))}
function sa(c){if(currentSort.col===c)return'<span class="sort-arrow">'+(currentSort.dir==="asc"?"&#9650;":"&#9660;")+'</span>';return'<span class="sort-arrow">&#9650;</span>'}
function th(l,c,cls,tip,sty){
  var s=currentSort.col===c?" sorted":"";
  var tipHtml=tip?'<span class="key-tip">'+tip+'</span>':"";
  var stAttr=sty?' style="'+sty+'"':"";
  return'<th class="'+(cls||"")+s+'"'+stAttr+' onclick="handleSort(\''+c+'\')">'+l+sa(c)+tipHtml+'</th>';
}

// FIX-16: graduated colour including grey neutral
function gradClass(v){
  if(v==null)return"neutral";
  var pct=v*100;
  if(pct>20)return"grad-green";
  if(pct>5)return"grad-lgreen";
  if(pct>-5)return"grad-neutral";
  if(pct>-20)return"grad-red";
  return"grad-dred";
}
function revClass(v){
  if(v==null)return"neutral";
  if(v>5)return"grad-green";
  if(v>1)return"grad-lgreen";
  if(v>-1)return"grad-neutral";
  if(v>-5)return"grad-red";
  return"grad-dred";
}
function pctileClass(v){
  if(v==null)return"neutral";
  if(v<20)return"grad-green";
  if(v<40)return"grad-lgreen";
  if(v<60)return"grad-neutral";
  if(v<80)return"grad-red";
  return"grad-dred";
}

// P/E range bar SVG
function buildRangeBar(lo,hi,cur){
  if(lo==null||hi==null||cur==null)return"&mdash;";
  if(hi<=lo)return"&mdash;";
  var w=100,ht=24,pad=4;
  var range=hi-lo;
  var median=(lo+hi)/2;
  var pos=pad+((cur-lo)/range)*(w-2*pad);
  if(pos<pad)pos=pad;if(pos>w-pad)pos=w-pad;
  var midX=pad+((median-lo)/range)*(w-2*pad);
  var isGreen=cur<=median;
  var markerColor=isGreen?"#2e7d32":"#c62828";
  var svg='<svg class="range-bar" width="'+w+'" height="'+ht+'" viewBox="0 0 '+w+' '+ht+'" xmlns="http://www.w3.org/2000/svg" style="vertical-align:middle">';
  svg+='<rect x="'+pad+'" y="9" width="'+(midX-pad)+'" height="6" rx="2" fill="#e8f5e9" />';
  svg+='<rect x="'+midX+'" y="9" width="'+(w-pad-midX)+'" height="6" rx="2" fill="#ffebee" />';
  svg+='<line x1="'+pad+'" y1="12" x2="'+(w-pad)+'" y2="12" stroke="#e8e3d4" stroke-width="1" />';
  svg+='<circle cx="'+pos.toFixed(1)+'" cy="12" r="4" fill="'+markerColor+'" />';
  // FIX-S4-MAMAP: Bigger text on range bar too
  svg+='<text x="'+pad+'" y="8" font-size="9" fill="#6b6b6b" font-family="var(--font)">'+nf(lo,1)+'</text>';
  svg+='<text x="'+(w-pad)+'" y="8" font-size="9" fill="#6b6b6b" font-family="var(--font)" text-anchor="end">'+nf(hi,1)+'</text>';
  svg+='<text x="'+pos.toFixed(1)+'" y="22" font-size="9" fill="'+markerColor+'" font-family="var(--font)" text-anchor="middle">'+nf(cur,1)+'</text>';
  svg+='</svg>';
  return svg;
}

// MA Map sparkline for Basing Plateau
// FIX-S4-MARANGE: Renamed MA Map→MA Range. Chart-matching colours. Normalised ±20% scale.
function buildMAMap(price,ma200,ma150,ma50){
  if(price==null)return"&mdash;";
  // Colours match the chart: Price=black, 50D=orange, 150D=navy, 200D=purple
  var vals=[],labels=[],colors=[],fmtVals=[];
  if(price!=null){vals.push(price);labels.push("P");colors.push("#1f2328");fmtVals.push(fp(price))}
  if(ma200!=null){vals.push(ma200);labels.push("200D");colors.push("#4a3d9e");fmtVals.push(fp(ma200))}
  if(ma150!=null){vals.push(ma150);labels.push("150D");colors.push("#1a5276");fmtVals.push(fp(ma150))}
  if(ma50!=null){vals.push(ma50);labels.push("50D");colors.push("#ff8c00");fmtVals.push(fp(ma50))}
  if(vals.length<2)return"&mdash;";
  // Normalised scale: ±20% around the 200D MA (or average if no 200D)
  var anchor=ma200||ma150||price;
  var scaleMin=anchor*0.80;
  var scaleMax=anchor*1.20;
  var range=scaleMax-scaleMin;if(range===0)range=1;
  var w=220,ht=42,pad=10;
  var mid=20;
  var svg='<svg width="'+w+'" height="'+ht+'" viewBox="0 0 '+w+' '+ht+'" xmlns="http://www.w3.org/2000/svg" style="vertical-align:middle">';
  svg+='<line x1="'+pad+'" y1="'+mid+'" x2="'+(w-pad)+'" y2="'+mid+'" stroke="#d4d0c8" stroke-width="1" />';
  var j;
  for(j=0;j<vals.length;j++){
    var x=pad+((vals[j]-scaleMin)/range)*(w-2*pad);
    x=Math.max(pad,Math.min(w-pad,x));
    svg+='<circle cx="'+x.toFixed(1)+'" cy="'+mid+'" r="4" fill="'+colors[j]+'" />';
    svg+='<text x="'+x.toFixed(1)+'" y="'+(mid-8)+'" font-size="10" fill="'+colors[j]+'" font-family="var(--font)" text-anchor="middle" font-weight="600">'+labels[j]+'</text>';
    svg+='<text x="'+x.toFixed(1)+'" y="'+(mid+14)+'" font-size="9" fill="'+colors[j]+'" font-family="var(--font)" text-anchor="middle">'+fmtVals[j]+'</text>';
  }
  svg+='</svg>';
  return svg;
}

// FIX-12: testCell used on ALL tabs with test columns
// FIX-S4-TESTCELL: If no % value available, keep showing tick/cross even in % mode
function testCell(pass,pctVal,cls){
  if(valueMode==="pct"&&pctVal!=null){
    var gc=gradClass(pctVal);
    return'<td class="'+cls+' col-num '+gc+'">'+fpc1(pctVal)+'</td>';
  }
  return'<td class="'+cls+'">'+tick(pass)+'</td>';
}

// UTR: format pct with 0dp, (X)% for negatives, colour-coded
function utrPct(v){
  if(v==null)return'<span class="neutral">&mdash;</span>';
  var n=Number(v);
  var txt=n<0?"("+Math.abs(n).toFixed(0)+"%)":n.toFixed(0)+"%";
  var gc=n<=-15?"grad-dred":n<=-5?"grad-red":n>=-2?"grad-lgreen":n<=5?"grad-neutral":"grad-green";
  return'<span class="'+gc+'">'+txt+'</span>';
}
// UTR: format MA distance with 0dp, (X)% for negatives, colour-coded
function utrMaDist(v){
  if(v==null)return'<span class="neutral">&mdash;</span>';
  var n=Number(v);
  var txt=n<0?"("+Math.abs(n).toFixed(0)+"%)":n.toFixed(0)+"%";
  // Closer to 0 = better (near MA). Negative = broken below
  var gc=n<-3?"grad-dred":n<0?"grad-red":n<=2?"grad-green":n<=5?"grad-lgreen":"grad-neutral";
  return'<span class="'+gc+'">'+txt+'</span>';
}
// UTR: colour-code Test MA cell
function utrTestMa(ma){
  if(!ma)return"&mdash;";
  if(ma==="50D")return'<span class="ma-50d">50D</span>';
  if(ma==="100D")return'<span class="ma-100d">100D</span>';
  if(ma==="150D")return'<span class="ma-150d">150D</span>';
  if(ma==="200D")return'<span class="ma-200d">200D</span>';
  return ma;
}
// UTR signal cell: shows pass/amber/fail or raw numeric value when toggled
function utrSigCell(sig,rawVal,extraCls){
  var cls="col-filter"+(extraCls?" "+extraCls:"");
  if(valueMode==="pct"&&rawVal!=null){
    return'<td class="'+cls+' col-num" style="font-size:10px">'+rawVal+'</td>';
  }
  var sc=sig==="pass"?"pass":sig==="amber"?"amber":sig==="fail"?"fail":"neutral";
  var icon=sig==="pass"?'<span class="tick">&#10003;</span>':sig==="amber"?'<span style="color:var(--amber);font-weight:700">&#9679;</span>':'<span class="cross">&#10007;</span>';
  return'<td class="'+cls+' '+sc+'">'+icon+'</td>';
}

function sumStat(l,v,c){return'<div class="summary-stat"><span class="label">'+l+'</span><span class="value'+(c?" "+c:"")+'">'+v+'</span></div>'}

// FIX-10: X / Y format helper
function xyFmt(x,y){return x+" / "+y}

// Industries + Sectors tables
// FIX-S4-TILESORT: Sort rows within a tile table when column header clicked
window.tileSortTable=function(thEl){
  var table=thEl.closest("table");
  if(!table)return;
  var idx=0;var th2=thEl;while(th2.previousElementSibling){th2=th2.previousElementSibling;idx++}
  var tbody=table.querySelector("tbody");
  if(!tbody)return;
  var rowsArr=Array.prototype.slice.call(tbody.querySelectorAll("tr"));
  var dir=thEl.getAttribute("data-sort-dir")==="asc"?"desc":"asc";
  thEl.setAttribute("data-sort-dir",dir);
  rowsArr.sort(function(a,b){
    var ca=a.children[idx],cb=b.children[idx];
    if(!ca||!cb)return 0;
    var va=ca.textContent.trim(),vb=cb.textContent.trim();
    var na=parseFloat(va.replace(/[^0-9.\-]/g,"")),nb=parseFloat(vb.replace(/[^0-9.\-]/g,""));
    if(!isNaN(na)&&!isNaN(nb))return dir==="asc"?na-nb:nb-na;
    return dir==="asc"?va.localeCompare(vb):vb.localeCompare(va);
  });
  for(var j=0;j<rowsArr.length;j++)tbody.appendChild(rowsArr[j]);
};
function buildIndSecTables(rows,groupDefs){
  var indMap={},secMap={};
  var j,k,t,ind,sec;
  for(j=0;j<CANONICAL_INDUSTRIES.length;j++){
    var ci=CANONICAL_INDUSTRIES[j];
    indMap[ci]={count:0,groups:{}};
    if(groupDefs){
      for(k=0;k<groupDefs.length;k++){
        indMap[ci].groups[groupDefs[k].key]={pass:0,total:0};
      }
    }
  }
  for(j=0;j<rows.length;j++){
    t=getTaxonomy(rows[j].ticker);
    ind=t.industry||"Unknown";sec=t.sector||"Unknown";
    if(!indMap[ind])indMap[ind]={count:0,groups:{}};
    indMap[ind].count++;
    if(!secMap[sec])secMap[sec]={count:0,industry:ind,groups:{}};
    secMap[sec].count++;
    if(groupDefs){
      for(k=0;k<groupDefs.length;k++){
        var gk=groupDefs[k].key;
        if(!indMap[ind].groups[gk])indMap[ind].groups[gk]={pass:0,total:0};
        indMap[ind].groups[gk].total++;
        if(rows[j][gk])indMap[ind].groups[gk].pass++;
        if(!secMap[sec].groups[gk])secMap[sec].groups[gk]={pass:0,total:0};
        secMap[sec].groups[gk].total++;
        if(rows[j][gk])secMap[sec].groups[gk].pass++;
      }
    }
  }
  var indKeys=Object.keys(indMap).sort();
  var secKeys=Object.keys(secMap).sort();

  // FIX-10: X / Y in industry/sector counts
  var h='<div class="ind-sec-wrap" id="section-industries">';
  h+='<div class="half-table"><div class="half-title">Industries</div>';
  h+='<div class="data-table-wrap"><table class="data-table"><thead><tr><th class="col-txt" onclick="tileSortTable(this)" style="cursor:pointer">Industry</th><th class="col-num" onclick="tileSortTable(this)" style="cursor:pointer"># Stocks</th>';
  if(groupDefs){for(k=0;k<groupDefs.length;k++)h+='<th class="col-num" onclick="tileSortTable(this)" style="cursor:pointer">'+groupDefs[k].label+'</th>'}
  h+='</tr></thead><tbody>';
  for(j=0;j<indKeys.length;j++){
    var ik=indKeys[j],iv=indMap[ik];
    var indActive=indFilter[ik]?' style="font-size:11px;background:#e8f5e9;font-weight:700"':' style="font-size:11px"';
    h+='<tr onclick="toggleIndFilter(\''+ik.replace(/'/g,"\\'")+'\')" style="cursor:pointer"><td class="col-txt"'+indActive+'>'+ik+'</td><td class="col-num" style="font-weight:600">'+iv.count+'</td>';
    if(groupDefs){
      for(k=0;k<groupDefs.length;k++){
        var gk2=groupDefs[k].key;
        var gd=iv.groups[gk2];
        var passN=gd?gd.pass:0;var totalN=gd?gd.total:0;
        var pcCls=totalN>0?(passN/totalN>0.5?"pass":passN/totalN>0.2?"amber":"fail"):"neutral";
        h+='<td class="col-num '+pcCls+'">'+(iv.count>0?xyFmt(passN,totalN):"&mdash;")+'</td>';
      }
    }
    h+='</tr>';
  }
  h+='</tbody></table></div></div>';

  h+='<div class="half-table" id="section-sectors"><div class="half-title">Sectors</div>';
  h+='<div class="data-table-wrap"><table class="data-table"><thead><tr><th class="col-txt" style="width:35%;cursor:pointer" onclick="tileSortTable(this)">Sector</th><th class="col-txt" style="width:20%;cursor:pointer" onclick="tileSortTable(this)">Industry</th><th class="col-num" style="width:30px;cursor:pointer" onclick="tileSortTable(this)">#</th>';
  if(groupDefs){for(k=0;k<groupDefs.length;k++)h+='<th class="col-num" onclick="tileSortTable(this)" style="cursor:pointer">'+groupDefs[k].label+'</th>'}
  h+='</tr></thead><tbody>';
  for(j=0;j<secKeys.length;j++){
    var sk=secKeys[j],sv=secMap[sk];
    var secActive=secFilter[sk]?' style="font-size:11px;background:#e8f5e9;font-weight:700"':' style="font-size:11px"';
    h+='<tr onclick="toggleSecFilter(\''+sk.replace(/'/g,"\\'")+'\')" style="cursor:pointer"><td class="col-txt"'+secActive+'>'+sk+'</td><td class="col-txt" style="font-size:10px;color:var(--text-dim)">'+sv.industry+'</td><td class="col-num" style="font-weight:600">'+sv.count+'</td>';
    if(groupDefs){
      for(k=0;k<groupDefs.length;k++){
        var gk3=groupDefs[k].key;
        var gd2=sv.groups[gk3];
        var passN2=gd2?gd2.pass:0;var totalN2=gd2?gd2.total:0;
        var pcCls2=totalN2>0?(passN2/totalN2>0.5?"pass":passN2/totalN2>0.2?"amber":"fail"):"neutral";
        h+='<td class="col-num '+pcCls2+'">'+xyFmt(passN2,totalN2)+'</td>';
      }
    }
    h+='</tr>';
  }
  h+='</tbody></table></div></div></div>';
  return h;
}

// Qualification group tiles — same columns as main table, filtered per group
// headersFn: function returning thead HTML (same as main table)
// rowFn: function(r) returning tr HTML (same as main table)
function buildQualTilesV2(rows,groups,totalCount,headersFn,rowFn){
  var h='<div id="section-groups">';
  for(var g=0;g<groups.length;g++){
    var gr=groups[g];
    var passed=[];
    for(var j=0;j<rows.length;j++){if(rows[j][gr.key])passed.push(rows[j])}
    h+='<div class="qual-tile" id="grp-'+gr.key+'">';
    h+='<h4 style="display:flex;gap:16px;align-items:baseline">'+gr.label+' <span style="font-size:12px;font-weight:400;color:var(--text-dim)">'+xyFmt(passed.length,totalCount)+' stocks';
    h+=' &mdash; L12M: <span class="neutral">0</span> &bull; L6M: <span class="neutral">0</span> &bull; L3M: <span class="neutral">0</span> &bull; L1M: <span class="neutral">0</span>';
    h+='</span></h4>';
    if(passed.length===0){
      h+='<p style="color:var(--text-dim);padding:8px 0">No stocks currently meet this criteria.</p>';
    } else {
      h+='<div class="data-table-wrap"><table class="data-table"><thead>'+headersFn()+'</thead><tbody>';
      for(var j2=0;j2<passed.length;j2++)h+=rowFn(passed[j2]);
      h+='</tbody></table></div>';
    }
    h+='</div>';
  }
  h+='</div>';
  return h;
}
// Legacy wrapper (fallback for tabs not yet converted)
function buildQualTiles(rows,groups,totalCount){
  return buildQualTilesV2(rows,groups,totalCount,
    function(){return'<tr>'+commonCols()+'</tr>'},
    function(r){return'<tr>'+commonTds(r)+ratingsColTds(r)+'</tr>'}
  );
}

// ORIG-17: Live portfolio tile — appears above Qualified Stocks on every tab
// Returns set of position tickers for filtering
function getPositionTickers(){
  if(!D.positions||!D.positions.investments)return{};
  var pt={};
  var invs=D.positions.investments;
  for(var j=0;j<invs.length;j++)pt[invs[j].ticker]=true;
  return pt;
}
// Filter enriched rows to positions only
function filterToPositions(rows){
  var pt=getPositionTickers();
  var out=[];
  for(var j=0;j<rows.length;j++){if(pt[rows[j].ticker])out.push(rows[j])}
  return out;
}
// FIX-S4-PORTFOLIO: Generic portfolio tile for tabs without custom portfolio rendering
function buildPortfolioTile(tabId){
  var pt=getPositionTickers();
  var allR=baseRows();
  var posRows=[];
  for(var j=0;j<allR.length;j++){if(pt[allR[j].ticker]&&passIndSecFilter(allR[j]))posRows.push(allR[j])}
  if(posRows.length===0)return"";
  var totalCount=allR.length;
  var h='<h3 class="qualified-title" id="section-portfolio">Live Portfolio ('+posRows.length+')</h3>';
  h+='<div class="data-table-wrap"><table class="data-table"><thead><tr>'+commonCols()+ratingsColHeaders()+'</tr></thead><tbody>';
  for(var j=0;j<posRows.length;j++){
    h+='<tr onclick="openChart(\''+posRows[j].ticker+'\')" style="cursor:pointer">'+commonTds(posRows[j])+ratingsColTds(posRows[j])+'</tr>';
  }
  h+='</tbody></table></div>';
  return h;
}

// FIX-7: Common columns - 52W High and 52W Low consolidated into single columns each
// FIX-9: alignment classes
// FIX-S4-COLW-V4: table-layout:auto — browser sizes columns by content
function commonCols(){
  var tkrW=displayMode==="company"?"width:180px":"width:120px";
  return th("Ticker","_display_name","col-txt col-identity","Stock ticker or company name (toggle in header)",tkrW)
    +th("Sector","_tax_sector","col-txt col-identity","Industry sector classification","width:200px")
    +th("Price","price","col-num col-price","Current stock price","width:52px")
    +th("52WH","high_52w","col-num col-price","52-week high (toggle to %)","width:52px")
    +th("52WL","low_52w","col-num col-price","52-week low (toggle to %)","width:52px")
    +th("20D","_ma20","col-num col-price","20-day moving average","width:46px")
    +th("50D","_ma50","col-num col-price","50-day moving average","width:46px")
    +th("150D","_ma150","col-num col-price","150-day moving average","width:46px")
    +th("200D","_ma200","col-num col-price","200-day moving average","width:46px")
    +th("RS","rs_pct","col-num col-rs","Relative Strength percentile 0-100 (IBD composite)","width:32px");
}
// UTR-specific common cols: Ticker+Sector always visible, rest have col-input class
function utrCommonCols(){
  var tkrW=displayMode==="company"?"width:180px":"width:120px";
  return th("Ticker","_display_name","col-txt col-identity","Stock ticker or company name",tkrW)
    +th("Sector","_tax_sector","col-txt col-identity col-input","Sector","width:200px")
    +th("Price","price","col-num col-price col-input","Price","width:52px")
    +th("52WH","high_52w","col-num col-price col-input","52-week high","width:52px")
    +th("52WL","low_52w","col-num col-price col-input","52-week low","width:52px")
    +th("20D","_ma20","col-num col-price col-input","20-day MA","width:46px")
    +th("50D","_ma50","col-num col-price col-input","50-day MA","width:46px")
    +th("150D","_ma150","col-num col-price col-input","150-day MA","width:46px")
    +th("200D","_ma200","col-num col-price col-input","200-day MA","width:46px")
    +th("RS","rs_pct","col-num col-rs col-input","RS percentile","width:32px");
}
function utrCommonTds(r){
  var tax=getTaxonomy(r.ticker);
  var dn=(displayMode==="company")?(r.company||r.ticker):r.ticker;
  var rc=r.rs_pct>=70?"var(--green)":r.rs_pct>=40?"var(--text)":"var(--red)";
  var h52val,l52val;
  if(valueMode==="pct"){
    h52val='<td class="col-num col-price col-input '+(r.pct_52wh!=null?gradClass(-r.pct_52wh):"")+'">'+fpc(r.pct_52wh)+'</td>';
    l52val='<td class="col-num col-price col-input '+(r.pct_52wl!=null?gradClass(r.pct_52wl):"")+'">'+fpc(r.pct_52wl)+'</td>';
  } else {
    h52val='<td class="col-num col-price col-input">'+fp(r.high_52w)+'</td>';
    l52val='<td class="col-num col-price col-input">'+fp(r.low_52w)+'</td>';
  }
  var ma20=r.mas?r.mas["20D"]:null;
  var ma50=r.mas?r.mas["50D"]:null;
  var ma150=r.mas?r.mas["150D"]:null;
  var ma200=r.mas?r.mas["200D"]:null;
  return'<td class="col-txt col-identity">'+dn+'</td>'
    +'<td class="col-txt col-identity col-input" title="'+tax.sector+'">'+tax.sector+'</td>'
    +'<td class="col-num col-price col-input">'+fp(r.price)+'</td>'
    +h52val+l52val
    +'<td class="col-num col-price col-input">'+(ma20!=null?fp(ma20):"&mdash;")+'</td>'
    +'<td class="col-num col-price col-input">'+(ma50!=null?fp(ma50):"&mdash;")+'</td>'
    +'<td class="col-num col-price col-input">'+(ma150!=null?fp(ma150):"&mdash;")+'</td>'
    +'<td class="col-num col-price col-input">'+(ma200!=null?fp(ma200):"&mdash;")+'</td>'
    +'<td class="col-num col-rs col-input" style="color:'+rc+'">'+nf(r.rs_pct)+'</td>';
}
function commonTds(r){
  var tax=getTaxonomy(r.ticker);
  var dn=(displayMode==="company")?(r.company||r.ticker):r.ticker;
  var rc=r.rs_pct>=70?"var(--green)":r.rs_pct>=40?"var(--text)":"var(--red)";
  // FIX-7: 52W High shows price in tick mode, % in pct mode. Same for Low.
  var h52val,l52val;
  if(valueMode==="pct"){
    h52val='<td class="col-num col-price '+(r.pct_52wh!=null?gradClass(-r.pct_52wh):"")+'">'+fpc(r.pct_52wh)+'</td>';
    l52val='<td class="col-num col-price '+(r.pct_52wl!=null?gradClass(r.pct_52wl):"")+'">'+fpc(r.pct_52wl)+'</td>';
  } else {
    h52val='<td class="col-num col-price">'+fp(r.high_52w)+'</td>';
    l52val='<td class="col-num col-price">'+fp(r.low_52w)+'</td>';
  }
  var ma20=r.mas?r.mas["20D"]:null;
  var ma50=r.mas?r.mas["50D"]:null;
  var ma150=r.mas?r.mas["150D"]:null;
  var ma200=r.mas?r.mas["200D"]:null;
  // FIX-S4-INPUTPCT: In % mode, MA columns show % distance from MA
  var ma20td,ma50td,ma150td,ma200td;
  if(valueMode==="pct"){
    var p20=ma20?(r.price-ma20)/ma20:null;var p50=ma50?(r.price-ma50)/ma50:null;
    var p150=ma150?(r.price-ma150)/ma150:null;var p200=ma200?(r.price-ma200)/ma200:null;
    ma20td='<td class="col-num col-price '+(p20!=null?gradClass(p20):"")+'">'+fpc(p20)+'</td>';
    ma50td='<td class="col-num col-price '+(p50!=null?gradClass(p50):"")+'">'+fpc(p50)+'</td>';
    ma150td='<td class="col-num col-price '+(p150!=null?gradClass(p150):"")+'">'+fpc(p150)+'</td>';
    ma200td='<td class="col-num col-price '+(p200!=null?gradClass(p200):"")+'">'+fpc(p200)+'</td>';
  } else {
    ma20td='<td class="col-num col-price">'+fp(ma20)+'</td>';
    ma50td='<td class="col-num col-price">'+fp(ma50)+'</td>';
    ma150td='<td class="col-num col-price">'+fp(ma150)+'</td>';
    ma200td='<td class="col-num col-price">'+fp(ma200)+'</td>';
  }
  return'<td class="col-txt col-identity" style="font-weight:600;color:var(--text-bright);min-width:90px;white-space:nowrap">'+dn+'</td>'
    +'<td class="col-txt col-identity" style="font-size:11px;min-width:140px;white-space:nowrap">'+tax.sector+'</td>'
    +'<td class="col-num col-price">'+fp(r.price)+'</td>'
    +h52val+l52val
    +ma20td+ma50td+ma150td+ma200td
    +'<td class="col-num col-rs" style="font-weight:600;color:'+rc+'">'+(r.rs_pct!=null?r.rs_pct:"&mdash;")+'</td>';
}

// FIX-3: Ratings columns (A-F pillars, Stage, Thematic Tags) on right side
// FIX-S4-2: Stage moved to far right of ratings group (after Tags) per Richard Message 3
// FIX-S4-QUAL: A-F ratings pulled from qualitative.json (IC Ratings Dashboard memos)
function ratingBadge(rating){
  if(!rating)return'&mdash;';
  var base=rating.replace('+','').replace('-','').replace(' (upper)','').replace(' (lower)','');
  var cls='';
  if(base==='A')cls='pass';
  else if(base==='B')cls='pass';
  else if(base==='C')cls='amber';
  else if(base==='D')cls='fail';
  else if(base==='F')cls='fail';
  return'<span class="'+cls+'" style="font-weight:600">'+rating+'</span>';
}
function ratingsColHeaders(){
  return'<th class="col-ratings col-txt" title="P1: Technical Strength">P1</th>'
    +'<th class="col-ratings col-txt" title="P2: Market Paradigm">P2</th>'
    +'<th class="col-ratings col-txt" title="P3: Fundamental Change">P3</th>'
    +'<th class="col-ratings col-txt" title="P4: Building Blocks">P4</th>'
    +'<th class="col-ratings col-txt" title="P5: SS Momentum">P5</th>'
    +'<th class="col-ratings col-txt" title="P6: Valuation/Upside">P6</th>'
    +'<th class="col-ratings col-txt">Tags</th>'
    +'<th class="col-ratings col-txt">Stage</th>';
}
function ratingsColTds(r){
  var stg=r.stage||r.bp_stage||r.pb_stage||r.utr_stage||"";
  var q=D.qualitative?D.qualitative[r.ticker]:null;
  if(q){
    return'<td class="col-ratings">'+ratingBadge(q.p1)+'</td>'
      +'<td class="col-ratings">'+ratingBadge(q.p2)+'</td>'
      +'<td class="col-ratings">'+ratingBadge(q.p3)+'</td>'
      +'<td class="col-ratings">'+ratingBadge(q.p4)+'</td>'
      +'<td class="col-ratings">'+ratingBadge(q.p5)+'</td>'
      +'<td class="col-ratings">'+ratingBadge(q.p6)+'</td>'
      +'<td class="col-ratings">&mdash;</td>'
      +'<td class="col-ratings col-txt">'+badge(q.stage||stg)+'</td>';
  }
  return'<td class="col-ratings">&mdash;</td><td class="col-ratings">&mdash;</td><td class="col-ratings">&mdash;</td>'
    +'<td class="col-ratings">&mdash;</td><td class="col-ratings">&mdash;</td><td class="col-ratings">&mdash;</td>'
    +'<td class="col-ratings">&mdash;</td>'
    +'<td class="col-ratings col-txt">'+badge(stg)+'</td>';
}

function baseRows(){
  var rows=[];
  for(var j=0;j<D.prices.length;j++){
    var p=D.prices[j],f=filterMap[p.ticker];
    if(!f)continue;
    var tax=getTaxonomy(p.ticker);
    rows.push({
      ticker:p.ticker,company:p.company_name,
      _display_name:(displayMode==="company")?(p.company_name||p.ticker):p.ticker,
      _tax_industry:tax.industry,_tax_sector:tax.sector,
      sector:p.sector,industry:p.industry,
      price:p.price,price_prev:p.price_prev,
      pct_52wh:p.high_52w>0?((p.high_52w-p.price)/p.high_52w):null,
      pct_52wl:p.low_52w>0?((p.price-p.low_52w)/p.low_52w):null,
      rs_pct:p.rs_percentile,rs_sector:p.rs_vs_sector,
      _ma20:p.mas?p.mas["20D"]:null,_ma50:p.mas?p.mas["50D"]:null,
      _ma150:p.mas?p.mas["150D"]:null,_ma200:p.mas?p.mas["200D"]:null,
      mas:p.mas,high_52w:p.high_52w,low_52w:p.low_52w,
      adv_1m:p.adv_1m,adv_3m:p.adv_3m,
      adv_1m_up:p.adv_1m_up||0,adv_1m_dn:p.adv_1m_dn||0,
      adv_3m_up:p.adv_3m_up||0,adv_3m_dn:p.adv_3m_dn||0,
      f:f
    });
  }
  return rows;
}

// Build header tab controls (score filter + group toggles)
function buildHeaderControls(tabId){
  var el=document.getElementById("header-tab-controls");
  if(!el)return;
  var h="";
  if(tabId==="mm99"){
    h+='<div class="score-filter">';
    // FIX-S4-3: Score filter uses /11 (11 tests: T1-T8 + T9-T11 RS)
    var sc=[0,7,8,9,10,11];
    for(var s=0;s<sc.length;s++){
      var lb=sc[s]===0?"All":(sc[s]+"/11+");
      h+='<button class="score-btn'+(mm99MinScore===sc[s]?" active":"")+'" onclick="setMM99Score('+sc[s]+')">'+lb+'</button>';
    }
    h+='</div>';
    h+='<div class="group-toggles" style="margin-left:12px">';
    var grps=[{k:"ga",l:"Long-term"},{k:"gb",l:"Mid-term"},{k:"gc",l:"Short-term"},{k:"gd",l:"Leadership"},{k:"ge",l:"Relative Strength"}];
    for(var g=0;g<grps.length;g++){
      var act=activeGroups[grps[g].k]?" active":"";
      h+='<button class="group-toggle'+act+'" onclick="toggleGroup(\''+grps[g].k+'\')">'+grps[g].l+'</button>';
    }
    h+='</div>';
  } else if(tabId==="bp"){
    h+='<div class="group-toggles">';
    var bpGrps=[{k:"ga",l:"Loose Plateau (\u00b115%)"},{k:"gb",l:"Medium Plateau (\u00b110%)"},{k:"gc",l:"Tight Plateau (\u00b15%)"}];
    for(var g2=0;g2<bpGrps.length;g2++){
      var act2=activeGroups[bpGrps[g2].k]?" active":"";
      h+='<button class="group-toggle'+act2+'" onclick="toggleGroup(\''+bpGrps[g2].k+'\')">'+bpGrps[g2].l+'</button>';
    }
    h+='</div>';
  } else if(tabId==="pb"){
    h+='<div class="group-toggles">';
    var pbGrps=[{k:"ga",l:"A: Early (3/5 rising)"},{k:"gb",l:"B: Late (20/50D)"},{k:"gc",l:"C: Dead Cat"},{k:"gd",l:"D: PB1 Capital"},{k:"ge",l:"E: PB2 Capital"}];
    for(var g3=0;g3<pbGrps.length;g3++){
      var act3=activeGroups[pbGrps[g3].k]?" active":"";
      h+='<button class="group-toggle'+act3+'" onclick="toggleGroup(\''+pbGrps[g3].k+'\')">'+pbGrps[g3].l+'</button>';
    }
    h+='</div>';
    // FIX-S4-PBEXCL: Exclude toggles for stocks meeting other filter criteria
    h+='<span style="border-left:1px solid var(--border);height:20px;margin:0 6px"></span>';
    h+='<div class="group-toggles">';
    var exGrps=[{k:"ex_mm99",l:"Exclude MM 99"},{k:"ex_vcp",l:"Exclude VCP"},{k:"ex_utr",l:"Exclude Retest"}];
    for(var e2=0;e2<exGrps.length;e2++){
      var eAct=pbExcludes[exGrps[e2].k]?" active":"";
      h+='<button class="group-toggle'+eAct+'" style="'+(pbExcludes[exGrps[e2].k]?"background:#c62828;border-color:#c62828;color:#fff":"")+'" onclick="togglePbExclude(\''+exGrps[e2].k+'\')">'+exGrps[e2].l+'</button>';
    }
    h+='</div>';
  } else if(tabId==="utr"){
    h+='<div class="score-filter">';
    var capScores=[0,5,6,7,8];
    for(var cs=0;cs<capScores.length;cs++){
      var cLb=capScores[cs]===0?"All":(capScores[cs]+"/8+");
      h+='<button class="score-btn'+(utrMinCap===capScores[cs]?" active":"")+'" onclick="setUtrMinCap('+capScores[cs]+')">'+cLb+'</button>';
    }
    h+='</div>';
    h+='<span style="border-left:1px solid var(--border);height:20px;margin:0 6px"></span>';
    h+='<div class="group-toggles">';
    var failFilters=[{k:"L1W",l:"Failed L1W"},{k:"L1M",l:"Failed L1M"}];
    for(var ff=0;ff<failFilters.length;ff++){
      var fAct=utrFailedFilter===failFilters[ff].k?" active":"";
      h+='<button class="group-toggle'+fAct+'" style="'+(utrFailedFilter===failFilters[ff].k?"background:#c62828;border-color:#c62828;color:#fff":"")+'" onclick="setUtrFailedFilter(\''+failFilters[ff].k+'\')">'+failFilters[ff].l+'</button>';
    }
    h+='</div>';
    h+='<span style="border-left:1px solid var(--border);height:20px;margin:0 6px"></span>';
    h+='<button class="group-toggle'+(utrShowInputs?" active":"")+'" onclick="toggleUtrInputs()">'+(utrShowInputs?"Hide Inputs":"Show Inputs")+'</button>';
  }
  el.innerHTML=h;

  // Populate per-group anchor links
  var gl=document.getElementById("group-links");
  if(gl){
    var gh="";
    var GROUP_LINKS={
      mm99:[{k:"ga",l:"Long-term"},{k:"gb",l:"Mid-term"},{k:"gc",l:"Short-term"},{k:"gd",l:"Leadership"},{k:"ge",l:"Rel. Strength"}],
      bp:[{k:"ga",l:"Loose"},{k:"gb",l:"Medium"},{k:"gc",l:"Tight"}],
      utr:[{k:"utr_early",l:"Early+"},{k:"utr_late",l:"Late+"},{k:"utr_capital",l:"Capital"}],
      pb:[{k:"ga",l:"Early"},{k:"gb",l:"Late"},{k:"gc",l:"Dead Cat"},{k:"gd",l:"PB1"},{k:"ge",l:"PB2"}]
    };
    var links=GROUP_LINKS[tabId];
    if(links){
      for(var gl2=0;gl2<links.length;gl2++){
        gh+='<a class="anchor-link" onclick="scrollToSection(\'grp-'+links[gl2].k+'\')">'+links[gl2].l+'</a>';
      }
    }
    gl.innerHTML=gh;
  }
}

// ================================================================
// MM99 TAB
// ================================================================
function renderMM99(){
  buildHeaderControls("mm99");
  var allRows=baseRows();
  // FIX-7: Enrich ALL rows with MM99 test data first (for Live Portfolio tile)
  for(var j=0;j<allRows.length;j++){
    var r=allRows[j],mm=r.f.mm99;
    if(!mm||!mm.group_a){r.mm99_score=0;r.stage="";r.t1=false;r.t2=false;r.t3=false;r.t4=false;r.t5=false;r.t6=false;r.t7=false;r.t8=false;r.t9=false;r.t10=false;r.t11=false;r.ga=false;r.gb=false;r.gc=false;r.gd=false;r.ge=false;r.pb_stage=r.f.probing_bet?r.f.probing_bet.stage:"";r.bp_stage=r.f.basing_plateau?r.f.basing_plateau.stage:"";r.t1_pct=null;r.t2_pct=null;r.t3_pct=null;r.t4_pct=null;r.t5_pct=null;r.t6_pct=null;r.t7_pct=null;r.t8_pct=null;r.ma200_months=null;continue;}
    r.mm99_score=mm.score_11;r.stage=mm.stage;
    r.t1=mm.group_a.tests.T1;r.t2=mm.group_a.tests.T2;r.t3=mm.group_b.tests.T3;r.t4=mm.group_b.tests.T4;
    r.t5=mm.group_c.tests.T5;r.t6=mm.group_c.tests.T6;r.t7=mm.group_d.tests.T7;r.t8=mm.group_d.tests.T8;
    r.t9=mm.group_e.tests.T9;r.t10=mm.group_e.tests.T10;r.t11=mm.group_e.tests.T11;
    r.ga=mm.group_a.pass;r.gb=mm.group_b.pass;r.gc=mm.group_c.pass;r.gd=mm.group_d.pass;r.ge=mm.group_e.pass;
    r.pb_stage=r.f.probing_bet?r.f.probing_bet.stage:"";r.bp_stage=r.f.basing_plateau?r.f.basing_plateau.stage:"";

    var m200=r.mas?r.mas["200D"]:null,m150=r.mas?r.mas["150D"]:null,m50=r.mas?r.mas["50D"]:null;
    r.t1_pct=m200?(r.price-m200)/m200:null;
    r.ma200_months=mm.group_a.ma200_months_rising!=null?mm.group_a.ma200_months_rising:null;
    r.t2_pct=null;
    r.t3_pct=m150?(r.price-m150)/m150:null;
    r.t4_pct=(m150&&m200)?(m150-m200)/m200:null;
    r.t5_pct=(m50&&m150)?(m50-m150)/m150:null;
    r.t6_pct=m50?(r.price-m50)/m50:null;
    r.t7_pct=r.low_52w?(r.price-r.low_52w)/r.low_52w:null;
    r.t8_pct=r.high_52w?(r.high_52w-r.price)/r.high_52w:null;
    // BUG-3-FIX: RS pct uses excess return (already decimal, e.g. 0.15 = 15%)
    var rse=mm.group_e;
    r.t9_pct=rse.rs_excess_sector!=null?rse.rs_excess_sector:null;
    r.t10_pct=rse.rs_excess_industry!=null?rse.rs_excess_industry:null;
    r.t11_pct=rse.rs_excess_market!=null?rse.rs_excess_market:null;
  }
  // FIX-7: Now filter into rows by score + group toggles (AFTER enrichment)
  var rows=[];
  for(var j=0;j<allRows.length;j++){
    var r=allRows[j];
    if(r.mm99_score<mm99MinScore)continue;
    var skip=false;
    if(activeGroups.ga&&!r.ga)skip=true;
    if(activeGroups.gb&&!r.gb)skip=true;
    if(activeGroups.gc&&!r.gc)skip=true;
    if(activeGroups.gd&&!r.gd)skip=true;
    if(activeGroups.ge&&!r.ge)skip=true;
    if(skip)continue;
    rows.push(r);
  }
  rows=sortData(rows,currentSort.col,currentSort.dir);
  var totalCount=allRows.length;
  // FIX-S4-3: Summary stats use /11 scoring
  var p11=0,p9=0,cap=0,lat=0,ear=0;
  for(var j=0;j<rows.length;j++){if(rows[j].mm99_score>=11)p11++;if(rows[j].mm99_score>=9)p9++;if(rows[j].stage==="Capital")cap++;if(rows[j].stage==="Late")lat++;if(rows[j].stage==="Early")ear++}

  var h='<div class="summary-tile" id="section-summary"><h3>MM 99 &mdash; Minervini Technical Screen (11 tests)</h3><div class="summary-stats">'
    +sumStat("11/11",xyFmt(p11,rows.length),"green")+sumStat("9/11+",xyFmt(p9,rows.length),"amber")+sumStat("Capital",xyFmt(cap,rows.length),"green")+sumStat("Late",xyFmt(lat,rows.length),"amber")+sumStat("Early",ear)+sumStat("Shown",xyFmt(rows.length,totalCount))
    +'</div></div>';

  var groupDefs=[
    {key:"ga",label:"Long-term"},{key:"gb",label:"Mid-term"},{key:"gc",label:"Short-term"},
    {key:"gd",label:"Leadership"},{key:"ge",label:"Relative Strength"}
  ];
  h+=buildIndSecTables(applyIndSecFilter(allRows),groupDefs);

  // FIX-2: Qualified Stocks title
  // MM99 table rendering function (reused for portfolio tile and main table)
  function mm99Headers(){
    var hdr='<tr class="group-header-row">';
    // FIX-S4-MM99: RS in Inputs group, PB+BP as Setups
    hdr+='<th colspan="2"></th><th colspan="8" style="background:rgba(100,100,100,0.06)">Inputs</th><th></th>';
    hdr+='<th colspan="2" style="background:rgba(200,50,50,0.08)">Long-term</th>';
    hdr+='<th colspan="2" style="background:rgba(200,150,0,0.08)">Mid-term</th>';
    hdr+='<th colspan="2" style="background:rgba(50,150,50,0.08)">Short-term</th>';
    hdr+='<th colspan="2" style="background:rgba(50,100,200,0.08)">52W Leadership</th>';
    hdr+='<th colspan="3" style="background:rgba(120,80,200,0.08)">Relative Strength</th>';
    hdr+='<th colspan="2" style="background:rgba(180,100,50,0.08)">Setups</th>';
    hdr+=ratingsColHeaders().length>0?'<th colspan="8" class="col-ratings">Ratings</th>':"";
    hdr+='</tr><tr class="col-header-row">';
    hdr+=commonCols()+th("Score","mm99_score","col-num col-filter","Minervini 11-test score (8 technical + 3 RS)")
      +th("P>200D","t1_pct","col-filter grp-lt-first","Price above 200-day MA")+th("200D Up","ma200_months","col-filter grp-lt-last","200-day MA months rising (of 12)")
      +th("P>150D","t3_pct","col-filter grp-mt-first","Price above 150-day MA")+th("150>200","t4_pct","col-filter grp-mt-last","150-day MA above 200-day MA")
      +th("50>150","t5_pct","col-filter grp-st-first","50-day MA above 150-day MA")+th("P>50D","t6_pct","col-filter grp-st-last","Price above 50-day MA")
      +th("P>20%L","t7_pct","col-filter grp-lead-first","Price at least 20% above 52-week low")+th("P<25%H","t8_pct","col-filter grp-lead-last","Price within 25% of 52-week high")
      +th("Sector","t9_pct","col-filter grp-rs-first","Relative strength vs sector")+th("Industry","t10_pct","col-filter","Relative strength vs industry")+th("Market","t11_pct","col-filter grp-rs-last","Relative strength vs market")
      +th("Probing","pb_stage","col-txt col-ref","Probing Bet filter stage")+th("Basing","bp_stage","col-txt col-ref","Basing Plateau filter stage")
      +ratingsColHeaders();
    hdr+='</tr>';
    return hdr;
  }
  function mm99Row(r){
    return'<tr onclick="openChart(\''+r.ticker+'\')" style="cursor:pointer">'+commonTds(r)
      +'<td class="col-num col-filter">'+testPips([r.t1,r.t2,r.t3,r.t4,r.t5,r.t6,r.t7,r.t8,r.t9,r.t10,r.t11])+' <span style="margin-left:4px;font-weight:600">'+r.mm99_score+'/11</span></td>'
      +testCell(r.t1,r.t1_pct,"col-filter grp-lt-first")+'<td class="col-num col-filter grp-lt-last '+(r.ma200_months>=6?"pass":r.ma200_months>=3?"amber":r.ma200_months>=1?"":"fail")+'" style="font-weight:600">'+(r.ma200_months!=null?r.ma200_months+"/12":"&mdash;")+'</td>'
      +testCell(r.t3,r.t3_pct,"col-filter grp-mt-first")+testCell(r.t4,r.t4_pct,"col-filter grp-mt-last")
      +testCell(r.t5,r.t5_pct,"col-filter grp-st-first")+testCell(r.t6,r.t6_pct,"col-filter grp-st-last")
      +testCell(r.t7,r.t7_pct,"col-filter grp-lead-first")+testCell(r.t8,r.t8_pct,"col-filter grp-lead-last")
      +testCell(r.t9,r.t9_pct,"col-filter grp-rs-first")+testCell(r.t10,r.t10_pct,"col-filter")+testCell(r.t11,r.t11_pct,"col-filter grp-rs-last")
      +'<td class="col-txt col-ref">'+badge(r.pb_stage)+'</td><td class="col-txt col-ref">'+badge(r.bp_stage)+'</td>'
      +ratingsColTds(r)+'</tr>';
  }

  // Live Portfolio tile — ALL position stocks (not filtered by tab criteria)
  var posRows=applyIndSecFilter(filterToPositions(allRows));
  if(posRows.length>0){
    h+='<h3 class="qualified-title" id="section-portfolio">Live Portfolio ('+posRows.length+')</h3>';
    h+='<div class="data-table-wrap" style="margin-bottom:12px"><table class="data-table"><thead>'+mm99Headers()+'</thead><tbody>';
    for(var pj=0;pj<posRows.length;pj++)h+=mm99Row(posRows[pj]);
    h+='</tbody></table></div>';
  }

  rows=applyIndSecFilter(rows);
  h+='<h3 class="qualified-title" id="section-stocks">Qualified Stocks ('+xyFmt(rows.length,totalCount)+')</h3>';
  h+='<div class="data-table-wrap"><table class="data-table"><thead>'+mm99Headers()+'</thead><tbody>';
  for(var j=0;j<rows.length;j++)h+=mm99Row(rows[j]);
  h+='</tbody></table></div>';
  h+=buildQualTilesV2(applyIndSecFilter(allRows),[
    {key:"ga",label:"Long-term Strength"},
    {key:"gb",label:"Mid-term Strength"},
    {key:"gc",label:"Short-term Strength"},
    {key:"gd",label:"52W Leadership"},
    {key:"ge",label:"Relative Strength"}
  ],totalCount,mm99Headers,mm99Row);
  document.getElementById("tab-mm99").innerHTML=h;
}
window.setMM99Score=function(s){mm99MinScore=s;renderTab("mm99")};
window.setUtrMinCap=function(s){utrMinCap=s;renderTab("utr")};
window.setUtrFailedFilter=function(f){utrFailedFilter=(utrFailedFilter===f)?"":f;renderTab("utr")};
window.toggleUtrInputs=function(){utrShowInputs=!utrShowInputs;renderTab("utr")};

// ================================================================
// BASING PLATEAU TAB
// FIX-12: testCell used for BP test columns
// FIX-15: Separate % columns removed -- testCell handles both modes
// ================================================================
function renderBP(){
  buildHeaderControls("bp");
  var allRows=baseRows();
  var rows=[];
  for(var j=0;j<allRows.length;j++){
    var r=allRows[j],bp=r.f.basing_plateau;
    if(!bp||!bp.group_a){r.bp_stage="";r.ga=false;r.gb=false;r.gc=false;r.t1=false;r.t2=false;r.t3=false;r.t4=false;r.t5=false;r.t6=false;r.t7=false;r.t8=false;r.t1_pct=null;r.t2_pct=null;r.t3_pct=null;r.t4_pct=null;r.t5_pct=null;r.t6_pct=null;r.t7_pct=null;r.t8_pct=null;r.mm_stage=r.f.mm99?r.f.mm99.stage:"";r.pb_stage2=r.f.probing_bet?r.f.probing_bet.stage:"";r.ma_map_price=r.price;r.ma_map_200=null;r.ma_map_150=null;r.ma_map_50=null;rows.push(r);continue;}
    r.bp_stage=bp.stage;r.ga=bp.group_a.pass;r.gb=bp.group_b.pass;r.gc=bp.group_c.pass;
    r.t1=bp.group_a.tests.T1;r.t2=bp.group_a.tests.T2;
    r.t3=bp.group_b.tests.T3;r.t4=bp.group_b.tests.T4;r.t5=bp.group_b.tests.T5;
    r.t6=bp.group_c.tests.T6;r.t7=bp.group_c.tests.T7;r.t8=bp.group_c.tests.T8;
    var m200=r.mas?r.mas["200D"]:null,m150=r.mas?r.mas["150D"]:null,m50=r.mas?r.mas["50D"]:null;

    // FIX-12: Compute pct values for BP testCell
    r.t1_pct=m200?(r.price-m200)/m200:null;       // P~200D
    r.t2_pct=(m50&&m200)?(m50-m200)/m200:null;     // 50~200D
    r.t3_pct=m200?(r.price-m200)/m200:null;         // P~200D (tighter)
    r.t4_pct=(m50&&m200)?(m50-m200)/m200:null;     // 50~200D (tighter)
    r.t5_pct=(m150&&m200)?(m150-m200)/m200:null;   // 150~200D
    r.t6_pct=m200?(r.price-m200)/m200:null;         // P~200D (tightest)
    r.t7_pct=(m50&&m200)?(m50-m200)/m200:null;     // 50~200D (tightest)
    r.t8_pct=(m150&&m200)?(m150-m200)/m200:null;   // 150~200D (tightest)

    r.mm_stage=r.f.mm99?r.f.mm99.stage:"";r.pb_stage2=r.f.probing_bet?r.f.probing_bet.stage:"";
    r.ma_map_price=r.price;r.ma_map_200=m200;r.ma_map_150=m150;r.ma_map_50=m50;

    var skip=false;
    if(activeGroups.ga&&!r.ga)skip=true;
    if(activeGroups.gb&&!r.gb)skip=true;
    if(activeGroups.gc&&!r.gc)skip=true;
    if(skip)continue;

    rows.push(r);
  }
  rows=sortData(rows,currentSort.col,currentSort.dir);
  var totalCount=allRows.length;
  var cap=0,lat=0,ear=0,non=0;
  for(var j=0;j<rows.length;j++){var s=rows[j].bp_stage;if(s==="Capital")cap++;else if(s==="Late")lat++;else if(s==="Early")ear++;else non++}
  var h='<div class="summary-tile" id="section-summary"><h3>Basing Plateau &mdash; Sideways Consolidation Screen</h3>'
    +'<div class="sub">Loose (&plusmn;15%) = Early | Medium (&plusmn;10%) = Late | Tight (&plusmn;5%) = Capital</div>'
    +'<div class="summary-stats">'+sumStat("Tight/Capital",xyFmt(cap,rows.length),"green")+sumStat("Medium/Late",xyFmt(lat,rows.length),"amber")+sumStat("Loose/Early",ear)+sumStat("None",non)+sumStat("Shown",xyFmt(rows.length,totalCount))+'</div></div>';
  // FIX-S4-TILES: Group defs for BP industry/sector tiles
  var bpGroupDefs=[{key:"ga",label:"Loose Plateau"},{key:"gb",label:"Medium Plateau"},{key:"gc",label:"Tight Plateau"}];
  h+=buildIndSecTables(applyIndSecFilter(allRows),bpGroupDefs);

  // FIX-2: Qualified Stocks title
  function bpHeaders(){
    // BP: 10(common) + 1(MA Range) + 2(Loose) + 3(Medium) + 3(Tight) + 2(refs) + 8(ratings) = 29
    var hdr='<tr class="group-header-row"><th colspan="2"></th><th colspan="7" style="background:rgba(100,100,100,0.06)">Inputs</th><th></th><th></th>';
    hdr+='<th colspan="2" style="background:rgba(50,100,200,0.08)">Loose Plateau (\u00b115%)</th>';
    hdr+='<th colspan="3" style="background:rgba(200,150,0,0.08)">Medium Plateau (\u00b110%)</th>';
    hdr+='<th colspan="3" style="background:rgba(50,150,50,0.08)">Tight Plateau (\u00b15%)</th>';
    hdr+='<th colspan="2"></th>';
    hdr+=ratingsColHeaders().length>0?'<th colspan="8" class="col-ratings">Ratings</th>':"";
    hdr+='</tr><tr class="col-header-row">';
    // FIX: MA Range 3x wider, test columns narrower
    hdr+=commonCols()+th("MA Range","ma_map_price","col-filter","Visual: relative positions of Price, 200D, 150D, 50D MAs","width:240px")
      +th("P~200","t1_pct","col-filter grp-loose-first","Price within 15% of 200D MA","width:50px")+th("50~200","t2_pct","col-filter grp-loose-last","50D within 15% of 200D MA","width:50px")
      +th("P~200","t3_pct","col-filter grp-med-first","Price within 10% of 200D MA","width:50px")+th("50~200","t4_pct","col-filter","50D within 10% of 200D MA","width:50px")+th("150~200","t5_pct","col-filter grp-med-last","150D within 10% of 200D MA","width:55px")
      +th("P~200","t6_pct","col-filter grp-tight-first","Price within 5% of 200D MA","width:50px")+th("50~200","t7_pct","col-filter","50D within 5% of 200D MA","width:50px")+th("150~200","t8_pct","col-filter grp-tight-last","150D within 5% of 200D MA","width:55px")
      +th("MM 99","mm_stage","col-txt col-ref","MM99 filter stage")+th("Probing Bet","pb_stage2","col-txt col-ref","Probing Bet filter stage")+ratingsColHeaders();
    hdr+='</tr>';return hdr;
  }
  function bpRow(r){
    return'<tr onclick="openChart(\''+r.ticker+'\')" style="cursor:pointer">'+commonTds(r)
      +'<td class="col-filter">'+buildMAMap(r.ma_map_price,r.ma_map_200,r.ma_map_150,r.ma_map_50)+'</td>'
      +testCell(r.t1,r.t1_pct,"col-filter grp-loose-first")+testCell(r.t2,r.t2_pct,"col-filter grp-loose-last")
      +testCell(r.t3,r.t3_pct,"col-filter grp-med-first")+testCell(r.t4,r.t4_pct,"col-filter")+testCell(r.t5,r.t5_pct,"col-filter grp-med-last")
      +testCell(r.t6,r.t6_pct,"col-filter grp-tight-first")+testCell(r.t7,r.t7_pct,"col-filter")+testCell(r.t8,r.t8_pct,"col-filter grp-tight-last")
      +'<td class="col-txt col-ref">'+badge(r.mm_stage)+'</td><td class="col-txt col-ref">'+badge(r.pb_stage2)+'</td>'
      +ratingsColTds(r)+'</tr>';
  }
  var posRowsBP=applyIndSecFilter(filterToPositions(allRows));
  // Enrich position rows with BP data (they may not have been enriched if filtered out)
  for(var pk=0;pk<posRowsBP.length;pk++){var pr=posRowsBP[pk];if(pr.bp_stage===undefined){var bpd=pr.f.basing_plateau;if(!bpd||!bpd.group_a){pr.bp_stage="";pr.ga=false;pr.gb=false;pr.gc=false;pr.t1=false;pr.t2=false;pr.t3=false;pr.t4=false;pr.t5=false;pr.t6=false;pr.t7=false;pr.t8=false;}else{pr.bp_stage=bpd.stage;pr.ga=bpd.group_a.pass;pr.gb=bpd.group_b.pass;pr.gc=bpd.group_c.pass;pr.t1=bpd.group_a.tests.T1;pr.t2=bpd.group_a.tests.T2;pr.t3=bpd.group_b.tests.T3;pr.t4=bpd.group_b.tests.T4;pr.t5=bpd.group_b.tests.T5;pr.t6=bpd.group_c.tests.T6;pr.t7=bpd.group_c.tests.T7;pr.t8=bpd.group_c.tests.T8;}var m200b=pr.mas?pr.mas["200D"]:null,m150b=pr.mas?pr.mas["150D"]:null,m50b=pr.mas?pr.mas["50D"]:null;pr.t1_pct=m200b?(pr.price-m200b)/m200b:null;pr.t2_pct=(m50b&&m200b)?(m50b-m200b)/m200b:null;pr.t3_pct=m200b?(pr.price-m200b)/m200b:null;pr.t4_pct=(m50b&&m200b)?(m50b-m200b)/m200b:null;pr.t5_pct=(m150b&&m200b)?(m150b-m200b)/m200b:null;pr.t6_pct=m200b?(pr.price-m200b)/m200b:null;pr.t7_pct=(m50b&&m200b)?(m50b-m200b)/m200b:null;pr.t8_pct=(m150b&&m200b)?(m150b-m200b)/m200b:null;pr.mm_stage=pr.f.mm99?pr.f.mm99.stage:"";pr.pb_stage2=pr.f.probing_bet?pr.f.probing_bet.stage:"";pr.ma_map_price=pr.price;pr.ma_map_200=m200b;pr.ma_map_150=m150b;pr.ma_map_50=m50b;}}
  if(posRowsBP.length>0){
    h+='<h3 class="qualified-title" id="section-portfolio">Live Portfolio ('+posRowsBP.length+')</h3>';
    h+='<div class="data-table-wrap" style="margin-bottom:12px"><table class="data-table"><thead>'+bpHeaders()+'</thead><tbody>';
    for(var pj=0;pj<posRowsBP.length;pj++)h+=bpRow(posRowsBP[pj]);
    h+='</tbody></table></div>';
  }
  rows=applyIndSecFilter(rows);
  h+='<h3 class="qualified-title" id="section-stocks">Qualified Stocks ('+xyFmt(rows.length,totalCount)+')</h3>';
  h+='<div class="data-table-wrap"><table class="data-table"><thead>'+bpHeaders()+'</thead><tbody>';
  for(var j=0;j<rows.length;j++)h+=bpRow(rows[j]);
  h+='</tbody></table></div>';
  h+=buildQualTilesV2(applyIndSecFilter(allRows),[
    {key:"ga",label:"Loose Basing (\u00b115%)"},
    {key:"gb",label:"Medium Basing (\u00b110%)"},
    {key:"gc",label:"Tight Basing (\u00b15%)"}
  ],totalCount,bpHeaders,bpRow);
  document.getElementById("tab-bp").innerHTML=h;
}

// ================================================================
// PROBING BET TAB
// FIX-12: testCell applied to PB test columns
// ================================================================
function renderPB(){
  buildHeaderControls("pb");
  var allRows=baseRows();
  var rows=[];
  for(var j=0;j<allRows.length;j++){
    var r=allRows[j],pb=r.f.probing_bet;
    if(!pb||!pb.group_a){r.pb_stage="";r.ga=false;r.a_met=0;r.gb=false;r.b_met=0;r.gc=false;r.dead_cat=false;r.pct_below=null;r.gd=false;r.ge=false;r.t1=false;r.t2=false;r.t3=false;r.t4=false;r.t5=false;r.t6=false;r.t7=false;r.t8=false;r.t9=false;r.t10=false;r.t11=false;r.t12=false;r.t1_pct=null;r.t2_pct=null;r.t3_pct=null;r.t4_pct=null;r.t5_pct=null;r.t6_pct=null;r.t7_pct=null;r.t8_pct=null;r.t9_pct=null;r.t10_pct=null;r.t11_pct=null;r.t12_pct=null;r.mm_stage=r.f.mm99?r.f.mm99.stage:"";r.bp_stage2=r.f.basing_plateau?r.f.basing_plateau.stage:"";r.utr_stage2=r.f.uptrend_retest?r.f.uptrend_retest.stage:"";r.vcp_s2=r.f.vcp?r.f.vcp.stage_2_uptrend:false;rows.push(r);continue;}
    r.pb_stage=pb.stage;
    r.ga=pb.group_a.pass;r.a_met=pb.group_a.met;
    r.gb=pb.group_b.pass;r.b_met=pb.group_b.met;
    r.gc=pb.group_c.pass;r.dead_cat=pb.group_c.tests.T8;r.pct_below=pb.group_c.pct_below_52wh;
    r.gd=pb.group_d.pass;r.ge=pb.group_e.pass;
    r.t1=pb.group_a.tests.T1;r.t2=pb.group_a.tests.T2;r.t3=pb.group_a.tests.T3;r.t4=pb.group_a.tests.T4;r.t5=pb.group_a.tests.T5;
    r.t6=pb.group_b.tests.T6;r.t7=pb.group_b.tests.T7;
    r.t8=pb.group_c.tests.T8;
    r.t9=pb.group_d.tests.T9;r.t10=pb.group_d.tests.T10;
    r.t11=pb.group_e.tests.T11;r.t12=pb.group_e.tests.T12;
    // pct values for PB (approximate)
    r.t1_pct=null;r.t2_pct=null;r.t3_pct=null;r.t4_pct=null;r.t5_pct=null;
    r.t6_pct=null;r.t7_pct=null;r.t8_pct=null;
    r.t9_pct=null;r.t10_pct=null;r.t11_pct=null;r.t12_pct=null;
    r.mm_stage=r.f.mm99?r.f.mm99.stage:"";r.bp_stage2=r.f.basing_plateau?r.f.basing_plateau.stage:"";
    r.utr_stage2=r.f.uptrend_retest?r.f.uptrend_retest.stage:"";r.vcp_s2=r.f.vcp?r.f.vcp.stage_2_uptrend:false;

    var skip=false;
    if(activeGroups.ga&&!r.ga)skip=true;
    if(activeGroups.gb&&!r.gb)skip=true;
    if(activeGroups.gc&&!r.gc)skip=true;
    if(activeGroups.gd&&!r.gd)skip=true;
    if(activeGroups.ge&&!r.ge)skip=true;
    // FIX-S4-PBEXCL: Exclude stocks meeting other filter criteria
    if(pbExcludes.ex_mm99&&(r.mm_stage==="Capital"||r.mm_stage==="Late"))skip=true;
    if(pbExcludes.ex_vcp&&r.vcp_s2)skip=true;
    if(pbExcludes.ex_utr&&(r.utr_stage2==="Capital"||r.utr_stage2==="Late"))skip=true;
    if(skip)continue;

    rows.push(r);
  }
  rows=sortData(rows,currentSort.col,currentSort.dir);
  var totalCount=allRows.length;
  var cap=0,lat=0,ear=0,dc=0;
  for(var j=0;j<rows.length;j++){var s=rows[j].pb_stage;if(s==="Capital")cap++;else if(s==="Late")lat++;else if(s==="Early")ear++;if(rows[j].dead_cat)dc++}
  var h='<div class="summary-tile" id="section-summary"><h3>Probing Bet &mdash; Entry Setup Screen</h3>'
    +'<div class="sub">A=Early (3/5 rising) | B=Late (20D/50D rising) | C=Dead Cat (&ge;30% below 52WH) | D=PB1 Capital (P&gt;20D+rising) | E=PB2 Capital (P&gt;50D+rising)</div>'
    +'<div class="summary-stats">'+sumStat("Capital",xyFmt(cap,rows.length),"green")+sumStat("Late",xyFmt(lat,rows.length),"amber")+sumStat("Early",ear)+sumStat("Dead Cat",dc,"red")+sumStat("Shown",xyFmt(rows.length,totalCount))+'</div></div>';
  var pbGroupDefs=[{key:"ga",label:"Early"},{key:"gb",label:"Late"},{key:"gd",label:"PB1 Capital"},{key:"ge",label:"PB2 Capital"}];
  h+=buildIndSecTables(applyIndSecFilter(allRows),pbGroupDefs);

  // PB table headers + rows extracted as functions for reuse in portfolio tile
  function pbHeaders(){
    var hdr='<tr class="group-header-row">';
    // PB: 10(common)+6(A)+3(B)+2(C)+3(D)+3(E)+2(refs)+8(ratings) = 37
    hdr+='<th colspan="2"></th><th colspan="7" style="background:rgba(100,100,100,0.06)">Inputs</th><th></th>';
    hdr+='<th colspan="6" style="background:rgba(50,100,200,0.08)">A: Early Stage (3 of 5)</th>';
    hdr+='<th colspan="3" style="background:rgba(200,150,0,0.08)">B: Late Stage</th>';
    hdr+='<th colspan="2" style="background:rgba(200,50,50,0.08)">C: Dead Cat</th>';
    hdr+='<th colspan="3" style="background:rgba(50,150,50,0.08)">D: PB1 Capital (20D)</th>';
    hdr+='<th colspan="3" style="background:rgba(120,80,200,0.08)">E: PB2 Capital (50D)</th>';
    hdr+='<th colspan="2"></th>';
    hdr+=ratingsColHeaders().length>0?"<th colspan=\"8\" class=\"col-ratings\">Ratings</th>":"";
    hdr+='</tr><tr class="col-header-row">';
    hdr+=commonCols()
      +th("P Up","t1","col-filter","Price rising day-on-day")+th("5D Up","t2","col-filter","5-day MA rising")+th("10D Up","t3","col-filter","10-day MA rising")+th("20D Up","t4","col-filter","20-day MA rising")+th("50D Up","t5","col-filter","50-day MA rising")+th("A(/5)","a_met","col-num col-filter","Group A: count of 5 rising signals met (need 3)")
      +th("20D Up","t6","col-filter","20-day MA rising (Late)")+th("50D Up","t7","col-filter","50-day MA rising (Late)")+th("B","gb","col-filter","Group B: Late stage (1 of 2)")
      +th("Dead Cat","dead_cat","col-filter","Price 30%+ below 52W high")+th("%<52WH","pct_below","col-num col-filter","% below 52-week high")
      +th("P>20D","t9","col-filter","Price above 20D MA (PB1 capital)")+th("20D Up","t10","col-filter","20D MA rising (PB1 capital)")+th("PB1","gd","col-green","PB1 capital qualification")
      +th("P>50D","t11","col-filter","Price above 50D MA (PB2 capital)")+th("50D Up","t12","col-filter","50D MA rising (PB2 capital)")+th("PB2","ge","col-green","PB2 capital qualification")
      +th("MM 99","mm_stage","col-txt col-ref","MM99 filter stage")+th("Basing","bp_stage2","col-txt col-ref","Basing Plateau filter stage")
      +ratingsColHeaders();
    hdr+='</tr>';return hdr;
  }
  function pbRow(r){
    return'<tr onclick="openChart(\''+r.ticker+'\')" style="cursor:pointer">'+commonTds(r)
      +testCell(r.t1,r.t1_pct,"col-filter")+testCell(r.t2,r.t2_pct,"col-filter")+testCell(r.t3,r.t3_pct,"col-filter")+testCell(r.t4,r.t4_pct,"col-filter")+testCell(r.t5,r.t5_pct,"col-filter")
      +'<td class="col-num col-filter" style="font-weight:600">'+r.a_met+'/5</td>'
      +testCell(r.t6,r.t6_pct,"col-filter")+testCell(r.t7,r.t7_pct,"col-filter")+'<td class="col-filter">'+tick(r.gb)+'</td>'
      +'<td class="col-filter '+(r.dead_cat?"fail":"")+'">'+tick(r.dead_cat)+'</td>'
      +'<td class="col-num col-filter '+(r.pct_below!=null?(r.pct_below>=0.3?"fail":r.pct_below>=0.2?"amber":"pass"):"neutral")+'">'+pf(r.pct_below)+'</td>'
      +testCell(r.t9,r.t9_pct,"col-filter")+testCell(r.t10,r.t10_pct,"col-filter")
      +'<td class="col-green" style="font-weight:700">'+tick(r.gd)+'</td>'
      +testCell(r.t11,r.t11_pct,"col-filter")+testCell(r.t12,r.t12_pct,"col-filter")
      +'<td class="col-green" style="font-weight:700">'+tick(r.ge)+'</td>'
      +'<td class="col-txt col-ref">'+badge(r.mm_stage)+'</td><td class="col-txt col-ref">'+badge(r.bp_stage2)+'</td>'
      +ratingsColTds(r)+'</tr>';
  }

  // Live Portfolio tile — ALL position stocks
  var posRowsPB2=filterToPositions(allRows);
  for(var pk2=0;pk2<posRowsPB2.length;pk2++){var pr2=posRowsPB2[pk2];if(pr2.pb_stage===undefined){var pbd2=pr2.f.probing_bet;if(!pbd2||!pbd2.group_a){pr2.pb_stage="";pr2.ga=false;pr2.a_met=0;pr2.gb=false;pr2.gc=false;pr2.gd=false;pr2.ge=false;pr2.dead_cat=false;pr2.pct_below=null;pr2.t1=false;pr2.t2=false;pr2.t3=false;pr2.t4=false;pr2.t5=false;pr2.t6=false;pr2.t7=false;pr2.t8=false;pr2.t9=false;pr2.t10=false;pr2.t11=false;pr2.t12=false;}else{pr2.pb_stage=pbd2.stage;pr2.ga=pbd2.group_a.pass;pr2.a_met=pbd2.group_a.met;pr2.gb=pbd2.group_b.pass;pr2.gc=pbd2.group_c.pass;pr2.gd=pbd2.group_d.pass;pr2.ge=pbd2.group_e.pass;pr2.dead_cat=pbd2.group_c.tests.T8;pr2.pct_below=pbd2.group_c.pct_below_52wh;pr2.t1=pbd2.group_a.tests.T1;pr2.t2=pbd2.group_a.tests.T2;pr2.t3=pbd2.group_a.tests.T3;pr2.t4=pbd2.group_a.tests.T4;pr2.t5=pbd2.group_a.tests.T5;pr2.t6=pbd2.group_b.tests.T6;pr2.t7=pbd2.group_b.tests.T7;pr2.t8=pbd2.group_c.tests.T8;pr2.t9=pbd2.group_d.tests.T9;pr2.t10=pbd2.group_d.tests.T10;pr2.t11=pbd2.group_e.tests.T11;pr2.t12=pbd2.group_e.tests.T12;}pr2.t1_pct=null;pr2.t2_pct=null;pr2.t3_pct=null;pr2.t4_pct=null;pr2.t5_pct=null;pr2.t6_pct=null;pr2.t7_pct=null;pr2.t8_pct=null;pr2.t9_pct=null;pr2.t10_pct=null;pr2.t11_pct=null;pr2.t12_pct=null;pr2.mm_stage=pr2.f.mm99?pr2.f.mm99.stage:"";pr2.bp_stage2=pr2.f.basing_plateau?pr2.f.basing_plateau.stage:"";pr2.utr_stage2=pr2.f.uptrend_retest?pr2.f.uptrend_retest.stage:"";}}
  // Apply ind/sec filter to portfolio too
  var posRowsPB2f=[];for(var pf2=0;pf2<posRowsPB2.length;pf2++){if(passIndSecFilter(posRowsPB2[pf2]))posRowsPB2f.push(posRowsPB2[pf2])}
  if(posRowsPB2f.length>0){
    h+='<h3 class="qualified-title" id="section-portfolio">Live Portfolio ('+posRowsPB2f.length+')</h3>';
    h+='<div class="data-table-wrap"><table class="data-table"><thead>'+pbHeaders()+'</thead><tbody>';
    for(var pj=0;pj<posRowsPB2f.length;pj++)h+=pbRow(posRowsPB2f[pj]);
    h+='</tbody></table></div>';
  }

  rows=applyIndSecFilter(rows);
  h+='<h3 class="qualified-title" id="section-stocks">Qualified Stocks ('+xyFmt(rows.length,totalCount)+')</h3>';
  h+='<div class="data-table-wrap"><table class="data-table"><thead>'+pbHeaders()+'</thead><tbody>';
  for(var j=0;j<rows.length;j++)h+=pbRow(rows[j]);
  h+='</tbody></table></div>';
  document.getElementById("tab-pb").innerHTML=h;
}

// ================================================================
// UPTREND RETEST TAB
// FIX-12: testCell for EWS columns
// ================================================================
function renderUTR(){
  buildHeaderControls("utr");
  var allRows=baseRows();
  var rows=[];
  for(var j=0;j<allRows.length;j++){
    var r=allRows[j],ut=r.f.uptrend_retest;
    if(!ut||!ut.tests){
      r.utr_stage="";r.depth_pct=null;r.test_ma="";r.test_ma_dist=null;r.retest_num=0;
      r.vol_q="";r.updn="";r.candle="";r.dist_d="";r.contr="";r.rs_h="";
      r.st_roll="";r.it_intact="";r.t_depth="";r.t_ma="";
      r.cap_count=0;r.late_quality=0;
      r.t_depth_v=null;r.t_ma_v=null;r.st_roll_v=null;r.it_intact_v=null;
      r.vol_q_v=null;r.updn_v=null;r.contr_v=null;r.dist_d_v=null;r.candle_v=null;r.rs_h_v=null;
      r.sort_vol=null;r.sort_updn=null;r.sort_contr=null;r.sort_dist=null;r.sort_candle=null;r.sort_rs=null;r.sort_st=null;r.sort_it=null;
      r.mm_stage=r.f.mm99?r.f.mm99.stage:"";r.pb_stage2=r.f.probing_bet?r.f.probing_bet.stage:"";
      r.utr_capital=false;r.utr_late=false;r.utr_early=false;
      rows.push(r);continue;
    }
    r.utr_stage=ut.stage;r.depth_pct=ut.depth_pct;r.test_ma=ut.test_ma||"";
    r.test_ma_dist=ut.test_ma_dist;r.retest_num=ut.current_retest_num||0;
    r.cap_count=ut.capital_count||0;r.late_quality=ut.late_quality||0;
    var t=ut.tests,stg=ut.stage;
    var mx=ut.metrics||{};
    r.t_depth=stg==="Capital"?t.c2_depth:stg==="Late"?t.l1_depth:t.e1_depth;
    r.t_ma=stg==="Capital"?t.c1_at_ma:t.l2_ma_approach;
    r.st_roll=t.e2_ma_roll;
    var md=ut.ma_direction||{};
    r.it_intact=(md["50d_rising"]&&md["150d_rising"])?"pass":md["50d_rising"]?"amber":"fail";
    r.vol_q=stg==="Capital"?t.c3_vol:stg==="Late"?t.l3_vol_dry:t.e3_vol;
    r.updn=stg==="Capital"?t.c4_updown:t.l4_updown;
    r.candle=t.c5_candle;
    r.dist_d=stg==="Capital"?t.c6_dist:stg==="Late"?t.l6_dist:t.e4_dist;
    // Raw numeric values for toggle display
    r.t_depth_v=r.depth_pct!=null?r.depth_pct.toFixed(1)+"%":null;
    r.t_ma_v=r.test_ma_dist!=null?r.test_ma_dist.toFixed(1)+"%":null;
    r.st_roll_v=(md["5d_declining"]?"5D\u2193":"5D\u2192")+" "+(md["10d_declining"]?"10D\u2193":"10D\u2192");
    r.it_intact_v=(md["50d_rising"]?"50D\u2191":"50D\u2193")+" "+(md["150d_rising"]?"150D\u2191":"150D\u2193");
    r.vol_q_v=mx.vol_trend!=null?mx.vol_trend.toFixed(2):null;
    r.updn_v=mx.updown_ratio!=null?mx.updown_ratio.toFixed(2):null;
    r.contr_v=mx.contraction!=null?mx.contraction.toFixed(2):null;
    r.dist_d_v=mx.dist_days!=null?mx.dist_days:null;
    r.candle_v=mx.candle_quality!=null?(mx.candle_quality*100).toFixed(0)+"%":null;
    r.rs_h_v=mx.rs_percentile!=null?mx.rs_percentile:null;
    // Raw numeric sort keys for UTR test columns
    r.sort_vol=mx.vol_trend!=null?mx.vol_trend:null;
    r.sort_updn=mx.updown_ratio!=null?mx.updown_ratio:null;
    r.sort_contr=mx.contraction!=null?mx.contraction:null;
    r.sort_dist=mx.dist_days!=null?mx.dist_days:null;
    r.sort_candle=mx.candle_quality!=null?mx.candle_quality:null;
    r.sort_rs=mx.rs_percentile!=null?mx.rs_percentile:null;
    r.sort_st=(md["5d_declining"]?1:0)+(md["10d_declining"]?1:0);
    r.sort_it=(md["50d_rising"]?1:0)+(md["150d_rising"]?1:0);
    r.contr=stg==="Capital"?t.c7_contraction:t.l5_contraction;
    r.rs_h=t.c8_rs;
    r.mm_stage=r.f.mm99?r.f.mm99.stage:"";r.pb_stage2=r.f.probing_bet?r.f.probing_bet.stage:"";
    r.utr_capital=r.utr_stage==="Capital";r.utr_late=r.utr_stage==="Late"||r.utr_stage==="Capital";r.utr_early=r.utr_stage==="Early"||r.utr_stage==="Late"||r.utr_stage==="Capital";
    // Failed retest = price has broken below the test MA (negative distance)
    r.utr_failed=r.test_ma_dist!=null&&r.test_ma_dist<0;
    r.utr_failed_deep=r.test_ma_dist!=null&&r.test_ma_dist<-3;  // deep break = probably >1 week
    rows.push(r);
  }
  // Apply UTR header filters
  if(utrMinCap>0){rows=rows.filter(function(r2){return r2.cap_count>=utrMinCap})}
  if(utrFailedFilter==="L1W"){rows=rows.filter(function(r2){return r2.utr_failed&&!r2.utr_failed_deep})}
  else if(utrFailedFilter==="L1M"){rows=rows.filter(function(r2){return r2.utr_failed})}
  rows=sortData(rows,currentSort.col,currentSort.dir);
  var totalCount=allRows.length;
  var cap=0,lat=0,ear=0;
  for(var j=0;j<rows.length;j++){var s=rows[j].utr_stage;if(s==="Capital")cap++;else if(s==="Late")lat++;else if(s==="Early")ear++}
  var h='<div class="summary-tile" id="section-summary"><h3>Uptrend Retest &mdash; Pullback Lifecycle Screen</h3>'
    +'<div class="sub">Tracks orderly pullbacks from swing high through MA retest. Early (pulling back) &rarr; Late (approaching MA) &rarr; Capital (healthy retest, act today). Invalidated if depth &gt;25%, MA break &gt;5%, dist days &ge;6, or RS &lt;50.</div>'
    +'<div class="summary-stats">'+sumStat("Capital",xyFmt(cap,rows.length),"green")+sumStat("Late",xyFmt(lat,rows.length),"amber")+sumStat("Early",ear)+sumStat("Shown",xyFmt(rows.length,totalCount))+'</div></div>';
  var utrGroupDefs=[{key:"utr_early",label:"Early+"},{key:"utr_late",label:"Late+"},{key:"utr_capital",label:"Capital"}];
  h+=buildIndSecTables(applyIndSecFilter(allRows),utrGroupDefs);

  h+=buildPortfolioTile(currentTab);
  rows=applyIndSecFilter(rows);
  h+='<h3 class="qualified-title" id="section-stocks">Qualified Stocks ('+xyFmt(rows.length,totalCount)+')</h3>';
  var inputHide=utrShowInputs?"":" utr-inputs-hidden";
  h+='<div class="data-table-wrap"><table class="data-table'+inputHide+'"><thead>';
  // ── Row 1: Key descriptions (shown by default on UTR only) ──
  h+='<tr class="utr-key-row">';
  h+='<td></td>';  // Ticker
  h+='<td class="col-input"></td>';  // Sector
  h+='<td class="col-input"></td><td class="col-input"></td><td class="col-input"></td><td class="col-input"></td><td class="col-input"></td><td class="col-input"></td><td class="col-input"></td><td class="col-input"></td>';  // Price..RS
  h+='<td>Which MA is being tested (50D/100D/150D/200D)</td><td>Completed retest cycles of this MA since uptrend began</td>';  // Test MA, Retest
  h+='<td>% below swing high (how deep is the pullback)</td><td>% distance to the test MA (how close to support)</td>';  // Depth%, MA Dist%
  h+='<td class="utr-e-first">Is pullback depth within healthy range for this stage?</td><td>Is price approaching or at the support MA?</td><td>Are short-term MAs (5D, 10D) rolling over, confirming pullback?</td><td class="utr-e-last">Are intermediate MAs (50D, 150D) still rising, confirming trend intact?</td>';  // Early
  h+='<td class="utr-l-first">Has selling volume dried up vs average? Lower = more constructive</td><td>Up-day volume vs down-day volume ratio. Above 1.0 = net accumulation</td><td>Is price range contracting? Volatility contraction precedes next move</td><td class="utr-l-last">High-volume down days in last 25 sessions. Institutional selling signal</td>';  // Late
  h+='<td class="utr-c-first">% of recent closes in upper portion of daily range. Buyers stepping in</td><td class="utr-c-last">Relative strength percentile. Must hold above 70 for Capital</td>';  // Capital
  h+='<td>Count of Capital-grade quality signals passing</td>';  // C#
  h+='<td>Pullback lifecycle stage</td>';  // Stage
  h+='<td></td><td></td>';  // X-ref
  h+=ratingsColHeaders().length>0?'<td class="col-ratings"></td><td class="col-ratings"></td><td class="col-ratings"></td><td class="col-ratings"></td><td class="col-ratings"></td><td class="col-ratings"></td><td class="col-ratings"></td><td class="col-ratings"></td>':"";
  h+='</tr>';
  // ── Row 2: Stage group headers (MM99 pattern) ──
  h+='<tr class="group-header-row">';
  h+='<th></th><th colspan="9" class="col-input" style="background:rgba(100,100,100,0.06)">Inputs</th>';
  h+='<th colspan="2" style="background:rgba(100,100,100,0.06)">Setup</th>';
  h+='<th colspan="2" style="background:rgba(100,100,100,0.06)">Metrics</th>';
  h+='<th colspan="4" style="background:rgba(200,170,0,0.08)">Early</th>';
  h+='<th colspan="4" style="background:rgba(230,100,0,0.08)">+ Late</th>';
  h+='<th colspan="2" style="background:rgba(46,125,50,0.08)">+ Capital</th>';
  h+='<th></th>';
  h+='<th style="background:rgba(120,80,200,0.08)">Stage</th>';
  h+='<th colspan="2" style="background:rgba(180,100,50,0.08)">X-Ref</th>';
  h+=ratingsColHeaders().length>0?'<th colspan="8" class="col-ratings">Ratings</th>':"";
  h+='</tr><tr class="col-header-row">';
  // ── Row 3: Individual column headers ──
  h+=utrCommonCols()
    +th("Test MA","test_ma","col-txt col-filter","Which moving average the stock is pulling back towards. Scans 50D, 100D, 150D, 200D in order and picks the first one price is approaching from above. 50D retest in a strong uptrend is the bread-and-butter Minervini entry. 200D retest is last line of defence.")
    +th("Retest #","retest_num","col-num col-filter","How many completed retest cycles of this MA since the uptrend began. A completed retest = price came within 2% of the MA then moved 5%+ above it. 1st retest is highest conviction (Minervini). 2nd is acceptable. 3rd+ is a warning \u2014 the setup is getting stale.")
    +th("Depth %","depth_pct","col-num","Percentage below the swing high. Measures how deep the pullback has gone. Early: 3\u201310% (just started). Late: 8\u201320% (Minervini guideline for buyable pullbacks). Capital: must stay under 25%. Deeper than 25% = invalidated, trend probably broken.")
    +th("MA Dist %","test_ma_dist","col-num","Distance from the test MA as a percentage. Positive = still above the MA. Late stage: within 5% and approaching. Capital stage: within 2% (at the MA or slight undercut). Negative = price has broken below \u2014 if beyond -5%, pattern is invalidated.")
    +th("Depth","depth_pct","col-filter utr-e-first","Is the pullback depth within healthy range for the current stage? Early: 3\u201310% from high. Late: 8\u201320%. Capital: under 25%. Pass means the pullback is sized correctly \u2014 not so shallow it is noise, not so deep the trend is breaking.")
    +th("MA Prox","test_ma_dist","col-filter","Is price approaching or sitting at the support MA? Late: within 5% and closing in. Capital: within 2% (touching or slight undercut). Minervini\u2019s undercut-and-rally is acceptable; a decisive break below is not.")
    +th("ST Roll","sort_st","col-filter","Are the short-term MAs (5-day and 10-day) rolling over? This confirms the pullback is real and short-term in nature. Both declining = clear pullback signal. If short-term MAs are still rising, the stock hasn\u2019t actually started pulling back yet.")
    +th("IT Intact","sort_it","col-filter utr-e-last","Are the intermediate MAs (50-day and 150-day) still rising? This is the Minervini Stage 2 requirement: the long-term trend must remain intact even as price pulls back. Both rising = pass. If 150D is declining, the broader uptrend may be over.")
    +th("Vol Dry","sort_vol","col-filter utr-l-first","Has selling volume dried up? Measured as 10-day average volume divided by 50-day average. Lower = sellers exhausted (constructive). Late: below 0.85. Capital: below 0.80. Minervini: best setups show volume dropping 40\u201360% below average during the pullback.")
    +th("Up/Dn","sort_updn","col-filter","Ratio of average up-day volume to average down-day volume. Above 1.0 = more volume on up days than down days (quiet accumulation). Capital: needs above 1.1. Below 0.8 = distribution, institutions selling \u2014 the pullback is not constructive.")
    +th("Contract","sort_contr","col-filter","Volatility contraction: ATR(10) divided by ATR(20). Below 1.0 means the daily range is narrowing \u2014 the stock is coiling. Late: below 0.90. Capital: below 0.85. One of the strongest pre-breakout signals (Minervini + Weinstein). Tight coil = energy stored for next leg.")
    +th("Dist Days","sort_dist","col-filter utr-l-last","Distribution days in the last 25 sessions. A distribution day = close below prior close on volume 25%+ above the 50-day average. Institutional selling footprint. Early: 0\u20131 expected. Late: 0\u20133 acceptable. Capital: 0\u20132 required. 6+ = invalidation.")
    +th("Candle","sort_candle","col-filter utr-c-first","Candle quality: percentage of the last 10 closes in the upper 40% of the daily range. Measures whether buyers are stepping in at the MA. Capital gate: needs 50%+. High candle quality at a support MA = accumulation pattern, buyers defending the level.")
    +th("RS Hold","sort_rs","col-filter utr-c-last","Relative strength percentile vs the market. Must hold above 70 for Capital qualification \u2014 the market still rates this stock highly despite the pullback. Below 50 = invalidation. If RS collapses during a pullback, it signals stock-specific weakness, not healthy rest.")
    +th("C#","cap_count","col-num","Count of Capital-grade quality signals currently passing (out of C1\u2013C8). All 8 must pass for Capital stage. Useful as a quick read on how close a Late-stage stock is to becoming actionable \u2014 higher count = closer to a buy signal.")
    +th("Stage","utr_stage","col-txt col-filter","Pullback lifecycle stage. Early = pullback initiated, short-term MAs rolling, trend intact. Late = approaching the test MA, quality checks intensifying. Capital = healthy retest confirmed, all signals pass, act today. None = no active pullback or pattern invalidated.")
    +th("MM99","mm_stage","col-txt col-ref","Cross-reference: Minervini 99 filter stage for this stock")+th("PB","pb_stage2","col-txt col-ref","Cross-reference: Probing Bet filter stage for this stock")
    +ratingsColHeaders();
  h+='</tr></thead><tbody>';
  for(var j=0;j<rows.length;j++){
    var r=rows[j];
    h+='<tr onclick="openChart(\''+r.ticker+'\')" style="cursor:pointer">'+utrCommonTds(r)
      +'<td class="col-txt col-filter">'+utrTestMa(r.test_ma)+'</td>'
      +'<td class="col-num col-filter">'+(r.retest_num?r.retest_num:"&mdash;")+'</td>'
      +'<td class="col-num">'+utrPct(r.depth_pct)+'</td>'
      +'<td class="col-num">'+utrMaDist(r.test_ma_dist)+'</td>'
      +utrSigCell(r.t_depth,r.t_depth_v,"utr-e-first")+utrSigCell(r.t_ma,r.t_ma_v,"")+utrSigCell(r.st_roll,r.st_roll_v,"")+utrSigCell(r.it_intact,r.it_intact_v,"utr-e-last")
      +utrSigCell(r.vol_q,r.vol_q_v,"utr-l-first")+utrSigCell(r.updn,r.updn_v,"")+utrSigCell(r.contr,r.contr_v,"")+utrSigCell(r.dist_d,r.dist_d_v,"utr-l-last")
      +utrSigCell(r.candle,r.candle_v,"utr-c-first")+utrSigCell(r.rs_h,r.rs_h_v,"utr-c-last")
      +'<td class="col-num">'+r.cap_count+'/8</td>'
      +'<td class="col-txt col-filter">'+badge(r.utr_stage)+'</td>'
      +'<td class="col-txt col-ref">'+badge(r.mm_stage)+'</td><td class="col-txt col-ref">'+badge(r.pb_stage2)+'</td>'
      +ratingsColTds(r)+'</tr>';
  }
  h+='</tbody></table></div>';
  document.getElementById("tab-utr").innerHTML=h;
}

// ================================================================
// VCP TAB
// FIX-12: testCell for VCP test columns
// ================================================================
function renderVCP(){
  buildHeaderControls("vcp");
  var allRows=baseRows();
  var rows=[];
  for(var j=0;j<allRows.length;j++){
    var r=allRows[j],vc=r.f.vcp;
    r.stage2=vc?vc.stage_2_uptrend:false;
    r.mm_score=r.f.mm99?r.f.mm99.score_11:0;r.mm_stage=r.f.mm99?r.f.mm99.stage:"";
    r.mm_ga=r.f.mm99&&r.f.mm99.group_a?r.f.mm99.group_a.pass:false;r.mm_gb=r.f.mm99&&r.f.mm99.group_b?r.f.mm99.group_b.pass:false;
    r.mm_ga_pct=null;r.mm_gb_pct=null;
    r.pb_stage=r.f.probing_bet?r.f.probing_bet.stage:"";r.bp_stage=r.f.basing_plateau?r.f.basing_plateau.stage:"";
    rows.push(r);
  }
  rows=sortData(rows,currentSort.col,currentSort.dir);
  var totalCount=allRows.length;
  var s2=0;for(var j=0;j<rows.length;j++)if(rows[j].stage2)s2++;
  var h='<div class="summary-tile" id="section-summary"><h3>VCP &mdash; Volatility Contraction Pattern</h3>'
    +'<div class="sub">Pattern detection pending Phase 2. Currently showing Stage 2 uptrend check (MM99 Groups A+B pass = price above rising 200D+150D).</div>'
    +'<div class="summary-stats">'+sumStat("Stage 2 Uptrend",xyFmt(s2,rows.length),"green")+sumStat("Not Stage 2",rows.length-s2)+sumStat("Shown",xyFmt(rows.length,totalCount))+'</div></div>';
  var vcpGroupDefs=[{key:"stage2",label:"Stage 2"},{key:"mm_ga",label:"P>200D"},{key:"mm_gb",label:"P>150D"}];
  h+=buildIndSecTables(applyIndSecFilter(allRows),vcpGroupDefs);

  h+=buildPortfolioTile(currentTab);
  rows=applyIndSecFilter(rows);
  h+='<h3 class="qualified-title" id="section-stocks">Qualified Stocks ('+xyFmt(rows.length,totalCount)+')</h3>';
  h+='<div class="data-table-wrap"><table class="data-table"><thead><tr>';
  h+=commonCols()+th("Stage 2","stage2","col-filter")+th("P>200D","mm_ga","col-filter")+th("P>150D, 150>200","mm_gb","col-filter")
    +th("MM 99","mm_score","col-num col-filter")+th("MM Stage","mm_stage","col-txt col-ref")+th("PB","pb_stage","col-txt col-ref")+th("BP","bp_stage","col-txt col-ref")
    +ratingsColHeaders();
  h+='</tr></thead><tbody>';
  for(var j=0;j<rows.length;j++){
    var r=rows[j];
    // FIX-12: testCell for VCP
    h+='<tr onclick="openChart(\''+r.ticker+'\')" style="cursor:pointer">'+commonTds(r)
      +'<td class="col-filter" style="font-weight:700">'+(r.stage2?'<span class="pass">STAGE 2</span>':'<span class="fail">NO</span>')+'</td>'
      +testCell(r.mm_ga,r.mm_ga_pct,"col-filter")+testCell(r.mm_gb,r.mm_gb_pct,"col-filter")
      +'<td class="col-num col-filter">'+scorePips(r.mm_score,11)+' '+r.mm_score+'/11</td>'
      +'<td class="col-txt col-ref">'+badge(r.mm_stage)+'</td><td class="col-txt col-ref">'+badge(r.pb_stage)+'</td><td class="col-txt col-ref">'+badge(r.bp_stage)+'</td>'
      +ratingsColTds(r)+'</tr>';
  }
  h+='</tbody></table></div>';
  document.getElementById("tab-vcp").innerHTML=h;
}

// ================================================================
// TECH DATA TAB
// ================================================================
function renderTech(){
  buildHeaderControls("tech");
  var allRows=baseRows();
  var rows=[];
  for(var j=0;j<allRows.length;j++){
    var r=allRows[j];
    r.ma5=r.mas?r.mas["5D"]:null;r.ma10=r.mas?r.mas["10D"]:null;r.ma20=r.mas?r.mas["20D"]:null;r.ma50=r.mas?r.mas["50D"]:null;
    r.ma100=r.mas?r.mas["100D"]:null;r.ma150=r.mas?r.mas["150D"]:null;r.ma200=r.mas?r.mas["200D"]:null;
    r.h52=r.high_52w;r.l52=r.low_52w;
    r.mm_score=r.f.mm99?r.f.mm99.score_11:0;
    rows.push(r);
  }
  rows=sortData(rows,currentSort.col,currentSort.dir);
  var totalCount=allRows.length;
  var h='<div class="summary-tile" id="section-summary"><h3>Technical Data &mdash; Reference View</h3>'
    +'<div class="sub">Raw price, moving average, volume, and 52-week data for all stocks in the universe.</div>'
    +'<div class="summary-stats">'+sumStat("Stocks",xyFmt(rows.length,totalCount))+'</div></div>';

  h+=buildPortfolioTile(currentTab);
  rows=applyIndSecFilter(rows);
  h+='<h3 class="qualified-title" id="section-stocks">Qualified Stocks ('+xyFmt(rows.length,totalCount)+')</h3>';
  h+='<div class="data-table-wrap"><table class="data-table"><thead><tr>';
  h+=commonCols()+th("5D","ma5","col-num col-price")+th("10D","ma10","col-num col-price")+th("20D","ma20","col-num col-price")+th("50D","ma50","col-num col-price")
    +th("100D","ma100","col-num col-price")+th("150D","ma150","col-num col-price")+th("200D","ma200","col-num col-price")
    +th("ADV 1M","adv_1m","col-num col-price")+th("ADV 3M","adv_3m","col-num col-price")
    +th("1M Up","adv_1m_up","col-num col-price")+th("1M Dn","adv_1m_dn","col-num col-price")
    +th("3M Up","adv_3m_up","col-num col-price")+th("3M Dn","adv_3m_dn","col-num col-price")
    +th("MM 99","mm_score","col-num col-filter");
  h+='</tr></thead><tbody>';
  for(var j=0;j<rows.length;j++){
    var r=rows[j];
    h+='<tr onclick="openChart(\''+r.ticker+'\')" style="cursor:pointer">'+commonTds(r)
      +'<td class="col-num col-price">'+fp(r.ma5)+'</td><td class="col-num col-price">'+fp(r.ma10)+'</td>'
      +'<td class="col-num col-price">'+fp(r.ma20)+'</td><td class="col-num col-price">'+fp(r.ma50)+'</td>'
      +'<td class="col-num col-price">'+fp(r.ma100)+'</td><td class="col-num col-price">'+fp(r.ma150)+'</td><td class="col-num col-price">'+fp(r.ma200)+'</td>'
      +'<td class="col-num col-price">'+nf(r.adv_1m)+'</td><td class="col-num col-price">'+nf(r.adv_3m)+'</td>'
      +'<td class="col-num col-price">'+nf(r.adv_1m_up)+'</td><td class="col-num col-price">'+nf(r.adv_1m_dn)+'</td>'
      +'<td class="col-num col-price">'+nf(r.adv_3m_up)+'</td><td class="col-num col-price">'+nf(r.adv_3m_dn)+'</td>'
      +'<td class="col-num col-filter">'+scorePips(r.mm_score,11)+'</td></tr>';
  }
  h+='</tbody></table></div>';
  document.getElementById("tab-tech").innerHTML=h;
}

// ================================================================
// COMBINATIONS TAB
// ================================================================
function renderCombos(){
  buildHeaderControls("combos");
  var allRows=baseRows();
  var rows=[];
  for(var j=0;j<allRows.length;j++){
    var r=allRows[j];
    r.bp_stage=r.f.basing_plateau?r.f.basing_plateau.stage:"";r.pb_stage=r.f.probing_bet?r.f.probing_bet.stage:"";
    r.mm_stage=r.f.mm99?r.f.mm99.stage:"";r.utr_stage=r.f.uptrend_retest?r.f.uptrend_retest.stage:"";
    r.vcp_s2=r.f.vcp?r.f.vcp.stage_2_uptrend:false;
    r.mm_score=r.f.mm99?r.f.mm99.score_11:0;
    r.filter_count=0;
    if(r.bp_stage)r.filter_count++;if(r.pb_stage)r.filter_count++;
    if(r.mm_stage)r.filter_count++;if(r.utr_stage)r.filter_count++;
    if(r.vcp_s2)r.filter_count++;
    r.capital_count=0;
    if(r.bp_stage==="Capital")r.capital_count++;if(r.pb_stage==="Capital")r.capital_count++;
    if(r.mm_stage==="Capital")r.capital_count++;if(r.utr_stage==="Capital")r.capital_count++;
    rows.push(r);
  }
  rows=sortData(rows,currentSort.col,currentSort.dir);
  var totalCount=allRows.length;
  var multi=0,cap2=0;
  for(var j=0;j<rows.length;j++){if(rows[j].filter_count>=2)multi++;if(rows[j].capital_count>=2)cap2++}
  var h='<div class="summary-tile" id="section-summary"><h3>Combinations &mdash; Cross-Filter Matrix</h3>'
    +'<div class="sub">Which stocks qualify across multiple filters simultaneously. Higher filter count = stronger technical setup.</div>'
    +'<div class="summary-stats">'+sumStat("2+ Filters",xyFmt(multi,rows.length),"green")+sumStat("2+ Capital",xyFmt(cap2,rows.length),"green")+sumStat("Shown",xyFmt(rows.length,totalCount))+'</div></div>';

  h+=buildPortfolioTile(currentTab);
  rows=applyIndSecFilter(rows);
  h+='<h3 class="qualified-title" id="section-stocks">Qualified Stocks ('+xyFmt(rows.length,totalCount)+')</h3>';
  h+='<div class="data-table-wrap"><table class="data-table"><thead><tr>';
  h+=commonCols()+th("Filters","filter_count","col-num col-filter")+th("Capitals","capital_count","col-num col-filter")
    +th("Basing Plateau","bp_stage","col-txt col-filter")+th("Probing Bet","pb_stage","col-txt col-filter")+th("MM 99","mm_stage","col-txt col-filter")
    +th("Uptrend Retest","utr_stage","col-txt col-filter")+th("VCP Stage 2","vcp_s2","col-filter")+th("MM Score","mm_score","col-num col-filter")
    +ratingsColHeaders();
  h+='</tr></thead><tbody>';
  for(var j=0;j<rows.length;j++){
    var r=rows[j];
    var fc=r.filter_count>=3?"green":r.filter_count>=2?"amber":r.filter_count>=1?"":"neutral";
    h+='<tr onclick="openChart(\''+r.ticker+'\')" style="cursor:pointer">'+commonTds(r)
      +'<td class="col-num col-filter combo-cell '+fc+'">'+r.filter_count+'</td>'
      +'<td class="col-num col-filter combo-cell '+(r.capital_count>=2?"green":r.capital_count>=1?"amber":"")+'">'+r.capital_count+'</td>'
      +'<td class="col-txt col-filter">'+badge(r.bp_stage)+'</td>'
      +'<td class="col-txt col-filter">'+badge(r.pb_stage)+'</td>'
      +'<td class="col-txt col-filter">'+badge(r.mm_stage)+'</td>'
      +'<td class="col-txt col-filter">'+badge(r.utr_stage)+'</td>'
      +'<td class="col-filter">'+(r.vcp_s2?'<span class="pass">S2</span>':'<span class="fail">&mdash;</span>')+'</td>'
      +'<td class="col-num col-filter">'+scorePips(r.mm_score,11)+'</td>'
      +ratingsColTds(r)+'</tr>';
  }
  h+='</tbody></table></div>';
  document.getElementById("tab-combos").innerHTML=h;
}

// ================================================================
// POSITIONS TAB
// ================================================================
function renderPositions(){
  buildHeaderControls("positions");
  var container=document.getElementById("tab-positions");
  if(!D.positions){
    container.innerHTML='<div class="summary-tile" style="text-align:center;padding:40px"><h3>Positions</h3><p style="color:var(--text-dim);margin-top:8px">positions.json not loaded. Run build_dashboard.py with positions.json in COWORK root.</p></div>';
    return;
  }
  var pos=D.positions;
  var invs=pos.investments||[];
  var totalTrades=0,activeTrades=0;
  for(var j=0;j<invs.length;j++)for(var k=0;k<invs[j].trades.length;k++){totalTrades++;if(invs[j].trades[k].status!=="planned")activeTrades++}

  var h='<div class="summary-tile" id="section-summary"><h3>Position Management</h3>'
    +'<div class="sub">Schema v'+pos.schema_version+'. Trade types: PB1/PB2 (probing bets), S1-S4 (legacy scaling). V2 migration to PB1/PB2/MM99/UR1-UR3 pending.</div>'
    +'<div class="summary-stats">'+sumStat("Investments",invs.length)+sumStat("Total Trades",totalTrades)+sumStat("Active",xyFmt(activeTrades,totalTrades),"green")+'</div></div>';

  h+='<div class="data-table-wrap" id="section-stocks"><table class="data-table"><thead><tr>'
    +'<th class="col-txt" style="width:120px">Ticker</th><th class="col-txt" style="width:200px">Company</th><th class="col-txt" style="width:50px">Currency</th>'
    +'<th>PB1</th><th>PB2</th><th>S1</th><th>S2</th><th>S3</th><th>S4</th>'
    +'<th class="col-txt">Filter Status</th></tr></thead><tbody>';

  for(var j=0;j<invs.length;j++){
    var inv=invs[j];
    var p=priceMap[inv.ticker];
    var f=filterMap[inv.ticker];
    var tradeCells="";
    var TRADE_SLOTS=6;
    for(var k=0;k<TRADE_SLOTS;k++){
      if(k<inv.trades.length){
        var t2=inv.trades[k];
        var cls=t2.status==="planned"?"neutral":t2.status==="open"?"pass":"amber";
        tradeCells+='<td class="'+cls+'" style="text-align:center">'+t2.status.charAt(0).toUpperCase()+'</td>';
      } else {
        tradeCells+='<td class="neutral" style="text-align:center">&mdash;</td>';
      }
    }
    var fStatus="&mdash;";
    if(f){
      var stages=[];
      if(f.probing_bet.stage)stages.push("PB:"+f.probing_bet.stage);
      if(f.mm99.stage)stages.push("MM:"+f.mm99.stage);
      if(f.uptrend_retest.stage)stages.push("UTR:"+f.uptrend_retest.stage);
      if(f.basing_plateau.stage)stages.push("BP:"+f.basing_plateau.stage);
      fStatus=stages.length>0?stages.join(" | "):"None qualifying";
    }
    h+='<tr onclick="openChart(\''+inv.ticker+'\')" style="cursor:pointer">'
      +'<td class="col-txt" style="font-weight:600;color:var(--text-bright)">'+inv.ticker+'</td>'
      +'<td class="col-txt">'+inv.name+'</td><td class="col-txt">'+inv.currency+'</td>'
      +tradeCells
      +'<td class="col-txt" style="font-size:11px">'+fStatus+'</td></tr>';
  }
  h+='</tbody></table></div>';
  container.innerHTML=h;
}

// ================================================================
// SSEM TAB
// ================================================================
function renderSSEM(){
  buildHeaderControls("ssem");
  var container=document.getElementById("tab-ssem");
  if(!D.ssem){
    container.innerHTML='<div class="summary-tile" style="text-align:center;padding:40px"><h3>SSEM</h3><p style="color:var(--text-dim);margin-top:8px">factset-ssem.json not loaded.</p></div>';
    return;
  }
  var allRows=baseRows();
  var rows=[];
  for(var j=0;j<allRows.length;j++){
    var r=allRows[j];
    var ss=D.ssem[r.ticker];
    if(!ss)continue;
    r.eps_1m=ss.eps_rev?ss.eps_rev.L1M:null;r.eps_3m=ss.eps_rev?ss.eps_rev.L3M:null;
    r.eps_6m=ss.eps_rev?ss.eps_rev.L6M:null;r.eps_12m=ss.eps_rev?ss.eps_rev.L12M:null;
    r.ebitda_1m=ss.ebitda_rev?ss.ebitda_rev.L1M:null;r.ebitda_3m=ss.ebitda_rev?ss.ebitda_rev.L3M:null;
    r.ebitda_6m=ss.ebitda_rev?ss.ebitda_rev.L6M:null;r.ebitda_12m=ss.ebitda_rev?ss.ebitda_rev.L12M:null;
    r.sales_1m=ss.sales_rev?ss.sales_rev.L1M:null;r.sales_3m=ss.sales_rev?ss.sales_rev.L3M:null;
    r.sales_6m=ss.sales_rev?ss.sales_rev.L6M:null;r.sales_12m=ss.sales_rev?ss.sales_rev.L12M:null;
    r.tp_1m=ss.tp_rev?ss.tp_rev.L1M:null;r.tp_3m=ss.tp_rev?ss.tp_rev.L3M:null;
    r.tp_6m=ss.tp_rev?ss.tp_rev.L6M:null;r.tp_12m=ss.tp_rev?ss.tp_rev.L12M:null;
    r.buy_1m=ss.buy_rev?ss.buy_rev.L1M:null;r.buy_3m=ss.buy_rev?ss.buy_rev.L3M:null;
    r.buy_6m=ss.buy_rev?ss.buy_rev.L6M:null;r.buy_12m=ss.buy_rev?ss.buy_rev.L12M:null;
    r.buy_pct=ss.buy_pct;
    r.momentum=ss.momentum!=null?ss.momentum:null;
    rows.push(r);
  }
  rows=sortData(rows,currentSort.col,currentSort.dir);
  var totalCount=allRows.length;

  var highMom=0,midMom=0;
  for(var j=0;j<rows.length;j++){if(rows[j].momentum!=null&&rows[j].momentum>=7)highMom++;if(rows[j].momentum!=null&&rows[j].momentum>=5)midMom++}
  var h='<div class="summary-tile" id="section-summary"><h3>SSEM &mdash; Sell-Side Earnings Momentum</h3>'
    +'<div class="sub">Consensus revision % by metric and look-back period. Momentum = composite count.</div>'
    +'<div class="summary-stats">'+sumStat("Stocks",xyFmt(rows.length,totalCount))+sumStat("Mom &ge;7",xyFmt(highMom,rows.length),"green")+sumStat("Mom &ge;5",xyFmt(midMom,rows.length),"amber")+'</div></div>';

  h+=buildIndSecTables(rows,null);

  h+=buildPortfolioTile(currentTab);
  rows=applyIndSecFilter(rows);
  h+='<h3 class="qualified-title" id="section-stocks">Qualified Stocks ('+xyFmt(rows.length,totalCount)+')</h3>';

  // FIX-4: Group header row for SSEM
  h+='<div class="data-table-wrap"><table class="data-table"><thead>';
  h+='<tr class="group-header-row">';
  h+='<th colspan="3"></th>';
  h+='<th colspan="4" style="background:rgba(50,150,50,0.08)">EPS Revisions</th>';
  h+='<th colspan="4" style="background:rgba(50,100,200,0.08)">EBITDA Revisions</th>';
  h+='<th colspan="4" style="background:rgba(200,150,0,0.08)">Sales Revisions</th>';
  h+='<th colspan="4" style="background:rgba(120,80,200,0.08)">Target Price</th>';
  h+='<th colspan="2" style="background:rgba(200,50,50,0.08)">Buy Rating</th>';
  h+='<th></th>';
  h+='</tr>';
  h+='<tr class="col-header-row">';
  h+=th("Ticker","_display_name","col-txt col-identity","","width:120px")+th("Sector","_tax_sector","col-txt col-identity","","width:200px")+th("Price","price","col-num col-price","","width:52px")
    +th("EPS 1M","eps_1m","col-num col-filter grp-eps-first")+th("EPS 3M","eps_3m","col-num col-filter")+th("EPS 6M","eps_6m","col-num col-filter")+th("EPS 12M","eps_12m","col-num col-filter grp-eps-last")
    +th("EBITDA 1M","ebitda_1m","col-num col-filter grp-ebitda-first")+th("EBITDA 3M","ebitda_3m","col-num col-filter")+th("EBITDA 6M","ebitda_6m","col-num col-filter")+th("EBITDA 12M","ebitda_12m","col-num col-filter grp-ebitda-last")
    +th("Sales 1M","sales_1m","col-num col-filter grp-sales-first")+th("Sales 3M","sales_3m","col-num col-filter")+th("Sales 6M","sales_6m","col-num col-filter")+th("Sales 12M","sales_12m","col-num col-filter grp-sales-last")
    +th("TP 1M","tp_1m","col-num col-filter grp-tp-first")+th("TP 3M","tp_3m","col-num col-filter")+th("TP 6M","tp_6m","col-num col-filter")+th("TP 12M","tp_12m","col-num col-filter grp-tp-last")
    +th("% Buy","buy_pct","col-num col-filter grp-buy-first")+th("Buy L6M","buy_6m","col-num col-filter grp-buy-last")
    +th("Momentum","momentum","col-num col-green");
  h+='</tr></thead><tbody>';
  for(var j=0;j<rows.length;j++){
    var r=rows[j];
    var tax=getTaxonomy(r.ticker);
    var dn=(displayMode==="company")?(r.company||r.ticker):r.ticker;
    h+='<tr onclick="openChart(\''+r.ticker+'\')" style="cursor:pointer">'
      +'<td class="col-txt col-identity" style="font-weight:600;color:var(--text-bright)">'+dn+'</td>'
      +'<td class="col-txt col-identity" style="font-size:11px">'+tax.sector+'</td>'
      +'<td class="col-num col-price">'+fp(r.price)+'</td>';
    h+='<td class="col-num col-filter grp-eps-first '+revClass(r.eps_1m)+'">'+fpcRaw(r.eps_1m)+'</td>';
    h+='<td class="col-num col-filter '+revClass(r.eps_3m)+'">'+fpcRaw(r.eps_3m)+'</td>';
    h+='<td class="col-num col-filter '+revClass(r.eps_6m)+'">'+fpcRaw(r.eps_6m)+'</td>';
    h+='<td class="col-num col-filter grp-eps-last '+revClass(r.eps_12m)+'">'+fpcRaw(r.eps_12m)+'</td>';
    h+='<td class="col-num col-filter grp-ebitda-first '+revClass(r.ebitda_1m)+'">'+fpcRaw(r.ebitda_1m)+'</td>';
    h+='<td class="col-num col-filter '+revClass(r.ebitda_3m)+'">'+fpcRaw(r.ebitda_3m)+'</td>';
    h+='<td class="col-num col-filter '+revClass(r.ebitda_6m)+'">'+fpcRaw(r.ebitda_6m)+'</td>';
    h+='<td class="col-num col-filter grp-ebitda-last '+revClass(r.ebitda_12m)+'">'+fpcRaw(r.ebitda_12m)+'</td>';
    h+='<td class="col-num col-filter grp-sales-first '+revClass(r.sales_1m)+'">'+fpcRaw(r.sales_1m)+'</td>';
    h+='<td class="col-num col-filter '+revClass(r.sales_3m)+'">'+fpcRaw(r.sales_3m)+'</td>';
    h+='<td class="col-num col-filter '+revClass(r.sales_6m)+'">'+fpcRaw(r.sales_6m)+'</td>';
    h+='<td class="col-num col-filter grp-sales-last '+revClass(r.sales_12m)+'">'+fpcRaw(r.sales_12m)+'</td>';
    h+='<td class="col-num col-filter grp-tp-first '+revClass(r.tp_1m)+'">'+fpcRaw(r.tp_1m)+'</td>';
    h+='<td class="col-num col-filter '+revClass(r.tp_3m)+'">'+fpcRaw(r.tp_3m)+'</td>';
    h+='<td class="col-num col-filter '+revClass(r.tp_6m)+'">'+fpcRaw(r.tp_6m)+'</td>';
    h+='<td class="col-num col-filter grp-tp-last '+revClass(r.tp_12m)+'">'+fpcRaw(r.tp_12m)+'</td>';
    h+='<td class="col-num col-filter grp-buy-first '+(r.buy_pct!=null&&r.buy_pct>=70?"pass":r.buy_pct!=null&&r.buy_pct>=40?"amber":"fail")+'">'+(r.buy_pct!=null?nf(r.buy_pct)+"%":"&mdash;")+'</td>';
    h+='<td class="col-num col-filter grp-buy-last '+revClass(r.buy_6m)+'">'+(r.buy_6m!=null?fpcRaw(r.buy_6m):"&mdash;")+'</td>';
    var momCls=r.momentum>=7?"pass":r.momentum>=5?"amber":r.momentum>=3?"":"fail";
    h+='<td class="col-num col-green '+momCls+'" style="font-weight:700">'+nf(r.momentum)+'</td>';
    h+='</tr>';
  }
  h+='</tbody></table></div>';
  container.innerHTML=h;
}

// ================================================================
// VALUATION TAB
// ================================================================
function renderVal(){
  buildHeaderControls("val");
  var container=document.getElementById("tab-val");
  if(!D.valuation){
    container.innerHTML='<div class="summary-tile" style="text-align:center;padding:40px"><h3>Valuation</h3><p style="color:var(--text-dim);margin-top:8px">factset-valuation.json not loaded.</p></div>';
    return;
  }
  var allRows=baseRows();
  var rows=[];
  for(var j=0;j<allRows.length;j++){
    var r=allRows[j];
    var vl=D.valuation[r.ticker];
    if(!vl)continue;
    r.pe_cur=vl.pe_current;r.pe_pctile=vl.pe_percentile;
    r.pe_10y_lo=vl.pe_10y_low;r.pe_10y_hi=vl.pe_10y_high;
    r.eps_24mf=vl.eps_24mf!=null?vl.eps_24mf:null;
    rows.push(r);
  }
  rows=sortData(rows,currentSort.col,currentSort.dir);
  var totalCount=allRows.length;

  var cheap=0,mid=0;
  for(var j=0;j<rows.length;j++){if(rows[j].pe_pctile!=null&&rows[j].pe_pctile<=25)cheap++;if(rows[j].pe_pctile!=null&&rows[j].pe_pctile<=50)mid++}

  var h='<div class="summary-tile" id="section-summary"><h3>Valuation &mdash; P/E Multiples &amp; History</h3>'
    +'<div class="sub">P/E: current, 10Y range (range bar: green=below median, red=above), percentile (0=cheapest, 100=most expensive), EPS 24MF.</div>'
    +'<div class="summary-stats">'+sumStat("Stocks",xyFmt(rows.length,totalCount))+sumStat("P/E &le;25th pctile",xyFmt(cheap,rows.length),"green")+sumStat("P/E &le;50th pctile",xyFmt(mid,rows.length),"amber")+'</div></div>';

  h+=buildIndSecTables(rows,null);

  h+=buildPortfolioTile(currentTab);
  rows=applyIndSecFilter(rows);
  h+='<h3 class="qualified-title" id="section-stocks">Qualified Stocks ('+xyFmt(rows.length,totalCount)+')</h3>';
  h+='<div class="data-table-wrap"><table class="data-table"><thead>';
  h+='<tr class="group-header-row">';
  h+='<th colspan="3"></th>';
  h+='<th colspan="4" style="background:rgba(50,150,50,0.08)">P/E Valuation</th>';
  h+='</tr>';
  h+='<tr class="col-header-row">';
  h+=th("Ticker","_display_name","col-txt col-identity","","width:120px")+th("Sector","_tax_sector","col-txt col-identity","","width:200px")+th("Price","price","col-num col-price","","width:52px")
    +th("P/E","pe_cur","col-num col-filter grp-pe-first")+th("P/E Pctile","pe_pctile","col-num col-filter")+'<th class="col-filter">P/E 10Y Range</th>'
    +th("EPS 24MF","eps_24mf","col-num col-filter grp-pe-last");
  h+='</tr></thead><tbody>';

  for(var j=0;j<rows.length;j++){
    var r=rows[j];
    var tax=getTaxonomy(r.ticker);
    var dn=(displayMode==="company")?(r.company||r.ticker):r.ticker;
    h+='<tr onclick="openChart(\''+r.ticker+'\')" style="cursor:pointer">'
      +'<td class="col-txt col-identity" style="font-weight:600;color:var(--text-bright)">'+dn+'</td>'
      +'<td class="col-txt col-identity" style="font-size:11px">'+tax.sector+'</td>'
      +'<td class="col-num col-price">'+fp(r.price)+'</td>';
    h+='<td class="col-num col-filter grp-pe-first" style="font-weight:600">'+nf(r.pe_cur,1)+'</td>';
    h+='<td class="col-num col-filter '+pctileClass(r.pe_pctile)+'" style="font-weight:600">'+nf(r.pe_pctile)+'</td>';
    h+='<td class="range-bar-cell">'+buildRangeBar(r.pe_10y_lo,r.pe_10y_hi,r.pe_cur)+'</td>';
    h+='<td class="col-num col-filter grp-pe-last">'+nf(r.eps_24mf,2)+'</td>';
    h+='</tr>';
  }
  h+='</tbody></table></div>';
  container.innerHTML=h;
}
// ================================================================
// TAB ROUTER
// ================================================================
function renderPlaceholder(id,title){
  var c=document.getElementById("tab-"+id);
  if(c)c.innerHTML='<div class="summary-tile" style="text-align:center;padding:40px"><h3>'+title+'</h3><p style="color:var(--text-dim);margin-top:8px">Pending &mdash; requires FactSet data or qualitative ratings (Phase 4+)</p></div>';
}


// FEAT-5: Update industry/sector filter pills
function updateIndSecPills(){
  var el=document.getElementById("indsec-pills");
  if(el)el.innerHTML=indSecFilterPills();
  // Highlight sector/industry columns when filter active
  var tables=document.querySelectorAll("table.data-table");
  for(var t=0;t<tables.length;t++){
    if(hasIndSecFilter())tables[t].classList.add("ind-sec-highlight");
    else tables[t].classList.remove("ind-sec-highlight");
  }
}
function renderTab(id){
  try{
  if(id==="mm99")renderMM99();
  else if(id==="bp")renderBP();
  else if(id==="pb")renderPB();
  else if(id==="utr")renderUTR();
  else if(id==="vcp")renderVCP();
  else if(id==="tech")renderTech();
  else if(id==="combos")renderCombos();
  else if(id==="positions")renderPositions();
  else if(id==="ssem")renderSSEM();
  else if(id==="val")renderVal();
  else{
    buildHeaderControls(id);
    for(var j=0;j<TAB_IDS.length;j++){if(TAB_IDS[j]===id){renderPlaceholder(id,TAB_LABELS[j]);updateIndSecPills();return}}
    renderPlaceholder(id,id);
  }
  }catch(e){console.error("renderTab("+id+") error:",e)}
  updateIndSecPills();
}

// Init: hide ratings by default (FIX-3)
var mainEl=document.querySelector(".main");
if(mainEl)mainEl.classList.add("ratings-hidden");

renderTab("mm99");
})();
"""

    html = (
        '<!DOCTYPE html>\n'
        '<html lang="en">\n'
        '<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        '<title>Master Dashboard &mdash; Viewforth</title>\n'
        '<style>\n'
        + css +
        '\n</style>\n'
        '</head>\n'
        '<body>\n'
        '<div class="header">\n'
        '  <!-- FIX-5 Row 1: Title + stats + Key + Chart -->\n'
        '  <div class="header-top">\n'
        '    <div class="header-title">Master Dashboard</div>\n'
        '    <div class="header-stats">\n'
        '      <span>Stocks: <span class="stat-value" id="stat-count">&mdash;</span></span>\n'
        '      <span>Data: <span class="stat-value" id="stat-source">&mdash;</span></span>\n'
        '      <span>Updated: <span class="stat-value" id="stat-updated">&mdash;</span></span>\n'
        '    </div>\n'
        '    <div class="header-right-btns">\n'
        '      <button class="ctrl-btn" onclick="openKey()">Key</button>\n'
        '      <button class="ctrl-btn" onclick="openChart(\'Overview\')">Chart</button>\n'
        '    </div>\n'
        '  </div>\n'
        '  <!-- FIX-5 Row 2: TABS label + tab navigation -->\n'
        '  <div class="header-tabs-row">\n'
        '    <span class="row-label">Tabs</span>\n'
        '    <div class="tab-nav">' + tab_buttons + '</div>\n'
        '  </div>\n'
        '  <!-- Row 3: Toggles + Filters -->\n'
        '  <div class="header-controls-row">\n'
        '    <span class="row-label">Toggles</span>\n'
        '    <button class="ctrl-btn" id="btn-display-mode" onclick="toggleDisplayMode()">Ticker</button>\n'
        '    <button class="ctrl-btn" id="btn-value-mode" onclick="toggleValueMode()">&#10003;&#10007;</button>\n'
        '    <button class="ctrl-btn" id="btn-ratings" onclick="toggleRatings()">Show case ratings</button><span id="indsec-pills"></span>\n'
        '    <span style="border-left:1px solid var(--border);height:20px;margin:0 8px"></span>\n'
        '    <span class="row-label" id="toggles-label">MM 99 Filters</span>\n'
        '    <div id="header-tab-controls"></div>\n'
        '    <div class="anchor-links">\n'
        '      <span class="row-label" style="font-size:10px;margin-right:4px">Jump to</span>\n'
        '      <a class="anchor-link" onclick="scrollToSection(\'section-summary\')">Summary</a>\n'
        '      <a class="anchor-link" onclick="scrollToSection(\'section-industries\')">Industries</a>\n'
        '      <a class="anchor-link" onclick="scrollToSection(\'section-sectors\')">Sectors</a>\n'
        '      <a class="anchor-link" onclick="scrollToSection(\'section-portfolio\')">Live Portfolio</a>\n'
        '      <a class="anchor-link" onclick="scrollToSection(\'section-stocks\')">Qualified Stocks</a>\n'
        '      <span id="group-links"></span>\n'
        '    </div>\n'
        '  </div>\n'
        '</div>\n'
        '<!-- FIX-1: Key panel overlay -->\n'
        '<div class="key-panel" id="key-panel"></div>\n'
        '<div class="main ratings-hidden">' + tab_containers + '</div>\n'
        '<div class="chart-panel" id="chart-panel">\n'
        '  <div id="chart-container" style="width:100%;min-height:calc(100vh - 200px)">Click a stock row to view chart</div>\n'
        '</div>\n'
        '<script>/* DATA_INJECTION_POINT */</script>\n'
        '<script>\n'
        + js +
        '\n</script>\n'
        '</body>\n'
        '</html>'
    )

    return html


def main():
    print("Loading data...")
    data_js = load_data()
    print("  Data JS: {:,} bytes".format(len(data_js)))

    # Auto-backup existing index.html before writing
    if OUTPUT_PATH.exists():
        backup_dir = PROJECT_DIR / "backups"
        backup_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        backup_path = backup_dir / "index_{}.html".format(ts)
        shutil.copy2(OUTPUT_PATH, backup_path)
        print("  Pre-write backup: {}".format(backup_path))

    print("Building HTML...")
    html = build_html(data_js)
    html = html.replace("/* DATA_INJECTION_POINT */", data_js)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    size = os.path.getsize(OUTPUT_PATH)
    print("  Written: {} ({:,} bytes)".format(OUTPUT_PATH, size))

    # Post-write backup
    backup_dir = PROJECT_DIR / "backups"
    backup_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    backup_path = backup_dir / "index_post_{}.html".format(ts)
    shutil.copy2(OUTPUT_PATH, backup_path)
    print("  Post-write backup: {}".format(backup_path))
    print("Done.")


if __name__ == "__main__":
    main()
