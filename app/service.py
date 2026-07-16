import sys
import json
import logging
import warnings
import time
import urllib.request
import urllib.parse
import math
import pandas as pd
import yfinance as yf
import pandas_ta as ta

from risk_controls import calculate_atr, calculate_stop_levels

try:
    from .liquidity_evidence import build_liquidity_evidence
except ImportError:
    from liquidity_evidence import build_liquidity_evidence

warnings.simplefilter(action="ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="yfinance")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

MAX_CONFIDENCE = 0.80
MIN_WALK_FORWARD_PROFIT_FACTOR = 1.20
MIN_WALK_FORWARD_SHARPE = 1.00
MAX_WALK_FORWARD_DRAWDOWN = 0.20


class TickerNotFound(Exception):
    pass


class AnalysisError(Exception):
    pass


TIMEFRAME_CONFIG = {
    "1d": {
        "periods": ["5y", "2y", "1y", "6mo"],
        "interval": "1d",
        "chart_days": 1825,
    },
    "1h": {
        "periods": ["730d", "365d", "90d"],
        "interval": "1h",
        "chart_days": 730,
    },
    "30m": {
        "periods": ["60d", "30d"],
        "interval": "30m",
        "chart_days": 60,
    },
    "15m": {
        "periods": ["60d", "30d"],
        "interval": "15m",
        "chart_days": 60,
    },
}


def cap_confidence(raw_confidence: float) -> float:
    try:
        return max(0.0, min(float(raw_confidence), MAX_CONFIDENCE))
    except (TypeError, ValueError):
        return 0.0


def _normalise_timeframe(timeframe: str | None) -> str:
    value = str(timeframe or "1d").strip().lower()
    return value if value in TIMEFRAME_CONFIG else "1d"


def _normalize_ohlcv_columns(data: pd.DataFrame) -> pd.DataFrame:
    if data is None or data.empty:
        return pd.DataFrame()
    data = data.copy()
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
    return data.rename(columns=rename_map)


def _fetch_with_yfinance(ticker: str, timeframe: str = "1d") -> pd.DataFrame:
    config = TIMEFRAME_CONFIG[_normalise_timeframe(timeframe)]
    attempts = [
        {
            "period": period,
            "interval": config["interval"],
            "auto_adjust": False,
        }
        for period in config["periods"]
    ]
    for kwargs in attempts:
        try:
            data = yf.download(
                ticker,
                progress=False,
                threads=False,
                **kwargs,
            )
            data = _normalize_ohlcv_columns(data)
            if not data.empty and "Close" in data.columns:
                return data
        except Exception as exc:
            logging.warning(
                "yfinance download failed for %s with %s: %s",
                ticker,
                kwargs,
                exc,
            )
    return pd.DataFrame()


def _fetch_with_yahoo_chart(ticker: str, timeframe: str = "1d") -> pd.DataFrame:
    timeframe = _normalise_timeframe(timeframe)
    config = TIMEFRAME_CONFIG[timeframe]
    period2 = int(time.time())
    period1 = period2 - (int(config["chart_days"]) * 24 * 60 * 60)
    symbol = urllib.parse.quote(ticker.upper())
    interval = config["interval"]
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{symbol}?period1={period1}&period2={period2}&interval={interval}"
        "&events=history&includeAdjustedClose=true"
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
        logging.warning("Yahoo chart fallback failed for %s: %s", ticker, exc)
        return pd.DataFrame()
    result = ((payload.get("chart") or {}).get("result") or [])
    if not result:
        return pd.DataFrame()
    item = result[0]
    timestamps = item.get("timestamp") or []
    quote = ((item.get("indicators") or {}).get("quote") or [{}])[0]
    adjclose = (
        ((item.get("indicators") or {}).get("adjclose") or [{}])[0].get(
            "adjclose"
        )
    )
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
    return data.dropna(subset=["Close"])


def get_stock_data(ticker: str, timeframe: str = "1d") -> pd.DataFrame:
    stock_ticker = ticker.upper().strip()
    timeframe = _normalise_timeframe(timeframe)
    data = _fetch_with_yfinance(stock_ticker, timeframe)
    if data.empty:
        data = _fetch_with_yahoo_chart(stock_ticker, timeframe)
    data = _normalize_ohlcv_columns(data)
    if data.empty or "Close" not in data.columns:
        raise TickerNotFound(f"No data found for ticker '{stock_ticker}'.")
    data = data.dropna(subset=["Close"])
    if data.empty:
        raise TickerNotFound(
            f"No usable close data found for ticker '{stock_ticker}'."
        )
    return data


def calculate_indicators(data: pd.DataFrame) -> pd.DataFrame:
    data = data.copy()
    try:
        data.ta.sma(length=200, append=True)
    except Exception as exc:
        logging.warning(
            "SMA calculation failed: %s. Defaulting to rolling mean.",
            exc,
        )
        data["SMA_200"] = data["Close"].rolling(
            window=min(200, len(data)),
            min_periods=1,
        ).mean()
    try:
        data.ta.rsi(length=14, append=True)
    except Exception as exc:
        logging.warning("RSI calculation failed: %s. Defaulting to 50.", exc)
        data["RSI_14"] = 50.0
    try:
        data.ta.macd(fast=12, slow=26, signal=9, append=True)
    except Exception as exc:
        logging.warning("MACD calculation failed: %s. Defaulting to 0.", exc)
        data["MACD_12_26_9"] = 0.0
        data["MACDh_12_26_9"] = 0.0
        data["MACDs_12_26_9"] = 0.0
    try:
        atr = ta.atr(
            high=data["High"],
            low=data["Low"],
            close=data["Close"],
            length=14,
        )
        data["ATR_14"] = atr
    except Exception as exc:
        logging.warning(
            "ATR calculation failed: %s. Defaulting to manual ATR.",
            exc,
        )
        data["ATR_14"] = calculate_atr(data, length=14)
    return data


def check_data_quality(data: pd.DataFrame, ticker: str):
    latest_data = data.iloc[-1]
    required_columns = [
        "Close",
        "High",
        "Low",
        "SMA_200",
        "RSI_14",
        "MACD_12_26_9",
        "MACDs_12_26_9",
        "ATR_14",
    ]
    for col in required_columns:
        if col not in latest_data or pd.isna(latest_data[col]):
            raise AnalysisError(
                f"Not enough data for '{ticker}'. Missing or NaN value for {col}."
            )


def generate_signal(latest_data: pd.Series) -> tuple[str, float, str]:
    price = latest_data["Close"]
    sma200 = latest_data["SMA_200"]
    rsi = latest_data["RSI_14"]
    macd_line = latest_data["MACD_12_26_9"]
    macd_signal = latest_data["MACDs_12_26_9"]
    if price > sma200:
        trend = "Uptrend"
    elif price < sma200:
        trend = "Downtrend"
    else:
        trend = "Sideways"
    action = "hold"
    if trend == "Uptrend" and rsi < 30 and macd_line > macd_signal:
        action = "buy"
    elif trend == "Downtrend" and rsi > 70 and macd_line < macd_signal:
        action = "sell"
    raw_confidence = 0.75 if action in ["buy", "sell"] else 0.5
    return action, raw_confidence, trend


def _safe_sharpe(returns: list[float]) -> float:
    if not returns:
        return 0.0
    series = pd.Series(returns)
    std = float(series.std()) if len(series) > 1 else 0.0
    if std == 0:
        return 0.0
    return float(series.mean() / std * math.sqrt(252))


def _max_drawdown(equity_curve: list[float]) -> float:
    peak = equity_curve[0] if equity_curve else 1.0
    max_dd = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        if peak > 0:
            max_dd = max(max_dd, (peak - value) / peak)
    return max_dd


def _evaluate_window(test_data: pd.DataFrame) -> dict:
    returns = []
    wins = 0
    losses = 0
    gross_profit = 0.0
    gross_loss = 0.0
    equity = [1.0]
    for idx in range(len(test_data) - 1):
        row = test_data.iloc[idx]
        next_close = float(test_data.iloc[idx + 1]["Close"])
        close = float(row["Close"])
        action, _, _ = generate_signal(row)
        if action == "hold" or close == 0:
            continue
        pct = (next_close - close) / close
        trade_return = pct if action == "buy" else -pct
        returns.append(trade_return)
        equity.append(equity[-1] * (1 + trade_return))
        if trade_return >= 0:
            wins += 1
            gross_profit += trade_return
        else:
            losses += 1
            gross_loss += abs(trade_return)
    trades = len(returns)
    win_rate = wins / trades if trades else 0.0
    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > 0
        else (gross_profit if gross_profit > 0 else 0.0)
    )
    max_dd = _max_drawdown(equity)
    sharpe = _safe_sharpe(returns)
    passed = (
        trades > 0
        and profit_factor >= MIN_WALK_FORWARD_PROFIT_FACTOR
        and sharpe >= MIN_WALK_FORWARD_SHARPE
        and max_dd <= MAX_WALK_FORWARD_DRAWDOWN
    )
    return {
        "trades": trades,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "max_drawdown": max_dd,
        "sharpe": sharpe,
        "passed": passed,
    }


