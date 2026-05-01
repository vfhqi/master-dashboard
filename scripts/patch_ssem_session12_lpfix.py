"""
SSEM Session 12 LP Rating Fix — 01-May-26
==========================================

Bug: Live Portfolio rows on SSEM tab show rating "undefined" because the LP branch
in buildPortfolioTile calls ssemEnrichRow (computes score) but doesn't call
ssemAssignRatings (assigns A-F via bell-curve).

Fix: Store full-universe ratings in a global ticker→rating lookup inside renderSSEM,
then read from it in buildPortfolioTile's SSEM branch.

This ensures LP shows the SAME rating as QS for the same stock — bell-curve
computed once over the full SSEM universe, applied consistently.
"""
import sys
import shutil
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
TARGET = SCRIPT_DIR / "build_dashboard.py"


def backup():
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = SCRIPT_DIR / f"build_dashboard.py.bak-pre-lpfix-{ts}"
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

    # ─────────────────────────────────────────────────────────────
    # Edit 1: Add a global rating lookup map declaration near other state vars.
    # ─────────────────────────────────────────────────────────────
    src = apply(
        src,
        'var ssemColMode = "TYPE";',
        'var ssemRatingMap = {};   // ticker -> A/B/C/D/F/- — populated by renderSSEM, read by buildPortfolioTile\nvar ssemColMode = "TYPE";',
        "1: add ssemRatingMap state",
    )

    # ─────────────────────────────────────────────────────────────
    # Edit 2: After ssemAssignRatings(rowsAll) in renderSSEM, populate the map.
    # ─────────────────────────────────────────────────────────────
    src = apply(
        src,
        '  ssemAssignRatings(rowsAll);\n  // Apply header filters',
        '  ssemAssignRatings(rowsAll);\n  // Populate global ticker->rating lookup so buildPortfolioTile (LP branch) shows the same rating.\n  ssemRatingMap = {};\n  for(var rk=0;rk<rowsAll.length;rk++){ssemRatingMap[rowsAll[rk].ticker]=rowsAll[rk].ssem_rating;}\n  // Apply header filters',
        "2: populate map after assignRatings",
    )

    # ─────────────────────────────────────────────────────────────
    # Edit 3: In buildPortfolioTile's SSEM branch, read rating from map after enrichment.
    # The current branch ends with:
    #     ssemEnrichRow(rE);
    #   } else {
    #     rE.ssem_score=0; rE.ssem_rating="-"; rE.ssem_nulls=15;
    #   }
    # We add: rE.ssem_rating = ssemRatingMap[rE.ticker] || "-";
    # ─────────────────────────────────────────────────────────────
    src = apply(
        src,
        '        ssemEnrichRow(rE);\n      } else {\n        rE.ssem_score=0; rE.ssem_rating="-"; rE.ssem_nulls=15;\n      }\n    }',
        '        ssemEnrichRow(rE);\n        // Look up rating from the full-universe bell-curve computed in renderSSEM.\n        rE.ssem_rating = ssemRatingMap[rE.ticker] || "-";\n      } else {\n        rE.ssem_score=0; rE.ssem_rating="-"; rE.ssem_nulls=15;\n      }\n    }',
        "3: read rating from map in LP branch",
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
