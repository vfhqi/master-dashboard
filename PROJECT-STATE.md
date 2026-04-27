# Master Dashboard — Project State

**Last updated:** 2026-04-27 19:30 (Watson, Cowork session — chart fix + sticky headers)
**Role:** Systems Architect
**Mode:** Execution

---

## What It Is

Unified technical screening dashboard for ~976 European equities. Single HTML file (`index.html`) with 10 tabs, hosted on GitHub Pages at `https://vfhqi.github.io/master-dashboard/`. Daily automated refresh at 18:00 UK via Windows Task Scheduler.

## Architecture

- **Data pipeline:** 3 Python scripts chained via batch files
  - `generate_master_data.py --full-universe` → prices.json + filter-results.json
  - `generate_chart_data.py --live` → per-ticker JS files in charts/ (~976 files, ~109MB)
  - `build_dashboard.py` → index.html (single file, embedded data)
- **Automation:** `scripts/refresh-dashboard-silent.bat` → Task Scheduler (18:00 daily)
- **Deployment:** git commit + push to `vfhqi/master-dashboard` → GitHub Pages
- **Git:** GitHub Desktop's bundled git (not on PATH). Credentials cached via Git Credential Manager.

## Tab Status

| # | Tab | Status | Notes |
|---|-----|--------|-------|
| 1 | MM99 | **Complete** | 8pt + 11pt extended, 5 groups, RS at 3 levels |
| 2 | Basing Plateau | **Complete** | 3 tightness tiers, 8 tests, 3-month duration |
| 3 | Probing Bet | **Complete** | 5 groups, 12 tests, dead cat detection |
| 4 | Uptrend Retest | **V2 Live** | V2 lifecycle stages live. Sort, key descriptions, stage filters, Jump To, chart loading all working. Sticky headers added. Threshold tuning pending. |
| 5 | VCP | **Stub** | Stage 2 uptrend only. Full pattern detection = Phase 2 |
| 6 | Technical Data | **Complete** | Raw data reference (7 SMAs, volume, 52W) |
| 7 | SSEM | **Complete** | FactSet consensus data (manual export dependency) |
| 8 | Valuation | **Complete** | FactSet P/E data (manual export dependency) |
| 9 | Combinations | **Complete** | Cross-filter matrix, multi-filter scoring |
| 10 | Live Investments | **Complete** | Portfolio overlay from positions.json |

## UTR V1 (Superseded)

**COMPLETED then SUPERSEDED (27-Apr-26).** V1 implemented 8 signals as a flat composite scorecard (S1-S8, summed to 8.0 max, stage thresholds at 3.0/4.5/6.0). Ran against 949 stocks: Early 265, Late 507, Capital 97, None 80. Distribution too generous — 92% passing at some level. Root cause: stages based on arbitrary composite thresholds rather than pullback lifecycle position. Amber bands too wide, pushing most scores to ~4.0.

V1 code remains in `generate_master_data.py` and will be replaced by V2.

---

## Current Work: UTR V2 Redesign

**Status:** Design spec agreed (27-Apr-26). Implementation pending.

### Higher Intent

Identify stocks in a confirmed uptrend that are currently pulling back in an orderly way, tracking them through the **pullback lifecycle** from initiation to actionable MA retest. The filter answers: "Is this pullback a healthy rest within the trend, and has it reached the point where adding capital is justified?"

This mirrors the stage progression of the other filters: Early (pattern forming) → Late (pattern maturing) → Capital (pattern confirmed, act today) → Invalidation (pattern failed).

### Stage Definitions

**EARLY — "Pullback has begun, is it likely to be orderly?"**

Stock has turned down from a recent high. Short-term MAs rolling over, intermediate MAs still rising. The pullback is young. Volume indicators provide early read on whether this is likely to resolve constructively.

