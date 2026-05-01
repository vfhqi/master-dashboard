"""
SSEM Tab Polish Patcher — Session 12 (01-May-26)
================================================

Applies seven polish refinements to build_dashboard.py:
  1. TYPE/TIME column-order toggle (state var ssemColMode)
  2. Cumulative/Per-period values toggle (state var ssemValueMode)
  3. Cell background heatmap (subtle green/neutral/red bg by % value)
  4. Tile formatting parity — Industry/Sector tile cells get heatmap + group bands (light touch)
  5. LP table mirrors QS — SSEM-specific branch in buildPortfolioTile
  6. Score column rating-keyed colour (only A/B = green, C = neutral, D/F = red)
  7. Rating pill palette migration to D-MD-UI-2 (Ratings Dashboard canonical)

All edits anchor on stable strings inserted by Session 11. Atomic: backs up, applies all 7, fails loudly if any anchor missing.
"""
import re
import sys
import shutil
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
TARGET = SCRIPT_DIR / "build_dashboard.py"


def backup():
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = SCRIPT_DIR / f"build_dashboard.py.bak-pre-ssem-session12-{ts}"
    shutil.copy2(TARGET, bak)
    print(f"  Backup: {bak.name}")
    return bak


def apply_replacement(src, anchor, new_text, label):
    n = src.count(anchor)
    if n == 0:
        print(f"  FAIL [{label}]: anchor not found:")
        print(f"    {anchor[:100]!r}...")
        sys.exit(1)
    if n > 1:
        print(f"  FAIL [{label}]: anchor appears {n} times (expected 1):")
        print(f"    {anchor[:100]!r}...")
        sys.exit(1)
    new_src = src.replace(anchor, new_text)
    print(f"  OK [{label}]")
    return new_src