def walk_forward_validate(
    ticker: str,
    timeframe: str = "1d",
    min_train_bars: int = 180,
    test_bars: int = 30,
    step_bars: int = 30,
) -> dict:
    timeframe = _normalise_timeframe(timeframe)
    data = calculate_indicators(get_stock_data(ticker, timeframe)).dropna(
        subset=[
            "Close",
            "SMA_200",
            "RSI_14",
            "MACD_12_26_9",
            "MACDs_12_26_9",
        ]
    )
    if len(data) < min_train_bars + test_bars:
        raise AnalysisError("Not enough data for walk-forward validation.")
    windows = []
    start = min_train_bars
    while start + test_bars <= len(data):
        train = data.iloc[:start]
        test = data.iloc[start : start + test_bars]
        metrics = _evaluate_window(test)
        windows.append(
            {
                "train_start": str(train.index[0]),
                "train_end": str(train.index[-1]),
                "test_start": str(test.index[0]),
                "test_end": str(test.index[-1]),
                **metrics,
            }
        )
        start += step_bars
    if not windows:
        raise AnalysisError("No walk-forward windows could be generated.")
    avg_pf = sum(w["profit_factor"] for w in windows) / len(windows)
    avg_sharpe = sum(w["sharpe"] for w in windows) / len(windows)
    avg_dd = sum(w["max_drawdown"] for w in windows) / len(windows)
    avg_wr = sum(w["win_rate"] for w in windows) / len(windows)
    passed = (
        avg_pf >= MIN_WALK_FORWARD_PROFIT_FACTOR
        and avg_sharpe >= MIN_WALK_FORWARD_SHARPE
        and avg_dd <= MAX_WALK_FORWARD_DRAWDOWN
    )
    return {
        "ticker": ticker.upper(),
        "timeframe": timeframe,
        "windows": len(windows),
        "avg_win_rate": round(avg_wr, 4),
        "avg_profit_factor": round(avg_pf, 4),
        "avg_max_drawdown": round(avg_dd, 4),
        "avg_sharpe": round(avg_sharpe, 4),
        "passed": bool(passed),
        "confidence_cap": MAX_CONFIDENCE,
        "criteria": {
            "min_profit_factor": MIN_WALK_FORWARD_PROFIT_FACTOR,
            "min_sharpe": MIN_WALK_FORWARD_SHARPE,
            "max_drawdown": MAX_WALK_FORWARD_DRAWDOWN,
        },
        "window_results": windows,
    }


