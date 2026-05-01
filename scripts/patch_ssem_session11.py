"""
SSEM Tab Rebuild Patcher — Session 11 (01-May-26)
==================================================

Applies five changes to build_dashboard.py:
  1. Rename tab label "SSEM" -> "SS Earnings Momentum"
  2. Add SSEM scoring + rating helpers (ssemDimScore, ssemAssignRatings, ssemTrendArrow, ssemSkewGlyph)
  3. Add SSEM filter state vars + setters
  4. Add buildSsemHeaderControls + wire into buildHeaderControls dispatch
  5. Replace renderSSEM with new version (Score + Rating columns, two-table pattern, ind/sec tile enrichment)
  6. Add CSS for SSEM rating pills, trend arrows, skew glyphs

Anchor-based string replacement. Atomic: backs up first, applies all 6 edits, fails loudly if any anchor missing.
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
    bak = SCRIPT_DIR / f"build_dashboard.py.bak-pre-ssem-rebuild-{ts}"
    shutil.copy2(TARGET, bak)
    print(f"  Backup: {bak.name}")
    return bak


def apply_replacement(src, anchor, new_text, label):
    """Replace anchor with new_text. Anchor must appear exactly once. Fails loudly otherwise."""
    n = src.count(anchor)
    if n == 0:
        print(f"  FAIL [{label}]: anchor not found:")
        print(f"    {anchor[:80]!r}...")
        sys.exit(1)
    if n > 1:
        print(f"  FAIL [{label}]: anchor appears {n} times (expected 1):")
        print(f"    {anchor[:80]!r}...")
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
    # Edit 1: Rename tab label
    # ─────────────────────────────────────────────────────────────
    src = apply_replacement(
        src,
        '{"id": "ssem",      "label": "SSEM",             "accent": "#2b6cb0"},',
        '{"id": "ssem",      "label": "SS Earnings Momentum", "accent": "#2b6cb0"},',
        "1: rename tab label",
    )

    # ─────────────────────────────────────────────────────────────
    # Edit 2: Add CSS for SSEM rating pill, trend arrows, skew glyphs
    # Anchor: insert just before the closing of the main CSS block (find an existing rule near end)
    # ─────────────────────────────────────────────────────────────
    css_anchor = "/* UTR key description row above headers"
    css_addition = """/* SESSION 11 — D-MD-SSEM-1..4: SS Earnings Momentum tab additions */
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

