"""The HTTP boundary must preserve the predicates produced by indicators."""
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.mark.parametrize("expected_action", ["buy", "hold"])
def test_http_analysis_preserves_computed_buy_predicates(monkeypatch, expected_action):
    if expected_action == "buy":
        close = np.r_[np.linspace(50, 100, 230), np.linspace(100, 160, 15),
                      np.linspace(160, 105, 12), np.repeat(105., 15)]
    else:
        close = np.linspace(50, 100, 272)
    frame = pd.DataFrame(
        {"Open": close, "High": close + 1, "Low": close - 1,
         "Close": close, "Volume": 1e6},
        index=pd.date_range(end=pd.Timestamp.now(tz="UTC"), periods=len(close), freq="D"),
    )
    monkeypatch.setattr("app.service.get_stock_data", lambda *args, **kwargs: frame)
    response = TestClient(app).post(
        "/analyze", json={"ticker": "TEST", "timeframe": "1d"},
        headers={"X-Correlation-ID": "http-decision-trace-regression"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["correlation_id"] == "http-decision-trace-regression"
    data = body["data"]
    assert data["action"] == expected_action
    trace = data["decision_trace"]
    assert trace["schema_version"] == "technical-decision-trace.v1"
    assert trace["action"] == expected_action
    assert trace["inputs"]["Close"] == float(close[-1])
    assert trace["inputs"]["SMA_200"] > 0
    assert len(trace["buy_conditions"]) == 3
    assert all(p["passed"] for p in trace["buy_conditions"]) == (expected_action == "buy")
    assert all(p["observed"] is not None and p["threshold"] is not None
               for p in trace["buy_conditions"])
    if expected_action == "hold":
        assert "TECHNICAL_RSI_NOT_OVERSOLD" in trace["reason_codes"]
