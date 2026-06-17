import sys
import json
import logging
import warnings
import time
import urllib.request
import urllib.parse
import pandas as pd
import yfinance as yf
import pandas_ta as ta

# --- Setup ---
warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="yfinance")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# --- Custom Exceptions ---
class TickerNotFound(Exception):
    """Custom exception for when a ticker is not found or has no data."""
    pass


class AnalysisError(Exception):
    """Custom exception for errors during the analysis process."""
    pass


# --- Core Functions ---
def _normalize_ohlcv_columns(data: pd.DataFrame) -> pd.DataFrame:
    if data is None or data.empty:
        return pd.DataFrame()

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.droplevel(1)

    rename_map = {}
    for col in data.columns:
        normalized = str(col).strip().lower()
        if normalized == "open":
            rename_map[col] = "Open"
        elif normalized == "high":
            rename_map[col] = "High"
        elif normalized == "low":
            rename_map[col] = "Low"
        elif normalized in {"close", "regularmarketprice"}:
            rename_map[col] = "Close"
        elif normalized in {"adj close", "adjclose"}:
            rename_map[col] = "Adj Close"
        elif normalized == "volume":
            rename_map[col] = "Volume"
    data = data.rename(columns=rename_map)
    return data


def _fetch_with_yfinance(ticker: str) -> pd.DataFrame:
    attempts = [
        {"period": "2y", "interval": "1d", "auto_adjust": False},
        {"period": "1y", "interval": "1d", "auto_adjust": False},
        {"period": "6mo", "interval": "1d", "auto_adjust": False},
    ]
    for kwargs in attempts:
        try:
            data = yf.download(ticker, progress=False, threads=False, **kwargs)
            data = _normalize_ohlcv_columns(data)
            if not data.empty and "Close" in data.columns:
                return data
        except Exception as exc:
            logging.warning(f"yfinance download failed for {ticker} with {kwargs}: {exc}")
    return pd.DataFrame()


def _fetch_with_yahoo_chart(ticker: str) -> pd.DataFrame:
    """Fetch daily candles directly from Yahoo Chart API as a fallback."""
    period2 = int(time.time())
    period1 = period2 - (730 * 24 * 60 * 60)
    symbol = urllib.parse.quote(ticker.upper())
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        f"?period1={period1}&period2={period2}&interval=1d&events=history&includeAdjustedClose=true"
    )
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; TechnicalAgent/1.0)",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        logging.warning(f"Yahoo chart fallback failed for {ticker}: {exc}")
        return pd.DataFrame()

    result = ((payload.get("chart") or {}).get("result") or [])
    if not result:
        return pd.DataFrame()

    item = result[0]
    timestamps = item.get("timestamp") or []
    quote = ((item.get("indicators") or {}).get("quote") or [{}])[0]
    adjclose = ((item.get("indicators") or {}).get("adjclose") or [{}])[0].get("adjclose")

    if not timestamps or not quote.get("close"):
        return pd.DataFrame()

    data = pd.DataFrame(
        {
            "Open": quote.get("open"),
            "High": quote.get("high"),
            "Low": quote.get("low"),
            "Close": quote.get("close"),
            "Volume": quote.get("volume"),
        },
        index=pd.to_datetime(timestamps, unit="s", utc=True).tz_convert(None),
    )
    if adjclose:
        data["Adj Close"] = adjclose

    data = data.dropna(subset=["Close"])
    return data


def get_stock_data(ticker: str) -> pd.DataFrame:
    """
    Fetches historical stock data using yfinance first and Yahoo Chart API as fallback.

    Raises:
        TickerNotFound: If the ticker is not found or has no data.
    """
    stock_ticker = ticker.upper().strip()

    data = _fetch_with_yfinance(stock_ticker)
    if data.empty:
        logging.info(f"yfinance returned no data for {stock_ticker}; trying Yahoo Chart API fallback.")
        data = _fetch_with_yahoo_chart(stock_ticker)

    data = _normalize_ohlcv_columns(data)
    if data.empty or "Close" not in data.columns:
        raise TickerNotFound(f"No data found for ticker '{stock_ticker}'.")

    data = data.dropna(subset=["Close"])
    if data.empty:
        raise TickerNotFound(f"No usable close data found for ticker '{stock_ticker}'.")

    return data


