# Liquidity Evidence Contract

`liquidity-evidence-v1` is a non-binding market-liquidity evidence contract produced by `Technical_Agent` and consumed by `Manager_Agent`.

It does not approve a trade, assign a strategy bucket, or bypass Backtest, Risk, or Execution gates.

## Runtime fields

```json
{
  "evidence_version": "liquidity-evidence-v1",
  "evidence_status": "partial",
  "evidence_completeness_score": 0.5714,
  "metrics": {
    "current_price": 190.25,
    "latest_volume": 51230000,
    "average_price": 187.91,
    "average_daily_volume": 48620000,
    "average_dollar_volume": 9134567890.12,
    "volume_ratio": 1.0537
  },
  "available_fields": [
    "average_daily_volume",
    "average_dollar_volume",
    "current_price",
    "volume_ratio"
  ],
  "missing_fields": ["ask", "bid", "spread_bps"],
  "evidence_reasons": [
    "average_dollar_volume_from_historical_ohlcv",
    "bid_ask_spread_unavailable"
  ],
  "provenance": {
    "historical_source": "historical_ohlcv",
    "quote_source": "unavailable",
    "calculation_method": "mean(close_times_volume)",
    "volume_lookback_bars": 20,
    "observed_bars": 20,
    "timeframe": "1d",
    "historical_as_of": "2026-07-15T00:00:00+00:00",
    "quote_as_of": null,
    "generated_at": "2026-07-16T01:00:00+00:00"
  }
}
```

## Status semantics

- `complete`: historical volume evidence and a valid bid/ask quote snapshot are both available.
- `partial`: useful historical liquidity evidence is available, but quote spread evidence is missing or incomplete.
- `unavailable`: no valid close/volume observations are available.

## Calculations

The default lookback is 20 bars.

```text
average_daily_volume = mean(volume)
average_price = mean(close)
average_dollar_volume = mean(close × volume)
volume_ratio = latest_volume / average_daily_volume
midpoint = (bid + ask) / 2
spread_bps = (ask - bid) / midpoint × 10,000
```

`average_dollar_volume` uses the mean of each bar's dollar volume rather than multiplying two separately rounded averages.

## Safety behavior

- NaN, Infinity, booleans, malformed strings, non-positive prices, and invalid quote pairs are not accepted as evidence.
- Missing bid/ask data is reported explicitly. No spread is synthesized.
- A bid greater than the ask is invalid and produces no spread value.
- Manager remains the only component allowed to apply investability thresholds.
- Missing liquidity fields are warnings until Manager explicitly enables required liquidity gates.

## Current provider coverage

The current runtime derives historical metrics from the same normalized OHLCV data already used for technical analysis. It does not add a second network request.

Bid/ask fields remain unavailable until a trusted quote provider is connected. The contract already supports an optional quote snapshot, so that provider can be added without changing the response schema.
