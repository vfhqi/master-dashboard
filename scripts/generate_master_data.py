"""
Master Dashboard — Unified Data Pipeline
=========================================
Reads universe.json, fetches OHLCV via yfinance (or generates sample data),
computes 7 SMAs, RS composite, and runs all 5 screening filters.

Outputs:
  data/prices.json         — per-stock price, MAs, volume, 52W stats
  data/filter-results.json — per-stock pass/fail for all 5 filters
  data/rs-data.json        — RS composite + percentile ranks

Usage:
  python generate_master_data.py                 # yfinance with cache
  python generate_master_data.py --sample        # sample data (no network)
  python generate_master_data.py --full-refresh  # force re-pull
"""

import json
import sys
import os
import math
from pathlib import Path
from datetime import datetime, timedelta, date
from collections import defaultdict
import argparse

# ── Paths ─────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
CACHE_DIR = PROJECT_DIR / "cache"
UNIVERSE_PATH = DATA_DIR / "universe.json"

# Reuse existing pullback-monitor cache if available
LEGACY_CACHE_DIR = SCRIPT_DIR.parent.parent / "databases" / "pullback-cache"

LOOKBACK_DAYS = 1650  # ~5.5 years for 200D MA warmup + chart display
SMA_PERIODS = [5, 10, 20, 50, 100, 150, 200]
BENCHMARK_TICKER = "^STOXX"

# ── Cache System (reused from pullback monitor) ──────────────────────────

def _cache_path(yf_ticker, cache_dir=None):
    """Return the cache file path for a yfinance ticker."""
    cd = cache_dir or CACHE_DIR
    safe = yf_ticker.replace("^", "_caret_").replace(".", "_dot_").replace("/", "_slash_")
    return cd / f"{safe}.json"


