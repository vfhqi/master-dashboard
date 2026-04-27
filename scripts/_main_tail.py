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
                "notes": "VCP pattern detection pending Phase 2. UTR signals 1-8 all live (27-Apr-26)."
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
