import math

import pandas as pd

from app.liquidity_evidence import build_liquidity_evidence


def _frame():
    return pd.DataFrame(
        {
            "Close": [10.0, 11.0, 12.0, 13.0],
            "Volume": [100_000.0, 120_000.0, 140_000.0, 160_000.0],
        },
        index=pd.date_range("2026-01-01", periods=4, freq="D"),
    )


def test_historical_ohlcv_builds_partial_liquidity_evidence():
    evidence = build_liquidity_evidence(
        _frame(),
        timeframe="1d",
        lookback_bars=3,
    )

    assert evidence["evidence_version"] == "liquidity-evidence-v1"
    assert evidence["evidence_status"] == "partial"
    assert evidence["metrics"]["current_price"] == 13.0
    assert evidence["metrics"]["average_daily_volume"] == 140_000.0
    assert evidence["metrics"]["average_price"] == 12.0
    assert evidence["metrics"]["average_dollar_volume"] == 1_693_333.333333
    assert evidence["metrics"]["volume_ratio"] == 1.142857
    assert "spread_bps" in evidence["missing_fields"]
    assert evidence["provenance"]["calculation_method"] == (
        "mean(close_times_volume)"
    )


def test_valid_quote_completes_bid_ask_spread():
    evidence = build_liquidity_evidence(
        _frame(),
        timeframe="1d",
        quote={
            "bid": 12.99,
            "ask": 13.01,
            "source": "alpaca_iex",
            "as_of": "2026-01-04T20:00:00Z",
        },
    )

    assert evidence["evidence_status"] == "complete"
    assert evidence["metrics"]["bid"] == 12.99
    assert evidence["metrics"]["ask"] == 13.01
    assert evidence["metrics"]["spread_bps"] == 15.3846
    assert evidence["provenance"]["quote_source"] == "alpaca_iex"


def test_invalid_quote_is_not_manufactured():
    evidence = build_liquidity_evidence(
        _frame(),
        timeframe="1d",
        quote={"bid": 13.10, "ask": 13.00, "source": "bad-fixture"},
    )

    assert evidence["evidence_status"] == "partial"
    assert "spread_bps" not in evidence["metrics"]
    assert "bid_ask_spread_unavailable" in evidence["evidence_reasons"]


def test_nan_and_infinity_are_excluded():
    frame = pd.DataFrame(
        {
            "Close": [10.0, math.nan, 12.0, math.inf],
            "Volume": [100_000.0, 120_000.0, math.inf, 160_000.0],
        }
    )

    evidence = build_liquidity_evidence(frame, timeframe="1d")

    assert evidence["evidence_status"] == "partial"
    assert evidence["metrics"]["current_price"] == 10.0
    assert evidence["metrics"]["average_daily_volume"] == 100_000.0
    assert evidence["metrics"]["average_dollar_volume"] == 1_000_000.0


def test_missing_volume_reports_unavailable_evidence():
    frame = pd.DataFrame({"Close": [10.0, 11.0, 12.0]})

    evidence = build_liquidity_evidence(frame, timeframe="1d")

    assert evidence["evidence_status"] == "unavailable"
    assert evidence["metrics"] == {}
    assert "average_dollar_volume" in evidence["missing_fields"]
    assert "average_dollar_volume_unavailable" in evidence[
        "evidence_reasons"
    ]
