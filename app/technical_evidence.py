from __future__ import annotations

import math
from typing import Any, Dict, Mapping, Optional


TECHNICAL_EVIDENCE_VERSION = "technical-evidence-v1"
BUCKET_DECISION_AUTHORITY = "manager"


def _mapping(value: Any) -> Dict[str, Any]:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return dict(value) if isinstance(value, Mapping) else {}


def _float_or_none(value: Any) -> Optional[float]:
    try:
        if value is None or value == "" or isinstance(value, bool):
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _cap01(value: float) -> float:
    return round(max(0.0, min(1.0, float(value))), 4)


def _round_optional(value: Any, digits: int = 6) -> Optional[float]:
    number = _float_or_none(value)
    return round(number, digits) if number is not None else None


def _trend_score(trend: str) -> Optional[float]:
    normalized = str(trend or "").strip().lower()
    return {
        "uptrend": 0.80,
        "sideways": 0.50,
        "downtrend": 0.20,
    }.get(normalized)


def _rsi_score(rsi: Optional[float]) -> Optional[float]:
    if rsi is None:
        return None
    return _cap01((rsi - 30.0) / 40.0)


def _macd_score(
    macd_line: Optional[float],
    macd_signal: Optional[float],
) -> Optional[float]:
    if macd_line is None or macd_signal is None:
        return None
    if macd_line > macd_signal:
        return 0.75
    if macd_line < macd_signal:
        return 0.25
    return 0.50


def _average(values: list[Optional[float]]) -> Optional[float]:
    available = [float(value) for value in values if value is not None]
    if not available:
        return None
    return _cap01(sum(available) / len(available))


def _price_range_position(
    price: Optional[float],
    support: Optional[float],
    resistance: Optional[float],
) -> Optional[float]:
    if price is None or support is None or resistance is None:
        return None
    width = resistance - support
    if width <= 0:
        return None
    return _cap01((price - support) / width)


def _breakout_ratio(
    price: Optional[float],
    resistance: Optional[float],
) -> Optional[float]:
    if price is None or resistance is None or resistance <= 0:
        return None
    return round(max(0.0, price / resistance), 6)


def _breakout_score(ratio: Optional[float]) -> Optional[float]:
    if ratio is None:
        return None
    return _cap01((ratio - 0.85) / 0.15)


def _volatility_score(atr_percent: Optional[float]) -> Optional[float]:
    if atr_percent is None:
        return None
    normalized = atr_percent / 100.0 if atr_percent > 1.0 else atr_percent
    return _cap01(normalized / 0.05)


def _vote_score(action: str) -> float:
    return {
        "buy": 0.80,
        "hold": 0.50,
        "sell": 0.20,
    }.get(str(action or "").strip().lower(), 0.50)


def _weighted_score(
    values: list[tuple[Optional[float], float]],
) -> Optional[float]:
    available = [
        (float(value), weight)
        for value, weight in values
        if value is not None
    ]
    if not available:
        return None
    total_weight = sum(weight for _, weight in available)
    if total_weight <= 0:
        return None
    return _cap01(
        sum(value * weight for value, weight in available) / total_weight
    )


def _evidence_status(completeness: float) -> str:
    if completeness >= 0.80:
        return "complete"
    if completeness >= 0.45:
        return "partial"
    return "insufficient"