Tests:
- **E1: Pullback initiated.** Price 3-10% below swing high. (<3% = noise, >10% = already Late territory)
- **E2: Short-term MAs rolling, intermediate intact.** 5D and/or 10D declining, while 50D AND 150D still rising. Confirms pullback is short-term only. (Minervini Stage 2 requirement: 150D and 200D must be rising.)
- **E3: Volume declining from peak.** 10D ADV / 50D ADV — health indicator at this stage. Declining volume = sellers drying up (constructive). Expanding volume = distribution from the start (warning). Not a pass/fail gate, but colours the "likely healthy?" assessment.
- **E4: Distribution days low.** 0-1 distribution days expected at Early stage. Even 2 is a yellow flag — institutions selling aggressively from the outset.

Early qualification: E1 + E2 pass. E3 + E4 provide health colouring (likely healthy vs. likely problematic).

**LATE — "Approaching the MA, quality check intensifies"**

Pullback established. Price within range of key support MA. Full quality picture now matters — Minervini's "pause" characteristics should be evident.

Tests:
- **L1: Depth 8-20% from swing high.** Minervini guideline: most buyable pullbacks stay within 10-20%, best setups 10-15%. Weinstein: Stage 2 stock retesting 30-week (150D) MA is normal.
- **L2: Price approaching key MA.** Within 5% of 50D, 100D, or 150D MA, still above it. Approaching the test zone — not testing yet.
- **L3: Volume dried up (confirmed).** 10D/50D ratio below 0.85. Persistent low volume on the decline. Minervini: "low volume contraction" — weak hands selling, not institutions.
- **L4: Up/down volume ratio.** Avg up-day vol / avg down-day vol > 1.0 = constructive (quiet accumulation on dips). < 0.8 = distribution.
- **L5: Range contracting.** ATR10/ATR20 below 0.9. Volatility contraction as pullback matures. Minervini + Weinstein: one of the strongest pre-breakout signals.
- **L6: Distribution days contained.** 0-3 acceptable. 4-5 warning. 6+ = institutions actively selling throughout — retest unlikely to hold.

Late qualification: L1 + L2 pass (right position), L3-L6 provide quality assessment.

**CAPITAL — "Healthy retest, actionable today"**

Price has reached the support MA. All quality indicators must confirm. This is the "buy today" signal — should be rare and high-conviction.

