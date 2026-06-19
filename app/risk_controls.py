import logging
from typing import Any, Dict

import pandas as pd


ATR_LENGTH = 14
SWING_LOOKBACK = 20
ATR_MULTIPLIER = 2.0


def calculate_atr(data: pd.DataFrame, length: int = ATR_LENGTH) -> pd.Series:
    high_low = data["High"] - data["Low"]
    high_close = (data["High"] - data["Close"].shift(1)).abs()
    low_close = (data["Low"] - data["Close"].shift(1)).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(window=length, min_periods=1).mean()


def classify_volatility_regime(atr_percent: float) -> str:
    if atr_percent < 1.5:
        return "low"
    if atr_percent < 3.0:
        return "normal"
    if atr_percent < 6.0:
        return "high"
    return "extreme"


def calculate_swing_levels(data: pd.DataFrame, lookback: int = SWING_LOOKBACK) -> Dict[str, float]:
    window = data.tail(max(2, lookback))
    return {
        "swing_low": float(window["Low"].min()),
        "swing_high": float(window["High"].max()),
    }


def calculate_stop_levels(data: pd.DataFrame, action: str, atr_multiplier: float = ATR_MULTIPLIER) -> Dict[str, Any]:
    latest = data.iloc[-1]
    close = float(latest["Close"])
    atr = float(latest.get("ATR_14", 0.0) or 0.0)
    atr_percent = 0.0 if close == 0 else (atr / close) * 100
    swings = calculate_swing_levels(data)

    atr_stop_long = close - (atr * atr_multiplier)
    atr_stop_short = close + (atr * atr_multiplier)
    swing_low = swings["swing_low"]
    swing_high = swings["swing_high"]

    if action == "sell":
        candidates = [value for value in [atr_stop_short, swing_high] if value > close]
        stop_loss = min(candidates) if candidates else atr_stop_short
        stop_method = "short_atr_swing_high"
    else:
        candidates = [value for value in [atr_stop_long, swing_low] if value < close]
        stop_loss = max(candidates) if candidates else atr_stop_long
        stop_method = "long_atr_swing_low"

    if stop_loss <= 0:
        logging.warning("Calculated non-positive stop level; falling back to ATR stop.")
        stop_loss = atr_stop_long if action != "sell" else atr_stop_short

    return {
        "atr": round(atr, 4),
        "atr_percent": round(atr_percent, 4),
        "atr_stop_long": round(atr_stop_long, 4),
        "atr_stop_short": round(atr_stop_short, 4),
        "swing_low": round(swing_low, 4),
        "swing_high": round(swing_high, 4),
        "stop_loss": round(float(stop_loss), 4),
        "stop_method": stop_method,
        "volatility_regime": classify_volatility_regime(atr_percent),
    }
