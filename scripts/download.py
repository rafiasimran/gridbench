"""Download the raw SMARD data for GridBench.

    python scripts/download.py
    python scripts/download.py --start 2020-01-01 --end 2026-11-01

Weekly files are cached in data/raw/smard/, and the combined table is written
to data/raw/smard_hourly.csv. Both stay out of git.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from gridbench.smard import SERIES, download_all  # noqa: E402


def main():
    p = argparse.ArgumentParser(description="Download hourly German grid data from SMARD.")
    p.add_argument("--start", default="2020-01-01", help="first day, UTC (YYYY-MM-DD)")
    p.add_argument("--end", default="2026-11-01", help="day after the last one, UTC (YYYY-MM-DD)")
    p.add_argument("--out", default=str(ROOT / "data" / "raw"))
    a = p.parse_args()

    out = Path(a.out)
    start, end = datetime.fromisoformat(a.start), datetime.fromisoformat(a.end)
    print(f"Downloading {len(SERIES)} series from SMARD, {a.start} to {a.end} ...")
    df = download_all(start, end, out / "smard")
    path = out / "smard_hourly.csv"
    df.to_csv(path)
    print(f"{len(df):,} hours x {df.shape[1]} series, {df.index[0]} to {df.index[-1]}")
    print("Empty values per series:")
    print(df.isna().sum().to_string())
    print(f"Saved {path}")


if __name__ == "__main__":
    main()
