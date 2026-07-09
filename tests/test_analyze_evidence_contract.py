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
    assert body["version"] == "1.4.0"
    assert body["correlation_id"] == "technical-evidence-test"
    assert body["metadata"]["evidence_version"] == "technical-evidence-v1"
    assert body["metadata"]["bucket_decision_authority"] == "manager"
    assert body["data"]["evidence_version"] == "technical-evidence-v1"
    assert body["data"]["manager_decision_required"] is True
    assert body["data"]["bucket_decision_authority"] == "manager"
    assert body["data"]["strategy_bucket_hint"] is None
    assert body["data"]["technical_score"] > 0.60
    assert body["data"]["raw_scores"]["trend_score"] == 0.80
    evidence = body["data"]["technical_evidence"]
    assert evidence["strategy_bucket_hint"] is None
    assert evidence["provenance"]["relative_strength_method"] == "local_swing_range_proxy"
    assert "volume_ratio" in evidence["missing_fields"]


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
    assert body["data"]["evidence_status"] == "insufficient"
    assert body["data"]["technical_score"] is None
    assert body["data"]["raw_scores"] == {}
    assert body["data"]["technical_evidence"]["evidence_reasons"] == [
        "technical_indicators_unavailable"
    ]
