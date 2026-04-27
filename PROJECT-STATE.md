# Master Dashboard — Project State

**Last updated:** 2026-04-27 (Watson, Cowork session)
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
| 4 | Uptrend Retest | **Complete** | All 8 signals live (27-Apr-26). EWS working. Thresholds may need tuning. |
| 5 | VCP | **Stub** | Stage 2 uptrend only. Full pattern detection = Phase 2 |
| 6 | Technical Data | **Complete** | Raw data reference (7 SMAs, volume, 52W) |
| 7 | SSEM | **Complete** | FactSet consensus data (manual export dependency) |
| 8 | Valuation | **Complete** | FactSet P/E data (manual export dependency) |
| 9 | Combinations | **Complete** | Cross-filter matrix, multi-filter scoring |
| 10 | Live Investments | **Complete** | Portfolio overlay from positions.json |

## Current Work: UTR Signals S3-S7

**COMPLETED (27-Apr-26).** Implemented the 5 placeholder UTR signals:

- S3: Volume quality — is volume declining during pullback? (10D ADV vs 50D ADV)
- S4: Up/down volume ratio — avg up-day vol / avg down-day vol (data already exists)
- S5: Candle quality — % of closes in upper 40% of daily range (accumulation proxy)
- S6: Distribution days — high-volume down days in last 25 sessions
- S7: Pullback contraction — ATR10 vs ATR20 (declining = contracting)

**Approach:** Pre-computed daily-derived metrics in `build_prices_json` (same pattern as basing plateau duration), passed through to `compute_all_filters`. Thresholds based on O'Neil/Minervini conventions.

**Thresholds (for future tuning):**
- S3 vol_trend: < 0.8 pass, 0.8-1.1 amber, > 1.1 fail
- S4 updown_ratio: > 1.3 pass, 0.9-1.3 amber, < 0.9 fail
- S5 candle_quality: >= 60% pass, 40-60% amber, < 40% fail
- S6 dist_days: 0-2 pass, 3-4 amber, 5+ fail
- S7 pullback_contraction: < 0.85 pass, 0.85-1.1 amber, > 1.1 fail

**Verified:** Sample run with 5 test stocks — all 8 signals producing real pass/amber/fail. Good differentiation. No division-by-zero errors.

## Backlog

### High Priority
- ~~**UTR S3-S7 implementation**~~ ✓ Done 27-Apr-26
- **Weekday-only scheduling** — Task Scheduler set to Daily, should be Mon-Fri (no Yahoo data on weekends)
- **UTR threshold tuning** — run against full 976-stock universe, eyeball pass/fail distribution, adjust thresholds

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
