from __future__ import annotations

import math
from typing import Any, Dict, Mapping, Optional


def _mapping(value: Any) -> Dict[str, Any]:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return dict(value) if isinstance(value, Mapping) else {}


def _finite_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _atr_ratio(value: Any) -> Optional[float]:
    number = _finite_float(value)
    if number is None or number < 0:
        return None
    return round(number / 100.0 if number > 1.0 else number, 6)


def _strength(value: Any) -> Optional[float]:
    number = _finite_float(value)
    if number is None:
        return None
    return round(max(0.0, min(1.0, number)), 4)


def _volume_strength(volume_ratio: Any) -> Optional[float]:
    number = _finite_float(volume_ratio)
    if number is None or number < 0:
        return None
    return round(min(1.0, number / 1.5), 4)


def build_profit_policy_context(
    *,
    technical_evidence: Mapping[str, Any] | None,
    liquidity_evidence: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    """Project existing evidence without manufacturing unavailable inputs."""
    technical = _mapping(technical_evidence)
    metrics = _mapping(technical.get("metrics"))
    raw_scores = _mapping(technical.get("raw_scores"))
    liquidity = _mapping(liquidity_evidence)
    liquidity_metrics = _mapping(liquidity.get("metrics"))
    liquidity_provenance = _mapping(liquidity.get("provenance"))
    return {
        "context_version": "profit-technical-context.v1",
        "atr_pct": _atr_ratio(metrics.get("atr_percent")),
        "trend_strength": _strength(raw_scores.get("trend_score")),
        "volume_strength": _volume_strength(
            liquidity_metrics.get("volume_ratio")
        ),
        "observed_at": liquidity_provenance.get("historical_as_of"),
        "evidence_status": str(
            technical.get("evidence_status") or "unavailable"
        ),
        "source": "technical-agent",
    }
