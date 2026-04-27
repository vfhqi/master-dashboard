"""
Extract Pillar Ratings from IC Ratings Dashboard Memos
======================================================
Reads all memo JSONs from databases/memos/{TICKER}/{Stage}.json
Extracts P1-P6 pillar ratings + conviction + stage.
Uses highest available stage per ticker (DD > ESA > Triaging).

Output: data/qualitative.json
Structure: { "TICKER": {"p1":"B","p2":"C","p3":"B+","p4":"C","p5":"A","p6":"B","conviction":"C+","stage":"ESA"}, ... }

Handles two memo schemas:
  V3 (NVTK/HTRO/EKTA): ratings_table rows with level="pillar", id="p1"
  V1/V2 (ENAV): ratings_table rows with pillar="P1" (attribute-level, needs aggregation)
"""

import json
import os
import glob
import re
from pathlib import Path
from collections import defaultdict

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
COWORK_ROOT = PROJECT_DIR.parent
MEMOS_DIR = COWORK_ROOT / "databases" / "memos"

# Rating value mapping for aggregation
RATING_VALUES = {
    "A+": 13, "A": 12, "A-": 11,
    "B+": 10, "B": 9, "B-": 8,
    "C+": 7, "C": 6, "C-": 5,
    "D+": 4, "D": 3, "D-": 2,
    "F": 1,
}

# Reverse mapping
VALUE_RATINGS = {v: k for k, v in RATING_VALUES.items()}

# Stage priority (higher = preferred)
STAGE_PRIORITY = {"DD": 3, "ESA": 2, "Triaging": 1}


def normalise_stage(filename):
    """Extract stage name from filename, stripping version suffixes."""
    name = filename.replace(".json", "")
    # Strip version suffixes like -v2, -v3
    name = re.sub(r"-v\d+$", "", name)
    return name


def parse_rating(rating_str):
    """Parse a rating string to its numeric value, or None if unparseable."""
    if not rating_str:
        return None
    # Clean up: strip whitespace, handle "(upper)" suffix
    rating = rating_str.strip().split()[0].replace("(", "").replace(")", "")
    # Handle "C+ (upper)" -> "C+"
    if rating in RATING_VALUES:
        return RATING_VALUES[rating]
    # Handle PASS/FAIL (from check-level rows)
    if rating.upper() in ("PASS", "FAIL", "N/A", "--", "—"):
        return None
    return None


def value_to_rating(val):
    """Convert numeric value back to nearest rating string."""
    if val is None:
        return None
    rounded = round(val)
    rounded = max(1, min(13, rounded))
    return VALUE_RATINGS.get(rounded, None)


def extract_pillar_ratings_v3(data):
    """Extract pillar ratings from V3 schema (level=pillar in ratings_table)."""
    pillars = {}
    c = data.get("sections", {}).get("C", {})
    for sub in c.get("subsections", []):
        if "C.I" not in sub.get("id", ""):
            continue
        for block in sub.get("blocks", []):
            if block.get("type") != "ratings_table":
                continue
            for row in block.get("rows", block.get("data", [])):
                if row.get("level") == "pillar":
                    pid = row.get("id", "")  # "p1", "p2", etc.
                    rating = row.get("rating", "")
                    if pid and rating:
                        pillars[pid] = rating
    return pillars


def extract_pillar_ratings_v1(data):
    """Extract pillar ratings from V1/V2 schema (attribute-level with pillar field).
    Aggregates attribute ratings by pillar using mean."""
    pillar_vals = defaultdict(list)
    c = data.get("sections", {}).get("C", {})
    for sub in c.get("subsections", []):
        if "C.I" not in sub.get("id", ""):
            continue
        for block in sub.get("blocks", []):
            if block.get("type") != "ratings_table":
                continue
            for row in block.get("rows", block.get("data", [])):
                pillar = row.get("pillar", "")
                rating = row.get("rating", "")
                if pillar and rating:
                    val = parse_rating(rating)
                    if val is not None:
                        # Normalise pillar name: "P1" -> "p1"
                        pid = pillar.lower()
                        pillar_vals[pid].append(val)

    # Aggregate: mean of attribute ratings
    pillars = {}
    for pid, vals in pillar_vals.items():
        if vals:
            mean_val = sum(vals) / len(vals)
            pillars[pid] = value_to_rating(mean_val)
    return pillars


def extract_conviction(data):
    """Extract conviction rating from memo header."""
    header = data.get("header", {})
    if isinstance(header, dict):
        return header.get("conviction", None)
    return None


def main():
    if not MEMOS_DIR.exists():
        print(f"Memos directory not found: {MEMOS_DIR}")
        return

    qualitative = {}

    for ticker_dir in sorted(MEMOS_DIR.iterdir()):
        if not ticker_dir.is_dir() or ticker_dir.name in ("markdown",):
            continue
        ticker = ticker_dir.name

        # Find all memo JSONs, pick highest stage
        best_stage = None
        best_priority = -1
        best_file = None

        # Prefer -v3 > -v2 > base files; within same stage, higher version wins
        for jf in sorted(ticker_dir.glob("*.json")):
            if ".bak" in jf.name or "_draft" in jf.name or "_section" in jf.name:
                continue
            stage = normalise_stage(jf.name)
            # Version bonus: -v3 > -v2 > base
            version_bonus = 0
            if "-v3" in jf.name:
                version_bonus = 2
            elif "-v2" in jf.name:
                version_bonus = 1
            priority = STAGE_PRIORITY.get(stage, 0) * 10 + version_bonus
            if priority > best_priority:
                best_priority = priority
                best_stage = stage
                best_file = jf

        if not best_file:
            continue

        try:
            with open(best_file) as f:
                data = json.load(f)
        except Exception as e:
            print(f"  {ticker}: Failed to read {best_file}: {e}")
            continue

        # Try V3 schema first, then V1
        pillars = extract_pillar_ratings_v3(data)
        schema = "V3"
        if not pillars:
            pillars = extract_pillar_ratings_v1(data)
            schema = "V1"

        conviction = extract_conviction(data)
        stage_from_data = data.get("stage", best_stage)

        if pillars:
            entry = {
                "p1": pillars.get("p1", None),
                "p2": pillars.get("p2", None),
                "p3": pillars.get("p3", None),
                "p4": pillars.get("p4", None),
                "p5": pillars.get("p5", None),
                "p6": pillars.get("p6", None),
                "conviction": conviction,
                "stage": stage_from_data,
            }
            qualitative[ticker] = entry
            ratings_str = " ".join(f"P{i}={entry[f'p{i}']}" for i in range(1, 7) if entry[f"p{i}"])
            print(f"  {ticker} [{best_stage}, {schema}]: {ratings_str}")
        else:
            print(f"  {ticker} [{best_stage}]: No pillar ratings found")

    out_path = DATA_DIR / "qualitative.json"
    with open(out_path, "w") as f:
        json.dump(qualitative, f, indent=2)
    print(f"\nWritten: {out_path} ({os.path.getsize(out_path):,} bytes)")
    print(f"Stocks with ratings: {len(qualitative)} / {len(list(MEMOS_DIR.iterdir()))}")


if __name__ == "__main__":
    main()
