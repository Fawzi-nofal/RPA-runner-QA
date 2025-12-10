from pathlib import Path
import argparse
from core.runner import run_scenario

def main():
    ap = argparse.ArgumentParser(description="RPA Runner (YAML + Playwright)")
    ap.add_argument("scenario", help="Path to YAML scenario")
    args = ap.parse_args()
    code = run_scenario(Path(args.scenario))
    raise SystemExit(code)

if __name__ == "__main__":
    main()