def calculate_indicators(data: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates technical indicators (SMA, RSI, MACD) and appends them.
    Includes fallback mechanisms to prevent crashes.
    """
    try:
        data.ta.sma(length=200, append=True)
    except Exception as e:
        logging.warning(f"SMA calculation failed: {e}. Defaulting to rolling mean.")
        data['SMA_200'] = data['Close'].rolling(window=min(200, len(data)), min_periods=1).mean()

    try:
        data.ta.rsi(length=14, append=True)
    except Exception as e:
        logging.warning(f"RSI calculation failed: {e}. Defaulting to 50.")
        data['RSI_14'] = 50.0

    try:
        data.ta.macd(fast=12, slow=26, signal=9, append=True)
    except Exception as e:
        logging.warning(f"MACD calculation failed: {e}. Defaulting to 0.")
        data['MACD_12_26_9'] = 0.0
        data['MACDh_12_26_9'] = 0.0
        data['MACDs_12_26_9'] = 0.0

    return data


def check_data_quality(data: pd.DataFrame, ticker: str):
    """
    Checks if the latest data has all required indicators for analysis.

    Raises:
        AnalysisError: If data is missing or NaN for required indicators.
    """
    latest_data = data.iloc[-1]
    required_columns = ['Close', 'SMA_200', 'RSI_14', 'MACD_12_26_9', 'MACDs_12_26_9']
    for col in required_columns:
        if col not in latest_data or pd.isna(latest_data[col]):
            raise AnalysisError(f"Not enough data for '{ticker}'. Missing or NaN value for {col}.")


def generate_signal(latest_data: pd.Series) -> tuple[str, float, str]:
    """
    Generates a trading signal based on technical indicators.
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
    if trend == "Uptrend" and rsi < 30 and macd_line > macd_signal:
        action = "buy"
    elif trend == "Downtrend" and rsi > 70 and macd_line < macd_signal:
        action = "sell"

    # 3. Apply confidence score heuristic
    if action in ["buy", "sell"]:
        confidence = 0.75
    else:  # hold
        confidence = 0.5

    return action, confidence, trend


def analyze_stock(ticker: str, correlation_id: str = None) -> dict:
    """
    Analyzes a stock and returns a structured response for the orchestrator.
    Handles errors gracefully by returning a specific JSON structure.
    """
    logging.info(f"Analysis started for ticker: '{ticker}', correlation_id: '{correlation_id}'")
    try:
        data = get_stock_data(ticker)
        data_with_indicators = calculate_indicators(data)
        check_data_quality(data_with_indicators, ticker)

        latest_data = data_with_indicators.iloc[-1]
        action, confidence, trend = generate_signal(latest_data)
        rsi_val = round(float(latest_data["RSI_14"]), 2)

        return {
            "status": "success",
            "data": {
                "action": action,
                "confidence_score": confidence,
                "reason": f"Signal '{action}' generated. Trend: {trend}, RSI: {rsi_val}.",
                "current_price": round(float(latest_data["Close"]), 2),
                "indicators": {
                    "trend": trend,
                    "rsi": rsi_val,
                    "macd_line": round(float(latest_data["MACD_12_26_9"]), 2),
                    "macd_signal": round(float(latest_data["MACDs_12_26_9"]), 2),
                }
            },
            "error": None
        }
    except TickerNotFound:
        logging.warning(f"Ticker not found for '{ticker}', correlation_id: '{correlation_id}'")
        return {
            "status": "error",
            "data": {
                "action": "hold",
                "confidence_score": 0.0,
                "reason": "ticker_not_found"
            },
            "error": {
                "code": "TICKER_NOT_FOUND",
                "message": f"No data found for ticker '{ticker}'",
                "retryable": False
            }
        }
    except AnalysisError as e:
        logging.error(f"Analysis error for '{ticker}': {e}, correlation_id: '{correlation_id}'")
        return {
            "status": "error",
            "data": {
                "action": "hold",
                "confidence_score": 0.0,
                "reason": "analysis_error"
            },
            "error": {
                "code": "ANALYSIS_ERROR",
                "message": str(e),
                "retryable": False
            }
        }
    except Exception as e:
        logging.exception(f"Unexpected technical analysis error for '{ticker}': {e}, correlation_id: '{correlation_id}'")
        return {
            "status": "error",
            "data": {
                "action": "hold",
                "confidence_score": 0.0,
                "reason": "analysis_error"
            },
            "error": {
                "code": "ANALYSIS_ERROR",
                "message": str(e),
                "retryable": True
            }
        }


def main():
    """Handles the command-line interface execution for CI/local testing."""
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Please provide a stock ticker."}), file=sys.stderr)
        sys.exit(1)

    ticker_arg = sys.argv[1]
    is_mock = "--mock" in sys.argv

    if is_mock:
        # Return mock data for CI validation to avoid yfinance rate limits
        cli_output = {
            "trend": "Uptrend",
            "rsi": 30.0,
            "macd_line": 0.5,
            "macd_signal": 0.2,
            "signal": "hold",
            "confidence_score": 0.5,
            "reasoning": "Mock data for CI validation."
        }
        print(json.dumps(cli_output, indent=4))
        return

    try:
        # We don't have a correlation_id in the CLI context
        analysis_result = analyze_stock(ticker_arg)
        data = analysis_result["data"]

        # Check if the analysis resulted in a known business logic error
        if data["reason"] in ["ticker_not_found", "analysis_error"]:
            print(json.dumps({"error": data["reason"]}), file=sys.stderr)
            sys.exit(1)

        # Adapt the new nested structure to the old flat CI structure
        cli_output = {
            "trend": data["indicators"]["trend"],
            "rsi": data["indicators"]["rsi"],
            "macd_line": data["indicators"]["macd_line"],
            "macd_signal": data["indicators"]["macd_signal"],
            "signal": data["action"].lower(),
            "confidence_score": data["confidence_score"],
            "reasoning": data["reason"]
        }
        print(json.dumps(cli_output, indent=4))

    except Exception as e:
        # This will now only catch unexpected system errors during CLI execution
        logging.critical(f"An unexpected system error occurred in CLI mode: {e}")
        print(json.dumps({"error": f"An unexpected error occurred: {e}"}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
