import pytest

from app.signal_decision import evaluate_signal
from app.models import StandardAgentData


def candle(**changes):
    return {
        "Close": 105,
        "SMA_200": 100,
        "RSI_14": 29.0,
        "MACD_12_26_9": 0.12,
        "MACDs_12_26_9": 0.11,
        **changes,
    }


def test_buy_requires_all_observed_predicates_and_survives_response_schema():
    trace = evaluate_signal(candle())
    assert trace["action"] == "buy"
    assert all(condition["passed"] for condition in trace["buy_conditions"])
    body = StandardAgentData(
        action="buy", confidence_score=0.75, reason="tested predicates", decision_trace=trace
    )
    assert body.model_dump(mode="json")["decision_trace"]["buy_passed"] is True


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"RSI_14": 30}, "TECHNICAL_RSI_NOT_OVERSOLD"),
        ({"Close": 100}, "TECHNICAL_PRICE_NOT_ABOVE_SMA200"),
        ({"MACD_12_26_9": 0.11}, "TECHNICAL_MACD_NOT_BULLISH"),
        ({"Close": float("nan")}, "TECHNICAL_INPUT_INVALID"),
    ],
)
def test_each_failed_predicate_retains_hold(changes, code):
    trace = evaluate_signal(candle(**changes))
    assert trace["action"] == "hold"
    assert code in trace["reason_codes"]


def test_qttb_snapshot_is_not_buy_despite_oversold_rsi():
    trace = evaluate_signal(candle(RSI_14=29.11, MACD_12_26_9=-0.48, MACDs_12_26_9=-0.01))
    assert trace["action"] == "hold"
    assert trace["reason_codes"] == ["TECHNICAL_MACD_NOT_BULLISH"]


def test_trend_and_macd_agreement_without_oversold_rsi_is_research_only():
    row = candle(RSI_14=66.28, MACD_12_26_9=0.35, MACDs_12_26_9=0.11)
    trace = evaluate_signal(row)
    assert trace["action"] == "hold"
    assert trace["buy_passed"] is False
    hypothesis = trace["research_observation"]
    assert hypothesis["trend_momentum_without_oversold_rsi"] is True
    assert hypothesis["hypothesis"] == "evaluate_trend_momentum_nested_oos"
    assert hypothesis["failed_buy_predicates"] == ["TECHNICAL_RSI_NOT_OVERSOLD"]
    assert hypothesis["observation_only"] is True
    assert hypothesis["execution_authorized"] is False
    assert hypothesis["strategy_promoted"] is False


def test_invalid_inputs_cannot_create_trend_momentum_observation():
    trace = evaluate_signal(candle(Close=float("nan"), RSI_14=66))
    assert trace["action"] == "hold"
    assert trace["research_observation"]["trend_momentum_without_oversold_rsi"] is False
    assert trace["research_observation"]["failed_buy_predicates"] == [
        "TECHNICAL_INPUT_INVALID"
    ]