def load_cache(yf_ticker):
    """Load cached OHLCV rows. Checks project cache first, then legacy."""
    for cd in [CACHE_DIR, LEGACY_CACHE_DIR]:
        path = _cache_path(yf_ticker, cd)
        if path.exists():
            try:
                with open(path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                continue
    return None


def save_cache(yf_ticker, rows):
    """Save OHLCV rows to project cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(yf_ticker)
    with open(path, "w") as f:
        json.dump(rows, f, separators=(",", ":"))


def _merge_cached_and_new(cached_rows, new_rows):
    by_date = {}
    for r in (cached_rows or []):
        by_date[r["date"]] = r
    for r in (new_rows or []):
        by_date[r["date"]] = r
    return sorted(by_date.values(), key=lambda r: r["date"])


# ── yfinance Fetch ────────────────────────────────────────────────────────

def _fetch_ticker(yf, ticker, start_date, end_date):
    """Fetch OHLCV for a single ticker from yfinance."""
    try:
        t = yf.Ticker(ticker)
        hist = t.history(start=start_date.strftime("%Y-%m-%d"),
                        end=end_date.strftime("%Y-%m-%d"))
        if len(hist) > 0:
            rows = []
            for idx, row in hist.iterrows():
                rows.append({
                    "date": idx.strftime("%Y-%m-%d"),
                    "open": round(float(row["Open"]), 4),
                    "high": round(float(row["High"]), 4),
                    "low": round(float(row["Low"]), 4),
                    "close": round(float(row["Close"]), 4),
                    "volume": int(row["Volume"]),
                })
            return rows
        return []
    except Exception as e:
        print(f"  ERR  {ticker:12s} — {e}")
        return []


def fetch_all_data(universe, full_refresh=False):
    """Fetch OHLCV for all universe stocks + benchmark."""
    import yfinance as yf

    end_date = datetime.now()
    full_start = end_date - timedelta(days=LOOKBACK_DAYS + 250)
    OVERLAP = 5

    tickers = [(s["yfinance_ticker"], s["ticker"]) for s in universe["stocks"]]
    tickers.append((BENCHMARK_TICKER, "BENCHMARK"))

    data = {}
    stats = {"full": 0, "incr": 0, "cache": 0, "err": 0}

    for yf_ticker, label in tickers:
        cached = None if full_refresh else load_cache(yf_ticker)

        if cached and not full_refresh:
            last_date = datetime.strptime(cached[-1]["date"], "%Y-%m-%d")
            days_stale = (end_date - last_date).days
            if days_stale <= 1:
                data[yf_ticker] = cached
                stats["cache"] += 1
                print(f"  CACHE {yf_ticker:12s} — {len(cached)} days")
                continue

            new_rows = _fetch_ticker(yf, yf_ticker, last_date - timedelta(days=OVERLAP), end_date)
            if new_rows:
                merged = _merge_cached_and_new(cached, new_rows)
                cutoff = (end_date - timedelta(days=LOOKBACK_DAYS + 250)).strftime("%Y-%m-%d")
                merged = [r for r in merged if r["date"] >= cutoff]
                save_cache(yf_ticker, merged)
                data[yf_ticker] = merged
                stats["incr"] += 1
                print(f"  INCR  {yf_ticker:12s} — {len(new_rows)} new, {len(merged)} total")
            else:
                data[yf_ticker] = cached
                stats["cache"] += 1
                print(f"  STALE {yf_ticker:12s} — using {len(cached)}-day cache")
        else:
            new_rows = _fetch_ticker(yf, yf_ticker, full_start, end_date)
            if new_rows:
                save_cache(yf_ticker, new_rows)
                data[yf_ticker] = new_rows
                stats["full"] += 1
                print(f"  FULL  {yf_ticker:12s} — {len(new_rows)} days")
            else:
                stats["err"] += 1
                print(f"  FAIL  {yf_ticker:12s}")

    print(f"\n  Summary: {stats['full']} full, {stats['incr']} incr, {stats['cache']} cached, {stats['err']} errors\n")
    return data


# ── Sample Data Generator ─────────────────────────────────────────────────

def generate_sample_data(universe):
    """Generate realistic sample OHLCV for testing without network."""
    import random
    random.seed(42)

    data = {}
    end = datetime.now()

    tickers = [(s["yfinance_ticker"], s["ticker"]) for s in universe["stocks"]]
    tickers.append((BENCHMARK_TICKER, "BENCHMARK"))

    for yf_ticker, label in tickers:
        rows = []
        price = random.uniform(15, 500)
        base_vol = random.randint(100000, 5000000)

        # Generate ~500 trading days (enough for 200D MA + history)
        trading_days = 500
        current = end - timedelta(days=int(trading_days * 1.45))

        # Alternate advance/pullback phases for realistic patterns
        phases = [
            (80, 0.002), (40, -0.001), (60, 0.0015), (30, -0.0008),
            (50, 0.002), (25, -0.001), (40, 0.0018), (20, -0.0012),
            (60, 0.001), (30, -0.0005), (65, 0.0012)
        ]
        phase_idx = 0
        phase_day = 0

        for _ in range(trading_days):
            while current.weekday() >= 5:
                current += timedelta(days=1)

            if phase_idx < len(phases):
                drift = phases[phase_idx][1]
                if phase_day >= phases[phase_idx][0]:
                    phase_idx += 1
                    phase_day = 0
            else:
                drift = 0.001

            daily_ret = drift + random.gauss(0, 0.015)
            price *= (1 + daily_ret)
            price = max(price, 0.5)

            intraday_range = price * random.uniform(0.008, 0.025)
            high = price + random.uniform(0, intraday_range * 0.6)
            low = price - random.uniform(0, intraday_range * 0.6)
            open_price = low + random.uniform(0.2, 0.8) * (high - low)
            vol = int(base_vol * random.uniform(0.5, 2.0))

            rows.append({
                "date": current.strftime("%Y-%m-%d"),
                "open": round(open_price, 4),
                "high": round(high, 4),
                "low": round(low, 4),
                "close": round(price, 4),
                "volume": vol,
            })

            current += timedelta(days=1)
            phase_day += 1

        data[yf_ticker] = rows
        print(f"  SAMPLE {yf_ticker:12s} — {len(rows)} days, last close: {price:.2f}")

    return data


# ── SMA Computation ───────────────────────────────────────────────────────

def compute_smas(ohlcv_rows, periods=SMA_PERIODS):
    """Compute SMAs for all specified periods. Returns list of dicts with SMA fields added."""
    closes = [r["close"] for r in ohlcv_rows]
    n = len(closes)

    result = []
    for i in range(n):
        row = dict(ohlcv_rows[i])
        for p in periods:
            key = f"sma_{p}"
            if i >= p - 1:
                row[key] = round(sum(closes[i - p + 1:i + 1]) / p, 4)
            else:
                row[key] = None
        result.append(row)
    return result


# ── RS Composite (IBD-style) ──────────────────────────────────────────────

def compute_rs_composite(stock_rows, benchmark_rows):
    """Compute IBD-style RS composite: 0.4*3M + 0.2*6M + 0.2*9M + 0.2*12M.
    Returns the composite value and component returns."""
    if len(stock_rows) < 252 or len(benchmark_rows) < 252:
        return None, {}

    def _period_return(rows, days):
        if len(rows) < days:
            return None
        start_price = rows[-days]["close"]
        end_price = rows[-1]["close"]
        if start_price <= 0:
            return None
        ret = (end_price - start_price) / start_price
        return max(min(ret, 2.0), -2.0)  # Cap at +/-200%

    stock_returns = {}
    bench_returns = {}
    for label, days in [("3M", 63), ("6M", 126), ("9M", 189), ("12M", 252)]:
        stock_returns[label] = _period_return(stock_rows, days)
        bench_returns[label] = _period_return(benchmark_rows, days)

    if any(v is None for v in stock_returns.values()):
        return None, stock_returns

    # Use RELATIVE returns (stock - benchmark) per Q6 decision (23-Apr-26)
    rel_returns = {}
    for label in ["3M", "6M", "9M", "12M"]:
        sr = stock_returns[label]
        br = bench_returns.get(label)
        if sr is not None and br is not None:
            rel_returns[label] = sr - br
        else:
            rel_returns[label] = sr  # Fallback to absolute if no benchmark

    composite = (0.4 * rel_returns["3M"] +
                 0.2 * rel_returns["6M"] +
                 0.2 * rel_returns["9M"] +
                 0.2 * rel_returns["12M"])

    return round(composite, 6), stock_returns


def compute_rs_percentiles(rs_values):
    """Given dict of {ticker: rs_composite}, compute 0-99 percentile ranks."""
    valid = {k: v for k, v in rs_values.items() if v is not None}
    if not valid:
        return {}
    sorted_items = sorted(valid.items(), key=lambda x: x[1])
    n = len(sorted_items)
    percentiles = {}
    for rank, (ticker, val) in enumerate(sorted_items):
        percentiles[ticker] = int(round(rank / max(n - 1, 1) * 99))
    return percentiles


# ── prices.json Builder ──────────────────────────────────────────────────

def build_prices_json(universe, raw_data, benchmark_rows):
    """Build prices.json with per-stock price data, MAs, 52W stats, RS."""
    prices = []
    rs_composites = {}

    for stock in universe["stocks"]:
        yf = stock["yfinance_ticker"]
        ticker = stock["ticker"]

        if yf not in raw_data or len(raw_data[yf]) < 200:
            print(f"  SKIP {ticker} — insufficient data ({len(raw_data.get(yf, []))} rows)")
            continue

        rows_with_sma = compute_smas(raw_data[yf])

        # Latest row + previous day
        latest = rows_with_sma[-1]
        prev = rows_with_sma[-2] if len(rows_with_sma) > 1 else latest

        # 52-week high/low (last 252 trading days)
        lookback_252 = rows_with_sma[-252:] if len(rows_with_sma) >= 252 else rows_with_sma
        high_52w = max(r["high"] for r in lookback_252)
        low_52w = min(r["low"] for r in lookback_252)

        # Swing high detection (Q8, 23-Apr-26): most recent local peak
        # A swing high = a day whose high is higher than the 5 days before and after it
        swing_high = high_52w  # fallback to 52W high
        lookback_for_swing = rows_with_sma[-126:] if len(rows_with_sma) >= 126 else rows_with_sma  # 6 months
        swing_window = 5  # days on each side
        for si in range(len(lookback_for_swing) - 1, swing_window - 1, -1):
            candidate = lookback_for_swing[si]["high"]
            is_peak = True
            for sj in range(max(0, si - swing_window), min(len(lookback_for_swing), si + swing_window + 1)):
                if sj != si and lookback_for_swing[sj]["high"] > candidate:
                    is_peak = False
                    break
            if is_peak:
                swing_high = candidate
                break

        # Volume averages
        recent_20 = rows_with_sma[-20:] if len(rows_with_sma) >= 20 else rows_with_sma
        recent_60 = rows_with_sma[-60:] if len(rows_with_sma) >= 60 else rows_with_sma
        adv_1m = round(sum(r["volume"] for r in recent_20) / len(recent_20))
        adv_3m = round(sum(r["volume"] for r in recent_60) / len(recent_60))

        # Up/down day volume split (ORIG-18)
        # Classify each day: up = close >= prior close, down = close < prior close
        def _split_vol(window):
            up_vols, dn_vols = [], []
            for i in range(1, len(window)):
                if window[i]["close"] >= window[i - 1]["close"]:
                    up_vols.append(window[i]["volume"])
                else:
                    dn_vols.append(window[i]["volume"])
            avg_up = round(sum(up_vols) / len(up_vols)) if up_vols else 0
            avg_dn = round(sum(dn_vols) / len(dn_vols)) if dn_vols else 0
            return avg_up, avg_dn

        adv_1m_up, adv_1m_dn = _split_vol(recent_20)
        adv_3m_up, adv_3m_dn = _split_vol(recent_60)

        # RS composite
        rs_composite, rs_returns = compute_rs_composite(raw_data[yf], benchmark_rows)
        rs_composites[ticker] = rs_composite

        # Build MAs dict (current + previous day for DoD comparison)
        mas = {}
        for p in SMA_PERIODS:
            key = f"sma_{p}"
            mas[f"{p}D"] = latest.get(key)
            mas[f"{p}D_prev"] = prev.get(key)

        # Previous day close for the SMA DoD calculations in the pullback monitor
        prev_sma_rows = rows_with_sma[-2] if len(rows_with_sma) > 1 else None

        # 200D uptrend month count: how many of last 12 months had 200D MA rising MoM
        ma200_months_rising = 0
        ma200_month_detail = []
        if len(rows_with_sma) >= 252:
            # Sample month-end 200D values (every ~21 trading days)
            month_samples = []
            for mi in range(13):  # 13 sample points = 12 intervals
                idx = len(rows_with_sma) - 1 - (mi * 21)
                if idx >= 0 and rows_with_sma[idx].get("sma_200") is not None:
                    month_samples.append(rows_with_sma[idx]["sma_200"])
                else:
                    month_samples.append(None)
            month_samples.reverse()  # oldest first
            for mi in range(1, len(month_samples)):
                if month_samples[mi] is not None and month_samples[mi - 1] is not None:
                    rising = month_samples[mi] > month_samples[mi - 1]
                    ma200_month_detail.append(rising)
                    if rising:
                        ma200_months_rising += 1
                else:
                    ma200_month_detail.append(False)

        # Basing Plateau 3-month duration: check each BP test over last 63 trading days
        # 95% threshold = at least 60 of 63 days must meet the condition.
        # Per-day pass/fail history + current continuous-streak retained (02-May-26)
        # so the dashboard can render duration richness, not just binary flags.
        bp_duration = {"loose": False, "medium": False, "tight": False}
        bp_lookback = min(63, len(rows_with_sma))
        bp_window = rows_with_sma[-bp_lookback:]
        bp_threshold = 0.95

        def _bp_history(window, test_fn):
            """Return per-day boolean list (oldest first) of test outcomes."""
            return [bool(test_fn(r)) for r in window]

        def _bp_streak(history):
            """Walk history backwards from latest day; count consecutive True's
            until first False. Returns 0 if today is failing."""
            n = 0
            for v in reversed(history):
                if v:
                    n += 1
                else:
                    break
            return n

        def _wp(r, key_a, key_b, pct):
            """Within ±pct of each other using SMA values from a single row."""
            va = r.get(key_a)
            vb = r.get(key_b)
            if va is None or vb is None or vb == 0:
                return False
            return abs(va - vb) / vb <= pct

        # Loose: P within ±15% of 200D AND 150D, AND 50D within ±15% of 200D AND 150D
        loose_test = lambda r: (
            _wp(r, "close", "sma_200", 0.15) and _wp(r, "close", "sma_150", 0.15) and
            _wp(r, "sma_50", "sma_200", 0.15) and _wp(r, "sma_50", "sma_150", 0.15))
        loose_history = _bp_history(bp_window, loose_test)
        loose_passes = sum(1 for v in loose_history if v)
        loose_pct = (loose_passes / len(loose_history)) if loose_history else 0
        bp_duration["loose"] = loose_pct >= bp_threshold
        bp_duration["loose_pct"] = round(loose_pct, 3)
        bp_duration["loose_days_passed"] = loose_passes
        bp_duration["loose_days_total"] = len(loose_history)
        bp_duration["loose_history"] = loose_history
        bp_duration["loose_streak"] = _bp_streak(loose_history)

        # Medium: + 150D within ±10% of 200D
        medium_test = lambda r: (
            _wp(r, "close", "sma_200", 0.10) and _wp(r, "close", "sma_150", 0.10) and
            _wp(r, "sma_50", "sma_200", 0.10) and _wp(r, "sma_50", "sma_150", 0.10) and
            _wp(r, "sma_150", "sma_200", 0.10))
        medium_history = _bp_history(bp_window, medium_test)
        medium_passes = sum(1 for v in medium_history if v)
        medium_pct = (medium_passes / len(medium_history)) if medium_history else 0
        bp_duration["medium"] = medium_pct >= bp_threshold
        bp_duration["medium_pct"] = round(medium_pct, 3)
        bp_duration["medium_days_passed"] = medium_passes
        bp_duration["medium_days_total"] = len(medium_history)
        bp_duration["medium_history"] = medium_history
        bp_duration["medium_streak"] = _bp_streak(medium_history)

        # Tight: all within ±5%
        tight_test = lambda r: (
            _wp(r, "close", "sma_200", 0.05) and _wp(r, "close", "sma_150", 0.05) and
            _wp(r, "sma_50", "sma_200", 0.05) and _wp(r, "sma_50", "sma_150", 0.05) and
            _wp(r, "sma_150", "sma_200", 0.05))
        tight_history = _bp_history(bp_window, tight_test)
        tight_passes = sum(1 for v in tight_history if v)
        tight_pct = (tight_passes / len(tight_history)) if tight_history else 0
        bp_duration["tight"] = tight_pct >= bp_threshold
        bp_duration["tight_pct"] = round(tight_pct, 3)
        bp_duration["tight_days_passed"] = tight_passes
        bp_duration["tight_days_total"] = len(tight_history)
        bp_duration["tight_history"] = tight_history
        bp_duration["tight_streak"] = _bp_streak(tight_history)

        # ── Pass B (03-May-26): 3 new orthogonal Stage-1 tests ─────
        # Stored as bp_extras dict; consumed by qualification block as bp.flat_mas_pass /
        # bp.vol_contraction_pass / bp.time_in_base_pass and the bp.score composite.

        bp_extras = {
            "flat_mas_pass": False, "slope_200": None, "slope_150": None,
            "vol_contraction_pass": False, "vol_ratio": None,
            "time_in_base_pass": False, "days_since_drop": None,
        }

        # T-NEW-1: MA slope flatness (annualised)
        # slope = (sma_today - sma_63d_ago) / sma_63d_ago * (252/63) = annualised
        # Pass if abs(slope_200) <= 0.05 AND abs(slope_150) <= 0.08 (loosened in Pass A.3)
        if len(rows_with_sma) >= 64:
            sma_200_today = rows_with_sma[-1].get("sma_200")
            sma_150_today = rows_with_sma[-1].get("sma_150")
            sma_200_prior = rows_with_sma[-64].get("sma_200")
            sma_150_prior = rows_with_sma[-64].get("sma_150")
            if sma_200_today and sma_200_prior and sma_200_prior != 0:
                slope_200 = (sma_200_today - sma_200_prior) / sma_200_prior * (252.0 / 63.0)
                bp_extras["slope_200"] = round(slope_200, 4)
            if sma_150_today and sma_150_prior and sma_150_prior != 0:
                slope_150 = (sma_150_today - sma_150_prior) / sma_150_prior * (252.0 / 63.0)
                bp_extras["slope_150"] = round(slope_150, 4)
            if bp_extras["slope_200"] is not None and bp_extras["slope_150"] is not None:
                # Pass A.3 (03-May-26): loosened from ±2%/±4% to ±5%/±8% per Richard.
                # Original ±2% caught only 5% of universe (most stocks have mild trend drift in
                # current Iran-driven environment). ±5% on 200D is still genuinely flat (5%/yr ≈ barely ticking).
                bp_extras["flat_mas_pass"] = (
                    abs(bp_extras["slope_200"]) <= 0.05 and abs(bp_extras["slope_150"]) <= 0.08
                )

        # T-NEW-2: Volume contraction — avg L3M vol / avg L12M vol < 0.90
        # L3M is INCLUDED in L12M (per Richard's spec; Watson flagged limitation in decisions.md).
        if len(rows_with_sma) >= 252:
            vols_l3m = [r.get("volume") for r in rows_with_sma[-63:] if r.get("volume") is not None]
            vols_l12m = [r.get("volume") for r in rows_with_sma[-252:] if r.get("volume") is not None]
            if len(vols_l3m) > 0 and len(vols_l12m) > 0:
                avg_l3m = sum(vols_l3m) / len(vols_l3m)
                avg_l12m = sum(vols_l12m) / len(vols_l12m)
                if avg_l12m > 0:
                    ratio = avg_l3m / avg_l12m
                    bp_extras["vol_ratio"] = round(ratio, 3)
                    bp_extras["vol_contraction_pass"] = ratio < 0.90

        # T-NEW-3: Time-in-base — ≥60 trading days since last 20% drop from prior 30d high
        # AND no MM99 Capital pass in last ~3 month-ends. (mm99_monthly_history populated below;
        # we use this stock's mm99_monthly_history list which we'll compute next.)
        # Walk back from today, find most recent close that was ≤80% of its prior 30d high.
        if len(rows_with_sma) >= 60:
            window_n = min(252, len(rows_with_sma))
            most_recent_drop_idx = None
            for back_i in range(window_n - 1, 30, -1):  # newest -> oldest, but keep last drop
                cl = rows_with_sma[-1 - (window_n - 1 - back_i)].get("close") if back_i < window_n else None
            # Simpler: index 0..len(rows_with_sma)-1 walking forward, track latest qualifying drop
            most_recent_drop_idx = None
            n_total = len(rows_with_sma)
            for i in range(30, n_total):
                row_i = rows_with_sma[i]
                cl = row_i.get("close")
                if cl is None:
                    continue
                prior_window = rows_with_sma[i-30:i]
                prior_highs = [r.get("high") for r in prior_window if r.get("high") is not None]
                if not prior_highs:
                    continue
                prior_high = max(prior_highs)
                if prior_high > 0 and cl <= prior_high * 0.80:
                    most_recent_drop_idx = i
            if most_recent_drop_idx is not None:
                days_since = (n_total - 1) - most_recent_drop_idx
            else:
                days_since = window_n  # no drop found in window — treat as full window
            bp_extras["days_since_drop"] = days_since
            # mm99 recent capital check — populated below; use placeholder of False here, refined
            # after mm99_monthly_history is built. Pre-set time_in_base_pass on days_since alone;
            # final pass-flag is recomputed after mm99_monthly_history exists (see below).
            bp_extras["time_in_base_pass"] = days_since >= 60

        # ── MM99 Monthly History (T1-T8, 28-Apr-26) ────────────────
        # At each of the last 12 calendar month-ends, reconstruct all 8
        # Minervini technical tests and record whether ALL 8 passed.
        # Result: list of 12 booleans, oldest first.
        mm99_monthly_history = []
        if len(rows_with_sma) >= 252:
            # Build a date-indexed lookup from rows_with_sma for fast access
            # Each row has row["date"] as a string "YYYY-MM-DD"
            row_dates = [r["date"] for r in rows_with_sma]

            # Determine the 12 calendar month-ends preceding the latest date
            latest_date = datetime.strptime(row_dates[-1], "%Y-%m-%d").date()
            month_end_dates = []
            # Walk backwards from the month before the latest date's month
            d = latest_date.replace(day=1) - timedelta(days=1)  # last day of prior month
            for _ in range(12):
                month_end_dates.append(d)
                d = d.replace(day=1) - timedelta(days=1)  # last day of month before
            month_end_dates.reverse()  # oldest first

            for me_date in month_end_dates:
                # Find the nearest trading day on or before this month-end
                me_str = me_date.strftime("%Y-%m-%d")
                # Binary search: find last row with date <= me_str
                best_idx = None
                for scan_i in range(len(row_dates) - 1, -1, -1):
                    if row_dates[scan_i] <= me_str:
                        best_idx = scan_i
                        break

                if best_idx is None or best_idx < 252:
                    # Not enough history at this month-end to compute 52W stats
                    mm99_monthly_history.append(False)
                    continue

                snap = rows_with_sma[best_idx]
                snap_p = snap["close"]
                snap_200 = snap.get("sma_200")
                snap_150 = snap.get("sma_150")
                snap_50 = snap.get("sma_50")

                if snap_200 is None or snap_150 is None or snap_50 is None:
                    mm99_monthly_history.append(False)
                    continue

                # T1: Price > 200D MA
                h_t1 = snap_p > snap_200
                # T2: 200D MA rising (compare to prior month's nearest row)
                # Use row ~21 trading days earlier
                prev_200_idx = max(0, best_idx - 21)
                prev_200_val = rows_with_sma[prev_200_idx].get("sma_200")
                h_t2 = (prev_200_val is not None and snap_200 > prev_200_val)
                # T3: Price > 150D MA
                h_t3 = snap_p > snap_150
                # T4: 150D > 200D
                h_t4 = snap_150 > snap_200
                # T5: 50D > 150D
                h_t5 = snap_50 > snap_150
                # T6: Price > 50D MA
                h_t6 = snap_p > snap_50
                # T7: Price > 52W Low * 1.20 (at that point in time)
                lookback_52w = rows_with_sma[max(0, best_idx - 252):best_idx + 1]
                h_h52 = max(r["high"] for r in lookback_52w)
                h_l52 = min(r["low"] for r in lookback_52w)
                h_t7 = (h_l52 > 0 and snap_p > h_l52 * 1.20)
                # T8: Price within 25% of 52W High
                h_t8 = (h_h52 > 0 and snap_p >= h_h52 * 0.75)

                all_pass = all([h_t1, h_t2, h_t3, h_t4, h_t5, h_t6, h_t7, h_t8])
                mm99_monthly_history.append(all_pass)
        else:
            mm99_monthly_history = [False] * 12

        # Pad to exactly 12 if we got fewer month-ends
        while len(mm99_monthly_history) < 12:
            mm99_monthly_history.insert(0, False)

        # Pass B refinement: time_in_base_pass also requires no recent MM99 Capital pass
        # (any of the last 3 month-ends). If MM99 Capital fired recently, the stock has
        # already launched into Stage 2 — it's not a fresh Stage 1 base.
        if bp_extras.get("time_in_base_pass") and len(mm99_monthly_history) >= 3:
            recent_mm99_capital = any(mm99_monthly_history[-3:])
            if recent_mm99_capital:
                bp_extras["time_in_base_pass"] = False

        # ── UTR pre-computed metrics (S3-S7, 27-Apr-26) ─────────────
        # These feed into compute_all_filters for Uptrend Retest signals.
        # Pattern follows BP duration: compute from daily rows here, pass as summary fields.

        # S3: Volume trend — is volume drying up during pullback?
        # Compare recent 10-day ADV to 50-day ADV. Ratio < 1.0 = volume declining (constructive).
        recent_10 = rows_with_sma[-10:] if len(rows_with_sma) >= 10 else rows_with_sma
        recent_50 = rows_with_sma[-50:] if len(rows_with_sma) >= 50 else rows_with_sma
        adv_10d = sum(r["volume"] for r in recent_10) / len(recent_10) if recent_10 else 0
        adv_50d = sum(r["volume"] for r in recent_50) / len(recent_50) if recent_50 else 0
        utr_vol_trend = round(adv_10d / adv_50d, 4) if adv_50d > 0 else None

        # S4: Up/down volume ratio (1-month) — already have adv_1m_up / adv_1m_dn
        utr_updown_ratio = round(adv_1m_up / adv_1m_dn, 4) if adv_1m_dn > 0 else None

        # S5: Candle quality — % of last 20 days where close is in upper 40% of daily range
        # Upper 40% means close >= low + 0.6 * (high - low). This signals accumulation.
        candle_window = rows_with_sma[-20:] if len(rows_with_sma) >= 20 else rows_with_sma
        candle_upper_count = 0
        candle_valid = 0
        for cr in candle_window:
            rng = cr["high"] - cr["low"]
            if rng > 0:
                candle_valid += 1
                if cr["close"] >= cr["low"] + 0.6 * rng:
                    candle_upper_count += 1
        utr_candle_quality = round(candle_upper_count / candle_valid, 4) if candle_valid > 0 else None

        # S6: Distribution days in last 25 sessions
        # O'Neil definition: close < prior close AND volume > 1.25× ADV50
        dist_window = rows_with_sma[-26:] if len(rows_with_sma) >= 26 else rows_with_sma  # 26 rows → 25 comparisons
        dist_day_count = 0
        for di in range(1, len(dist_window)):
            if (dist_window[di]["close"] < dist_window[di - 1]["close"] and
                    adv_50d > 0 and dist_window[di]["volume"] > 1.25 * adv_50d):
                dist_day_count += 1
        utr_dist_days = dist_day_count

        # S7: Pullback contraction — ATR10 vs ATR20
        # True Range = max(H-L, |H-prev_C|, |L-prev_C|). Ratio < 1.0 = range contracting.
        def _atr(window):
            """Average True Range over a window of daily rows."""
            trs = []
            for ai in range(1, len(window)):
                h = window[ai]["high"]
                l = window[ai]["low"]
                pc = window[ai - 1]["close"]
                tr = max(h - l, abs(h - pc), abs(l - pc))
                trs.append(tr)
            return sum(trs) / len(trs) if trs else 0

        atr_window_20 = rows_with_sma[-21:] if len(rows_with_sma) >= 21 else rows_with_sma
        atr_window_10 = rows_with_sma[-11:] if len(rows_with_sma) >= 11 else rows_with_sma
        atr_20 = _atr(atr_window_20)
        atr_10 = _atr(atr_window_10)
        utr_pullback_contraction = round(atr_10 / atr_20, 4) if atr_20 > 0 else None

        # ── UTR V2 pre-computed fields (27-Apr-26) ─────────────────────
        # MA direction bools: confirm pullback is short-term (Early stage E2)
        utr_5d_declining = False
        utr_10d_declining = False
        utr_50d_rising = False
        utr_150d_rising = False
        if prev_sma_rows is not None:
            sma5_now = latest.get("sma_5")
            sma5_prev = prev_sma_rows.get("sma_5")
            if sma5_now is not None and sma5_prev is not None:
                utr_5d_declining = sma5_now < sma5_prev
            sma10_now = latest.get("sma_10")
            sma10_prev = prev_sma_rows.get("sma_10")
            if sma10_now is not None and sma10_prev is not None:
                utr_10d_declining = sma10_now < sma10_prev
            sma50_now = latest.get("sma_50")
            sma50_prev = prev_sma_rows.get("sma_50")
            if sma50_now is not None and sma50_prev is not None:
                utr_50d_rising = sma50_now > sma50_prev
            sma150_now = latest.get("sma_150")
            sma150_prev = prev_sma_rows.get("sma_150")
            if sma150_now is not None and sma150_prev is not None:
                utr_150d_rising = sma150_now > sma150_prev

        # Test MA identification: which MA is price approaching from above?
        # Scan 50D → 100D → 150D → 200D. First one price is within range of AND above.
        utr_test_ma = None
        utr_test_ma_dist = None
        _price = latest["close"]
        for _ma_label, _ma_period in [("50D", 50), ("100D", 100), ("150D", 150), ("200D", 200)]:
            _ma_val = latest.get(f"sma_{_ma_period}")
            if _ma_val is not None and _ma_val > 0:
                _dist_pct = (_price - _ma_val) / _ma_val
                # Price must be above or at most 2% below (slight undercut OK per Minervini)
                # and within 10% above (beyond 10% above = not approaching)
                if -0.02 <= _dist_pct <= 0.10:
                    utr_test_ma = _ma_label
                    utr_test_ma_dist = round(_dist_pct * 100, 2)  # as percentage
                    break

        # Retest counting: completed touch-and-bounce cycles per MA since uptrend began.
        # A completed retest = price came within 2% of MA, then moved at least 5% above it.
        # "Uptrend began" proxy: first point where 200D MA began rising in our lookback.
        utr_retest_counts = {"50D": 0, "100D": 0, "150D": 0}
        if len(rows_with_sma) >= 200:
            # Find uptrend start: first row where 200D is rising vs prior row
            _uptrend_start_idx = None
            for _ri in range(1, len(rows_with_sma)):
                _r_now = rows_with_sma[_ri]
                _r_prev = rows_with_sma[_ri - 1]
                if (_r_now.get("sma_200") is not None and _r_prev.get("sma_200") is not None
                        and _r_now["sma_200"] > _r_prev["sma_200"]):
                    _uptrend_start_idx = _ri
                    break

            if _uptrend_start_idx is not None:
                _scan_rows = rows_with_sma[_uptrend_start_idx:]
                for _ma_label, _ma_period in [("50D", 50), ("100D", 100), ("150D", 150)]:
                    _in_touch = False  # currently within 2% of MA
                    _bounced = False   # has moved 5%+ above after a touch
                    _count = 0
                    for _sr in _scan_rows:
                        _ma_v = _sr.get(f"sma_{_ma_period}")
                        if _ma_v is None or _ma_v <= 0:
                            continue
                        _d = (_sr["close"] - _ma_v) / _ma_v
                        if not _in_touch and -0.02 <= _d <= 0.02:
                            # Touched the MA
                            _in_touch = True
                            _bounced = False
                        elif _in_touch and _d > 0.05:
                            # Bounced 5%+ above — retest complete
                            _count += 1
                            _in_touch = False
                            _bounced = True
                        elif _in_touch and _d < -0.05:
                            # Broke down through MA — failed retest, reset
                            _in_touch = False
                            _bounced = False
                    utr_retest_counts[_ma_label] = _count

        entry = {
            "ticker": ticker,
            "yf_ticker": yf,
            "company_name": stock["company_name"],
            "sector": stock["sector"],
            "industry": stock["industry"],
            "price": latest["close"],
            "price_prev": prev["close"],
            "date": latest["date"],
            "mas": mas,
            "ma200_months_rising": ma200_months_rising,
            "ma200_month_detail": ma200_month_detail,
            "mm99_monthly_history": mm99_monthly_history,
            "bp_duration": bp_duration,
            "bp_extras": bp_extras,
            "high_52w": round(high_52w, 4),
            "swing_high": round(swing_high, 4),
            "low_52w": round(low_52w, 4),
            "adv_1m": adv_1m,
            "adv_3m": adv_3m,
            "adv_1m_up": adv_1m_up,
            "adv_1m_dn": adv_1m_dn,
            "adv_3m_up": adv_3m_up,
            "adv_3m_dn": adv_3m_dn,
            "rs_composite": rs_composite,
            "rs_returns": rs_returns,
            # UTR pre-computed metrics (S3-S7)
            "utr_vol_trend": utr_vol_trend,           # S3: 10D/50D ADV ratio (< 1.0 = declining)
            "utr_updown_ratio": utr_updown_ratio,     # S4: up-day vol / down-day vol
            "utr_candle_quality": utr_candle_quality,  # S5: % closes in upper 40% of range
            "utr_dist_days": utr_dist_days,           # S6: distribution day count (last 25)
            "utr_pullback_contraction": utr_pullback_contraction,  # S7: ATR10/ATR20 ratio
            # UTR V2 fields
            "utr_5d_declining": utr_5d_declining,
            "utr_10d_declining": utr_10d_declining,
            "utr_50d_rising": utr_50d_rising,
            "utr_150d_rising": utr_150d_rising,
            "utr_test_ma": utr_test_ma,               # which MA being tested: "50D"/"100D"/"150D"/"200D"/None
            "utr_test_ma_dist": utr_test_ma_dist,     # % distance to test MA
            "utr_retest_counts": utr_retest_counts,   # {"50D": N, "100D": N, "150D": N}
        }
        prices.append(entry)

    # Compute RS percentiles across the alpha universe
    rs_pcts = compute_rs_percentiles(rs_composites)
    for entry in prices:
        entry["rs_percentile"] = rs_pcts.get(entry["ticker"])

    # Sector-level RS: compute per-sector, then rank within sector
    sector_stocks = defaultdict(list)
    for entry in prices:
        sector_stocks[entry["sector"]].append(entry["ticker"])
    for sector, tickers_in_sector in sector_stocks.items():
        sector_rs = {t: rs_composites.get(t) for t in tickers_in_sector}
        sector_pcts = compute_rs_percentiles(sector_rs)
        # Compute sector mean RS for excess return calculation (Q2, 23-Apr-26)
        sector_vals = [v for v in sector_rs.values() if v is not None]
        sector_mean = sum(sector_vals) / len(sector_vals) if sector_vals else None
        for entry in prices:
            if entry["ticker"] in sector_pcts:
                entry["rs_vs_sector"] = sector_pcts[entry["ticker"]]
                # Excess return: stock RS - sector mean RS (positive = outperforming sector)
                my_rs = rs_composites.get(entry["ticker"])
                entry["rs_excess_sector"] = round(my_rs - sector_mean, 6) if my_rs is not None and sector_mean is not None else None

    # Industry-level RS: compute per-industry, then rank within industry (Q3, 23-Apr-26)
    industry_stocks = defaultdict(list)
    for entry in prices:
        industry_stocks[entry.get("industry", "")].append(entry["ticker"])
    for industry, tickers_in_industry in industry_stocks.items():
        industry_rs = {t: rs_composites.get(t) for t in tickers_in_industry}
        industry_pcts = compute_rs_percentiles(industry_rs)
        industry_vals = [v for v in industry_rs.values() if v is not None]
        industry_mean = sum(industry_vals) / len(industry_vals) if industry_vals else None
        for entry in prices:
            if entry["ticker"] in industry_pcts:
                entry["rs_vs_industry"] = industry_pcts[entry["ticker"]]
                my_rs = rs_composites.get(entry["ticker"])
                entry["rs_excess_industry"] = round(my_rs - industry_mean, 6) if my_rs is not None and industry_mean is not None else None

    # Market-level excess return: stock RS - universe mean RS
    all_rs_vals = [v for v in rs_composites.values() if v is not None]
    market_mean = sum(all_rs_vals) / len(all_rs_vals) if all_rs_vals else None
    for entry in prices:
        my_rs = rs_composites.get(entry["ticker"])
        entry["rs_excess_market"] = round(my_rs - market_mean, 6) if my_rs is not None and market_mean is not None else None

    return prices


# ── Filter Computation Engine ─────────────────────────────────────────────

def compute_all_filters(prices):
    """Compute all 5 screening filters for each stock. Returns filter-results dict."""
    results = []

    for stock in prices:
        ticker = stock["ticker"]
        p = stock["price"]
        p_prev = stock["price_prev"]
        mas = stock["mas"]
        h52 = stock["high_52w"]
        l52 = stock["low_52w"]

        # Helper: safe MA access
        def ma(period):
            return mas.get(f"{period}D")

        def ma_prev(period):
            return mas.get(f"{period}D_prev")

        def ma_rising(period):
            curr = ma(period)
            prev = ma_prev(period)
            if curr is None or prev is None:
                return False
            return curr > prev

        def within_pct(val, ref, pct):
            """Is val within ±pct% of ref?"""
            if val is None or ref is None or ref == 0:
                return False
            ratio = abs(val - ref) / ref
            return ratio <= pct

        def above(val, ref):
            if val is None or ref is None:
                return False
            return val > ref

        # ── BASING PLATEAU ────────────────────────────────────────────
        # Tests check TODAY's values + 3-month duration (95% of 63 days)
        bp = {}
        bp_dur = stock.get("bp_duration", {})

        # Group A — Loose (±15%) — today's test AND 3-month duration
        t1 = within_pct(p, ma(200), 0.15) and within_pct(p, ma(150), 0.15)
        t2 = within_pct(ma(50), ma(200), 0.15) and within_pct(ma(50), ma(150), 0.15)
        loose_dur = bp_dur.get("loose", False)
        bp["group_a"] = {"pass": t1 and t2 and loose_dur, "tests": {"T1": t1, "T2": t2},
                         "duration_met": loose_dur, "duration_pct": bp_dur.get("loose_pct", 0),
                         "days_passed": bp_dur.get("loose_days_passed", 0),
                         "days_total": bp_dur.get("loose_days_total", 0),
                         "history": bp_dur.get("loose_history", []),
                         "streak": bp_dur.get("loose_streak", 0)}

        # Group B — Medium (±10%)
        t3 = within_pct(p, ma(200), 0.10) and within_pct(p, ma(150), 0.10)
        t4 = within_pct(ma(50), ma(200), 0.10) and within_pct(ma(50), ma(150), 0.10)
        t5 = within_pct(ma(150), ma(200), 0.10)
        medium_dur = bp_dur.get("medium", False)
        bp["group_b"] = {"pass": t3 and t4 and t5 and medium_dur, "tests": {"T3": t3, "T4": t4, "T5": t5},
                         "duration_met": medium_dur, "duration_pct": bp_dur.get("medium_pct", 0),
                         "days_passed": bp_dur.get("medium_days_passed", 0),
                         "days_total": bp_dur.get("medium_days_total", 0),
                         "history": bp_dur.get("medium_history", []),
                         "streak": bp_dur.get("medium_streak", 0)}

        # Group C — Tight (±5%)
        t6 = within_pct(p, ma(200), 0.05) and within_pct(p, ma(150), 0.05)
        t7 = within_pct(ma(50), ma(200), 0.05) and within_pct(ma(50), ma(150), 0.05)
        t8 = within_pct(ma(150), ma(200), 0.05)
        tight_dur = bp_dur.get("tight", False)
        bp["group_c"] = {"pass": t6 and t7 and t8 and tight_dur, "tests": {"T6": t6, "T7": t7, "T8": t8},
                         "duration_met": tight_dur, "duration_pct": bp_dur.get("tight_pct", 0),
                         "days_passed": bp_dur.get("tight_days_passed", 0),
                         "days_total": bp_dur.get("tight_days_total", 0),
                         "history": bp_dur.get("tight_history", []),
                         "streak": bp_dur.get("tight_streak", 0)}

        # ── Pass B (D-MD-FILTER-12 to 15): composite-score + new stage mapping ──
        # Pull the 3 new test results from bp_extras (computed in build_prices_json).
        bp_ex = stock.get("bp_extras", {}) or {}
        bp["flat_mas_pass"] = bp_ex.get("flat_mas_pass", False)
        bp["slope_200"] = bp_ex.get("slope_200")
        bp["slope_150"] = bp_ex.get("slope_150")
        bp["vol_contraction_pass"] = bp_ex.get("vol_contraction_pass", False)
        bp["vol_ratio"] = bp_ex.get("vol_ratio")
        bp["time_in_base_pass"] = bp_ex.get("time_in_base_pass", False)
        bp["days_since_drop"] = bp_ex.get("days_since_drop")

        # Composite BP score: 0-4 based on the 4 orthogonal tests.
        # Test 1 = Basing (group_a pass, i.e. Loose ±15% + 3-month duration)
        # Test 2 = Flat MAs (T-NEW-1)
        # Test 3 = Volume contraction (T-NEW-2)
        # Test 4 = Time-in-base (T-NEW-3)
        bp_test_basing = bool(bp["group_a"]["pass"])
        bp_test_flat = bool(bp["flat_mas_pass"])
        bp_test_vol = bool(bp["vol_contraction_pass"])
        bp_test_time = bool(bp["time_in_base_pass"])
        bp["score"] = sum([bp_test_basing, bp_test_flat, bp_test_vol, bp_test_time])
        bp["score_max"] = 4
        bp["score_breakdown"] = {
            "basing": bp_test_basing,
            "flat_mas": bp_test_flat,
            "vol_contraction": bp_test_vol,
            "time_in_base": bp_test_time,
        }

        # Stage mapping (D-MD-FILTER-12): 4->Capital, 3->Late, 2->Early, <2->None.
        # Score=1 (Basing only) is rendered as "Base Only" tile but does NOT count as a stage.
        if bp["score"] == 4:
            bp["stage"] = "Capital"
        elif bp["score"] == 3:
            bp["stage"] = "Late"
        elif bp["score"] == 2:
            bp["stage"] = "Early"
        else:
            bp["stage"] = None

        # ── PROBING BET ───────────────────────────────────────────────
        pb = {}
        # Group A — Early (3 of 5 rising)
        pb_t1 = p > p_prev if p_prev else False
        pb_t2 = ma_rising(5)
        pb_t3 = ma_rising(10)
        pb_t4 = ma_rising(20)
        pb_t5 = ma_rising(50)
        a_tests = {"T1": pb_t1, "T2": pb_t2, "T3": pb_t3, "T4": pb_t4, "T5": pb_t5}
        a_met = sum(1 for v in a_tests.values() if v)
        pb["group_a"] = {"pass": a_met >= 3, "met": a_met, "required": 3, "tests": a_tests}

        # Group B — Late (1 of 2)
        pb_t6 = ma_rising(20)
        pb_t7 = ma_rising(50)
        b_tests = {"T6": pb_t6, "T7": pb_t7}
        b_met = sum(1 for v in b_tests.values() if v)
        pb["group_b"] = {"pass": b_met >= 1, "met": b_met, "required": 1, "tests": b_tests}

        # Group C — Dead Cat (price ≥30% below 52W high)
        pct_below_52wh = (h52 - p) / h52 if h52 > 0 else 0
        pb_t8 = pct_below_52wh >= 0.30
        pb["group_c"] = {"pass": pb_t8, "tests": {"T8": pb_t8}, "pct_below_52wh": round(pct_below_52wh, 4)}

        # Group D — Capital PB1 (P>20D + 20D rising)
        pb_t9 = above(p, ma(20))
        pb_t10 = ma_rising(20)
        pb["group_d"] = {"pass": pb_t9 and pb_t10, "tests": {"T9": pb_t9, "T10": pb_t10}}

        # Group E — Capital PB2 (P>50D + 50D rising)
        pb_t11 = above(p, ma(50))
        pb_t12 = ma_rising(50)
        pb["group_e"] = {"pass": pb_t11 and pb_t12, "tests": {"T11": pb_t11, "T12": pb_t12}}

        # PB qualification stage
        if pb["group_d"]["pass"] or pb["group_e"]["pass"]:
            pb["stage"] = "Capital"
        elif pb["group_b"]["pass"]:
            pb["stage"] = "Late"
        elif pb["group_a"]["pass"]:
            pb["stage"] = "Early"
        else:
            pb["stage"] = None

        # ── MM 99 ────────────────────────────────────────────────────
        mm = {}
        # Group A — Long-term
        mm_t1 = above(p, ma(200))
        # T2: 200D upward trend MoM — use month count (pass = at least 1 month rising)
        ma200_mr = stock.get("ma200_months_rising", 0)
        mm_t2 = ma200_mr >= 1
        mm["group_a"] = {"pass": mm_t1 and mm_t2, "tests": {"T1": mm_t1, "T2": mm_t2}, "ma200_months_rising": ma200_mr}

        # Group B — Mid-term
        mm_t3 = above(p, ma(150))
        mm_t4 = above(ma(150), ma(200))
        mm["group_b"] = {"pass": mm_t3 and mm_t4, "tests": {"T3": mm_t3, "T4": mm_t4}}

        # Group C — Short-term
        mm_t5 = above(ma(50), ma(150))
        mm_t6 = above(p, ma(50))
        mm["group_c"] = {"pass": mm_t5 and mm_t6, "tests": {"T5": mm_t5, "T6": mm_t6}}

        # Group D — 52W Leadership
        mm_t7 = above(p, l52 * 1.20) if l52 and l52 > 0 else False  # P > 20% above 52W low
        mm_t8 = (p >= h52 * 0.75) if h52 and h52 > 0 else False  # P within 25% of 52W high
        mm["group_d"] = {"pass": mm_t7 and mm_t8, "tests": {"T7": mm_t7, "T8": mm_t8}}

        # Group E — Relative Strength: excess return tests (Q2/Q3, 23-Apr-26)
        # T9: stock RS - sector mean RS > 0 (outperforming sector)
        # T10: stock RS - industry mean RS > 0 (outperforming industry)
        # T11: stock RS - market mean RS > 0 (outperforming market)
        rs_pct = stock.get("rs_percentile")
        rs_vs_sector = stock.get("rs_vs_sector")
        rs_excess_sector = stock.get("rs_excess_sector")
        rs_excess_industry = stock.get("rs_excess_industry")
        rs_excess_market = stock.get("rs_excess_market")
        mm_t9 = (rs_excess_sector is not None and rs_excess_sector > 0)
        mm_t10 = (rs_excess_industry is not None and rs_excess_industry > 0)
        mm_t11 = (rs_excess_market is not None and rs_excess_market > 0)
        mm["group_e"] = {
            "pass": mm_t9 and mm_t10 and mm_t11,
            "tests": {"T9": mm_t9, "T10": mm_t10, "T11": mm_t11},
            "rs_percentile": rs_pct,
            "rs_vs_sector": rs_vs_sector,
            "rs_excess_sector": rs_excess_sector,
            "rs_excess_industry": rs_excess_industry,
            "rs_excess_market": rs_excess_market,
        }

        # MM99 score: count passing groups A-D tests (8 tests = original Minervini template)
        mm_8pt = sum(1 for t in [mm_t1, mm_t2, mm_t3, mm_t4, mm_t5, mm_t6, mm_t7, mm_t8] if t)
        mm["score_8pt"] = mm_8pt
        # Full 11-test score
        mm_11 = mm_8pt + sum(1 for t in [mm_t9, mm_t10, mm_t11] if t)
        mm["score_11"] = mm_11

        # Monthly history: how many of last 12 months passed all 8 technical tests
        mm_hist = stock.get("mm99_monthly_history", [False] * 12)
        mm["monthly_history"] = mm_hist
        mm["months_passing"] = sum(1 for m in mm_hist if m)

        # MM99 qualification
        if mm_8pt >= 8 and mm["group_e"]["pass"]:
            mm["stage"] = "Capital"
        elif mm_8pt >= 7:
            mm["stage"] = "Late"
        elif mm_8pt >= 5:
            mm["stage"] = "Early"
        else:
            mm["stage"] = None

        # ── VCP (simplified — full pattern detection is Phase 2) ─────
        vcp = {}
        # T1: Stage 2 uptrend (require MM Groups A+B pass)
        vcp_t1 = mm["group_a"]["pass"] and mm["group_b"]["pass"]
        # T2-T5: Pattern detection requires multi-day swing analysis — placeholder
        vcp["stage_2_uptrend"] = vcp_t1
        vcp["pattern_detected"] = False  # Placeholder until pattern detection built
        vcp["note"] = "VCP pattern detection pending — Phase 2. Stage 2 check only."
        vcp["stage"] = None  # Cannot qualify without pattern detection

        # ── UPTREND RETEST V2 — Pullback Lifecycle (27-Apr-26) ────────
        # Stage = position in pullback lifecycle, not a composite score.
        # Early (pulling back) → Late (approaching MA) → Capital (healthy retest) → Invalidation
        utr = {}

        # ── Raw metrics used across stages ──
        swing_h = stock.get("swing_high", h52)
        depth = (swing_h - p) / swing_h if swing_h and swing_h > 0 else 0
        depth_pct = round(depth * 100, 2)
        vol_trend = stock.get("utr_vol_trend")        # 10D/50D ADV ratio
        updown_ratio = stock.get("utr_updown_ratio")  # up-day vol / down-day vol
        candle_q = stock.get("utr_candle_quality")     # % closes in upper 40% of range
        dist_days = stock.get("utr_dist_days")         # distribution day count (25d)
        pb_contract = stock.get("utr_pullback_contraction")  # ATR10/ATR20
        test_ma = stock.get("utr_test_ma")             # "50D"/"100D"/"150D"/"200D"/None
        test_ma_dist = stock.get("utr_test_ma_dist")   # % distance to test MA
        retest_counts = stock.get("utr_retest_counts", {})
        _5d_dec = stock.get("utr_5d_declining", False)
        _10d_dec = stock.get("utr_10d_declining", False)
        _50d_rise = stock.get("utr_50d_rising", False)
        _150d_rise = stock.get("utr_150d_rising", False)

        # ── EARLY tests ──
        # E1: Pullback initiated — depth 3-10% from swing high
        e1 = 0.03 <= depth <= 0.10
        # E2: Short-term MAs rolling, intermediate intact
        e2 = (_5d_dec or _10d_dec) and _50d_rise and _150d_rise
        # E3: Volume declining (health indicator, not a gate)
        e3 = "pass" if (vol_trend is not None and vol_trend < 1.0) else "amber" if (vol_trend is not None and vol_trend <= 1.2) else "fail"
        # E4: Distribution days low (0-1 expected at Early)
        e4 = "pass" if (dist_days is not None and dist_days <= 1) else "amber" if (dist_days is not None and dist_days <= 2) else "fail"

        early_qual = e1 and e2  # E1 + E2 required

        # ── LATE tests ──
        # L1: Depth 8-20% from swing high
        l1 = 0.08 <= depth <= 0.20
        # L2: Price approaching key MA — within 5% of test MA, still above
        l2 = test_ma is not None and test_ma_dist is not None and 0 <= test_ma_dist <= 5.0
        # L3: Volume dried up (confirmed) — 10D/50D < 0.85
        l3 = vol_trend is not None and vol_trend < 0.85
        # L4: Up/down volume ratio > 1.0 (constructive)
        l4 = updown_ratio is not None and updown_ratio > 1.0
        # L5: Range contracting — ATR10/ATR20 < 0.9
        l5 = pb_contract is not None and pb_contract < 0.9
        # L6: Distribution days contained — 0-3
        l6 = dist_days is not None and dist_days <= 3

        late_qual = l1 and l2  # L1 + L2 required (position check)
        late_quality = sum(1 for x in [l3, l4, l5, l6] if x)  # quality score 0-4

        # ── CAPITAL tests ──
        # C1: Price at support MA — within 2% (above or slight undercut)
        c1 = test_ma is not None and test_ma_dist is not None and -2.0 <= test_ma_dist <= 2.0
        # C2: Depth reasonable — below 25%
        c2 = depth < 0.25
        # C3: Volume dried up — 10D/50D < 0.80
        c3 = vol_trend is not None and vol_trend < 0.80
        # C4: Up/down ratio positive — > 1.1
        c4 = updown_ratio is not None and updown_ratio > 1.1
        # C5: Candle quality — >=50% of last 10d close in upper 40% range
        c5 = candle_q is not None and candle_q >= 0.50
        # C6: Distribution days low — 0-2 in last 25d
        c6 = dist_days is not None and dist_days <= 2
        # C7: Range contracted — ATR10/ATR20 < 0.85
        c7 = pb_contract is not None and pb_contract < 0.85
        # C8: RS holding — percentile >= 70
        c8 = rs_pct is not None and rs_pct >= 70

        capital_tests = [c1, c2, c3, c4, c5, c6, c7, c8]
        capital_qual = all(capital_tests)  # ALL must pass
        capital_count = sum(1 for x in capital_tests if x)

        # ── INVALIDATION checks ──
        # Any one kills the pattern
        inv_depth = depth > 0.25
        inv_ma_break = (test_ma is not None and test_ma_dist is not None and test_ma_dist < -5.0)
        inv_dist = dist_days is not None and dist_days >= 6
        inv_rs = rs_pct is not None and rs_pct < 50
        invalidated = inv_depth or inv_ma_break or inv_dist or inv_rs

        # ── Stage determination (lifecycle progression) ──
        if invalidated:
            utr["stage"] = None
        elif capital_qual:
            utr["stage"] = "Capital"
        elif late_qual:
            utr["stage"] = "Late"
        elif early_qual:
            utr["stage"] = "Early"
        else:
            utr["stage"] = None

        # ── Retest count for current test MA (Minervini conviction modifier) ──
        current_retest_num = 0
        if test_ma and test_ma in retest_counts:
            current_retest_num = retest_counts[test_ma]
        # Current retest is the one in progress (not yet completed), so display as N+1
        if test_ma:
            current_retest_num += 1

        # ── Output structure ──
        utr["depth_pct"] = depth_pct
        utr["test_ma"] = test_ma
        utr["test_ma_dist"] = test_ma_dist
        utr["retest_counts"] = retest_counts
        utr["current_retest_num"] = current_retest_num

        # Per-test results for dashboard display (pass/amber/fail per stage context)
        utr["tests"] = {
            "e1_depth": "pass" if e1 else ("amber" if 0.01 <= depth <= 0.12 else "fail"),
            "e2_ma_roll": "pass" if e2 else "fail",
            "e3_vol": e3,
            "e4_dist": e4,
            "l1_depth": "pass" if l1 else ("amber" if 0.05 <= depth <= 0.22 else "fail"),
            "l2_ma_approach": "pass" if l2 else ("amber" if test_ma is not None and test_ma_dist is not None and test_ma_dist <= 8.0 else "fail"),
            "l3_vol_dry": "pass" if l3 else ("amber" if vol_trend is not None and vol_trend < 1.0 else "fail"),
            "l4_updown": "pass" if l4 else ("amber" if updown_ratio is not None and updown_ratio >= 0.8 else "fail"),
            "l5_contraction": "pass" if l5 else ("amber" if pb_contract is not None and pb_contract < 1.05 else "fail"),
            "l6_dist": "pass" if l6 else ("amber" if dist_days is not None and dist_days <= 5 else "fail"),
            "c1_at_ma": "pass" if c1 else "fail",
            "c2_depth": "pass" if c2 else "fail",
            "c3_vol": "pass" if c3 else "fail",
            "c4_updown": "pass" if c4 else "fail",
            "c5_candle": "pass" if c5 else "fail",
            "c6_dist": "pass" if c6 else "fail",
            "c7_contraction": "pass" if c7 else "fail",
            "c8_rs": "pass" if c8 else "fail",
        }
        utr["capital_count"] = capital_count
        utr["late_quality"] = late_quality

        # Invalidation flags for dashboard
        utr["invalidation"] = {
            "depth": inv_depth,
            "ma_break": inv_ma_break,
            "dist": inv_dist,
            "rs": inv_rs,
        }

        # MA direction bools (for dashboard display)
        utr["ma_direction"] = {
            "5d_declining": _5d_dec,
            "10d_declining": _10d_dec,
            "50d_rising": _50d_rise,
            "150d_rising": _150d_rise,
        }

        # Raw metric values for tooltip/detail display
        utr["metrics"] = {
            "vol_trend": vol_trend,
            "updown_ratio": updown_ratio,
            "candle_quality": candle_q,
            "dist_days": dist_days,
            "contraction": pb_contract,
            "rs_percentile": rs_pct,
        }

        # ── Assemble result ───────────────────────────────────────────
        results.append({
            "ticker": ticker,
            "basing_plateau": bp,
            "probing_bet": pb,
            "mm99": mm,
            "vcp": vcp,
            "uptrend_retest": utr,
        })

    return results


def main():
    parser = argparse.ArgumentParser(description="Master Dashboard data pipeline")
    parser.add_argument("--sample", action="store_true", help="Use sample data (no yfinance)")
    parser.add_argument("--full-refresh", action="store_true", help="Force full re-pull from yfinance")
    parser.add_argument("--full-universe", action="store_true", help="Use full 976-stock watchlist instead of alpha universe")
    args = parser.parse_args()

    # Load universe — either alpha (125 stocks) or full watchlist (976 stocks)
    if args.full_universe:
        watchlist_path = SCRIPT_DIR.parent.parent / "databases" / "pullback-watchlist.json"
        if not watchlist_path.exists():
            print(f"ERROR: Watchlist not found at {watchlist_path}")
            sys.exit(1)
        with open(watchlist_path) as f:
            wl = json.load(f)
        universe = {"stocks": wl["stocks"]}
        print(f"Loaded FULL watchlist: {len(universe['stocks'])} stocks")
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(UNIVERSE_PATH, "w") as f:
            json.dump(universe, f, indent=2)
        print(f"  Saved as universe.json ({len(universe['stocks'])} stocks)")
    else:
        with open(UNIVERSE_PATH) as f:
            universe = json.load(f)
        print(f"Loaded universe: {len(universe['stocks'])} stocks")

    # ── Canonical taxonomy lookup ──
    sm_path = SCRIPT_DIR.parent.parent / "stock_mapping_final.json"
    sm_map = {}
    if sm_path.exists():
        with open(sm_path) as f:
            sm_raw = json.load(f)
        for tk, td in sm_raw.items():
            if isinstance(td, dict) and td.get("new_industry"):
                sm_map[tk] = {"industry": td["new_industry"], "sector": td["new_sector"]}
        print(f"Loaded canonical taxonomy: {len(sm_map)} tickers from stock_mapping_final.json")
        mapped = 0
        unmapped = []
        for stock in universe["stocks"]:
            tk = stock["ticker"]
            if tk in sm_map:
                stock["industry"] = sm_map[tk]["industry"]
                stock["sector"] = sm_map[tk]["sector"]
                mapped += 1
            else:
                unmapped.append(tk)
        print(f"  Mapped: {mapped} / {len(universe['stocks'])}. Unmapped: {len(unmapped)}")
        if unmapped[:10]:
            print(f"  Unmapped sample: {unmapped[:10]}")
    else:
        print(f"WARNING: stock_mapping_final.json not found at {sm_path} — using raw watchlist taxonomy")

    # Fetch data
    data_source = "sample"
    if args.sample:
        print("\n── Generating sample data ──")
        raw_data = generate_sample_data(universe)
    else:
        print("\n── Fetching yfinance data ──")
        try:
            raw_data = fetch_all_data(universe, full_refresh=args.full_refresh)
            data_source = "yfinance"
        except ImportError:
            print("  yfinance not available — falling back to sample data")
            print("  NOTE: Run this on Richard's machine with yfinance installed for real data")
            raw_data = generate_sample_data(universe)

    # Get benchmark data
    benchmark_rows = raw_data.get(BENCHMARK_TICKER, [])
    if not benchmark_rows:
        print("  WARNING: No benchmark data — RS calculations will be affected")

    # Build prices.json
    print("\n── Building prices.json ──")
    prices = build_prices_json(universe, raw_data, benchmark_rows)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_DIR / "prices.json", "w") as f:
        json.dump({
            "_meta": {
                "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "count": len(prices),
                "source": data_source,
            },
            "stocks": prices
        }, f, indent=2)
    print(f"  Written {len(prices)} stocks to data/prices.json")

    # Compute filters
    print("\n── Computing filters ──")
    filter_results = compute_all_filters(prices)
    with open(DATA_DIR / "filter-results.json", "w") as f:
        json.dump({
            "_meta": {
                "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "count": len(filter_results),
                "filters": ["basing_plateau", "probing_bet", "mm99", "vcp", "uptrend_retest"],
                "notes": "VCP pattern detection pending Phase 2. UTR V2 lifecycle stages live (27-Apr-26)."
            },
            "stocks": filter_results
        }, f, indent=2)
    print(f"  Written {len(filter_results)} stocks to data/filter-results.json")

    # Summary
    print("\n── Filter Summary ──")
    for filt in ["basing_plateau", "probing_bet", "mm99", "uptrend_retest"]:
        stages = {"Early": 0, "Late": 0, "Capital": 0, "None": 0}
        for r in filter_results:
            stage = r[filt].get("stage") or "None"
            stages[stage] = stages.get(stage, 0) + 1
        print(f"  {filt:20s} — Early: {stages['Early']}, Late: {stages['Late']}, Capital: {stages['Capital']}, None: {stages['None']}")

    # MM99 score distribution
    score_dist = defaultdict(int)
    for r in filter_results:
        score_dist[r["mm99"]["score_8pt"]] += 1
    print(f"  MM99 8pt scores: {dict(sorted(score_dist.items()))}")

    print("\nDone.")


if __name__ == "__main__":
    main()