/* UTR key description row above headers"""
    src = apply_replacement(src, css_anchor, css_addition, "2: SSEM CSS block")

    # ─────────────────────────────────────────────────────────────
    # Edit 3: Add SSEM filter state vars + helper functions
    # Anchor: just before "function renderSSEM"
    # ─────────────────────────────────────────────────────────────
    helpers_anchor = "function renderSSEM(){"
    helpers_block = """// ================================================================
// SS EARNINGS MOMENTUM — Session 11 helpers (D-MD-SSEM-1..4)
// ================================================================
// Filter state — sticky across tab switches per D-MD-UI-7 pattern.
var ssemDimFilters = {eps: true, ebitda: true, sales: true, tp: true, buy: true};
var ssemRatingFilters = {A: true, B: true, C: true, D: true, F: true, N: true};

// Sub-score for one dimension using net-off logic.
// Net-off: L1M test = raw L1M, L3M test = (L3M - L1M), L6M test = (L6M - L3M).
// Each test: positive=+1, zero=0, negative=-1, null=0. Returns object with sub_score and net values.
function ssemDimScore(L1M, L3M, L6M) {
  function sgn(v) { if (v == null) return 0; if (v > 0) return 1; if (v < 0) return -1; return 0; }
  var l1 = (L1M == null) ? 0 : L1M;
  var l3 = (L3M == null) ? 0 : L3M;
  var l6 = (L6M == null) ? 0 : L6M;
  var test_l1m = l1;
  var test_l3m = l3 - l1;
  var test_l6m = l6 - l3;
  var sub = sgn(test_l1m) + sgn(test_l3m) + sgn(test_l6m);
  // Count nulls for null-aware rating eligibility
  var nullCount = (L1M == null ? 1 : 0) + (L3M == null ? 1 : 0) + (L6M == null ? 1 : 0);
  return {sub: sub, l1m_net: test_l1m, l3m_net: test_l3m, l6m_net: test_l6m, nulls: nullCount};
}

// Compute total SSEM score (-15 to +15) and per-dimension sub-scores.
// Mutates row r adding: r.ssem_score, r.ssem_dim_eps/ebitda/sales/tp/buy (sub-scores), r.ssem_nulls (count).
function ssemEnrichRow(r) {
  var dims = [
    {key: "eps", l1: r.eps_1m, l3: r.eps_3m, l6: r.eps_6m},
    {key: "ebitda", l1: r.ebitda_1m, l3: r.ebitda_3m, l6: r.ebitda_6m},
    {key: "sales", l1: r.sales_1m, l3: r.sales_3m, l6: r.sales_6m},
    {key: "tp", l1: r.tp_1m, l3: r.tp_3m, l6: r.tp_6m},
    {key: "buy", l1: r.buy_1m, l3: r.buy_3m, l6: r.buy_6m}
  ];
  var total = 0, totalNulls = 0;
  for (var d = 0; d < dims.length; d++) {
    var ds = ssemDimScore(dims[d].l1, dims[d].l3, dims[d].l6);
    r["ssem_dim_" + dims[d].key] = ds.sub;
    r["ssem_l3m_net_" + dims[d].key] = ds.l3m_net;
    total += ds.sub;
    totalNulls += ds.nulls;
  }
  r.ssem_score = total;
  r.ssem_nulls = totalNulls;
}

// Assign A/B/C/D/F/- ratings via bell-curve distribution: 10/15/25/25/25.
// Mutates each row in `rows`. Stocks with >=3 null tests get rating "-" and are excluded from the percentile ranking.
function ssemAssignRatings(rows) {
  var eligible = [];
  var ineligible = [];
  for (var j = 0; j < rows.length; j++) {
    if (rows[j].ssem_nulls >= 3) ineligible.push(rows[j]);
    else eligible.push(rows[j]);
  }
  // Sort eligible by score descending; ties broken by ticker ascending for stability.
  eligible.sort(function(a, b) {
    if (b.ssem_score !== a.ssem_score) return b.ssem_score - a.ssem_score;
    return (a.ticker || "").localeCompare(b.ticker || "");
  });
  var n = eligible.length;
  // Cut points (10% / 15% / 25% / 25% / 25%) — assign by ordinal rank.
  var cutA = Math.ceil(n * 0.10);
  var cutB = cutA + Math.ceil(n * 0.15);
  var cutC = cutB + Math.ceil(n * 0.25);
  var cutD = cutC + Math.ceil(n * 0.25);
  for (var i = 0; i < n; i++) {
    var rating;
    if (i < cutA) rating = "A";
    else if (i < cutB) rating = "B";
    else if (i < cutC) rating = "C";
    else if (i < cutD) rating = "D";
    else rating = "F";
    eligible[i].ssem_rating = rating;
  }
  for (var k = 0; k < ineligible.length; k++) {
    ineligible[k].ssem_rating = "-";
  }
}

// Pill HTML for SSEM rating
function ssemRatingPill(grade) {
  var key = (grade === "-") ? "N" : grade;
  var label = (grade === "-") ? "&mdash;" : grade;
  return '<span class="ssem-rating-pill ssem-rating-' + key + '">' + label + '</span>';
}

// Sort key for ratings (so A sorts above F when sorting by rating column).
function ssemRatingSortKey(grade) {
  var order = {A: 5, B: 4, C: 3, D: 2, F: 1, "-": 0};
  return order[grade] != null ? order[grade] : -1;
}

// Trend arrow: comparing avg L1M vs avg L6M with 1pp threshold.
// Returns HTML string with up/flat/down arrow.
function ssemTrendArrow(avgL1M, avgL6M) {
  if (avgL1M == null || avgL6M == null) return '<span class="ssem-trend-flat">&mdash;</span>';
  var delta = avgL1M - avgL6M;
  if (delta > 1) return '<span class="ssem-trend-up" title="Accelerating: avg L1M ' + avgL1M.toFixed(1) + '% vs avg L6M ' + avgL6M.toFixed(1) + '%">&uarr;</span>';
  if (delta < -1) return '<span class="ssem-trend-down" title="Decelerating: avg L1M ' + avgL1M.toFixed(1) + '% vs avg L6M ' + avgL6M.toFixed(1) + '%">&darr;</span>';
  return '<span class="ssem-trend-flat" title="Flat: avg L1M ' + avgL1M.toFixed(1) + '% vs avg L6M ' + avgL6M.toFixed(1) + '%">&rarr;</span>';
}

// Skew glyph: cross-sectional stdev of L3M values bucketed narrow/medium/wide.
function ssemSkewGlyph(stdev) {
  if (stdev == null) return '<span class="ssem-skew">&mdash;</span>';
  var glyph, label;
  if (stdev < 3) { glyph = "&lt;&gt;"; label = "narrow"; }
  else if (stdev < 8) { glyph = "&lt;&mdash;&gt;"; label = "medium"; }
  else { glyph = "&lt;&mdash;&mdash;&gt;"; label = "wide"; }
  return '<span class="ssem-skew" title="' + label + ' (stdev ' + stdev.toFixed(1) + 'pp)">' + glyph + '</span>';
}

// Average + stdev helpers
function ssemMean(values) {
  var vals = []; for (var i = 0; i < values.length; i++) if (values[i] != null) vals.push(values[i]);
  if (vals.length === 0) return null;
  var s = 0; for (var k = 0; k < vals.length; k++) s += vals[k];
  return s / vals.length;
}
function ssemStdev(values) {
  var vals = []; for (var i = 0; i < values.length; i++) if (values[i] != null) vals.push(values[i]);
  if (vals.length < 2) return null;
  var m = 0; for (var k = 0; k < vals.length; k++) m += vals[k]; m = m / vals.length;
  var sq = 0; for (var p = 0; p < vals.length; p++) sq += (vals[p] - m) * (vals[p] - m);
  return Math.sqrt(sq / vals.length);
}

// SSEM-specific industry/sector tiles: enriched with 5 dim x 2 cols (avg L3M%, trend+skew glyph).
function buildSsemIndSecTables(rows) {
  // Build aggregations per industry and per sector.
  var indMap = {};
  var secMap = {};
  for (var j = 0; j < rows.length; j++) {
    var r = rows[j];
    var tax = getTaxonomy(r.ticker);
    var ind = tax.industry || "";
    var sec = tax.sector || "";
    if (!indMap[ind]) indMap[ind] = {count: 0, eps_l1m: [], eps_l3m: [], eps_l6m: [], ebitda_l1m: [], ebitda_l3m: [], ebitda_l6m: [], sales_l1m: [], sales_l3m: [], sales_l6m: [], tp_l1m: [], tp_l3m: [], tp_l6m: [], buy_l1m: [], buy_l3m: [], buy_l6m: []};
    if (!secMap[sec]) secMap[sec] = {industry: ind, count: 0, eps_l1m: [], eps_l3m: [], eps_l6m: [], ebitda_l1m: [], ebitda_l3m: [], ebitda_l6m: [], sales_l1m: [], sales_l3m: [], sales_l6m: [], tp_l1m: [], tp_l3m: [], tp_l6m: [], buy_l1m: [], buy_l3m: [], buy_l6m: []};
    indMap[ind].count++;
    secMap[sec].count++;
    var dims = ["eps", "ebitda", "sales", "tp", "buy"];
    for (var d = 0; d < dims.length; d++) {
      indMap[ind][dims[d] + "_l1m"].push(r[dims[d] + "_1m"]);
      indMap[ind][dims[d] + "_l3m"].push(r[dims[d] + "_3m"]);
      indMap[ind][dims[d] + "_l6m"].push(r[dims[d] + "_6m"]);
      secMap[sec][dims[d] + "_l1m"].push(r[dims[d] + "_1m"]);
      secMap[sec][dims[d] + "_l3m"].push(r[dims[d] + "_3m"]);
      secMap[sec][dims[d] + "_l6m"].push(r[dims[d] + "_6m"]);
    }
  }
  // Render
  var dimsLabels = [{k: "eps", l: "EPS"}, {k: "ebitda", l: "EBITDA"}, {k: "sales", l: "Sales"}, {k: "tp", l: "TP"}, {k: "buy", l: "Buy"}];
  function renderTile(map, isSector) {
    var keys = Object.keys(map).sort();
    var titleLabelSingular = isSector ? "Sector" : "Industry";
    var titleLabelPlural = isSector ? "Sectors" : "Industries";
    var h = '<div class="half-table"><div class="half-title">' + titleLabelPlural + '</div>';
    var titleLabel = titleLabelSingular;
    h += '<div class="data-table-wrap"><table class="data-table data-table-tile"><thead><tr>';
    h += '<th class="col-txt" style="cursor:pointer" onclick="tileSortTable(this)">' + titleLabel + '</th>';
    if (isSector) h += '<th class="col-txt" style="cursor:pointer" onclick="tileSortTable(this)">Industry</th>';
    h += '<th class="col-num" style="cursor:pointer" onclick="tileSortTable(this)">#</th>';
    for (var d = 0; d < dimsLabels.length; d++) {
      var lbl = dimsLabels[d].l;
      h += '<th class="col-num" style="cursor:pointer" onclick="tileSortTable(this)" title="' + lbl + ' avg L3M revision %">' + lbl + ' L3M</th>';
      h += '<th class="col-num" style="cursor:pointer" title="' + lbl + ' trend (L1M vs L6M) and skew (cross-sectional stdev of L3M)">' + lbl + ' &uarr;&darr;</th>';
    }
    h += '</tr></thead><tbody>';
    for (var k = 0; k < keys.length; k++) {
      var key = keys[k];
      var m = map[key];
      h += '<tr><td class="col-txt" style="font-size:11px">' + key + '</td>';
      if (isSector) h += '<td class="col-txt" style="font-size:10px;color:var(--text-dim)">' + m.industry + '</td>';
      h += '<td class="col-num" style="font-weight:600">' + m.count + '</td>';
      for (var d = 0; d < dimsLabels.length; d++) {
        var dk = dimsLabels[d].k;
        var avgL1M = ssemMean(m[dk + "_l1m"]);
        var avgL3M = ssemMean(m[dk + "_l3m"]);
        var avgL6M = ssemMean(m[dk + "_l6m"]);
        var stdevL3M = ssemStdev(m[dk + "_l3m"]);
        var avgStr = (avgL3M == null) ? "&mdash;" : (avgL3M >= 0 ? "+" : "") + avgL3M.toFixed(1) + "%";
        h += '<td class="ssem-tile-cell">' + avgStr + '</td>';
        h += '<td class="ssem-tile-glyph">' + ssemTrendArrow(avgL1M, avgL6M) + " " + ssemSkewGlyph(stdevL3M) + '</td>';
      }
      h += '</tr>';
    }
    h += '</tbody></table></div></div>';
    return h;
  }
  return '<div class="ind-sec-wrap" id="section-industries">' + renderTile(indMap, false) + renderTile(secMap, true) + '</div>';
}

// Setters for SSEM filter toggles
window.toggleSsemDim = function(dim) { ssemDimFilters[dim] = !ssemDimFilters[dim]; renderTab("ssem"); };
window.toggleSsemRating = function(rating) { ssemRatingFilters[rating] = !ssemRatingFilters[rating]; renderTab("ssem"); };

// SSEM-specific header controls (5 dim toggles + 6 rating toggles)
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
}

"""
    src = apply_replacement(src, helpers_anchor, helpers_block + helpers_anchor, "3: helpers + state vars")

    # ─────────────────────────────────────────────────────────────
    # Edit 4: Wire ssem into buildHeaderControls dispatch
    # Anchor `} else if(tabId==="combos"){` is unique to buildHeaderControls; the other
    # occurrence of `if(tabId==="combos")` at line ~1520 (buildPortfolioTile) doesn't have the `} else ` prefix.
    # ─────────────────────────────────────────────────────────────
    src = apply_replacement(
        src,
        '} else if(tabId==="combos"){',
        '} else if(tabId==="ssem"){buildSsemHeaderControls();return;\n  } else if(tabId==="combos"){',
        "4: wire ssem into header dispatch",
    )

    # ─────────────────────────────────────────────────────────────
    # Edit 5: Replace the entire renderSSEM function with new version.
    # ─────────────────────────────────────────────────────────────
    # The original starts with `function renderSSEM(){` and ends with `container.innerHTML=h;\n}\n` followed by `// =====` block for VALUATION.
    # We replace from `function renderSSEM(){` up to (but not including) `// =================` for Valuation.
    old_render_start = "function renderSSEM(){"
    old_render_end_anchor = "// VALUATION TAB"
    start_idx = src.index(old_render_start)
    # The end anchor is preceded by `// =================================================` (separator line) — find the separator above VALUATION.
    val_idx = src.index(old_render_end_anchor, start_idx)
    # Walk backwards to find the "// ====" line that opens the valuation section header
    sep_idx = src.rfind("// ====", start_idx, val_idx)
    if sep_idx < 0:
        print("  FAIL [5]: could not find separator before VALUATION TAB")
        sys.exit(1)
    old_block = src[start_idx:sep_idx]
    new_render = '''function renderSSEM(){
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
    // Compute SSEM score + per-dim sub-scores via net-off logic.
    ssemEnrichRow(r);
    rowsAll.push(r);
  }
  // Bell-curve rating distribution: 10/15/25/25/25 over eligible (>=3 nulls => "-").
  ssemAssignRatings(rowsAll);
  // Apply header filters: dim toggles (AND on net L3M positive) + rating toggles.
  // Dim semantics: a dim toggle ON means "show stocks where dim_net_l3m > 0". AND across active dims (intersection).
  // If all dim toggles OFF: show all (no constraint). Same idea as TIMELINESS toggles.
  var rows=[];
  for(var rj=0;rj<rowsAll.length;rj++){
    var rr=rowsAll[rj];
    var ratingKey=rr.ssem_rating==="-"?"N":rr.ssem_rating;
    if(!ssemRatingFilters[ratingKey])continue;
    // Dim filter: AND semantics — if a dim is ON, stock must be positive on that dim's net L3M.
    var dimOK=true;
    var anyDimOn=false;
    var dims=["eps","ebitda","sales","tp","buy"];
    for(var dx=0;dx<dims.length;dx++){
      if(ssemDimFilters[dims[dx]]){
        anyDimOn=true;
        if(!(rr["ssem_l3m_net_"+dims[dx]]>0)){dimOK=false;break}
      }
    }
    // If no dims on, show all (don't filter on dims).
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
    +'<div class="sub">15-test net-of-prior-period scoring across 5 dimensions (EPS, EBITDA, Sales, TP, Buy) x 3 timeframes (L1M, L3M-net, L6M-net). Score range -15 to +15. A-F bell-curve distribution across the SSEM-covered universe (10/15/25/25/25). L12M shown for visual reference only (not scored). D-MD-SSEM-1..4.</div>'
    +'<div class="summary-stats">'
    +sumStat("Stocks",xyFmt(rowsAll.length,totalCount))
    +sumStat("A",distA,"green")+sumStat("B",distB,"green")+sumStat("C",distC,"amber")+sumStat("D",distD,"amber")+sumStat("F",distF,"red")+sumStat("&mdash;",distN)
    +'</div></div>';
  // Industry/Sector tiles — enriched per Session 11.
  h+=buildSsemIndSecTables(rowsAll);
  // Live Portfolio (separate table, mirrors UTR/TIMELINESS pattern).
  h+=buildPortfolioTile(currentTab);
  // Apply ind/sec filter to qualified stocks list.
  rows=applyIndSecFilter(rows);
  h+='<h3 class="qualified-title" id="section-stocks">Qualified Stocks ('+xyFmt(rows.length,totalCount)+')</h3>';
  h+='<div class="data-table-wrap"><table class="data-table"><thead>';
  h+='<tr class="group-header-row">';
  h+='<th colspan="3"></th>';
  h+='<th colspan="4" style="background:rgba(50,150,50,0.08)">EPS Revisions</th>';
  h+='<th colspan="4" style="background:rgba(50,100,200,0.08)">EBITDA Revisions</th>';
  h+='<th colspan="4" style="background:rgba(200,150,0,0.08)">Sales Revisions</th>';
  h+='<th colspan="4" style="background:rgba(120,80,200,0.08)">Target Price</th>';
  h+='<th colspan="2" style="background:rgba(200,50,50,0.08)">Buy Rating</th>';
  h+='<th colspan="2" style="background:rgba(27,61,92,0.10)">SSEM Score</th>';
  h+='</tr>';
  h+='<tr class="col-header-row">';
  h+=th("Ticker","_display_name","col-txt col-identity","Stock ticker","width:120px")
    +th("Sector","_tax_sector","col-txt col-identity","Sector","width:200px")
    +th("Price","price","col-num col-price","Current price","width:52px")
    +th("EPS 1M","eps_1m","col-num col-filter grp-eps-first","EPS revision % L1M")+th("EPS 3M","eps_3m","col-num col-filter","EPS revision % L3M (cumulative)")+th("EPS 6M","eps_6m","col-num col-filter","EPS revision % L6M (cumulative)")+th("EPS 12M","eps_12m","col-num col-filter grp-eps-last","EPS revision % L12M (reference only — not scored)")
    +th("EBITDA 1M","ebitda_1m","col-num col-filter grp-ebitda-first","EBITDA revision % L1M")+th("EBITDA 3M","ebitda_3m","col-num col-filter","EBITDA revision % L3M (cumulative)")+th("EBITDA 6M","ebitda_6m","col-num col-filter","EBITDA revision % L6M (cumulative)")+th("EBITDA 12M","ebitda_12m","col-num col-filter grp-ebitda-last","EBITDA L12M (reference only)")
    +th("Sales 1M","sales_1m","col-num col-filter grp-sales-first","Sales revision % L1M")+th("Sales 3M","sales_3m","col-num col-filter","Sales L3M cumulative")+th("Sales 6M","sales_6m","col-num col-filter","Sales L6M cumulative")+th("Sales 12M","sales_12m","col-num col-filter grp-sales-last","Sales L12M (reference)")
    +th("TP 1M","tp_1m","col-num col-filter grp-tp-first","Target price revision % L1M")+th("TP 3M","tp_3m","col-num col-filter","TP L3M cumulative")+th("TP 6M","tp_6m","col-num col-filter","TP L6M cumulative")+th("TP 12M","tp_12m","col-num col-filter grp-tp-last","TP L12M (reference)")
    +th("% Buy","buy_pct","col-num col-filter grp-buy-first","Current % of analysts rating Buy")
    +th("Buy L6M","buy_6m","col-num col-filter grp-buy-last","Change in Buy% over L6M")
    +th("Score","ssem_score","col-num","Total SSEM score (-15 to +15) using net-off logic across 15 tests")
    +th("Rating","ssem_rating_sort","col-txt","A-F rating via bell-curve over SSEM universe (10/15/25/25/25)");
  h+='</tr></thead><tbody>';
  for(var jr=0;jr<rows.length;jr++){
    var rr2=rows[jr];
    var tax=getTaxonomy(rr2.ticker);
    var dn=(displayMode==="company")?(rr2.company||rr2.ticker):rr2.ticker;
    h+='<tr onclick="openChart(\\''+rr2.ticker+'\\')" style="cursor:pointer">'
      +'<td class="col-txt col-identity" style="font-weight:600;color:var(--text-bright)">'+dn+'</td>'
      +'<td class="col-txt col-identity" style="font-size:11px">'+tax.sector+'</td>'
      +'<td class="col-num col-price">'+fp(rr2.price)+'</td>';
    h+='<td class="col-num col-filter grp-eps-first '+revClass(rr2.eps_1m)+'">'+fpcRaw(rr2.eps_1m)+'</td>';
    h+='<td class="col-num col-filter '+revClass(rr2.eps_3m)+'">'+fpcRaw(rr2.eps_3m)+'</td>';
    h+='<td class="col-num col-filter '+revClass(rr2.eps_6m)+'">'+fpcRaw(rr2.eps_6m)+'</td>';
    h+='<td class="col-num col-filter grp-eps-last '+revClass(rr2.eps_12m)+'">'+fpcRaw(rr2.eps_12m)+'</td>';
    h+='<td class="col-num col-filter grp-ebitda-first '+revClass(rr2.ebitda_1m)+'">'+fpcRaw(rr2.ebitda_1m)+'</td>';
    h+='<td class="col-num col-filter '+revClass(rr2.ebitda_3m)+'">'+fpcRaw(rr2.ebitda_3m)+'</td>';
    h+='<td class="col-num col-filter '+revClass(rr2.ebitda_6m)+'">'+fpcRaw(rr2.ebitda_6m)+'</td>';
    h+='<td class="col-num col-filter grp-ebitda-last '+revClass(rr2.ebitda_12m)+'">'+fpcRaw(rr2.ebitda_12m)+'</td>';
    h+='<td class="col-num col-filter grp-sales-first '+revClass(rr2.sales_1m)+'">'+fpcRaw(rr2.sales_1m)+'</td>';
    h+='<td class="col-num col-filter '+revClass(rr2.sales_3m)+'">'+fpcRaw(rr2.sales_3m)+'</td>';
    h+='<td class="col-num col-filter '+revClass(rr2.sales_6m)+'">'+fpcRaw(rr2.sales_6m)+'</td>';
    h+='<td class="col-num col-filter grp-sales-last '+revClass(rr2.sales_12m)+'">'+fpcRaw(rr2.sales_12m)+'</td>';
    h+='<td class="col-num col-filter grp-tp-first '+revClass(rr2.tp_1m)+'">'+fpcRaw(rr2.tp_1m)+'</td>';
    h+='<td class="col-num col-filter '+revClass(rr2.tp_3m)+'">'+fpcRaw(rr2.tp_3m)+'</td>';
    h+='<td class="col-num col-filter '+revClass(rr2.tp_6m)+'">'+fpcRaw(rr2.tp_6m)+'</td>';
    h+='<td class="col-num col-filter grp-tp-last '+revClass(rr2.tp_12m)+'">'+fpcRaw(rr2.tp_12m)+'</td>';
    h+='<td class="col-num col-filter grp-buy-first '+(rr2.buy_pct!=null&&rr2.buy_pct>=70?"pass":rr2.buy_pct!=null&&rr2.buy_pct>=40?"amber":"fail")+'">'+(rr2.buy_pct!=null?nf(rr2.buy_pct)+"%":"&mdash;")+'</td>';
    h+='<td class="col-num col-filter grp-buy-last '+revClass(rr2.buy_6m)+'">'+(rr2.buy_6m!=null?fpcRaw(rr2.buy_6m):"&mdash;")+'</td>';
    var scCls=rr2.ssem_score>0?"ssem-score-pos":(rr2.ssem_score<0?"ssem-score-neg":"ssem-score-zero");
    h+='<td class="ssem-score-cell '+scCls+'">'+(rr2.ssem_score>0?"+":"")+rr2.ssem_score+'</td>';
    h+='<td style="text-align:center">'+ssemRatingPill(rr2.ssem_rating)+'</td>';
    h+='</tr>';
  }
  h+='</tbody></table></div>';
  container.innerHTML=h;
}

'''
    src = src[:start_idx] + new_render + src[sep_idx:]
    print("  OK [5: replace renderSSEM]")

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
