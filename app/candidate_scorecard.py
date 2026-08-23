from __future__ import annotations

import math
from typing import Any, Dict, Mapping, Optional

CANDIDATE_SCORE_VERSION = "candidate-score.v1"
TECHNICAL_MAX_POINTS = 4


def _finite(value: Any) -> Optional[float]:
    try:
        if value is None or value == "" or isinstance(value, bool):
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def build_technical_candidate_scorecard(
    *,
    trend: Optional[str],
    volume_ratio: Any,
    relative_strength_method: Optional[str],
    evidence_status: Optional[str],
) -> Dict[str, Any]:
    """Project technical inputs used by Manager's 10-point score.

    Technical_Agent can prove price-vs-SMA200 from its trend signal and volume
    confirmation. It deliberately does not award the SMA50>SMA200 or benchmark
    relative-strength points because those inputs are not present in this API.
    Scanner_Agent may supply them to Manager_Agent later in the pipeline.
    """

    normalized_trend = str(trend or "").strip().lower()
    volume = _finite(volume_ratio)
    trend_available = normalized_trend in {"uptrend", "downtrend", "sideways"}
    trend_passed = normalized_trend == "uptrend"
    volume_available = volume is not None
    volume_passed = volume is not None and volume >= 1.10

    relative_is_benchmark = str(relative_strength_method or "").strip().lower() in {
        "benchmark_relative",
        "benchmark_relative_return",
    }

    criteria = {
        "price_above_sma200": {
            "available": trend_available,
            "passed": trend_passed,
            "point": 1 if trend_available and trend_passed else 0,
            "observed": normalized_trend or None,
            "threshold": "trend == uptrend (trend is derived from price vs SMA200)",
            "source": "technical_evidence.metrics.trend",
        },
        "sma50_above_sma200": {
            "available": False,
            "passed": False,
            "point": 0,
            "observed": None,
            "threshold": "SMA50 > SMA200",
            "source": "scanner_candidate_score_inputs_required",
        },
        "relative_strength": {
            "available": relative_is_benchmark,
            "passed": False,
            "point": 0,
            "observed": relative_strength_method,
            "threshold": "benchmark-relative strength must be positive/strong",
            "source": "benchmark_evidence_required",
        },
        "volume_confirmation": {
            "available": volume_available,
            "passed": volume_passed,
            "point": 1 if volume_available and volume_passed else 0,
            "observed": volume,
            "threshold": "relative volume >= 1.10",
            "source": "liquidity_evidence.metrics.volume_ratio",
        },
    }

    points = sum(int(row["point"]) for row in criteria.values())
    available = sum(1 for row in criteria.values() if row["available"])
    return {
        "score_version": CANDIDATE_SCORE_VERSION,
        "scope": "technical",
        "points": points,
        "max_points": TECHNICAL_MAX_POINTS,
        "coverage_ratio": round(available / TECHNICAL_MAX_POINTS, 4),
        "evidence_complete": available == TECHNICAL_MAX_POINTS,
        "usable_for_manager_scoring": evidence_status not in {"insufficient", "unavailable"},
        "criteria": criteria,
        "authority": "advisory_only",
        "manager_decision_required": True,
    }