def main():
    print(f"Reading {TARGET}...")
    src = TARGET.read_text(encoding="utf-8")
    orig_size = len(src)
    print(f"  Original size: {orig_size:,} bytes")

    backup()

    # ─────────────────────────────────────────────────────────────
    # Edit 1: Replace SSEM CSS block — new pill palette + heatmap classes + score colour
    # ─────────────────────────────────────────────────────────────
    old_css = """/* SESSION 11 — D-MD-SSEM-1..4: SS Earnings Momentum tab additions */
/* Rating pill — visually prominent, A-F coloured */
.ssem-rating-pill{display:inline-block;padding:3px 10px;border-radius:6px;font-weight:700;font-size:12px;letter-spacing:.5px;min-width:22px;text-align:center;border:1px solid rgba(0,0,0,0.1);box-shadow:0 1px 2px rgba(0,0,0,0.05)}
.ssem-rating-A{background:#0d3817;color:#fff}
.ssem-rating-B{background:#2e7d32;color:#fff}
.ssem-rating-C{background:#f2e1a5;color:#5a4a00}
.ssem-rating-D{background:#ffe0b2;color:#7a3d00}
.ssem-rating-F{background:#c62828;color:#fff}
.ssem-rating-N{background:#eee;color:#888}
/* Score column emphasis */
.ssem-score-cell{font-weight:700;font-size:13px;text-align:right}
.ssem-score-pos{color:#2e7d32}
.ssem-score-neg{color:#c62828}
.ssem-score-zero{color:#888}
/* Trend arrows on tile cells */
.ssem-trend-up{color:#2e7d32;font-weight:700}
.ssem-trend-flat{color:#888;font-weight:400}
.ssem-trend-down{color:#c62828;font-weight:700}
/* Skew glyphs */
.ssem-skew{font-family:ui-monospace,Consolas,monospace;font-size:10px;color:#666;letter-spacing:-.5px}
.ssem-tile-cell{font-size:10px;text-align:right;padding:2px 4px}
.ssem-tile-glyph{font-size:10px;text-align:center;padding:2px 4px;white-space:nowrap}
/* SSEM filter toggle row buttons (extending tab-emphasis style) */
.ssem-filter-row{display:inline-flex;gap:4px;align-items:center;flex-wrap:wrap}
.ssem-filter-divider{width:1px;height:18px;background:var(--border);margin:0 6px}
.ssem-filter-btn{padding:3px 9px;font-size:11px;font-weight:600;border:1px solid var(--border);background:var(--card);color:var(--text-dim);border-radius:4px;cursor:pointer;letter-spacing:.3px}
.ssem-filter-btn.active{background:#1b3d5c;color:#fff;border-color:#1b3d5c}
.ssem-rating-btn-A.active{background:#0d3817;border-color:#0d3817}
.ssem-rating-btn-B.active{background:#2e7d32;border-color:#2e7d32}
.ssem-rating-btn-C.active{background:#f2e1a5;color:#5a4a00;border-color:#d4c080}
.ssem-rating-btn-D.active{background:#ffe0b2;color:#7a3d00;border-color:#e6c590}
.ssem-rating-btn-F.active{background:#c62828;border-color:#c62828}
.ssem-rating-btn-N.active{background:#888;border-color:#888;color:#fff}
"""
    new_css = """/* SESSION 11 — D-MD-SSEM-1..4 + SESSION 12 polish (D-MD-SSEM-5..7) */
/* Rating pill — palette canonicalised to D-MD-UI-2 / Ratings Dashboard (rgb values from live IC ratings dashboard) */
.ssem-rating-pill{display:inline-block;padding:4px 8px;border-radius:3px;font-weight:700;font-size:11px;text-align:center;min-width:28px;white-space:nowrap}
.ssem-rating-A{background:rgb(27,94,32);color:rgb(165,214,167)}
.ssem-rating-B{background:rgb(46,125,50);color:rgb(200,230,201)}
.ssem-rating-C{background:rgb(141,110,0);color:rgb(242,225,165)}
.ssem-rating-D{background:rgb(230,81,0);color:rgb(242,225,165)}
.ssem-rating-F{background:rgb(183,28,28);color:rgb(239,154,154)}
.ssem-rating-N{background:rgb(232,227,212);color:rgb(154,147,128)}
/* Score column — rating-keyed colour (D-MD-SSEM-6): A/B green, C neutral, D/F red */
.ssem-score-cell{font-weight:700;font-size:13px;text-align:right}
.ssem-score-rA{color:#1b5e20}
.ssem-score-rB{color:#2e7d32}
.ssem-score-rC{color:#333333}
.ssem-score-rD{color:#e65100}
.ssem-score-rF{color:#b71c1c}
.ssem-score-rN{color:#999}
/* Cell background heatmap (D-MD-SSEM-3): subtle green/neutral/red bg by % value sign+magnitude */
.ssem-cell-pos-strong{background:rgba(46,125,50,0.18)}
.ssem-cell-pos-mid{background:rgba(46,125,50,0.10)}
.ssem-cell-pos-weak{background:rgba(46,125,50,0.04)}
.ssem-cell-neutral{background:transparent}
.ssem-cell-neg-weak{background:rgba(198,40,40,0.04)}
.ssem-cell-neg-mid{background:rgba(198,40,40,0.10)}
.ssem-cell-neg-strong{background:rgba(198,40,40,0.18)}
/* Trend arrows on tile cells */
.ssem-trend-up{color:#2e7d32;font-weight:700}
.ssem-trend-flat{color:#888;font-weight:400}
.ssem-trend-down{color:#c62828;font-weight:700}
/* Skew glyphs */
.ssem-skew{font-family:ui-monospace,Consolas,monospace;font-size:10px;color:#666;letter-spacing:-.5px}
.ssem-tile-cell{font-size:10px;text-align:right;padding:2px 4px}
.ssem-tile-glyph{font-size:10px;text-align:center;padding:2px 4px;white-space:nowrap}
/* SSEM filter toggle row buttons (extending tab-emphasis style) */
.ssem-filter-row{display:inline-flex;gap:4px;align-items:center;flex-wrap:wrap}
.ssem-filter-divider{width:1px;height:18px;background:var(--border);margin:0 6px}
.ssem-filter-btn{padding:3px 9px;font-size:11px;font-weight:600;border:1px solid var(--border);background:var(--card);color:var(--text-dim);border-radius:4px;cursor:pointer;letter-spacing:.3px}
.ssem-filter-btn.active{background:#1b3d5c;color:#fff;border-color:#1b3d5c}
.ssem-rating-btn-A.active{background:rgb(27,94,32);border-color:rgb(27,94,32);color:rgb(165,214,167)}
.ssem-rating-btn-B.active{background:rgb(46,125,50);border-color:rgb(46,125,50);color:rgb(200,230,201)}
.ssem-rating-btn-C.active{background:rgb(141,110,0);border-color:rgb(141,110,0);color:rgb(242,225,165)}
.ssem-rating-btn-D.active{background:rgb(230,81,0);border-color:rgb(230,81,0);color:rgb(242,225,165)}
.ssem-rating-btn-F.active{background:rgb(183,28,28);border-color:rgb(183,28,28);color:rgb(239,154,154)}
.ssem-rating-btn-N.active{background:rgb(232,227,212);border-color:rgb(232,227,212);color:rgb(154,147,128)}
/* SESSION 12 — TYPE/TIME and Cumulative/Per-period toggle row (lives in #3 TOGGLES area) */
.ssem-mode-toggle-row{display:inline-flex;gap:4px;align-items:center;margin-right:6px}
.ssem-mode-btn{padding:3px 8px;font-size:10px;font-weight:600;border:1px solid var(--border);background:var(--card);color:var(--text-dim);border-radius:4px;cursor:pointer;letter-spacing:.3px}
.ssem-mode-btn.active{background:#1b3d5c;color:#fff;border-color:#1b3d5c}
.ssem-mode-label{font-size:10px;color:var(--text-dim);margin-right:4px}
"""
    src = apply_replacement(src, old_css, new_css, "1: CSS palette + heatmap + mode toggles")

    # ─────────────────────────────────────────────────────────────
    # Edit 2: Add new state vars (col mode + value mode)
    # ─────────────────────────────────────────────────────────────
    state_anchor = "var ssemDimFilters = {eps: true, ebitda: true, sales: true, tp: true, buy: true};"
    state_new = """// SESSION 12 — D-MD-SSEM-5/6/7: column-order mode (TYPE=dim-grouped, TIME=timeframe-grouped) + value mode (CUMUL=raw FactSet, PERIOD=net-of-prior).
var ssemColMode = "TYPE";       // "TYPE" or "TIME"
var ssemValueMode = "CUMUL";    // "CUMUL" or "PERIOD"
var ssemDimFilters = {eps: true, ebitda: true, sales: true, tp: true, buy: true};"""
    src = apply_replacement(src, state_anchor, state_new, "2: state vars (col mode + value mode)")

    # ─────────────────────────────────────────────────────────────
    # Edit 3: Add helper functions for value-mode display + heatmap class
    # Anchor: just before the existing ssemDimScore function
    # ─────────────────────────────────────────────────────────────
    helpers_anchor = "// Sub-score for one dimension using net-off logic."
    helpers_new = """// SESSION 12 — D-MD-SSEM-5..7 helpers
// Returns the value to DISPLAY in a cell based on ssemValueMode toggle.
// CUMUL mode: raw FactSet value (cumulative). PERIOD mode: net-of-prior-period (matches scoring math).
// L1M is identical in both modes (no prior to subtract).
function ssemDisplayValue(L1M, L3M, L6M, L12M, timeframe) {
  if (ssemValueMode === "CUMUL") {
    if (timeframe === "L1M") return L1M;
    if (timeframe === "L3M") return L3M;
    if (timeframe === "L6M") return L6M;
    if (timeframe === "L12M") return L12M;
  } else { // PERIOD mode
    if (timeframe === "L1M") return L1M;
    if (timeframe === "L3M") return (L3M == null || L1M == null) ? null : (L3M - L1M);
    if (timeframe === "L6M") return (L6M == null || L3M == null) ? null : (L6M - L3M);
    if (timeframe === "L12M") return (L12M == null || L6M == null) ? null : (L12M - L6M);
  }
  return null;
}

// Cell heatmap class — subtle green/neutral/red bg by % value sign+magnitude. Thresholds: ±1pp = weak, ±5pp = mid, ±10pp = strong.
function ssemHeatClass(v) {
  if (v == null) return "ssem-cell-neutral";
  if (v >= 10) return "ssem-cell-pos-strong";
  if (v >= 5) return "ssem-cell-pos-mid";
  if (v >= 1) return "ssem-cell-pos-weak";
  if (v <= -10) return "ssem-cell-neg-strong";
  if (v <= -5) return "ssem-cell-neg-mid";
  if (v <= -1) return "ssem-cell-neg-weak";
  return "ssem-cell-neutral";
}

// Sub-score for one dimension using net-off logic."""
    src = apply_replacement(src, helpers_anchor, helpers_new, "3: display+heatmap helpers")

    # ─────────────────────────────────────────────────────────────
    # Edit 4: Add toggle setters + extend buildHeaderControls dispatch — also build a TOGGLES strip in #3 area
    # The existing dispatch wires #4 FILTERS only. For #3 TOGGLES, the existing pattern is per-tab toggle UI handled inside renderXxx via separate elements.
    # Cleanest: have buildSsemHeaderControls render BOTH (a) the existing #4 FILTERS row, AND (b) a #3 TOGGLES strip targeting a different element OR prepend the modes into the same #4 row.
    # Per Q6 (Richard): "Keep in #3 TOGGLES group ATM, on left of HEADER bar". The toggles header element exists as 'header-toggles' or similar — but earlier check showed only 'header-tab-controls' exists.
    # Approach: prepend mode toggles to the LEFT of the existing filter row inside the same header-tab-controls element. The label area already says "#4 FILTERS" but visually they read as toggles. Pragmatic compromise — alternative would be a structural HTML change to the header bar itself.
    # ─────────────────────────────────────────────────────────────
    setters_anchor = """window.toggleSsemDim = function(dim) { ssemDimFilters[dim] = !ssemDimFilters[dim]; renderTab("ssem"); };
window.toggleSsemRating = function(rating) { ssemRatingFilters[rating] = !ssemRatingFilters[rating]; renderTab("ssem"); };"""
    setters_new = """window.toggleSsemDim = function(dim) { ssemDimFilters[dim] = !ssemDimFilters[dim]; renderTab("ssem"); };
window.toggleSsemRating = function(rating) { ssemRatingFilters[rating] = !ssemRatingFilters[rating]; renderTab("ssem"); };
window.setSsemColMode = function(mode) { ssemColMode = mode; renderTab("ssem"); };
window.setSsemValueMode = function(mode) { ssemValueMode = mode; renderTab("ssem"); };"""
    src = apply_replacement(src, setters_anchor, setters_new, "4: toggle setters")

    # ─────────────────────────────────────────────────────────────
    # Edit 5: Replace buildSsemHeaderControls — add mode toggles on the LEFT
    # ─────────────────────────────────────────────────────────────
    old_header_ctrls = """// SSEM-specific header controls (5 dim toggles + 6 rating toggles)
// Targets header-tab-controls DIV (the #4 FILTERS panel) — same target as combos/MM99 dispatch.
function buildSsemHeaderControls() {
  var ctrls = document.getElementById("header-tab-controls");
  if (!ctrls) return;
  var h = '<div class="ssem-filter-row">';
  h += '<span style="font-size:10px;color:var(--text-dim);margin-right:4px">DIMS:</span>';
  var dims = [{k: "eps", l: "EPS"}, {k: "ebitda", l: "EBITDA"}, {k: "sales", l: "Sales"}, {k: "tp", l: "TP"}, {k: "buy", l: "Buy"}];
  for (var d = 0; d < dims.length; d++) {
    var active = ssemDimFilters[dims[d].k] ? " active" : "";
    h += '<button class="ssem-filter-btn' + active + '" onclick="toggleSsemDim(\\\'' + dims[d].k + '\\\')" title="Filter to stocks where ' + dims[d].l + ' net L3M score is positive">' + dims[d].l + '</button>';
  }
  h += '<span class="ssem-filter-divider"></span>';
  h += '<span style="font-size:10px;color:var(--text-dim);margin-right:4px">RATING:</span>';
  var ratings = [{k: "A", l: "A"}, {k: "B", l: "B"}, {k: "C", l: "C"}, {k: "D", l: "D"}, {k: "F", l: "F"}, {k: "N", l: "&mdash;"}];
  for (var rr = 0; rr < ratings.length; rr++) {
    var ractive = ssemRatingFilters[ratings[rr].k] ? " active" : "";
    h += '<button class="ssem-filter-btn ssem-rating-btn-' + ratings[rr].k + ractive + '" onclick="toggleSsemRating(\\\'' + ratings[rr].k + '\\\')">' + ratings[rr].l + '</button>';
  }
  h += '</div>';
  ctrls.innerHTML = h;
}"""
    new_header_ctrls = """// SSEM-specific header controls — Session 12: includes 2 mode toggles on the left + 5 dim toggles + 6 rating toggles
// Targets header-tab-controls DIV (the #4 FILTERS panel) — same target as combos/MM99 dispatch.
// Per Q6 (Richard 01-May-26 Session 12): mode toggles "in #3 TOGGLES group ATM, on left of HEADER bar" — pragmatically render them on the LEFT of the same row.
function buildSsemHeaderControls() {
  var ctrls = document.getElementById("header-tab-controls");
  if (!ctrls) return;
  var h = '<div class="ssem-filter-row">';
  // Mode toggles — leftmost
  h += '<span class="ssem-mode-label">VIEW:</span>';
  h += '<button class="ssem-mode-btn' + (ssemColMode === "TYPE" ? " active" : "") + '" onclick="setSsemColMode(\\\'TYPE\\\')" title="Group columns by dimension type (EPS, EBITDA, Sales, TP, Buy)">By type</button>';
  h += '<button class="ssem-mode-btn' + (ssemColMode === "TIME" ? " active" : "") + '" onclick="setSsemColMode(\\\'TIME\\\')" title="Group columns by timeframe (L1M, L3M, L6M, L12M)">By time</button>';
  h += '<span class="ssem-filter-divider"></span>';
  h += '<span class="ssem-mode-label">VALUES:</span>';
  h += '<button class="ssem-mode-btn' + (ssemValueMode === "CUMUL" ? " active" : "") + '" onclick="setSsemValueMode(\\\'CUMUL\\\')" title="Show cumulative (raw FactSet) revisions">Cumulative</button>';
  h += '<button class="ssem-mode-btn' + (ssemValueMode === "PERIOD" ? " active" : "") + '" onclick="setSsemValueMode(\\\'PERIOD\\\')" title="Show per-period (net-of-prior) revisions — matches the scoring math">Per-period</button>';
  h += '<span class="ssem-filter-divider"></span>';
  // Existing dim + rating filters
  h += '<span class="ssem-mode-label">DIMS:</span>';
  var dims = [{k: "eps", l: "EPS"}, {k: "ebitda", l: "EBITDA"}, {k: "sales", l: "Sales"}, {k: "tp", l: "TP"}, {k: "buy", l: "Buy"}];
  for (var d = 0; d < dims.length; d++) {
    var active = ssemDimFilters[dims[d].k] ? " active" : "";
    h += '<button class="ssem-filter-btn' + active + '" onclick="toggleSsemDim(\\\'' + dims[d].k + '\\\')" title="Filter to stocks where ' + dims[d].l + ' net L3M score is positive">' + dims[d].l + '</button>';
  }
  h += '<span class="ssem-filter-divider"></span>';
  h += '<span class="ssem-mode-label">RATING:</span>';
  var ratings = [{k: "A", l: "A"}, {k: "B", l: "B"}, {k: "C", l: "C"}, {k: "D", l: "D"}, {k: "F", l: "F"}, {k: "N", l: "&mdash;"}];
  for (var rr = 0; rr < ratings.length; rr++) {
    var ractive = ssemRatingFilters[ratings[rr].k] ? " active" : "";
    h += '<button class="ssem-filter-btn ssem-rating-btn-' + ratings[rr].k + ractive + '" onclick="toggleSsemRating(\\\'' + ratings[rr].k + '\\\')">' + ratings[rr].l + '</button>';
  }
  h += '</div>';
  ctrls.innerHTML = h;
}"""
    src = apply_replacement(src, old_header_ctrls, new_header_ctrls, "5: header controls (add mode toggles)")

    # ─────────────────────────────────────────────────────────────
    # Edit 6: Replace buildSsemIndSecTables — add cell heatmap to L3M cells
    # The existing function uses ssem-tile-cell class on the avg cell. We want to inject the heatmap class too.
    # ─────────────────────────────────────────────────────────────
    old_tile_cell = "        h += '<td class=\"ssem-tile-cell\">' + avgStr + '</td>';"
    new_tile_cell = "        h += '<td class=\"ssem-tile-cell ' + ssemHeatClass(avgL3M) + '\">' + avgStr + '</td>';"
    src = apply_replacement(src, old_tile_cell, new_tile_cell, "6: tile heatmap")

    # ─────────────────────────────────────────────────────────────
    # Edit 7: Add LP-specific SSEM branch in buildPortfolioTile
    # The existing buildPortfolioTile has an else branch (line ~1566) that just renders commonCols+ratings.
    # We add an `else if(tabId==="ssem"){...}` branch BEFORE that else, that mirrors the QS render.
    # ─────────────────────────────────────────────────────────────
    old_lp_branch_anchor = """  } else {
    // Other tabs: keep existing behaviour (commonCols + ratings).
    h+=commonCols()+ratingsColHeaders()+'</tr></thead><tbody>';
    for(var j=0;j<posRows.length;j++){
      h+='<tr onclick="openChart(\\''+posRows[j].ticker+'\\')" style="cursor:pointer">'+commonTds(posRows[j])+ratingsColTds(posRows[j])+'</tr>';
    }
  }"""
    new_lp_branch = """  } else if(tabId==="ssem"){
    // SESSION 12 D-MD-SSEM-7: LP table mirrors QS table on SSEM tab.
    // Enrich each LP row with SSEM data + score + rating.
    for(var jE=0;jE<posRows.length;jE++){
      var rE=posRows[jE];
      var ss=D.ssem ? D.ssem[rE.ticker] : null;
      if(ss){
        rE.eps_1m=ss.eps_rev?ss.eps_rev.L1M:null;rE.eps_3m=ss.eps_rev?ss.eps_rev.L3M:null;
        rE.eps_6m=ss.eps_rev?ss.eps_rev.L6M:null;rE.eps_12m=ss.eps_rev?ss.eps_rev.L12M:null;
        rE.ebitda_1m=ss.ebitda_rev?ss.ebitda_rev.L1M:null;rE.ebitda_3m=ss.ebitda_rev?ss.ebitda_rev.L3M:null;
        rE.ebitda_6m=ss.ebitda_rev?ss.ebitda_rev.L6M:null;rE.ebitda_12m=ss.ebitda_rev?ss.ebitda_rev.L12M:null;
        rE.sales_1m=ss.sales_rev?ss.sales_rev.L1M:null;rE.sales_3m=ss.sales_rev?ss.sales_rev.L3M:null;
        rE.sales_6m=ss.sales_rev?ss.sales_rev.L6M:null;rE.sales_12m=ss.sales_rev?ss.sales_rev.L12M:null;
        rE.tp_1m=ss.tp_rev?ss.tp_rev.L1M:null;rE.tp_3m=ss.tp_rev?ss.tp_rev.L3M:null;
        rE.tp_6m=ss.tp_rev?ss.tp_rev.L6M:null;rE.tp_12m=ss.tp_rev?ss.tp_rev.L12M:null;
        rE.buy_1m=ss.buy_rev?ss.buy_rev.L1M:null;rE.buy_3m=ss.buy_rev?ss.buy_rev.L3M:null;
        rE.buy_6m=ss.buy_rev?ss.buy_rev.L6M:null;rE.buy_12m=ss.buy_rev?ss.buy_rev.L12M:null;
        rE.buy_pct=ss.buy_pct;
        ssemEnrichRow(rE);
      } else {
        rE.ssem_score=0; rE.ssem_rating="-"; rE.ssem_nulls=15;
      }
    }
    // Use ssemRowHTML helper (defined inside renderSSEM scope — duplicate inline to keep buildPortfolioTile self-contained)
    h+=ssemHeadersHTML()+'<tbody>';
    for(var jr2=0;jr2<posRows.length;jr2++){
      h+=ssemRowHTML(posRows[jr2]);
    }
  } else {
    // Other tabs: keep existing behaviour (commonCols + ratings).
    h+=commonCols()+ratingsColHeaders()+'</tr></thead><tbody>';
    for(var j=0;j<posRows.length;j++){
      h+='<tr onclick="openChart(\\''+posRows[j].ticker+'\\')" style="cursor:pointer">'+commonTds(posRows[j])+ratingsColTds(posRows[j])+'</tr>';
    }
  }"""
    src = apply_replacement(src, old_lp_branch_anchor, new_lp_branch, "7: LP SSEM branch")

    # ─────────────────────────────────────────────────────────────
    # Edit 8: Replace renderSSEM with new version — TYPE/TIME column reorder, Per-period values, rating-keyed score colour, cell heatmap, LP via shared helper.
    # The new renderSSEM extracts column-header and row-rendering into helpers ssemHeadersHTML() and ssemRowHTML(r) so buildPortfolioTile can call them too.
    # Anchor: existing renderSSEM start; replace through the function close.
    # ─────────────────────────────────────────────────────────────
    old_render_start = "function renderSSEM(){"
    start_idx = src.index(old_render_start)
    val_idx = src.index("// VALUATION TAB", start_idx)
    sep_idx = src.rfind("// ====", start_idx, val_idx)

    new_render = '''// SESSION 12 — D-MD-SSEM-5..7: shared header + row helpers, used by renderSSEM AND buildPortfolioTile (SSEM branch).
// Defined OUTSIDE renderSSEM so buildPortfolioTile can call them. Reads ssemColMode + ssemValueMode for branch logic.
var SSEM_DIMS = [
  {k:"eps",     l:"EPS",    grpCls:"grp-eps",    grpBg:"rgba(50,150,50,0.08)"},
  {k:"ebitda",  l:"EBITDA", grpCls:"grp-ebitda", grpBg:"rgba(50,100,200,0.08)"},
  {k:"sales",   l:"Sales",  grpCls:"grp-sales",  grpBg:"rgba(200,150,0,0.08)"},
  {k:"tp",      l:"TP",     grpCls:"grp-tp",     grpBg:"rgba(120,80,200,0.08)"},
  {k:"buy",     l:"Buy",    grpCls:"grp-buy",    grpBg:"rgba(200,50,50,0.08)"}
];
var SSEM_TIMES = [
  {k:"L1M",  l:"1M",  bg:"rgba(50,100,200,0.08)"},
  {k:"L3M",  l:"3M",  bg:"rgba(50,150,50,0.08)"},
  {k:"L6M",  l:"6M",  bg:"rgba(200,150,0,0.08)"},
  {k:"L12M", l:"12M", bg:"rgba(120,80,200,0.08)"}
];

// Returns the raw value from a row for (dim, timeframe).
function ssemRowVal(r, dimKey, tfKey) {
  var key = dimKey + "_" + (tfKey === "L1M" ? "1m" : tfKey === "L3M" ? "3m" : tfKey === "L6M" ? "6m" : "12m");
  return r[key];
}

// Build the thead HTML for the SSEM table (mode-aware). Returns full <thead>...</thead> block.
function ssemHeadersHTML() {
  var h = '<thead>';
  h += '<tr class="group-header-row">';
  h += '<th colspan="3"></th>';
  if (ssemColMode === "TYPE") {
    // 5 groups of 4 timeframes each = 20 cols
    for (var d = 0; d < SSEM_DIMS.length; d++) {
      h += '<th colspan="4" style="background:' + SSEM_DIMS[d].grpBg + '">' + SSEM_DIMS[d].l + ' Revisions</th>';
    }
  } else {
    // 4 timeframe groups of 5 dims each = 20 cols
    for (var t = 0; t < SSEM_TIMES.length; t++) {
      h += '<th colspan="5" style="background:' + SSEM_TIMES[t].bg + '">' + SSEM_TIMES[t].l + (SSEM_TIMES[t].k === "L12M" ? ' (ref)' : '') + '</th>';
    }
  }
  h += '<th colspan="2" style="background:rgba(27,61,92,0.10)">SSEM Score</th>';
  h += '</tr>';
  h += '<tr class="col-header-row">';
  h += th("Ticker","_display_name","col-txt col-identity","Stock ticker","width:120px")
    + th("Sector","_tax_sector","col-txt col-identity","Sector","width:200px")
    + th("Price","price","col-num col-price","Current price","width:52px");
  if (ssemColMode === "TYPE") {
    for (var d2 = 0; d2 < SSEM_DIMS.length; d2++) {
      var dm = SSEM_DIMS[d2];
      for (var t2 = 0; t2 < SSEM_TIMES.length; t2++) {
        var tm = SSEM_TIMES[t2];
        var firstLast = (t2 === 0 ? " " + dm.grpCls + "-first" : (t2 === SSEM_TIMES.length-1 ? " " + dm.grpCls + "-last" : ""));
        var sortKey = dm.k + "_" + (tm.k === "L1M" ? "1m" : tm.k === "L3M" ? "3m" : tm.k === "L6M" ? "6m" : "12m");
        h += th(dm.l + " " + tm.l, sortKey, "col-num col-filter" + firstLast, dm.l + " revision % " + tm.k + (tm.k === "L12M" ? " (reference only — not scored)" : ""));
      }
    }
  } else {
    // TIME mode: 4 timeframe groups
    for (var t3 = 0; t3 < SSEM_TIMES.length; t3++) {
      var tm3 = SSEM_TIMES[t3];
      for (var d3 = 0; d3 < SSEM_DIMS.length; d3++) {
        var dm3 = SSEM_DIMS[d3];
        var firstLast3 = (d3 === 0 ? " grp-tp-first" : (d3 === SSEM_DIMS.length-1 ? " grp-tp-last" : ""));
        var sortKey3 = dm3.k + "_" + (tm3.k === "L1M" ? "1m" : tm3.k === "L3M" ? "3m" : tm3.k === "L6M" ? "6m" : "12m");
        h += th(dm3.l, sortKey3, "col-num col-filter" + firstLast3, dm3.l + " " + tm3.k + " revision %");
      }
    }
  }
  h += th("Score","ssem_score","col-num","Total SSEM score (-15 to +15) using net-off logic across 15 tests");
  h += th("Rating","ssem_rating_sort","col-txt","A-F rating via bell-curve over SSEM universe (10/15/25/25/25)");
  h += '</tr></thead>';
  return h;
}

// Build the row HTML for one SSEM row (mode-aware).
function ssemRowHTML(r) {
  var tax = getTaxonomy(r.ticker);
  var dn = (displayMode === "company") ? (r.company || r.ticker) : r.ticker;
  var h = '<tr onclick="openChart(\\''+r.ticker+'\\')" style="cursor:pointer">';
  h += '<td class="col-txt col-identity" style="font-weight:600;color:var(--text-bright)">' + dn + '</td>';
  h += '<td class="col-txt col-identity" style="font-size:11px">' + tax.sector + '</td>';
  h += '<td class="col-num col-price">' + fp(r.price) + '</td>';
  if (ssemColMode === "TYPE") {
    for (var d = 0; d < SSEM_DIMS.length; d++) {
      var dm = SSEM_DIMS[d];
      for (var t = 0; t < SSEM_TIMES.length; t++) {
        var tm = SSEM_TIMES[t];
        var firstLast = (t === 0 ? " " + dm.grpCls + "-first" : (t === SSEM_TIMES.length-1 ? " " + dm.grpCls + "-last" : ""));
        var rawVals = [ssemRowVal(r, dm.k, "L1M"), ssemRowVal(r, dm.k, "L3M"), ssemRowVal(r, dm.k, "L6M"), ssemRowVal(r, dm.k, "L12M")];
        var v = ssemDisplayValue(rawVals[0], rawVals[1], rawVals[2], rawVals[3], tm.k);
        h += '<td class="col-num col-filter' + firstLast + ' ' + ssemHeatClass(v) + '">' + fpcRaw(v) + '</td>';
      }
    }
  } else {
    for (var t2 = 0; t2 < SSEM_TIMES.length; t2++) {
      var tm2 = SSEM_TIMES[t2];
      for (var d2 = 0; d2 < SSEM_DIMS.length; d2++) {
        var dm2 = SSEM_DIMS[d2];
        var firstLast2 = (d2 === 0 ? " grp-tp-first" : (d2 === SSEM_DIMS.length-1 ? " grp-tp-last" : ""));
        var rawVals2 = [ssemRowVal(r, dm2.k, "L1M"), ssemRowVal(r, dm2.k, "L3M"), ssemRowVal(r, dm2.k, "L6M"), ssemRowVal(r, dm2.k, "L12M")];
        var v2 = ssemDisplayValue(rawVals2[0], rawVals2[1], rawVals2[2], rawVals2[3], tm2.k);
        h += '<td class="col-num col-filter' + firstLast2 + ' ' + ssemHeatClass(v2) + '">' + fpcRaw(v2) + '</td>';
      }
    }
  }
  // Score — rating-keyed colour (D-MD-SSEM-6)
  var ratingKey = (r.ssem_rating === "-") ? "N" : r.ssem_rating;
  h += '<td class="ssem-score-cell ssem-score-r' + ratingKey + '">' + (r.ssem_score > 0 ? "+" : "") + r.ssem_score + '</td>';
  h += '<td style="text-align:center">' + ssemRatingPill(r.ssem_rating) + '</td>';
  h += '</tr>';
  return h;
}

function renderSSEM(){
  buildHeaderControls("ssem");
  var container=document.getElementById("tab-ssem");
  if(!D.ssem){
    container.innerHTML='<div class="summary-tile" style="text-align:center;padding:40px"><h3>SS Earnings Momentum</h3><p style="color:var(--text-dim);margin-top:8px">factset-ssem.json not loaded.</p></div>';
    return;
  }
  var allRows=baseRows();
  var rowsAll=[];
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
    ssemEnrichRow(r);
    rowsAll.push(r);
  }
  ssemAssignRatings(rowsAll);
  // Apply header filters
  var rows=[];
  for(var rj=0;rj<rowsAll.length;rj++){
    var rr=rowsAll[rj];
    var ratingKey=rr.ssem_rating==="-"?"N":rr.ssem_rating;
    if(!ssemRatingFilters[ratingKey])continue;
    var dimOK=true;
    var anyDimOn=false;
    var dims=["eps","ebitda","sales","tp","buy"];
    for(var dx=0;dx<dims.length;dx++){
      if(ssemDimFilters[dims[dx]]){
        anyDimOn=true;
        if(!(rr["ssem_l3m_net_"+dims[dx]]>0)){dimOK=false;break}
      }
    }
    if(anyDimOn && !dimOK)continue;
    rows.push(rr);
  }
  // Default sort: ssem_score desc, ticker asc tiebreak.
  if(currentSort.col==="" || currentSort.col==null || currentSort.col==="momentum"){
    rows.sort(function(a,b){if(b.ssem_score!==a.ssem_score)return b.ssem_score-a.ssem_score; return (a.ticker||"").localeCompare(b.ticker||"")});
  } else {
    rows=sortData(rows,currentSort.col,currentSort.dir);
  }
  var totalCount=allRows.length;
  // Distribution stats for summary tile.
  var distA=0,distB=0,distC=0,distD=0,distF=0,distN=0;
  for(var jc=0;jc<rowsAll.length;jc++){
    var g=rowsAll[jc].ssem_rating;
    if(g==="A")distA++;else if(g==="B")distB++;else if(g==="C")distC++;
    else if(g==="D")distD++;else if(g==="F")distF++;else distN++;
  }
  var h='<div class="summary-tile" id="section-summary"><h3>SS Earnings Momentum &mdash; Decision Lens</h3>'
    +'<div class="sub">15-test net-of-prior-period scoring across 5 dimensions (EPS, EBITDA, Sales, TP, Buy) x 3 timeframes (L1M, L3M-net, L6M-net). Score range -15 to +15. A-F bell-curve distribution across the SSEM-covered universe (10/15/25/25/25). L12M shown for visual reference only (not scored). Use VIEW toggle to switch column grouping (TYPE/TIME); use VALUES toggle to switch between cumulative (raw) and per-period (net) revisions.</div>'
    +'<div class="summary-stats">'
    +sumStat("Stocks",xyFmt(rowsAll.length,totalCount))
    +sumStat("A",distA,"green")+sumStat("B",distB,"green")+sumStat("C",distC,"amber")+sumStat("D",distD,"amber")+sumStat("F",distF,"red")+sumStat("&mdash;",distN)
    +'</div></div>';
  h+=buildSsemIndSecTables(rowsAll);
  h+=buildPortfolioTile(currentTab);
  rows=applyIndSecFilter(rows);
  h+='<h3 class="qualified-title" id="section-stocks">Qualified Stocks ('+xyFmt(rows.length,totalCount)+')</h3>';
  h+='<div class="data-table-wrap"><table class="data-table">'+ssemHeadersHTML()+'<tbody>';
  for(var jr=0;jr<rows.length;jr++){
    h+=ssemRowHTML(rows[jr]);
  }
  h+='</tbody></table></div>';
  container.innerHTML=h;
}

'''
    src = src[:start_idx] + new_render + src[sep_idx:]
    print("  OK [8: rewrite renderSSEM with helpers + mode awareness]")

    new_size = len(src)
    print(f"  New size: {new_size:,} bytes (delta {new_size - orig_size:+,})")

    print(f"Writing {TARGET}...")
    TARGET.write_text(src, encoding="utf-8")

    print("Verifying Python compile...")
    import py_compile
    try:
        py_compile.compile(str(TARGET), doraise=True)
        print("  OK: py_compile passed")
    except py_compile.PyCompileError as e:
        print(f"  FAIL py_compile: {e}")
        sys.exit(1)

    print("\nDONE. Run: python build_dashboard.py")


if __name__ == "__main__":
    main()
