from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_analyze_response_exposes_versioned_technical_evidence(monkeypatch):
    def fake_analyze_stock(ticker, timeframe, correlation_id=None):
        return {
            "status": "success",
            "data": {
                "action": "buy",
                "confidence_score": 0.75,
                "reason": "test technical signal",
                "current_price": 108.0,
                "liquidity_evidence": {
                    "evidence_version": "liquidity-evidence-v1",
                    "evidence_status": "partial",
                    "evidence_completeness_score": 0.5714,
                    "metrics": {
                        "current_price": 108.0,
                        "average_daily_volume": 2_000_000.0,
                        "average_dollar_volume": 216_000_000.0,
                        "volume_ratio": 1.25,
                    },
                    "available_fields": [
                        "average_daily_volume",
                        "average_dollar_volume",
                        "current_price",
                        "volume_ratio",
                    ],
                    "missing_fields": ["ask", "bid", "spread_bps"],
                    "evidence_reasons": [
                        "average_dollar_volume_from_historical_ohlcv",
                        "bid_ask_spread_unavailable",
                    ],
                    "provenance": {
                        "historical_source": "historical_ohlcv",
                        "quote_source": "unavailable",
                        "calculation_method": "mean(close_times_volume)",
                        "volume_lookback_bars": 20,
                        "observed_bars": 20,
                        "timeframe": timeframe,
                        "historical_as_of": "2026-07-22T00:00:00Z",
                    },
                },
                "indicators": {
                    "trend": "Uptrend",
                    "rsi": 62.0,
                    "macd_line": 2.0,
                    "macd_signal": 1.0,
                    "atr": 2.5,
                    "atr_percent": 0.025,
                    "swing_low": 90.0,
                    "swing_high": 110.0,
                    "stop_loss": 98.0,
                    "stop_method": "atr",
                    "volatility_regime": "normal",
                    "timeframe": timeframe,
                    "confidence_cap": 0.80,
                    "raw_confidence_score": 0.75,
                    "validation_status": "walk_forward_required_before_live",
                    "walk_forward_passed": None,
                },
            },
            "error": None,
        }

    monkeypatch.setattr("app.main.analyze_stock", fake_analyze_stock)

    response = client.post(
        "/analyze",
        json={"ticker": "TEST", "timeframe": "1d"},
        headers={"X-Correlation-ID": "technical-evidence-test"},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "success"
    assert body["version"] == "1.5.0"
    assert body["correlation_id"] == "technical-evidence-test"
    assert body["metadata"]["evidence_version"] == "technical-evidence-v1"
    assert body["metadata"]["liquidity_evidence_version"] == (
        "liquidity-evidence-v1"
    )
    assert body["metadata"]["liquidity_evidence_status"] == "partial"
    assert body["metadata"]["bucket_decision_authority"] == "manager"
    assert body["data"]["evidence_version"] == "technical-evidence-v1"
    assert body["data"]["manager_decision_required"] is True
    assert body["data"]["bucket_decision_authority"] == "manager"
    assert body["data"]["strategy_bucket_hint"] is None
    assert body["data"]["technical_score"] > 0.60
    assert body["data"]["raw_scores"]["trend_score"] == 0.80
    assert body["data"]["raw_scores"]["volume_ratio"] == 1.25
    profit_context = body["data"]["profit_policy_context"]
    assert profit_context == {
        "context_version": "profit-technical-context.v1",
        "atr_pct": 0.025,
        "trend_strength": 0.8,
        "volume_strength": 0.8333,
        "observed_at": "2026-07-22T00:00:00Z",
        "evidence_status": body["data"]["evidence_status"],
        "source": "technical-agent",
    }

    liquidity = body["data"]["liquidity_evidence"]
    assert liquidity["evidence_version"] == "liquidity-evidence-v1"
    assert liquidity["metrics"]["average_dollar_volume"] == 216_000_000.0
    assert "spread_bps" in liquidity["missing_fields"]

    evidence = body["data"]["technical_evidence"]
    assert evidence["strategy_bucket_hint"] is None
    assert evidence["metrics"]["average_daily_volume"] == 2_000_000.0
    assert evidence["metrics"]["average_dollar_volume"] == 216_000_000.0
    assert evidence["provenance"]["relative_strength_method"] == (
        "local_swing_range_proxy"
    )
    assert evidence["provenance"]["liquidity_evidence_version"] == (
        "liquidity-evidence-v1"
    )
    assert "volume_ratio" not in evidence["missing_fields"]


def test_analyze_error_response_reports_insufficient_evidence(monkeypatch):
    def fake_analyze_stock(ticker, timeframe, correlation_id=None):
        return {
            "status": "error",
            "data": {
                "action": "hold",
                "confidence_score": 0.0,
                "reason": "analysis_error",
            },
            "error": {
                "code": "ANALYSIS_ERROR",
                "message": "no usable indicators",
                "retryable": False,
            },
        }

    monkeypatch.setattr("app.main.analyze_stock", fake_analyze_stock)

    response = client.post(
        "/analyze",
        json={"ticker": "BAD", "timeframe": "1d"},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "error"
    assert body["metadata"]["liquidity_evidence_status"] == "unavailable"
    assert body["data"]["evidence_status"] == "insufficient"
    assert body["data"]["technical_score"] is None
    assert body["data"]["raw_scores"] == {}
    assert body["data"]["liquidity_evidence"] is None
    assert body["data"]["technical_evidence"]["evidence_reasons"] == [
        "technical_indicators_unavailable"
    ]
    assert body["data"]["profit_policy_context"]["atr_pct"] is None
    assert body["data"]["profit_policy_context"]["trend_strength"] is None
    assert body["data"]["profit_policy_context"]["volume_strength"] is None
    assert body["data"]["profit_policy_context"]["observed_at"] is None
