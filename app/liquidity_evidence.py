from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional

import pandas as pd


LIQUIDITY_EVIDENCE_VERSION = "liquidity-evidence-v1"
DEFAULT_LOOKBACK_BARS = 20


def _finite_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _positive_float(value: Any) -> Optional[float]:
    number = _finite_float(value)
    return number if number is not None and number > 0 else None


def _iso_timestamp(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        timestamp = pd.Timestamp(value)
    except Exception:
        return None
    if pd.isna(timestamp):
        return None
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize(timezone.utc)
    else:
        timestamp = timestamp.tz_convert(timezone.utc)
    return timestamp.isoformat()


def _normalized_quote(quote: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    return dict(quote) if isinstance(quote, Mapping) else {}


def _spread_bps(bid: Optional[float], ask: Optional[float]) -> Optional[float]:
    if bid is None or ask is None or bid <= 0 or ask <= 0 or ask < bid:
        return None
    midpoint = (bid + ask) / 2.0
    if midpoint <= 0:
        return None
    return round(((ask - bid) / midpoint) * 10_000.0, 4)


def _liquidity_window(
    valid: pd.DataFrame,
    *,
    timeframe: str,
    lookback: int,
) -> tuple[pd.DataFrame, str]:
    """Return daily observations, aggregating intraday bars when possible."""

    if valid.empty:
        return valid, "unavailable"

    normalized_timeframe = str(timeframe or "1d").strip().lower()
    prepared = valid.copy()
    prepared["dollar_volume"] = prepared["close"] * prepared["volume"]

    if normalized_timeframe == "1d":
        return prepared.tail(lookback), "daily_bars"

    if isinstance(prepared.index, pd.DatetimeIndex):
        session_dates = pd.to_datetime(prepared.index, utc=True).date
        prepared["session_date"] = session_dates
        daily = prepared.groupby("session_date", sort=True).agg(
            close=("close", "last"),
            volume=("volume", "sum"),
            dollar_volume=("dollar_volume", "sum"),
        )
        return daily.tail(lookback), "intraday_bars_aggregated_by_utc_date"

    return prepared.tail(lookback), "per_bar_fallback_no_datetime_index"


def build_liquidity_evidence(
    data: pd.DataFrame,
    *,
    timeframe: str,
    quote: Optional[Mapping[str, Any]] = None,
    lookback_bars: int = DEFAULT_LOOKBACK_BARS,
    source: str = "historical_ohlcv",
) -> Dict[str, Any]:
    """Build non-binding liquidity evidence without inventing missing quotes.

    Historical OHLCV provides average daily volume and average daily dollar
    volume. Intraday bars are aggregated by UTC session date before averaging.
    Bid/ask spread is included only when a caller supplies a valid quote.
    """

    frame = data.copy() if isinstance(data, pd.DataFrame) else pd.DataFrame()
    requested_lookback = max(1, int(lookback_bars or DEFAULT_LOOKBACK_BARS))
    available_fields: list[str] = []
    missing_fields: list[str] = []
    reasons: list[str] = []

    close = pd.Series(dtype="float64")
    volume = pd.Series(dtype="float64")
    if not frame.empty and "Close" in frame.columns:
        close = pd.to_numeric(frame["Close"], errors="coerce")
    if not frame.empty and "Volume" in frame.columns:
        volume = pd.to_numeric(frame["Volume"], errors="coerce")

    valid = pd.DataFrame({"close": close, "volume": volume}).replace(
        [float("inf"), float("-inf")],
        float("nan"),
    )
    if not valid.empty:
        valid = valid.dropna(subset=["close", "volume"])
        valid = valid[(valid["close"] > 0) & (valid["volume"] >= 0)]

    current_price = (
        _positive_float(valid["close"].iloc[-1]) if not valid.empty else None
    )
    window, aggregation_mode = _liquidity_window(
        valid,
        timeframe=timeframe,
        lookback=requested_lookback,
    )

    latest_volume = None
    average_price = None
    average_daily_volume = None
    average_dollar_volume = None
    volume_ratio = None

    if not window.empty:
        latest_volume = _finite_float(window["volume"].iloc[-1])
        average_price = _positive_float(window["close"].mean())
        average_daily_volume = _finite_float(window["volume"].mean())
        average_dollar_volume = _finite_float(
            window["dollar_volume"].mean()
        )
        if (
            latest_volume is not None
            and average_daily_volume is not None
            and average_daily_volume > 0
        ):
            volume_ratio = _finite_float(latest_volume / average_daily_volume)

    quote_data = _normalized_quote(quote)
    bid = _positive_float(
        quote_data.get("bid")
        if quote_data.get("bid") is not None
        else quote_data.get("bid_price")
    )
    ask = _positive_float(
        quote_data.get("ask")
        if quote_data.get("ask") is not None
        else quote_data.get("ask_price")
    )
    spread_bps = _spread_bps(bid, ask)
    quote_pair_invalid = bid is not None and ask is not None and spread_bps is None
    if quote_pair_invalid:
        bid = None
        ask = None

    metrics = {
        "current_price": current_price,
        "latest_volume": latest_volume,
        "average_price": average_price,
        "average_daily_volume": average_daily_volume,
        "average_dollar_volume": average_dollar_volume,
        "volume_ratio": volume_ratio,
        "bid": bid,
        "ask": ask,
        "spread_bps": spread_bps,
    }
    metrics = {
        key: round(value, 6) if isinstance(value, float) else value
        for key, value in metrics.items()
        if value is not None
    }

    historical_fields = (
        "current_price",
        "average_daily_volume",
        "average_dollar_volume",
        "volume_ratio",
    )
    quote_fields = ("bid", "ask", "spread_bps")
    for field in historical_fields + quote_fields:
        if field in metrics:
            available_fields.append(field)
        else:
            missing_fields.append(field)

    if average_dollar_volume is None:
        reasons.append("average_dollar_volume_unavailable")
    else:
        reasons.append("average_dollar_volume_from_historical_ohlcv")
    if quote_pair_invalid:
        reasons.append("bid_ask_quote_pair_invalid")
    if spread_bps is None:
        reasons.append("bid_ask_spread_unavailable")
    else:
        reasons.append("bid_ask_spread_from_quote_snapshot")

    historical_complete = all(field in metrics for field in historical_fields)
    quote_complete = all(field in metrics for field in quote_fields)
    if historical_complete and quote_complete:
        status = "complete"
    elif historical_complete or metrics:
        status = "partial"
    else:
        status = "unavailable"

    historical_as_of = _iso_timestamp(frame.index[-1]) if not frame.empty else None
    generated_at = datetime.now(timezone.utc).isoformat()
    quote_as_of = _iso_timestamp(
        quote_data.get("as_of")
        or quote_data.get("timestamp")
        or quote_data.get("updated_at")
    )

    provenance = {
        "historical_source": source,
        "quote_source": quote_data.get("source") or "unavailable",
        "calculation_method": "mean(daily_close_times_volume)",
        "aggregation_mode": aggregation_mode,
        "volume_lookback_sessions": requested_lookback,
        "observed_sessions": int(len(window)),
        "timeframe": str(timeframe or "1d"),
        "historical_as_of": historical_as_of,
        "quote_as_of": quote_as_of,
        "generated_at": generated_at,
    }

    completeness = round(
        len(available_fields) / max(1, len(historical_fields + quote_fields)),
        4,
    )
    return {
        "evidence_version": LIQUIDITY_EVIDENCE_VERSION,
        "evidence_status": status,
        "evidence_completeness_score": completeness,
        "metrics": metrics,
        "available_fields": sorted(available_fields),
        "missing_fields": sorted(missing_fields),
        "evidence_reasons": reasons,
        "provenance": provenance,
    }
