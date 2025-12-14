
import sys
import json
import warnings
import pandas as pd
import yfinance as yf
import pandas_ta as ta  # noqa: F401

# Suppress specific warnings for cleaner output
warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="yfinance")


class TickerNotFound(Exception):
    """Custom exception for when a ticker is not found or has no data."""
    pass


class AnalysisError(Exception):
    """Custom exception for errors during the analysis process."""
    pass


def get_stock_data(ticker: str) -> pd.DataFrame:
    """
    Fetches 5 years of historical stock data.

    Args:
        ticker (str): The stock ticker symbol.

    Returns:
        pd.DataFrame: A DataFrame with historical stock data.

    Raises:
        TickerNotFound: If the ticker is not found or has no data.
    """
    stock_ticker = ticker.upper()
    data = yf.download(stock_ticker, period="5y", progress=False)

    if data.empty:
        raise TickerNotFound(f"No data found for ticker '{stock_ticker}'. "
                             "It might be delisted or incorrect.")

    # If yfinance returns a MultiIndex, flatten it
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.droplevel(1)

    return data


def calculate_indicators(data: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates technical indicators (SMA, RSI, MACD) and appends them.

    Args:
        data (pd.DataFrame): The input DataFrame with stock data.

    Returns:
        pd.DataFrame: The DataFrame with appended indicator columns.
    """
    data.ta.sma(length=200, append=True)
    data.ta.rsi(length=14, append=True)
    data.ta.macd(append=True)
    return data


def check_data_quality(data: pd.DataFrame, ticker: str):
    """
    Checks if the latest data has all required indicators for analysis.

    Args:
        data (pd.DataFrame): The DataFrame with indicators.
        ticker (str): The stock ticker for error messaging.

    Raises:
        AnalysisError: If data is missing or NaN for required indicators.
    """
    latest_data = data.iloc[-1]
    required_columns = ['Close', 'SMA_200', 'RSI_14',
                        'MACD_12_26_9', 'MACDs_12_26_9']
    for col in required_columns:
        if col not in latest_data or pd.isna(latest_data[col]):
            raise AnalysisError(
                f"Not enough data to calculate technical indicators for "
                f"'{ticker}'. Missing or NaN value for {col}."
            )


def generate_signal(latest_data: pd.Series) -> tuple[str, float, str]:
    """
    Generates a trading signal based on technical indicators.

    Args:
        latest_data (pd.Series): The latest row of data with indicators.

    Returns:
        tuple[str, float, str]: A tuple containing the action
                                ('buy', 'sell', 'hold'), the confidence
                                score, and the trend.
    """
    price = latest_data['Close']
    sma200 = latest_data['SMA_200']
    rsi = latest_data['RSI_14']
    macd_line = latest_data['MACD_12_26_9']
    macd_signal = latest_data['MACDs_12_26_9']

    # 1. Determine Trend
    if price > sma200:
        trend = "Uptrend"
    elif price < sma200:
        trend = "Downtrend"
    else:
        trend = "Sideways"

    # 2. Generate Signal based on Trend
    action = "hold"
    confidence = 0.5  # Default confidence

    if trend == "Uptrend":
        if rsi < 30 and macd_line > macd_signal:
            action = "buy"
            confidence = 0.85
        elif rsi > 70:
            confidence = 0.6
    elif trend == "Downtrend":
        if rsi > 70 and macd_line < macd_signal:
            action = "sell"
            confidence = 0.85
        else:
            confidence = 0.6

    return action, confidence, trend


def analyze_stock(ticker: str) -> dict:
    """
    Analyzes a stock's technical indicators to generate a trading signal.

    Args:
        ticker (str): The stock ticker symbol.

    Returns:
        dict: A dictionary containing the analysis results.
    """
    data = get_stock_data(ticker)
    data_with_indicators = calculate_indicators(data)
    check_data_quality(data_with_indicators, ticker)

    latest_data = data_with_indicators.iloc[-1]
    action, confidence, trend = generate_signal(latest_data)

    # Format the final output
    return {
        "current_price": round(latest_data['Close'], 2),
        "action": action,
        "confidence_score": confidence,
        "indicators": {
            "trend": trend,
            "rsi": round(latest_data['RSI_14'], 2),
            "macd_line": round(latest_data['MACD_12_26_9'], 2),
            "macd_signal": round(latest_data['MACDs_12_26_9'], 2),
        }
    }


def main():
    """Handles the command-line interface execution."""
    if len(sys.argv) < 2:
        print(json.dumps({
            "error": "Please provide a stock ticker."
        }), file=sys.stderr)
        sys.exit(1)

    ticker_arg = sys.argv[1]
    try:
        # For CLI, flatten the structure for CI validation
        analysis_result = analyze_stock(ticker_arg)
        cli_output = {
            "trend": analysis_result["indicators"]["trend"],
            "rsi": analysis_result["indicators"]["rsi"],
            "macd_line": analysis_result["indicators"]["macd_line"],
            "macd_signal": analysis_result["indicators"]["macd_signal"],
            "signal": analysis_result["action"].upper(),
            "reasoning": "CLI output does not generate reasoning."
        }
        print(json.dumps(cli_output, indent=4))
    except (TickerNotFound, AnalysisError) as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(json.dumps({
            "error": f"An unexpected error occurred: {e}"
        }), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
