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
    # Hypothesis only: trend + MACD can agree while the established
    # oversold-RSI BUY gate legitimately blocks execution. Never convert
    # this observation into an order signal or modify the BUY thresholds.
    trend_momentum_observation = bool(
        valid and buy[0]["passed"] and buy[2]["passed"] and not buy[1]["passed"]
    )
    # Independent research hypotheses. These are intentionally non-binding:
    # they cannot change action, confidence, or the production BUY predicates.
    trend_following = bool(
        valid and price > sma and 50 <= rsi <= 70 and macd > signal
    )
    mean_reversion = bool(
        valid and price < sma and rsi < 30 and macd > signal
    )
    research_strategies = {
        "trend_following": {
            "candidate": trend_following,
            "predicates": {
                "price_above_sma200": bool(valid and price > sma),
                "rsi_between_50_and_70": bool(valid and 50 <= rsi <= 70),
                "macd_bullish": bool(valid and macd > signal),
            },
        },
        "mean_reversion": {
            "candidate": mean_reversion,
            "predicates": {
                "price_below_sma200": bool(valid and price < sma),
                "rsi_oversold": bool(valid and rsi < 30),
                "macd_recovery": bool(valid and macd > signal),
            },
        },
    }
    research_observation = {
        "schema_version": "technical-research-observation.v1",
        "observation_only": True,
        "research_strategies": research_strategies,
        "execution_authorized": False,
        "strategy_promoted": False,
        "trend_momentum_without_oversold_rsi": trend_momentum_observation,
        "hypothesis": "evaluate_trend_momentum_nested_oos"
        if trend_momentum_observation else None,
        "failed_buy_predicates": [
            item["reason_code"] for item in buy if not item["passed"]
        ] if valid else ["TECHNICAL_INPUT_INVALID"],
    }
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
        "research_observation": research_observation,
    }
