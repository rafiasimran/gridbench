"""Download hourly German grid data from SMARD (Bundesnetzagentur).

SMARD serves every series as weekly JSON files:

    index: {BASE}/{id}/DE/index_hour.json            -> {"timestamps": [ms, ...]}
    week:  {BASE}/{id}/DE/{id}_DE_hour_{start}.json  -> {"series": [[ms, value], ...]}

The index lists the first hour of each week. Timestamps are milliseconds since
1970 in UTC, so the clock changes are already handled: the week with the
October change has 169 hours and the one in March 167. Hours that haven't
happened yet come back as null.

Each week is saved in data/raw/ as it was downloaded, so a rebuild only
fetches what is new, and the cleaning steps can always be checked against
the original files.

Data: Bundesnetzagentur | SMARD.de, CC BY 4.0.
"""

import json
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

BASE = "https://www.smard.de/app/chart_data"
REGION = "DE"

# Column name -> SMARD filter id. Generation and load are MWh per hour
# (the same number as the average power in MW); prices are EUR/MWh for the
# Germany-Luxembourg bidding zone.
SERIES = {
    "load_mwh": 410,
    "residual_load_mwh": 4359,
    "price_eur_mwh": 4169,
    "solar_mwh": 4068,
    "wind_onshore_mwh": 4067,
    "wind_offshore_mwh": 1225,
    "biomass_mwh": 4066,
    "hydro_mwh": 1226,
    "other_renewable_mwh": 1228,
    "nuclear_mwh": 1224,
    "lignite_mwh": 1223,
    "hard_coal_mwh": 4069,
    "gas_mwh": 4071,
    "pumped_storage_mwh": 4070,
    "other_conventional_mwh": 1227,
}

# A week this close to today can still be revised, so it is downloaded again
# instead of read from the cache.
FRESH_DAYS = 14


def fetch_json(url: str, retries: int = 3) -> dict:
    """GET a URL and parse the JSON, retrying a few times on network errors."""
    req = urllib.request.Request(url, headers={"User-Agent": "gridbench (research dataset build)"})
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except OSError:
            if attempt == retries:
                raise
            time.sleep(2 * attempt)


def _ms(dt: datetime) -> int:
    return int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)


def week_starts(series_id: int, start: datetime, end: datetime, get=fetch_json) -> list[int]:
    """Start times (ms) of the weeks that overlap start..end, both in UTC."""
    stamps = get(f"{BASE}/{series_id}/{REGION}/index_hour.json")["timestamps"]
    week_ms = 7 * 24 * 3600 * 1000
    lo, hi = _ms(start), _ms(end)
    return [t for t in stamps if t + week_ms > lo and t < hi]


def parse_week(data: dict) -> pd.Series:
    """One weekly file -> Series of floats on a UTC index. Nulls become NaN."""
    rows = data.get("series") or []
    index = pd.to_datetime([t for t, _ in rows], unit="ms", utc=True)
    values = pd.to_numeric(pd.Series([v for _, v in rows], dtype="object"), errors="coerce")
    return pd.Series(values.to_numpy(dtype=float), index=index)


def download_series(name: str, start: datetime, end: datetime, cache_dir: str | Path,
                    get=fetch_json, now: datetime | None = None) -> pd.Series:
    """Download one series for start..end (UTC), using the cache in cache_dir.

    Returns the raw values as SMARD sent them, cut to start <= t < end.
    Duplicates and gaps are not fixed here; that is the cleaning step's job.
    """
    series_id = SERIES[name]
    folder = Path(cache_dir) / str(series_id)
    folder.mkdir(parents=True, exist_ok=True)
    fresh_after = _ms((now or datetime.now(timezone.utc).replace(tzinfo=None)) - timedelta(days=FRESH_DAYS))

    parts = []
    for week in week_starts(series_id, start, end, get):
        path = folder / f"{week}.json"
        if path.exists() and week < fresh_after:
            data = json.loads(path.read_text(encoding="utf-8"))
        else:
            data = get(f"{BASE}/{series_id}/{REGION}/{series_id}_{REGION}_hour_{week}.json")
            path.write_text(json.dumps(data), encoding="utf-8")
        parts.append(parse_week(data))

    if not parts:
        return pd.Series(dtype=float, name=name)
    s = pd.concat(parts).sort_index()
    lo, hi = pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC")
    s = s[(s.index >= lo) & (s.index < hi)]
    s.name = name
    return s


def download_all(start: datetime, end: datetime, cache_dir: str | Path, names=None,
                 get=fetch_json, now: datetime | None = None) -> pd.DataFrame:
    """All series side by side on one UTC index.

    Hours at the end where every series is still empty (they haven't happened
    yet, or SMARD hasn't published them) are dropped. Empty hours in the
    middle are kept, so the quality report can count them.

    If a timestamp appears twice in one series, the first value is kept, so
    the columns can be lined up. How many were dropped per series is stored
    in df.attrs["duplicates"] for the quality report.
    """
    cols = [download_series(n, start, end, cache_dir, get, now) for n in (names or SERIES)]
    duplicates = {c.name: int(c.index.duplicated().sum()) for c in cols}
    cols = [c[~c.index.duplicated(keep="first")] for c in cols]
    df = pd.concat(cols, axis=1).sort_index()
    df.attrs["duplicates"] = duplicates
    filled = df.notna().any(axis=1)
    if filled.any():
        df = df.loc[: filled[filled].index[-1]]
    df.index.name = "timestamp_utc"
    return df
