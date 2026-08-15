from datetime import datetime, timedelta, timezone

import pandas as pd

from app.data_quality import assess_data_quality


NOW = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)


def _quality_frame(rows: int = 220) -> pd.DataFrame:
    end = NOW - timedelta(hours=1)
    index = pd.date_range(end=end, periods=rows, freq="h", tz="UTC")
    close = [100.0 + (idx * 0.1) for idx in range(rows)]
    return pd.DataFrame(
        {
            "Open": [value - 0.2 for value in close],
            "High": [value + 0.5 for value in close],
            "Low": [value - 0.5 for value in close],
            "Close": close,
            "Volume": [1_000_000.0 for _ in close],
            "SMA_200": [105.0 for _ in close],
            "RSI_14": [55.0 for _ in close],
            "MACD_12_26_9": [0.5 for _ in close],
            "MACDs_12_26_9": [0.4 for _ in close],
            "ATR_14": [1.2 for _ in close],
        },
        index=index,
    )


def test_complete_quality_requires_fresh_full_indicator_set():
    report = assess_data_quality(
        _quality_frame(),
        timeframe="1h",
        now=NOW,
    )

    assert report["status"] == "complete"
    assert report["completeness_score"] == 1.0
    assert report["fresh"] is True
    assert report["bars_available"] == 220
    assert report["missing_fields"] == []


def test_missing_volume_is_partial_not_fabricated():
    frame = _quality_frame().drop(columns=["Volume"])

    report = assess_data_quality(frame, timeframe="1h", now=NOW)

    assert report["status"] == "partial"
    assert "Volume" in report["missing_fields"]
    assert "missing_supplemental_price_field:Volume" in report["reasons"]


def test_missing_rsi_is_insufficient():
    frame = _quality_frame()
    frame.loc[frame.index[-1], "RSI_14"] = float("nan")

    report = assess_data_quality(frame, timeframe="1h", now=NOW)

    assert report["status"] == "insufficient"
    assert "RSI_14" in report["missing_fields"]
    assert "invalid_latest_indicator:RSI_14" in report["reasons"]


def test_insufficient_history_fails_closed():
    report = assess_data_quality(
        _quality_frame(rows=50),
        timeframe="1h",
        now=NOW,
    )

    assert report["status"] == "insufficient"
    assert "bars_below_minimum:50/200" in report["reasons"]


def test_stale_market_data_fails_closed():
    frame = _quality_frame()
    frame.index = pd.date_range(
        end=NOW - timedelta(days=4),
        periods=len(frame),
        freq="h",
        tz="UTC",
    )

    report = assess_data_quality(frame, timeframe="1h", now=NOW)

    assert report["status"] == "insufficient"
    assert report["fresh"] is False
    assert any(reason.startswith("stale_market_data:") for reason in report["reasons"])


def test_unsupported_timeframe_fails_closed():
    report = assess_data_quality(
        _quality_frame(),
        timeframe="2h",
        now=NOW,
    )

    assert report["status"] == "insufficient"
    assert report["reasons"] == ["unsupported_timeframe"]
