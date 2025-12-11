
import yfinance as yf
import pandas as pd
import pandas_ta as ta  # noqa: F401
import sys
import json
import warnings

warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="yfinance")


class TickerNotFound(Exception):
    """Custom exception for when a ticker is not found or has no data."""
    pass


class AnalysisError(Exception):
    """Custom exception for errors during the analysis process."""
    pass


def analyze_stock(ticker):
    """
    Analyzes a stock's technical indicators to generate a trading signal.

    Args:
        ticker (str): The stock ticker symbol.

    Returns:
        dict: A dictionary containing the analysis results.

    Raises:
        TickerNotFound: If the ticker is not found or has no data.
        AnalysisError: If there's not enough data for analysis.
    """
    stock_ticker = ticker.upper()

    # Fetch 5 years of historical data
    data = yf.download(stock_ticker, period="5y", progress=False)

    # If yfinance returns a MultiIndex, flatten it
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.droplevel(1)

    if data.empty:
        raise TickerNotFound(f"No data found for ticker '{stock_ticker}'. "
                             "It might be delisted or incorrect.")

    # Calculate Technical Indicators
    data.ta.sma(length=200, append=True)
    data.ta.rsi(length=14, append=True)
    data.ta.macd(append=True)

    # Get the latest data
    latest_data = data.iloc[-1]

    # --- Pre-analysis Check ---
    required_columns = ['Close', 'SMA_200', 'RSI_14',
                        'MACD_12_26_9', 'MACDs_12_26_9']
    for col in required_columns:
        if col not in latest_data or pd.isna(latest_data[col]):
            raise AnalysisError(
                f"Not enough data to calculate technical indicators for "
                f"'{stock_ticker}'. Missing or NaN value for {col}."
            )

    # --- Analysis Logic ---

    # 1. Trend Analysis
    price = latest_data['Close']
    sma200 = latest_data['SMA_200']

    if price > sma200:
        trend = "Uptrend"
    elif price < sma200:
        trend = "Downtrend"
    else:
        trend = "Sideways"

    # 2. Momentum Analysis
    rsi = latest_data['RSI_14']
    macd_line = latest_data['MACD_12_26_9']
    macd_signal = latest_data['MACDs_12_26_9']

    # 3. Signal Generation
    signal = "WAIT"
    reasoning = ""
    confidence_score = 0.5  # Default score

    if trend == "Uptrend":
        if rsi < 30 and macd_line > macd_signal:
            signal = "BUY"
            confidence_score = 0.8
            reasoning = (
                "The stock is in a clear uptrend and is currently "
                "oversold (RSI < 30). The MACD crossover provides "
                "additional confirmation, indicating a strong buying "
                "opportunity."
            )
        elif rsi > 70:
            signal = "WAIT"
            confidence_score = 0.6
            reasoning = (
                "The stock is in an uptrend but is currently "
                "overbought (RSI > 70). It's better to wait for a "
                "price correction before buying."
            )
        else:
            signal = "WAIT"
            reasoning = (
                "The stock is in an uptrend, but momentum is neutral. "
                "Wait for a clearer signal from RSI or MACD."
            )

    elif trend == "Downtrend":
        if rsi > 70 and macd_line < macd_signal:
            signal = "SELL"
            confidence_score = 0.8
            reasoning = (
                "The stock is in a clear downtrend and is currently "
                "overbought (RSI > 70). The MACD crossover provides "
                "additional confirmation, presenting a potential selling "
                "or shorting opportunity."
            )
        else:
            signal = "WAIT"
            reasoning = (
                "The stock is in a downtrend. It is not advisable to "
                "buy. Wait for a trend reversal confirmed by indicators."
            )

    else:  # Sideways
        reasoning = (
            "The stock is in a sideways trend. No clear entry or exit "
            "signal."
        )

    # Map signal to the action required by the orchestrator
    action_map = {"BUY": "buy", "SELL": "sell", "WAIT": "hold"}
    final_action = action_map[signal]

    # --- Output ---
    return {
        "current_price": round(price, 2),
        "action": final_action,
        "confidence_score": confidence_score,
        "reason": reasoning,  # Renamed from 'reasoning'
        "indicators": {
            "trend": trend,
            "rsi": round(rsi, 2),
            "macd_line": round(macd_line, 2),
            "macd_signal": round(macd_signal, 2),
        }
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({
            "error": "Please provide a stock ticker."
        }), file=sys.stderr)
        sys.exit(1)

    ticker_arg = sys.argv[1]
    try:
        analysis_result = analyze_stock(ticker_arg)
        print(json.dumps(analysis_result, indent=4))
    except TickerNotFound as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)
    except AnalysisError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(json.dumps({
            "error": f"An unexpected error occurred: {e}"
        }), file=sys.stderr)
        sys.exit(1)
