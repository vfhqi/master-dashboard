"""
Chart Overflow Fix — Session 12 (01-May-26)
============================================

Bug: chart shows only first 10 months of 2Y data; recent months drawn off-canvas to the right.

Root cause: drawMasterChart line 833 forces `barW = Math.max(4, plotW/n)`. At 2Y zoom
(n=504 trading days) and chart panel ½ width (W=912, plotW=766), the calculated barW
would be 1.52px but is forced to 4px. 504 bars × 4px = 2016px, far exceeding plotW=766px.
Last ~295 bars (14 months) drawn beyond right edge of canvas, invisible.

Same problem at Full width (panel=1905px, plotW≈1759, calc barW=3.49 → forced to 4 →
504*4=2016 still overflows by ~257px = ~3 months cut).

Fix: drop the minimum-barW floor for chart bars. Let barW shrink to whatever fits.
Candle width retains its 0.78x multiplier of barW so candles can become 1px wide if
needed — at narrow zooms (504 bars on a 766px plot) this is the right behaviour.

Three places affected (line 833 area):
  - barW = plotW / n  (no min)
  - candleW = Math.max(1, barW * 0.78)  (allow 1px minimum, was 3px)
"""
import sys
import shutil
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
TARGET = SCRIPT_DIR / "build_dashboard.py"


def backup():
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = SCRIPT_DIR / f"build_dashboard.py.bak-pre-chartoverflow-{ts}"
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
        '  var barW=Math.max(4,plotW/n);\n  var candleW=Math.max(3,barW*0.78);',
        '  // SESSION 12 D-MD-CHART-2: drop barW floor so bars shrink to fit.\n  // Old: Math.max(4, plotW/n) — forced 4px min, caused overflow at 2Y zoom on narrow panels.\n  var barW=plotW/n;\n  var candleW=Math.max(1,barW*0.78);',
        "1: drop barW minimum",
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
    print("\nDONE. Run: python build_dashboard.py")


if __name__ == "__main__":
    main()
