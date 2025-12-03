
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import sys
import json

def analyze_stock(ticker):
    """
    Analyzes a stock's technical indicators to generate a trading signal.

    Args:
        ticker (str): The stock ticker symbol.

    Returns:
        dict: A dictionary containing the analysis results.
    """
    try:
        # Append .BK for stocks in the Stock Exchange of Thailand (SET)
        stock_ticker = ticker.upper() + ".BK"

        # Fetch 2 years of historical data
        data = yf.download(stock_ticker, period="2y", progress=False)

        # If yfinance returns a MultiIndex, flatten it
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.droplevel(1)

        if data.empty:
            return {
                "error": "No data found for the given ticker. It might be delisted or incorrect."
            }

        # Calculate Technical Indicators
        data.ta.sma(length=200, append=True)
        data.ta.rsi(length=14, append=True)

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

        # 3. Signal Generation
        signal = "WAIT"
        reasoning = ""

        if trend == "Uptrend":
            if rsi < 30:
                signal = "BUY"
                reasoning = "The stock is in a clear uptrend and is currently oversold (RSI < 30), indicating a strong buying opportunity."
            elif rsi > 70:
                signal = "WAIT"
                reasoning = "The stock is in an uptrend but is currently overbought (RSI > 70). It's better to wait for a price correction before buying."
            else:
                signal = "WAIT"
                reasoning = "The stock is in an uptrend, but momentum is neutral. Wait for a clearer signal."

        elif trend == "Downtrend":
            if rsi > 70:
                signal = "SELL"
                reasoning = "The stock is in a clear downtrend and is currently overbought (RSI > 70), presenting a potential selling or shorting opportunity."
            else:
                signal = "WAIT"
                reasoning = "The stock is in a downtrend. It is not advisable to buy. Wait for a trend reversal."

        else: # Sideways
            reasoning = "The stock is in a sideways trend. No clear entry or exit signal."


        # --- Output ---
        return {
            "trend": trend,
            "rsi": round(rsi, 2),
            "signal": signal,
            "reasoning": reasoning
        }

    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Please provide a stock ticker as a command-line argument."}))
    else:
        ticker = sys.argv[1]
        result = analyze_stock(ticker)
        print(json.dumps(result, indent=4))
