
import yfinance as yf
import pandas as pd
import pandas_ta as ta  # noqa: F401
import sys
import json
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="yfinance")


def analyze_stock(ticker):
    """
    Analyzes a stock's technical indicators to generate a trading signal.

    Args:
        ticker (str): The stock ticker symbol.

    Returns:
        dict: A dictionary containing the analysis results.
    """
    try:
        stock_ticker = ticker.upper()

        # Fetch 5 years of historical data
        data = yf.download(stock_ticker, period="5y", progress=False)

        # If yfinance returns a MultiIndex, flatten it
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.droplevel(1)

        if data.empty:
            return {
                "error": "No data found for the given ticker. "
                         "It might be delisted or incorrect."
            }

        # Calculate Technical Indicators
        data.ta.sma(length=200, append=True)
        data.ta.rsi(length=14, append=True)
        data.ta.macd(append=True)

        # Get the latest data
        latest_data = data.iloc[-1]

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

        if trend == "Uptrend":
            if rsi < 30 and macd_line > macd_signal:
                signal = "BUY"
                reasoning = (
                    "The stock is in a clear uptrend and is currently "
                    "oversold (RSI < 30). The MACD crossover provides "
                    "additional confirmation, indicating a strong buying "
                    "opportunity."
                )
            elif rsi > 70:
                signal = "WAIT"
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

        # --- Output ---
        return {
            "trend": trend,
            "rsi": round(rsi, 2),
            "macd_line": round(macd_line, 2),
            "macd_signal": round(macd_signal, 2),
            "signal": signal,
            "reasoning": reasoning
        }

    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({
            "error": "Please provide a stock ticker."
        }), file=sys.stderr)
        sys.exit(1)

    ticker = sys.argv[1]
    result = analyze_stock(ticker)

    if "error" in result:
        print(json.dumps(result, indent=4), file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, indent=4))
