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
    expected = int((df.index[-1] - df.index[0]).total_seconds() // 3600) + 1
    print(f"Hours expected between first and last: {expected:,} (missing rows: {expected - len(df):,})")
    print(f"Duplicate timestamps dropped: {df.attrs.get('duplicates', {})}")
    print("\nEmpty values per series and year:")
    print(df.isna().groupby(df.index.year).sum().T.to_string())
    print("\nFirst and last hour with a value, per series:")
    for col in df.columns:
        s = df[col].dropna()
        print(f"  {col:24} {s.index[0] if len(s) else '-'}  ->  {s.index[-1] if len(s) else '-'}")
    print("\nRange per series (min / max):")
    print(df.agg(["min", "max"]).T.to_string())
    print(f"\nSaved {path}")


if __name__ == "__main__":
    main()
