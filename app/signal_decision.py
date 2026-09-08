"""One source of truth for technical direction and its predicate trace."""

import math


def _number(value):
    try:
        value = float(value) if not isinstance(value, bool) else None
        return value if value is not None and math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def evaluate_signal(row):
    values = {
        key: _number(row.get(key))
        for key in (
            "Close",
            "SMA_200",
            "RSI_14",
            "MACD_12_26_9",
            "MACDs_12_26_9",
        )
    }
    price, sma, rsi, macd, signal = values.values()
    valid = all(value is not None for value in values.values())
    valid = valid and price > 0 and sma > 0 and 0 <= rsi <= 100
    trend = (
        "Unknown"
        if price is None or sma is None
        else ("Uptrend" if price > sma else "Downtrend" if price < sma else "Sideways")
    )
    buy = [
        {
            "field": "Close",
            "observed": price,
            "operator": ">",
            "threshold": sma,
            "threshold_field": "SMA_200",
            "passed": bool(valid and price > sma),
            "reason_code": "TECHNICAL_PRICE_NOT_ABOVE_SMA200",
        },
        {
            "field": "RSI_14",
            "observed": rsi,
            "operator": "<",
            "threshold": 30,
            "passed": bool(valid and rsi < 30),
            "reason_code": "TECHNICAL_RSI_NOT_OVERSOLD",
        },
        {
            "field": "MACD_12_26_9",
            "observed": macd,
            "operator": ">",
            "threshold": signal,
            "threshold_field": "MACDs_12_26_9",
            "passed": bool(valid and macd > signal),
            "reason_code": "TECHNICAL_MACD_NOT_BULLISH",
        },
    ]
    buy_passed = valid and all(item["passed"] for item in buy)
    sell_passed = valid and price < sma and rsi > 70 and macd < signal
    action = "buy" if buy_passed else "sell" if sell_passed else "hold"
    return {
        "schema_version": "technical-decision-trace.v1",
        "action": action,
        "raw_confidence": 0.75 if action != "hold" else 0.5,
        "trend": trend,
        "input_valid": bool(valid),
        "inputs": values,
        "buy_conditions": buy,
        "buy_passed": bool(buy_passed),
        "sell_passed": bool(sell_passed),
        "sell_thresholds": {"price_below_sma200": True, "rsi_above": 70, "macd_below_signal": True},
        "reason_codes": (
            ["TECHNICAL_INPUT_INVALID"]
            if not valid
            else [item["reason_code"] for item in buy if not item["passed"]]
        ),
        "fallback_used": not bool(valid),
    }
