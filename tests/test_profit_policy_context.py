from app.profit_policy_context import build_profit_policy_context


def test_context_normalizes_percent_atr_and_caps_volume_strength():
    context = build_profit_policy_context(
        technical_evidence={
            "evidence_status": "complete",
            "metrics": {"atr_percent": 2.5},
            "raw_scores": {"trend_score": 0.8},
        },
        liquidity_evidence={
            "metrics": {"volume_ratio": 2.0},
            "provenance": {"historical_as_of": "2026-07-22T00:00:00Z"},
        },
    )

    assert context["atr_pct"] == 0.025
    assert context["trend_strength"] == 0.8
    assert context["volume_strength"] == 1.0
    assert context["observed_at"] == "2026-07-22T00:00:00Z"


def test_context_does_not_fabricate_missing_evidence():
    context = build_profit_policy_context(
        technical_evidence={"evidence_status": "insufficient"},
        liquidity_evidence=None,
    )

    assert context["atr_pct"] is None
    assert context["trend_strength"] is None
    assert context["volume_strength"] is None
    assert context["observed_at"] is None
    assert context["evidence_status"] == "insufficient"