def build_technical_evidence(
    *,
    action: str,
    confidence_score: Any,
    current_price: Any,
    indicators: Mapping[str, Any] | None,
    liquidity_evidence: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build non-binding technical and liquidity evidence for Manager_Agent."""

    indicator_data = _mapping(indicators)
    liquidity_data = _mapping(liquidity_evidence)
    liquidity_metrics = _mapping(liquidity_data.get("metrics"))
    liquidity_provenance = _mapping(liquidity_data.get("provenance"))

    price = _float_or_none(current_price)
    trend = str(indicator_data.get("trend") or "").strip()
    rsi = _float_or_none(indicator_data.get("rsi"))
    macd_line = _float_or_none(indicator_data.get("macd_line"))
    macd_signal = _float_or_none(indicator_data.get("macd_signal"))
    atr = _float_or_none(indicator_data.get("atr"))
    atr_percent = _float_or_none(indicator_data.get("atr_percent"))
    support = _float_or_none(
        indicator_data.get("swing_low")
        if indicator_data.get("swing_low") is not None
        else indicator_data.get("support_level")
    )
    resistance = _float_or_none(
        indicator_data.get("swing_high")
        if indicator_data.get("swing_high") is not None
        else indicator_data.get("resistance_level")
    )
    timeframe = str(indicator_data.get("timeframe") or "").strip() or None
    validation_status = str(
        indicator_data.get("validation_status") or "unavailable"
    )
    walk_forward_passed = indicator_data.get("walk_forward_passed")

    volume_ratio = _float_or_none(liquidity_metrics.get("volume_ratio"))
    average_daily_volume = _float_or_none(
        liquidity_metrics.get("average_daily_volume")
    )
    average_dollar_volume = _float_or_none(
        liquidity_metrics.get("average_dollar_volume")
    )
    bid = _float_or_none(liquidity_metrics.get("bid"))
    ask = _float_or_none(liquidity_metrics.get("ask"))
    spread_bps = _float_or_none(liquidity_metrics.get("spread_bps"))

    trend_score = _trend_score(trend)
    rsi_component = _rsi_score(rsi)
    macd_component = _macd_score(macd_line, macd_signal)
    momentum_score = _weighted_score(
        [(rsi_component, 0.45), (macd_component, 0.55)]
    )
    relative_strength_score = _price_range_position(
        price,
        support,
        resistance,
    )
    breakout_ratio = _breakout_ratio(price, resistance)
    breakout_score = _breakout_score(breakout_ratio)
    volatility_score = _volatility_score(atr_percent)
    technical_vote_score = _vote_score(action)
    indicator_score = _average(
        [trend_score, momentum_score, breakout_score]
    )
    technical_score = _weighted_score(
        [
            (trend_score, 0.30),
            (momentum_score, 0.30),
            (relative_strength_score, 0.15),
            (breakout_score, 0.10),
            (technical_vote_score, 0.15),
        ]
    )

    validation_penalty_applied = walk_forward_passed is False
    if validation_penalty_applied and technical_score is not None:
        technical_score = _cap01(technical_score * 0.70)

    raw_confidence = _float_or_none(
        indicator_data.get("raw_confidence_score")
    )
    capped_confidence = _float_or_none(confidence_score)

    raw_scores: Dict[str, Any] = {}
    score_values = {
        "technical_score": technical_score,
        "trend_score": trend_score,
        "momentum_score": momentum_score,
        "relative_strength_score": relative_strength_score,
        "indicator_score": indicator_score,
        "technical_vote_score": technical_vote_score,
        "volatility_score": volatility_score,
        "breakout_ratio": breakout_ratio,
        "volume_ratio": volume_ratio,
    }
    for key, value in score_values.items():
        if value is not None:
            raw_scores[key] = value

    metrics = {
        "trend": trend or None,
        "rsi": _round_optional(rsi),
        "macd_line": _round_optional(macd_line),
        "macd_signal": _round_optional(macd_signal),
        "atr": _round_optional(atr),
        "atr_percent": _round_optional(atr_percent),
        "current_price": _round_optional(price),
        "support_level": _round_optional(support),
        "resistance_level": _round_optional(resistance),
        "breakout_ratio": breakout_ratio,
        "volume_ratio": _round_optional(volume_ratio),
        "average_daily_volume": _round_optional(average_daily_volume),
        "average_dollar_volume": _round_optional(average_dollar_volume),
        "bid": _round_optional(bid),
        "ask": _round_optional(ask),
        "spread_bps": _round_optional(spread_bps),
        "timeframe": timeframe,
        "volatility_regime": indicator_data.get("volatility_regime"),
        "stop_loss": _round_optional(indicator_data.get("stop_loss")),
        "stop_method": indicator_data.get("stop_method"),
    }
    metrics = {
        key: value for key, value in metrics.items() if value is not None
    }

    expected_fields = {
        "technical_score",
        "trend_score",
        "momentum_score",
        "relative_strength_score",
        "indicator_score",
        "technical_vote_score",
        "volatility_score",
        "breakout_ratio",
        "volume_ratio",
        "current_price",
        "support_level",
        "resistance_level",
        "timeframe",
    }
    available_fields = sorted(
        {
            *raw_scores.keys(),
            *(key for key in metrics if key in expected_fields),
        }
    )
    missing_fields = sorted(expected_fields - set(available_fields))
    completeness = round(
        len(available_fields) / max(1, len(expected_fields)),
        4,
    )
    status = _evidence_status(completeness)

    reasons = [
        f"evidence_status:{status}",
        f"available_fields:{len(available_fields)}",
        f"trend:{trend.lower() if trend else 'unavailable'}",
        f"validation_status:{validation_status}",
    ]
    if volume_ratio is not None:
        reasons.append(f"volume_ratio:{round(volume_ratio, 6)}")
    else:
        reasons.append("volume_ratio_unavailable")
    if average_dollar_volume is not None:
        reasons.append("average_dollar_volume_available")
    else:
        reasons.append("average_dollar_volume_unavailable")
    if spread_bps is not None:
        reasons.append("bid_ask_spread_available")
    else:
        reasons.append("bid_ask_spread_unavailable")
    if relative_strength_score is not None:
        reasons.append("relative_strength_method:local_swing_range_proxy")
    else:
        reasons.append("relative_strength_unavailable")
    if validation_penalty_applied:
        reasons.append("walk_forward_failed_confidence_penalty_applied")
    elif walk_forward_passed is True:
        reasons.append("walk_forward_passed")
    else:
        reasons.append("walk_forward_validation_pending")

    provenance = {
        "evidence_source": "technical_agent_indicators",
        "timeframe": timeframe,
        "relative_strength_method": (
            "local_swing_range_proxy"
            if relative_strength_score is not None
            else "unavailable"
        ),
        "volume_ratio_source": (
            "liquidity_evidence"
            if volume_ratio is not None
            else "unavailable"
        ),
        "liquidity_evidence_version": liquidity_data.get(
            "evidence_version"
        ),
        "liquidity_evidence_status": liquidity_data.get(
            "evidence_status"
        ),
        "liquidity_historical_source": liquidity_provenance.get(
            "historical_source"
        ),
        "liquidity_quote_source": liquidity_provenance.get("quote_source"),
        "validation_status": validation_status,
        "walk_forward_passed": walk_forward_passed,
        "validation_penalty_applied": validation_penalty_applied,
        "confidence_cap": indicator_data.get("confidence_cap"),
        "raw_confidence_score": raw_confidence,
        "capped_confidence_score": capped_confidence,
    }

    return {
        "evidence_version": TECHNICAL_EVIDENCE_VERSION,
        "evidence_status": status,
        "evidence_completeness_score": completeness,
        "raw_scores": raw_scores,
        "metrics": metrics,
        "available_fields": available_fields,
        "missing_fields": missing_fields,
        "evidence_reasons": reasons,
        "provenance": provenance,
        "strategy_bucket_hint": None,
        "bucket_decision_authority": BUCKET_DECISION_AUTHORITY,
        "manager_decision_required": True,
    }
