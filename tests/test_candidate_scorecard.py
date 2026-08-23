from app.candidate_scorecard import build_technical_candidate_scorecard
from app.technical_evidence import build_technical_evidence


def test_technical_scorecard_awards_only_proven_local_points():
    scorecard = build_technical_candidate_scorecard(
        trend="Uptrend",
        volume_ratio=1.4,
        relative_strength_method="local_swing_range_proxy",
        evidence_status="complete",
    )

    assert scorecard["score_version"] == "candidate-score.v1"
    assert scorecard["points"] == 2
    assert scorecard["max_points"] == 4
    assert scorecard["criteria"]["price_above_sma200"]["point"] == 1
    assert scorecard["criteria"]["volume_confirmation"]["point"] == 1
    assert scorecard["criteria"]["sma50_above_sma200"]["available"] is False
    assert scorecard["criteria"]["relative_strength"]["available"] is False


def test_local_relative_strength_proxy_does_not_get_benchmark_point():
    scorecard = build_technical_candidate_scorecard(
        trend="Uptrend",
        volume_ratio=1.0,
        relative_strength_method="local_swing_range_proxy",
        evidence_status="complete",
    )

    assert scorecard["criteria"]["relative_strength"]["point"] == 0
    assert scorecard["criteria"]["relative_strength"]["source"] == (
        "benchmark_evidence_required"
    )


def test_technical_evidence_publishes_candidate_scorecard():
    evidence = build_technical_evidence(
        action="buy",
        confidence_score=0.75,
        current_price=105.0,
        indicators={
            "trend": "Uptrend",
            "rsi": 55.0,
            "macd_line": 1.2,
            "macd_signal": 0.8,
            "atr": 2.0,
            "atr_percent": 0.02,
            "swing_low": 100.0,
            "swing_high": 112.0,
            "timeframe": "1d",
        },
        liquidity_evidence={
            "evidence_version": "liquidity-evidence-v1",
            "evidence_status": "partial",
            "metrics": {"volume_ratio": 1.5},
            "provenance": {},
        },
    )

    scorecard = evidence["provenance"]["candidate_scorecard"]
    assert scorecard["points"] == 2
    assert evidence["raw_scores"]["candidate_technical_points"] == 2
