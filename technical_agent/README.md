# Technical Stock Analysis Agent

This agent analyzes a stock's historical data to provide a trading signal (BUY, SELL, or WAIT) based on technical indicators.

## How it Works

The agent performs the following steps:

1.  **Input:** Takes a stock ticker symbol as a command-line argument.
2.  **Data Fetching:** Retrieves the last two years of historical stock data from Yahoo Finance. For stocks on the Stock Exchange of Thailand (SET), it automatically appends the `.BK` suffix.
3.  **Indicator Calculation:**
    *   **SMA200:** Calculates the 200-day Simple Moving Average to determine the long-term trend.
    *   **RSI:** Calculates the 14-day Relative Strength Index to gauge momentum.
4.  **Analysis:**
    *   **Trend:** Checks if the price is above (Uptrend) or below (Downtrend) the SMA200.
    *   **Momentum:** Checks if the RSI is overbought (>70) or oversold (<30).
5.  **Output:** Generates a JSON object containing the trend, RSI value, a final signal (`BUY`, `SELL`, or `WAIT`), and a clear reasoning for the signal.

## Installation

1.  Clone the repository.
2.  Install the required Python packages:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

Run the agent from your terminal by providing a stock ticker:

```bash
python main.py <TICKER>
```

**Example (for a Thai stock):**

```bash
python main.py AOT
```

**Example Output:**

```json
{
    "trend": "Uptrend",
    "rsi": 65.5,
    "signal": "WAIT",
    "reasoning": "The stock is in an uptrend, but momentum is neutral. Wait for a clearer signal."
}
```
