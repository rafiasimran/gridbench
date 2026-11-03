"""Tests for the SMARD downloader. They use small fake weekly files, so no network is needed."""

from datetime import datetime

import pandas as pd

from gridbench import smard

HOUR = 3600 * 1000
WEEK = 7 * 24 * HOUR
W1 = smard._ms(datetime(2025, 10, 19, 22))   # week with the October clock change
W2 = W1 + WEEK + HOUR                         # the next week starts one hour later in UTC


def fake_smard(weeks, calls=None):
    """weeks: {start_ms: [values]}. Returns a get() that serves index and week files."""
    def get(url):
        if calls is not None:
            calls.append(url)
        if url.endswith("index_hour.json"):
            return {"timestamps": sorted(weeks)}
        start = int(url.rsplit("_", 1)[1].removesuffix(".json"))
        return {"meta_data": {"version": 1}, "series": [[start + i * HOUR, v] for i, v in enumerate(weeks[start])]}
    return get


def test_parse_week_keeps_utc_and_turns_null_into_nan():
    s = smard.parse_week({"series": [[W1, 70.04], [W1 + HOUR, None], [W1 + 2 * HOUR, 60.98]]})
    assert str(s.index.tz) == "UTC"
    assert s.index[0] == pd.Timestamp("2025-10-19 22:00", tz="UTC")
    assert s.isna().tolist() == [False, True, False]


def test_clock_change_week_has_169_hours(tmp_path):
    get = fake_smard({W1: [1.0] * 169})
    s = smard.download_series("price_eur_mwh", datetime(2025, 10, 19, 22), datetime(2025, 10, 26, 23),
                              tmp_path, get, now=datetime(2026, 1, 1))
    assert len(s) == 169
    assert s.index.is_monotonic_increasing and not s.index.duplicated().any()


def test_only_weeks_in_range_are_downloaded(tmp_path):
    calls = []
    get = fake_smard({W1: [1.0] * 169, W2: [2.0] * 168}, calls)
    s = smard.download_series("load_mwh", datetime(2025, 10, 28), datetime(2025, 10, 29), tmp_path, get,
                              now=datetime(2026, 1, 1))
    assert len(s) == 24 and (s == 2.0).all()
    assert not any(str(W1) in c for c in calls)


def test_cached_weeks_are_not_downloaded_again(tmp_path):
    calls = []
    get = fake_smard({W1: [1.0] * 169}, calls)
    args = ("load_mwh", datetime(2025, 10, 20), datetime(2025, 10, 21), tmp_path, get)
    smard.download_series(*args, now=datetime(2026, 1, 1))
    smard.download_series(*args, now=datetime(2026, 1, 1))
    assert sum(str(W1) in c for c in calls) == 1


def test_recent_weeks_are_downloaded_again(tmp_path):
    calls = []
    get = fake_smard({W1: [1.0] * 169}, calls)
    args = ("load_mwh", datetime(2025, 10, 20), datetime(2025, 10, 21), tmp_path, get)
    smard.download_series(*args, now=datetime(2025, 10, 25))
    smard.download_series(*args, now=datetime(2025, 10, 25))
    assert sum(str(W1) in c for c in calls) == 2


def test_hours_that_have_not_happened_yet_are_dropped(tmp_path):
    values = [5.0] * 100 + [None] * 68          # SMARD returns the rest of the current week as null
    gap = [5.0] * 10 + [None] * 3 + [5.0] * 155  # a real gap in the middle must stay
    get = fake_smard({W2: values})
    get_gap = fake_smard({W2: gap})
    start, end = datetime(2025, 10, 26, 23), datetime(2025, 11, 3)
    df = smard.download_all(start, end, tmp_path / "a", ["load_mwh"], get, now=datetime(2025, 10, 30))
    assert len(df) == 100 and df.index.name == "timestamp_utc"
    df_gap = smard.download_all(start, end, tmp_path / "b", ["load_mwh"], get_gap, now=datetime(2026, 1, 1))
    assert len(df_gap) == 168 and df_gap["load_mwh"].isna().sum() == 3


def test_real_smard_week_with_the_october_clock_change():
    # A real weekly file: day-ahead prices for 20-26 Oct 2025, as downloaded from SMARD.
    # Data: Bundesnetzagentur | SMARD.de, CC BY 4.0
    import json
    from pathlib import Path
    data = json.loads((Path(__file__).parent / "data" / "smard_price_week_2025-10-20.json").read_text())
    s = smard.parse_week(data)
    assert len(s) == 169                                   # 7 days + the extra hour on 26 Oct
    assert s.index[0] == pd.Timestamp("2025-10-19 22:00", tz="UTC")   # Monday 00:00 in Berlin (CEST)
    assert s.index[-1] == pd.Timestamp("2025-10-26 22:00", tz="UTC")  # Sunday 23:00 in Berlin (CET)
    assert (s.index.to_series().diff().dropna() == pd.Timedelta(hours=1)).all()
    assert s.min() < 0 and s.notna().all()                 # prices went below zero that weekend


def test_duplicate_hours_are_counted_not_hidden(tmp_path):
    # Two weekly files that overlap by one hour.
    get = fake_smard({W1: [1.0] * 169, W1 + 168 * HOUR: [9.0] * 168})
    df = smard.download_all(datetime(2025, 10, 19, 22), datetime(2025, 11, 3), tmp_path, ["load_mwh"], get,
                            now=datetime(2026, 1, 1))
    assert df.index.is_unique
    assert df.attrs["duplicates"] == {"load_mwh": 1}
