"""
Chart Data Generator for Master Dashboard
==========================================
Generates per-stock OHLCV + MA data for the interactive chart panel.
Reads from yfinance (live) or generates sample data (sandbox).

Output: charts/<TICKER>.js  (one file per ticker, lazy-loaded by dashboard)
        data/chart-manifest.json  (list of available tickers for the loader)

Each .js file contains: var CHART_REGISTRY=CHART_REGISTRY||{};CHART_REGISTRY["TICKER"]=[...];
This works with file:// (script tag injection) and GitHub Pages.

Legacy output data/chart-data.json is NO LONGER generated (was 185MB+).

Usage:
  python generate_chart_data.py             # sample data mode
  python generate_chart_data.py --live      # yfinance mode (Richard's machine)
"""

import json
import os
import sys
import math
import random
from pathlib import Path
from datetime import datetime, timedelta

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
CHARTS_DIR = PROJECT_DIR / "charts"

# Try existing pullback cache first
COWORK_ROOT = PROJECT_DIR.parent
PULLBACK_CACHE_DIR = COWORK_ROOT / "databases" / "pullback-cache"


def load_universe():
    with open(DATA_DIR / "universe.json") as f:
        data = json.load(f)
    return data.get("stocks", data) if isinstance(data, dict) else data


def compute_mas(closes, periods):
    """Compute simple moving averages for given periods."""
    mas = {p: [None] * len(closes) for p in periods}
    for p in periods:
        for i in range(p - 1, len(closes)):
            mas[p][i] = sum(closes[i - p + 1:i + 1]) / p
    return mas


def generate_sample_data(ticker, days=756):
    """Generate realistic-looking sample OHLCV data."""
    random.seed(hash(ticker) % 2**31)
    base_price = random.uniform(5, 500)
    daily_vol = random.uniform(0.005, 0.025)
    avg_volume = random.randint(50000, 2000000)

    data = []
    price = base_price
    start_date = datetime.now() - timedelta(days=days)

    closes = []
    for i in range(days):
        dt = start_date + timedelta(days=i)
        # Skip weekends
        if dt.weekday() >= 5:
            continue

        change = random.gauss(0.0003, daily_vol)
        price = price * (1 + change)
        o = price * (1 + random.gauss(0, 0.003))
        h = max(o, price) * (1 + abs(random.gauss(0, 0.005)))
        l = min(o, price) * (1 - abs(random.gauss(0, 0.005)))
        c = price
        v = int(avg_volume * (0.5 + random.random()))

        closes.append(c)
        data.append({
            "d": dt.strftime("%Y-%m-%d"),
            "o": round(o, 2), "h": round(h, 2),
            "l": round(l, 2), "c": round(c, 2),
            "v": v
        })

    # Compute MAs
    periods = [5, 10, 20, 50, 100, 150, 200]
    mas = compute_mas(closes, periods)
    for i in range(len(data)):
        for p in periods:
            if mas[p][i] is not None:
                data[i]["ma" + str(p)] = round(mas[p][i], 2)

    return data


def try_pullback_cache(ticker, yf_ticker=None):
    """Try to load chart data from existing pullback monitor cache."""
    # Cache files use yfinance ticker with dots replaced: HTWS.L -> HTWS_dot_L.json
    candidates = []
    if yf_ticker:
        candidates.append(PULLBACK_CACHE_DIR / f"{yf_ticker.replace('.', '_dot_')}.json")
    candidates.append(PULLBACK_CACHE_DIR / f"{ticker.replace('.', '_dot_')}.json")
    candidates.append(PULLBACK_CACHE_DIR / f"{ticker}.json")

    for cache_file in candidates:
        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    cached = json.load(f)
                # Cache format varies — check for OHLCV arrays (lowercase or titlecase keys)
                if isinstance(cached, list) and len(cached) > 0:
                    first = cached[0]
                    if "Close" in first or "close" in first:
                        return convert_yfinance_cache(cached)
            except Exception:
                pass
    return None


def _g(r, key):
    """Get value from record, trying titlecase then lowercase."""
    return r.get(key) if key in r else r.get(key.lower())


