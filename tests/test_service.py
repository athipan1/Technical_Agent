import pandas as pd
import pytest
import sys
import os

# Add the app directory to sys.path to import service
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../app')))

from service import calculate_indicators, generate_signal

def test_calculate_indicators():
    # Create mock data (need enough points for indicators)
    # SMA 200 needs 200 points
    # MACD needs some points
    data = pd.DataFrame({
        'Close': [float(100 + i) for i in range(250)]
    })
    # Ensure it's a Series if it was just one column, but ta expects DataFrame
    result = calculate_indicators(data)

    assert 'SMA_200' in result.columns
    assert 'RSI_14' in result.columns
    assert 'MACD_12_26_9' in result.columns

    # Check if last values are calculated (not NaN)
    assert not pd.isna(result['SMA_200'].iloc[-1])
    assert not pd.isna(result['RSI_14'].iloc[-1])
    assert not pd.isna(result['MACD_12_26_9'].iloc[-1])

def test_generate_signal_buy():
    latest_data = pd.Series({
        'Close': 110.0,
        'SMA_200': 100.0,
        'RSI_14': 25.0,
        'MACD_12_26_9': 5.0,
        'MACDs_12_26_9': 2.0
    })
    action, confidence, trend = generate_signal(latest_data)
    assert action == 'buy'
    assert trend == 'Uptrend'
    assert confidence == 0.75

def test_generate_signal_sell():
    latest_data = pd.Series({
        'Close': 90.0,
        'SMA_200': 100.0,
        'RSI_14': 75.0,
        'MACD_12_26_9': -5.0,
        'MACDs_12_26_9': -2.0
    })
    action, confidence, trend = generate_signal(latest_data)
    assert action == 'sell'
    assert trend == 'Downtrend'
    assert confidence == 0.75

def test_generate_signal_hold():
    latest_data = pd.Series({
        'Close': 105.0,
        'SMA_200': 100.0,
        'RSI_14': 50.0,
        'MACD_12_26_9': 1.0,
        'MACDs_12_26_9': 2.0
    })
    action, confidence, trend = generate_signal(latest_data)
    assert action == 'hold'
    assert trend == 'Uptrend'
    assert confidence == 0.5