Tests:
- **C1: Price at support MA.** Within 2% of 50D, 100D, or 150D MA (above or slight undercut — Minervini's "undercut and rally" is acceptable, decisive break is not).
- **C2: Depth reasonable.** Below 25% from swing high. Minervini's outer limit. Most Capital-grade retests: 8-15%.
- **C3: Volume dried up.** 10D/50D ratio below 0.80. Definitive dryness — not "roughly in line." Minervini's best setups: volume drops 40-60% below average during pullback.
- **C4: Up/down ratio positive.** Above 1.1 — net accumulation on the balance. Clear but doesn't need to be extreme.
- **C5: Candle quality.** >=50% of last 10 days with close in upper 40% of range. Buyers stepping in at the MA. Most relevant at the decision point.
- **C6: Distribution days low.** 0-2 in last 25 days. Non-negotiable at Capital stage. 3+ with a buy signal = odds against you.
- **C7: Range contracted.** ATR10/ATR20 below 0.85. Tight, coiled, ready to move. Volatility contraction = precursor to next leg up.
- **C8: RS holding.** RS percentile >=70. Market still rates the stock highly despite pullback. Collapsed RS = stock-specific weakness, not healthy rest.

Capital qualification: ALL of C1-C8 must pass.

**INVALIDATION — "Failed pullback"**

Any one of these kills the pattern → stage = None:
- Price >5% below the support MA
- Depth >25% from swing high
- Distribution days >=6 in last 25
- RS percentile <50

### Test MA Identification (New)

The system must identify WHICH MA the stock is testing. Scan from 50D → 100D → 150D → 200D and find the first one that price is within X% of and approaching from above.

Output field: `utr_test_ma` = "50D" | "100D" | "150D" | "200D" | None

Not all MA tests are equal:
- 50D retest in a strong uptrend = bread and butter (Minervini's favourite entry)
- 150D retest = deeper correction, still valid but requires stronger quality confirmation
- 200D retest = last line of defence, if this fails → likely Stage 3 transition

Proximity thresholds vary by stage:
- Late: within 5% of the test MA
- Capital: within 2% of the test MA

### Retest Counting (New)

Track how many completed retest cycles have occurred per MA since the uptrend began.

Definition of a completed retest: price came within 2% of the MA, then subsequently moved at least 5% above it, before pulling back again.

"Uptrend began" proxy: first date in lookback where 200D MA began rising (or MM99 would have qualified). Scan forward counting touch-and-bounce cycles per MA.

Output field: `utr_retest_counts` = {"50D": 2, "100D": 0, "150D": 1}

Minervini principle: "First pullback to the 50-day line after a breakout is usually the best buying opportunity. Second time is okay. By the third time, be careful."

Retest count feeds into Capital qualification as a quality modifier:
- 1st retest: highest conviction
- 2nd retest: acceptable
- 3rd+ retest: warning flag — should downgrade or require stronger quality signals

### Signal Mapping: Old → New

| Old Signal | Early | Late | Capital | Notes |
|---|---|---|---|---|
| S1 Depth | E1 (3-10%) | L1 (8-20%) | C2 (<25%) | Split into stage-appropriate windows |
| S2 MA150 support | — | L2 (within 5%) | C1 (within 2%) | Tightens per stage; now multi-MA |
| S3 Vol quality | E3 (indicator) | L3 (<0.85) | C3 (<0.80) | Threshold tightens per stage |
| S4 Up/down ratio | — | L4 (>1.0) | C4 (>1.1) | Late + Capital |
| S5 Candle quality | — | — | C5 (>=50%) | Capital only — decision point |
| S6 Dist days | E4 (0-1) | L6 (0-3) | C6 (0-2) | Threshold varies by stage |
| S7 Contraction | — | L5 (<0.9) | C7 (<0.85) | Late + Capital, tightens |
| S8 RS holding | — | — | C8 (>=70) | Capital gate |
| NEW: E2 | E2 (ST MAs roll) | — | — | 5D/10D declining, 50D/150D rising |
| NEW: test_ma | — | L2 target | C1 target | Which MA is being tested |
| NEW: retest_count | — | display | C modifier | Count per MA since uptrend start |

### Data Requirements

All computed in `build_prices_json` from daily OHLCV rows (same pattern as BP duration):

**Already available:** swing_high, all 7 MAs (current + prev), adv_1m_up/dn, adv_3m_up/dn, rs_percentile

**Already computed (V1, to be retained):** utr_vol_trend, utr_updown_ratio, utr_candle_quality, utr_dist_days, utr_pullback_contraction

**New fields needed:**
- `utr_test_ma`: which MA is being tested ("50D", "100D", "150D", "200D", or None)
- `utr_test_ma_dist`: % distance to test MA
- `utr_retest_counts`: {"50D": N, "100D": N, "150D": N} — completed retest cycles per MA
- `utr_5d_declining`: bool — 5D MA declining (today < yesterday)
- `utr_10d_declining`: bool — 10D MA declining
- `utr_50d_rising`: bool — 50D MA rising
- `utr_150d_rising`: bool — 150D MA rising

### Implementation Plan

1. ~~Add new pre-computed fields to `build_prices_json`~~ ✓ Done 27-Apr-26 — 7 new fields: utr_5d_declining, utr_10d_declining, utr_50d_rising, utr_150d_rising, utr_test_ma, utr_test_ma_dist, utr_retest_counts. Code at lines 509-588. Compiles clean.
2. ~~Rewrite `compute_all_filters` UTR section with stage-progression logic~~ ✓ Done 27-Apr-26 — V1 flat scorecard replaced with Early/Late/Capital/Invalidation lifecycle. Lines 873-1041. File truncated during edit (same issue as V1 session), rebuilt via bash head+append. Compiles clean, 1164 lines.
3. ~~Update `build_dashboard.py` UTR tab rendering + key/legend~~ ✓ Done 27-Apr-26 — renderUTR() rewritten lines 1809-1906. New columns: Stage/Test MA/Retest#/Depth%/MA Dist + 10 quality signals + C# count. Summary tile updated. Key tooltips per V2 spec. File truncated during edit (recurring issue), rebuilt via head+git-tail. Compiles clean, 2427 lines.
4. ~~Test against sample universe~~ ✓ Done 27-Apr-26 — pipeline runs clean end-to-end. V2 JSON structure confirmed correct (18 tests, metrics, ma_direction, invalidation, retest_counts). Dashboard builds without error. **Full 976-stock test pending** (requires real machine run — sandbox universe.json truncated).
5. Tune thresholds based on real results — PENDING (after full universe run)

### Dashboard Tab Redesign (Step 3 Detail)

**Summary tile:** Replace V1 description with: "Pullback lifecycle screen — tracks orderly pullbacks from swing high through MA retest. Early (pulling back) → Late (approaching MA) → Capital (healthy retest, act today) → Invalidated (failed)."

**Column structure (V2):**

| Column | Data Field | Key Tooltip | Stage Relevance |
|--------|-----------|-------------|-----------------|
| Stage | utr_stage | "Pullback lifecycle: Early/Late/Capital/None" | All |
| Test MA | utr_test_ma | "Which MA is being tested (50D/100D/150D/200D)" | Late + Capital |
| Retest # | utr_retest_count | "Completed retest cycles of this MA. 1st = highest conviction (Minervini)" | Late + Capital |
| Depth | utr_depth_pct | "% below swing high. E: 3-10%, L: 8-20%, C: <25%" | All stages, threshold varies |
| MA Dist | utr_test_ma_dist | "% distance to test MA. L: <5%, C: <2%" | Late + Capital |
| ST Roll | utr_5d_declining + utr_10d_declining | "Short-term MAs (5D/10D) rolling over — confirms pullback is short-term" | Early |
| IT Intact | utr_50d_rising + utr_150d_rising | "Intermediate MAs (50D/150D) still rising — trend intact" | Early |
| Vol Q | utr_vol_trend | "10D/50D ADV ratio. E: indicator, L: <0.85, C: <0.80 = sellers drying up" | All stages, threshold tightens |
| Up/Dn | utr_updown_ratio | "Up-day vol / down-day vol. L: >1.0, C: >1.1 = net accumulation" | Late + Capital |
| Candle | utr_candle_quality | "% closes in upper 40% of range (last 10d). C: >=50% = buyers at MA" | Capital |
| Dist | utr_dist_days | "Distribution days (25d). E: 0-1, L: 0-3, C: 0-2. High = institutions selling" | All stages, threshold varies |
| Contr | utr_pullback_contraction | "ATR10/ATR20. L: <0.9, C: <0.85 = volatility coiling, pre-breakout" | Late + Capital |
| RS | rs_percentile | "RS percentile. C: >=70 required. <50 = invalidation" | Capital gate + invalidation |

**Removed from V1:** Composite score column (no longer applicable — stages are lifecycle, not scored). EWS section (5 columns) — these were short-term momentum checks that don't fit the V2 lifecycle model. The MA direction checks (5D/10D/50D rising) are now integrated as proper Early-stage tests instead.

**Retained:** MM99 + PB cross-reference columns. Ratings columns.

**Signal colouring approach:** Show all columns for all stocks. Colour = pass/amber/fail based on the stock's CURRENT stage thresholds. Grey out (neutral) tests that don't apply to the stock's current stage — e.g., Candle quality is grey for Early-stage stocks since it only matters at Capital. This matches the convention used by BP and PB tabs.

**Key toggle:** Same `.key-tip` mechanism. Each `th()` call gets the tooltip text from the table above.

## Backlog

### High Priority
- ~~**UTR S3-S7 implementation**~~ ✓ Done 27-Apr-26 (V1, now superseded)
- **UTR V2 redesign** — stage-progression architecture, test MA identification, retest counting. Design spec agreed 27-Apr-26. Implementation next.
- **Weekday-only scheduling** — Task Scheduler set to Daily, should be Mon-Fri (no Yahoo data on weekends)

### Medium Priority
- **VCP Phase 2** — full volatility contraction pattern detection (multi-day swing analysis)
- **FactSet automation** — SSEM + Valuation tabs depend on manual FactSet JSON exports
- **Change detection / "What's New"** — daily diff summary at top of dashboard

### Lower Priority
- **Qualitative ratings pipeline** — automate Notion → qualitative.json flow
- **Error notification** — email/Notion flag if silent refresh fails
- **Threshold tuning** — calibrate all filter thresholds against real universe results

## Key Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 23-Apr-26 | RS uses relative returns (stock - benchmark) | IBD convention, better cross-market comparison |
| 23-Apr-26 | Swing high = 5-day window local peak in last 6 months | Balance between recency and noise |
| 27-Apr-26 | UTR metrics pre-computed in build_prices_json | Follows existing BP duration pattern, keeps compute_all_filters clean |
| 27-Apr-26 | Candle quality = % closes in upper 40% of range | Crude but directionally right accumulation proxy |
| 27-Apr-26 | Distribution day = close < prior close AND vol > 1.25× ADV50 | Standard O'Neil definition |
| 27-Apr-26 | UTR V1 superseded — flat composite scorecard doesn't match filter intent | Stages should reflect pullback lifecycle, not arbitrary score thresholds |
| 27-Apr-26 | UTR V2: stage = position in pullback lifecycle (Early/Late/Capital/Invalid) | Aligns with MM99, BP, PB stage architecture |
| 27-Apr-26 | UTR V2: identify which MA is being tested (50D/100D/150D/200D) | Different MAs = different setup character and conviction |
| 27-Apr-26 | UTR V2: count prior retests per MA since uptrend began | 1st retest highest conviction, 3rd+ is warning (Minervini) |
| 27-Apr-26 | UTR V2: volume indicators span all stages with tightening thresholds | Volume quality is an early warning system, not just a Capital gate |
| 27-Apr-26 | CHART_REGISTRY declared at global scope (before IIFE) | Lazy-loaded chart files eval in async callback scope — must be global for registration to work |
| 27-Apr-26 | overflow-x:clip on .data-table-wrap (was hidden) | Enables position:sticky on table headers by not creating a scroll context |
| 27-Apr-26 | Edit tool ban tightened to >~50KB (was >~800KB) | build_dashboard.py (156KB) was truncated by Edit tool — third occurrence |
| 27-Apr-26 | UTR sort keys: numeric fields (sort_vol, sort_st, etc.) replacing signal strings | Signal strings (pass/amber/fail) all sort identically — numeric values enable meaningful sort |
| 27-Apr-26 | UTR stage filter toggles replace score buttons (5/8, 6/8, 7/8, 8/8) | Score thresholds are meaningless in V2 lifecycle model — stage filters match the architecture |

## File Map

```
master-dashboard/
├── index.html              ← generated output (GitHub Pages serves this)
├── data/
│   ├── prices.json         ← per-stock price/MA/RS/volume data
│   ├── filter-results.json ← all 5 filters, per-stock pass/fail
│   ├── factset-ssem.json   ← FactSet consensus (manual export)
│   ├── factset-valuation.json ← FactSet P/E (manual export)
│   ├── qualitative.json    ← case ratings
│   ├── universe.json       ← stock list (976 when --full-universe)
│   └── chart-data.json     ← LEGACY, 214MB, gitignored
├── charts/                 ← per-ticker JS files (~976 files)
├── scripts/
│   ├── generate_master_data.py  ← data fetch + filter computation
│   ├── generate_chart_data.py   ← per-ticker chart JS generation
│   ├── build_dashboard.py       ← HTML builder
│   ├── refresh-dashboard.bat    ← interactive (double-click)
│   ├── refresh-dashboard-silent.bat ← Task Scheduler (18:00 daily)
│   └── SETUP-SCHEDULED-REFRESH.md
├── cache/                  ← yfinance OHLCV cache (gitignored)
├── backups/                ← pre/post-build HTML snapshots (gitignored)
├── logs/                   ← refresh logs (gitignored)
└── .gitignore
```