def convert_yfinance_cache(records):
    """Convert yfinance cache format to chart format with MAs."""
    data = []
    closes = []
    for r in records:
        close_val = _g(r, "Close")
        if close_val is None:
            continue
        closes.append(close_val)
        data.append({
            "d": _g(r, "Date") or "",
            "o": round(_g(r, "Open") or close_val, 2),
            "h": round(_g(r, "High") or close_val, 2),
            "l": round(_g(r, "Low") or close_val, 2),
            "c": round(close_val, 2),
            "v": int(_g(r, "Volume") or 0)
        })

    # Compute MAs
    periods = [5, 10, 20, 50, 100, 150, 200]
    mas = compute_mas(closes, periods)
    for i in range(len(data)):
        for p in periods:
            if mas[p][i] is not None:
                data[i]["ma" + str(p)] = round(mas[p][i], 2)

    return data


def safe_ticker_filename(ticker):
    """Convert ticker to safe filename: HTWS.L -> HTWS_L, NSIS-B.CO -> NSIS-B_CO"""
    return ticker.replace(".", "_").replace("/", "_")


def write_ticker_js(ticker, data):
    """Write a single ticker's chart data as a self-registering JS file.

    Format: var CHART_REGISTRY=CHART_REGISTRY||{};CHART_REGISTRY["TICKER"]=[...];
    Uses compact array-of-arrays format to minimise file size:
    [date, open, high, low, close, volume, ma5, ma10, ma20, ma50, ma100, ma150, ma200]
    """
    # Convert to compact array format — saves ~40% vs repeated key names
    ma_keys = ["ma5", "ma10", "ma20", "ma50", "ma100", "ma150", "ma200"]
    rows = []
    for bar in data:
        row = [
            bar["d"],
            bar["o"], bar["h"], bar["l"], bar["c"], bar["v"]
        ]
        for mk in ma_keys:
            row.append(bar.get(mk))
        rows.append(row)

    safe_name = safe_ticker_filename(ticker)
    js_path = CHARTS_DIR / f"{safe_name}.js"

    # Use compact JSON — no spaces
    rows_json = json.dumps(rows, separators=(",", ":"))

    # Self-registering pattern: works with file:// script injection
    js_content = 'var CHART_REGISTRY=CHART_REGISTRY||{};'
    js_content += f'CHART_REGISTRY["{ticker}"]={rows_json};\n'

    with open(js_path, "w") as f:
        f.write(js_content)

    return os.path.getsize(js_path)


def main():
    live_mode = "--live" in sys.argv
    universe = load_universe()

    # Create charts directory
    CHARTS_DIR.mkdir(exist_ok=True)

    manifest = []
    total_bytes = 0

    for stock in universe:
        ticker = stock["ticker"] if isinstance(stock, dict) else stock
        yf_ticker = stock.get("yfinance_ticker", ticker) if isinstance(stock, dict) else ticker

        data = None
        source = "sample"

        # Always try pullback cache first (has real data from prior yfinance runs)
        cached = try_pullback_cache(ticker, yf_ticker)
        if cached and len(cached) > 100:
            data = cached
            source = "pullback cache"

        if data is None and live_mode:
            # Try yfinance
            try:
                import yfinance as yf
                tk = yf.Ticker(yf_ticker)
                hist = tk.history(period="5y")
                records = []
                for idx, row in hist.iterrows():
                    records.append({
                        "Date": idx.strftime("%Y-%m-%d"),
                        "Open": row["Open"], "High": row["High"],
                        "Low": row["Low"], "Close": row["Close"],
                        "Volume": int(row["Volume"])
                    })
                data = convert_yfinance_cache(records)
                source = "yfinance"
            except Exception as e:
                print(f"  {ticker}: yfinance failed ({e}), using sample")

        if data is None:
            data = generate_sample_data(ticker)
            source = "sample"

        # Write per-ticker JS file
        file_bytes = write_ticker_js(ticker, data)
        total_bytes += file_bytes
        manifest.append({
            "ticker": ticker,
            "file": safe_ticker_filename(ticker) + ".js",
            "days": len(data)
        })
        print(f"  {ticker}: {len(data)} days, {file_bytes:,} bytes ({source})")

    # Write manifest (small JSON listing all available tickers)
    manifest_path = DATA_DIR / "chart-manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, separators=(",", ":"))

    print(f"\nWritten: {len(manifest)} ticker files to {CHARTS_DIR}/")
    print(f"Total chart data: {total_bytes:,} bytes across {len(manifest)} files")
    print(f"Manifest: {manifest_path} ({os.path.getsize(manifest_path):,} bytes)")


if __name__ == "__main__":
    main()
