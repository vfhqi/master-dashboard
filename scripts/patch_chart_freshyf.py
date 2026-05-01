"""
Chart Data Freshness Fix — Session 12 (01-May-26)
==================================================

Bug: generate_chart_data.py prefers pullback-cache over yfinance, even with --live flag.
Pullback cache itself is stale (last refreshed mid-April), so charts show data through
17-Apr while prices.json (from generate_master_data) shows 29-Apr. User reports price
mismatch on every chart.

Fix: when --live is passed, try yfinance FIRST, fall back to pullback cache only on
yfinance failure. Without --live, keep current cache-first behaviour (sandbox mode).
"""
import sys
import shutil
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
TARGET = SCRIPT_DIR / "generate_chart_data.py"


def backup():
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = SCRIPT_DIR / f"generate_chart_data.py.bak-pre-freshyf-{ts}"
    shutil.copy2(TARGET, bak)
    print(f"  Backup: {bak.name}")


def apply(src, anchor, new_text, label):
    n = src.count(anchor)
    if n != 1:
        print(f"  FAIL [{label}]: anchor count = {n} (expected 1)")
        sys.exit(1)
    print(f"  OK [{label}]")
    return src.replace(anchor, new_text)


def main():
    print(f"Reading {TARGET}...")
    src = TARGET.read_text(encoding="utf-8")
    print(f"  Original: {len(src):,} bytes")
    backup()

    src = apply(
        src,
        '''        data = None
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
                print(f"  {ticker}: yfinance failed ({e}), using sample")''',
        '''        data = None
        source = "sample"

        # SESSION 12 fix: in --live mode, try yfinance FIRST (fresh data), fall back to pullback cache.
        # In sandbox mode (no --live), use pullback cache first as before.
        if live_mode:
            # Try yfinance live (fresh data)
            try:
                import yfinance as yf
                tk = yf.Ticker(yf_ticker)
                hist = tk.history(period="5y")
                if len(hist) > 100:
                    records = []
                    for idx, row in hist.iterrows():
                        records.append({
                            "Date": idx.strftime("%Y-%m-%d"),
                            "Open": row["Open"], "High": row["High"],
                            "Low": row["Low"], "Close": row["Close"],
                            "Volume": int(row["Volume"])
                        })
                    data = convert_yfinance_cache(records)
                    source = "yfinance live"
            except Exception as e:
                print(f"  {ticker}: yfinance failed ({e}), trying cache")

            # Fallback: pullback cache
            if data is None:
                cached = try_pullback_cache(ticker, yf_ticker)
                if cached and len(cached) > 100:
                    data = cached
                    source = "pullback cache (yfinance fallback)"
        else:
            # Sandbox mode: cache first, no yfinance
            cached = try_pullback_cache(ticker, yf_ticker)
            if cached and len(cached) > 100:
                data = cached
                source = "pullback cache"''',
        "1: yfinance-first in live mode",
    )

    new_size = len(src)
    print(f"  New: {new_size:,} bytes")
    TARGET.write_text(src, encoding="utf-8")

    print("Verifying py_compile...")
    import py_compile
    try:
        py_compile.compile(str(TARGET), doraise=True)
        print("  OK")
    except py_compile.PyCompileError as e:
        print(f"  FAIL: {e}")
        sys.exit(1)
    print("\nDONE. Run: python generate_chart_data.py --live")


if __name__ == "__main__":
    main()
