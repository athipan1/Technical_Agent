import os
import sys
from unittest.mock import patch

import pandas as pd

# Add the app directory to sys.path to import service.
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../app"))
)

from service import analyze_stock, calculate_indicators, generate_signal  # noqa: E402


def _ohlcv_frame(rows=250):
    close = [float(100 + index) for index in range(rows)]
    return pd.DataFrame(
        {
            "Open": [value - 0.5 for value in close],
            "High": [value + 1.0 for value in close],
            "Low": [value - 1.0 for value in close],
            "Close": close,
            "Volume": [1_000_000 + index for index in range(rows)],
        }
    )


def test_calculate_indicators():
    result = calculate_indicators(_ohlcv_frame())

    assert "SMA_200" in result.columns
    assert "RSI_14" in result.columns
    assert "MACD_12_26_9" in result.columns
    assert "ATR_14" in result.columns
    assert not pd.isna(result["SMA_200"].iloc[-1])
    assert not pd.isna(result["RSI_14"].iloc[-1])
    assert not pd.isna(result["MACD_12_26_9"].iloc[-1])
    assert not pd.isna(result["ATR_14"].iloc[-1])


def test_generate_signal_buy():
    latest_data = pd.Series(
        {
            "Close": 110.0,
            "SMA_200": 100.0,
            "RSI_14": 25.0,
            "MACD_12_26_9": 5.0,
            "MACDs_12_26_9": 2.0,
        }
    )
    action, confidence, trend = generate_signal(latest_data)
    assert action == "buy"
    assert trend == "Uptrend"
    assert confidence == 0.75


def test_generate_signal_sell():
    latest_data = pd.Series(
        {
            "Close": 90.0,
            "SMA_200": 100.0,
            "RSI_14": 75.0,
            "MACD_12_26_9": -5.0,
            "MACDs_12_26_9": -2.0,
        }
    )
    action, confidence, trend = generate_signal(latest_data)
    assert action == "sell"
    assert trend == "Downtrend"
    assert confidence == 0.75


def test_generate_signal_hold():
    latest_data = pd.Series(
        {
            "Close": 105.0,
            "SMA_200": 100.0,
            "RSI_14": 50.0,
            "MACD_12_26_9": 1.0,
            "MACDs_12_26_9": 2.0,
        }
    )
    action, confidence, trend = generate_signal(latest_data)
    assert action == "hold"
    assert trend == "Uptrend"
    assert confidence == 0.5


@patch("service.get_stock_data")
def test_analyze_stock_success(mock_get_data):
    mock_get_data.return_value = _ohlcv_frame()

    result = analyze_stock("AAPL")

    assert result["status"] == "success"
    assert result["data"]["confidence_score"] == 0.5
    assert "indicators" in result["data"]
    assert result["data"]["indicators"]["swing_low"] is not None
    assert result["data"]["indicators"]["swing_high"] is not None
