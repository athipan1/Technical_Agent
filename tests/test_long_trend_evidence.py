import pandas as pd

from app.liquidity_evidence import build_liquidity_evidence


def _daily_frame(rows: int = 220) -> pd.DataFrame:
    close = [100.0 + (index * 0.5) for index in range(rows)]
    volume = [1_000_000.0 + index for index in range(rows)]
    return pd.DataFrame(
        {"Close": close, "Volume": volume},
        index=pd.date_range("2025-01-01", periods=rows, freq="D"),
    )


def test_daily_history_publishes_sma_and_return_context_without_extra_provider_call():
    frame = _daily_frame()
    evidence = build_liquidity_evidence(frame, timeframe="1d")
    metrics = evidence["metrics"]
    context = evidence["provenance"]["long_trend_context"]

    assert metrics["sma50"] > metrics["sma200"]
    assert metrics["price_above_sma200"] is True
    assert metrics["sma50_above_sma200"] is True
    assert metrics["return_20d"] > 0
    assert metrics["return_60d"] > 0
    assert context["status"] == "complete"
    assert context["timeframe"] == "1d"
    assert context["method"] == "daily_ohlcv_rolling_close"
    assert context["observed_bars"] == 220
    assert "daily_long_trend_evidence_complete" in evidence["evidence_reasons"]


def test_long_trend_evidence_is_partial_when_history_is_short():
    evidence = build_liquidity_evidence(_daily_frame(70), timeframe="1d")
    metrics = evidence["metrics"]
    context = evidence["provenance"]["long_trend_context"]

    assert "sma50" in metrics
    assert "sma200" not in metrics
    assert "return_20d" in metrics
    assert "return_60d" in metrics
    assert context["status"] == "partial"
    assert "sma200" in context["missing_fields"]


def test_intraday_history_never_masquerades_as_daily_sma_evidence():
    frame = _daily_frame()
    evidence = build_liquidity_evidence(frame, timeframe="1h")
    context = evidence["provenance"]["long_trend_context"]

    assert "sma50" not in evidence["metrics"]
    assert "sma200" not in evidence["metrics"]
    assert context["status"] == "unavailable"
    assert context["timeframe"] == "1h"
    assert "daily_long_trend_evidence_unavailable" in evidence["evidence_reasons"]
