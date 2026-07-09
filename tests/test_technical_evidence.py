from app.models import Action, StandardAgentData
from app.technical_evidence import build_technical_evidence


def _indicators(**overrides):
    data = {
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
        "timeframe": "1d",
        "confidence_cap": 0.80,
        "raw_confidence_score": 0.75,
        "validation_status": "walk_forward_required_before_live",
        "walk_forward_passed": None,
    }
    data.update(overrides)
    return data


def test_build_technical_evidence_is_versioned_and_non_binding():
    evidence = build_technical_evidence(
        action="buy",
        confidence_score=0.75,
        current_price=108.0,
        indicators=_indicators(),
    )

    assert evidence["evidence_version"] == "technical-evidence-v1"
    assert evidence["evidence_status"] == "complete"
    assert evidence["strategy_bucket_hint"] is None
    assert evidence["bucket_decision_authority"] == "manager"
    assert evidence["manager_decision_required"] is True
    assert evidence["raw_scores"]["technical_score"] > 0.60
    assert evidence["raw_scores"]["trend_score"] == 0.80
    assert evidence["raw_scores"]["technical_vote_score"] == 0.80
    assert evidence["raw_scores"]["breakout_ratio"] == round(108 / 110, 6)
    assert evidence["metrics"]["support_level"] == 90.0
    assert evidence["metrics"]["resistance_level"] == 110.0
    assert "volume_ratio" in evidence["missing_fields"]
    assert evidence["provenance"]["relative_strength_method"] == "local_swing_range_proxy"


def test_failed_walk_forward_reduces_technical_score():
    passed = build_technical_evidence(
        action="buy",
        confidence_score=0.75,
        current_price=108.0,
        indicators=_indicators(walk_forward_passed=True),
    )
    failed = build_technical_evidence(
        action="buy",
        confidence_score=0.75,
        current_price=108.0,
        indicators=_indicators(walk_forward_passed=False),
    )

    assert failed["raw_scores"]["technical_score"] < passed["raw_scores"]["technical_score"]
    assert failed["provenance"]["validation_penalty_applied"] is True
    assert "walk_forward_failed_confidence_penalty_applied" in failed["evidence_reasons"]


def test_sparse_indicators_report_partial_evidence():
    evidence = build_technical_evidence(
        action="hold",
        confidence_score=0.50,
        current_price=100.0,
        indicators={
            "trend": "Sideways",
            "rsi": 50.0,
            "macd_line": 0.0,
            "macd_signal": 0.0,
            "timeframe": "1d",
            "validation_status": "walk_forward_required_before_live",
        },
    )

    assert evidence["evidence_status"] == "partial"
    assert "relative_strength_score" in evidence["missing_fields"]
    assert "breakout_ratio" in evidence["missing_fields"]
    assert "volume_ratio" in evidence["missing_fields"]
    assert "relative_strength_unavailable" in evidence["evidence_reasons"]


def test_standard_data_does_not_manufacture_score_without_indicators():
    data = StandardAgentData(
        action=Action.HOLD,
        confidence_score=0.0,
        reason="analysis_error",
        current_price=None,
        indicators=None,
    )

    assert data.evidence_status == "insufficient"
    assert data.evidence_completeness_score == 0.0
    assert data.technical_score is None
    assert data.raw_scores == {}
    assert data.technical_evidence is not None
    assert data.technical_evidence.evidence_reasons == [
        "technical_indicators_unavailable"
    ]
    assert data.technical_evidence.strategy_bucket_hint is None
