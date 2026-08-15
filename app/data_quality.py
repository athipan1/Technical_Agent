from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import pandas as pd


MIN_REQUIRED_BARS = 200
SUPPORTED_TIMEFRAMES = {"1d", "1h", "30m", "15m"}
FRESHNESS_LIMITS = {
    "1d": timedelta(days=5),
    "1h": timedelta(days=3),
    "30m": timedelta(days=3),
    "15m": timedelta(days=3),
}

CRITICAL_PRICE_FIELDS = ("High", "Low", "Close")
SUPPLEMENTAL_PRICE_FIELDS = ("Open", "Volume")
CRITICAL_INDICATOR_FIELDS = (
    "SMA_200",
    "RSI_14",
    "MACD_12_26_9",
    "MACDs_12_26_9",
    "ATR_14",
)


def _is_finite(value: Any) -> bool:
    try:
        return value is not None and math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _observed_at(index: pd.Index) -> Optional[datetime]:
    if len(index) == 0:
        return None
    try:
        timestamp = pd.Timestamp(index[-1])
    except Exception:
        return None
    if pd.isna(timestamp):
        return None
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize(timezone.utc)
    else:
        timestamp = timestamp.tz_convert(timezone.utc)
    return timestamp.to_pydatetime()


def assess_data_quality(
    data: pd.DataFrame,
    *,
    timeframe: str,
    now: Optional[datetime] = None,
    minimum_bars: int = MIN_REQUIRED_BARS,
) -> Dict[str, Any]:
    """Assess whether OHLCV and derived indicators are safe to trade on.

    Critical price or indicator gaps, stale observations, and insufficient
    history fail closed. Missing supplemental Open/Volume data is reported as
    partial so Manager_Agent can decide whether the evidence remains usable.
    """

    normalized_timeframe = str(timeframe or "").strip().lower()
    if normalized_timeframe not in SUPPORTED_TIMEFRAMES:
        return {
            "status": "insufficient",
            "completeness_score": 0.0,
            "timeframe": normalized_timeframe or None,
            "bars_available": 0,
            "minimum_bars_required": minimum_bars,
            "latest_observed_at": None,
            "fresh": False,
            "freshness_max_age_seconds": None,
            "missing_fields": [],
            "reasons": ["unsupported_timeframe"],
        }

    frame = data if isinstance(data, pd.DataFrame) else pd.DataFrame()
    bars_available = int(len(frame))
    missing_fields: list[str] = []
    reasons: list[str] = []
    critical_failure = frame.empty
    partial_failure = False

    if frame.empty:
        reasons.append("ohlcv_unavailable")

    if bars_available < minimum_bars:
        critical_failure = True
        reasons.append(
            f"bars_below_minimum:{bars_available}/{minimum_bars}"
        )

    latest = frame.iloc[-1] if not frame.empty else pd.Series(dtype="float64")

    for field in CRITICAL_PRICE_FIELDS:
        if field not in frame.columns:
            missing_fields.append(field)
            reasons.append(f"missing_critical_price_field:{field}")
            critical_failure = True
        elif not _is_finite(latest.get(field)):
            missing_fields.append(field)
            reasons.append(f"invalid_latest_price_field:{field}")
            critical_failure = True

    for field in SUPPLEMENTAL_PRICE_FIELDS:
        if field not in frame.columns:
            missing_fields.append(field)
            reasons.append(f"missing_supplemental_price_field:{field}")
            partial_failure = True
        elif not _is_finite(latest.get(field)):
            missing_fields.append(field)
            reasons.append(f"invalid_latest_supplemental_field:{field}")
            partial_failure = True

    for field in CRITICAL_INDICATOR_FIELDS:
        if field not in frame.columns:
            missing_fields.append(field)
            reasons.append(f"missing_critical_indicator:{field}")
            critical_failure = True
        elif not _is_finite(latest.get(field)):
            missing_fields.append(field)
            reasons.append(f"invalid_latest_indicator:{field}")
            critical_failure = True

    observed_at = _observed_at(frame.index)
    freshness_limit = FRESHNESS_LIMITS[normalized_timeframe]
    freshness_max_age_seconds = int(freshness_limit.total_seconds())
    fresh: Optional[bool]

    if observed_at is None:
        fresh = None
        partial_failure = True
        reasons.append("observation_timestamp_unavailable")
    else:
        reference_now = now or datetime.now(timezone.utc)
        if reference_now.tzinfo is None:
            reference_now = reference_now.replace(tzinfo=timezone.utc)
        else:
            reference_now = reference_now.astimezone(timezone.utc)
        age = reference_now - observed_at
        if age.total_seconds() < -3600:
            fresh = False
            critical_failure = True
            reasons.append("observation_timestamp_in_future")
        else:
            fresh = age <= freshness_limit
            if not fresh:
                critical_failure = True
                reasons.append(
                    f"stale_market_data:{int(max(0, age.total_seconds()))}s"
                )

    expected_fields = {
        *CRITICAL_PRICE_FIELDS,
        *SUPPLEMENTAL_PRICE_FIELDS,
        *CRITICAL_INDICATOR_FIELDS,
        "minimum_history",
        "freshness",
    }
    available_fields = {
        field
        for field in (
            *CRITICAL_PRICE_FIELDS,
            *SUPPLEMENTAL_PRICE_FIELDS,
            *CRITICAL_INDICATOR_FIELDS,
        )
        if field not in missing_fields
    }
    if bars_available >= minimum_bars:
        available_fields.add("minimum_history")
    if fresh is True:
        available_fields.add("freshness")

    completeness_score = round(
        len(available_fields) / max(1, len(expected_fields)),
        4,
    )

    if critical_failure:
        status = "insufficient"
    elif partial_failure:
        status = "partial"
    else:
        status = "complete"

    if not reasons:
        reasons.append("technical_data_quality_complete")

    return {
        "status": status,
        "completeness_score": completeness_score,
        "timeframe": normalized_timeframe,
        "bars_available": bars_available,
        "minimum_bars_required": minimum_bars,
        "latest_observed_at": observed_at,
        "fresh": fresh,
        "freshness_max_age_seconds": freshness_max_age_seconds,
        "missing_fields": sorted(set(missing_fields)),
        "reasons": reasons,
    }