def analyze_stock(
    ticker: str,
    timeframe: str = "1d",
    correlation_id: str = None,
) -> dict:
    timeframe = _normalise_timeframe(timeframe)
    logging.info(
        "Analysis started for ticker: '%s', timeframe: '%s', correlation_id: '%s'",
        ticker,
        timeframe,
        correlation_id,
    )
    try:
        data = get_stock_data(ticker, timeframe)
        liquidity_evidence = build_liquidity_evidence(
            data,
            timeframe=timeframe,
        )
        data_with_indicators = calculate_indicators(data)
        check_data_quality(data_with_indicators, ticker)
        latest_data = data_with_indicators.iloc[-1]
        action, raw_confidence, trend = generate_signal(latest_data)
        confidence = cap_confidence(raw_confidence)
        rsi_val = round(float(latest_data["RSI_14"]), 2)
        stop_levels = calculate_stop_levels(data_with_indicators, action)
        return {
            "status": "success",
            "data": {
                "action": action,
                "confidence_score": confidence,
                "reason": (
                    f"Signal '{action}' generated. Trend: {trend}, "
                    f"RSI: {rsi_val}, volatility: "
                    f"{stop_levels['volatility_regime']}. "
                    f"Confidence capped at {MAX_CONFIDENCE}."
                ),
                "current_price": round(float(latest_data["Close"]), 2),
                "liquidity_evidence": liquidity_evidence,
                "indicators": {
                    "trend": trend,
                    "rsi": rsi_val,
                    "macd_line": round(
                        float(latest_data["MACD_12_26_9"]),
                        2,
                    ),
                    "macd_signal": round(
                        float(latest_data["MACDs_12_26_9"]),
                        2,
                    ),
                    "atr": stop_levels["atr"],
                    "atr_percent": stop_levels["atr_percent"],
                    "atr_stop_long": stop_levels["atr_stop_long"],
                    "atr_stop_short": stop_levels["atr_stop_short"],
                    "swing_low": stop_levels["swing_low"],
                    "swing_high": stop_levels["swing_high"],
                    "stop_loss": stop_levels["stop_loss"],
                    "stop_method": stop_levels["stop_method"],
                    "volatility_regime": stop_levels["volatility_regime"],
                    "timeframe": timeframe,
                    "confidence_cap": MAX_CONFIDENCE,
                    "raw_confidence_score": raw_confidence,
                    "validation_status": "walk_forward_required_before_live",
                    "walk_forward_passed": None,
                },
            },
            "error": None,
        }
    except TickerNotFound:
        return {
            "status": "error",
            "data": {
                "action": "hold",
                "confidence_score": 0.0,
                "reason": "ticker_not_found",
            },
            "error": {
                "code": "TICKER_NOT_FOUND",
                "message": f"No data found for ticker '{ticker}'",
                "retryable": False,
            },
        }
    except AnalysisError as exc:
        return {
            "status": "error",
            "data": {
                "action": "hold",
                "confidence_score": 0.0,
                "reason": "analysis_error",
            },
            "error": {
                "code": "ANALYSIS_ERROR",
                "message": str(exc),
                "retryable": False,
            },
        }
    except Exception as exc:
        logging.exception(
            "Unexpected technical analysis error for '%s': %s, correlation_id: '%s'",
            ticker,
            exc,
            correlation_id,
        )
        return {
            "status": "error",
            "data": {
                "action": "hold",
                "confidence_score": 0.0,
                "reason": "analysis_error",
            },
            "error": {
                "code": "ANALYSIS_ERROR",
                "message": str(exc),
                "retryable": True,
            },
        }


