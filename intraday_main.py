from app.services.intraday_scan_service import run_intraday_scan

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--fast", action="store_true",
                         help="Scan only top swing picks instead of full universe (~30s vs ~5min)")
    args = parser.parse_args()
    run_intraday_scan(fast_mode=args.fast)