def main():
    if len(sys.argv) < 2:
        print(
            json.dumps({"error": "Please provide a stock ticker."}),
            file=sys.stderr,
        )
        sys.exit(1)
    ticker_arg = sys.argv[1]
    timeframe_arg = "1d"
    is_mock = "--mock" in sys.argv
    for arg in sys.argv[2:]:
        if arg.startswith("--timeframe="):
            timeframe_arg = arg.split("=", 1)[1]
    if is_mock:
        cli_output = {
            "trend": "Uptrend",
            "rsi": 30.0,
            "macd_line": 0.5,
            "macd_signal": 0.2,
            "atr": 1.25,
            "volatility_regime": "normal",
            "stop_loss": 95.0,
            "timeframe": _normalise_timeframe(timeframe_arg),
            "signal": "hold",
            "confidence_score": 0.5,
            "confidence_cap": MAX_CONFIDENCE,
            "reasoning": "Mock data for CI validation.",
        }
        print(json.dumps(cli_output, indent=4))
        return
    try:
        analysis_result = analyze_stock(ticker_arg, timeframe=timeframe_arg)
        data = analysis_result["data"]
        if data["reason"] in ["ticker_not_found", "analysis_error"]:
            print(json.dumps({"error": data["reason"]}), file=sys.stderr)
            sys.exit(1)
        indicators = data["indicators"]
        cli_output = {
            "trend": indicators["trend"],
            "rsi": indicators["rsi"],
            "macd_line": indicators["macd_line"],
            "macd_signal": indicators["macd_signal"],
            "atr": indicators.get("atr"),
            "volatility_regime": indicators.get("volatility_regime"),
            "stop_loss": indicators.get("stop_loss"),
            "timeframe": indicators.get("timeframe"),
            "signal": data["action"],
            "confidence_score": data["confidence_score"],
            "confidence_cap": indicators.get("confidence_cap"),
            "liquidity_evidence": data.get("liquidity_evidence"),
            "reasoning": data["reason"],
        }
        print(json.dumps(cli_output, indent=4))
    except Exception as exc:
        logging.exception("CLI execution failed")
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
