# Technical_Agent API Contract

This document defines the baseline API contract for `Technical_Agent` in the multi-agent trading system.

`Technical_Agent` provides technical-analysis signals, versioned technical evidence, versioned liquidity evidence, data-quality reports, and validation reports for Manager orchestration. It must not submit orders or bypass Risk/Execution gates.

## Standard Headers

```http
Content-Type: application/json
X-Correlation-ID: <uuid>
X-API-KEY: <technical-agent-api-key>
```

## Standard Response Envelope

```json
{
  "status": "success",
  "agent_type": "technical",
  "version": "1.6.0",
  "schema_version": "1.0",
  "timestamp": "2026-08-15T00:00:00Z",
  "correlation_id": "00000000-0000-0000-0000-000000000000",
  "data": {},
  "metadata": {},
  "error": null,
  "confidence_score": null
}
```

## Operational Endpoints

```http
GET /health
GET /ready
GET /version
```

Operational endpoints advertise:

```text
technical-analyze.v2
technical-evidence-v1
liquidity-evidence-v1
fail-closed data quality gate
```

## Analysis Endpoints

```http
POST /analyze
POST /validate/walk-forward
```

### Analyze request: `technical-analyze.v2`

```json
{
  "ticker": "AAPL",
  "timeframe": "1d"
}
```

Supported candle timeframes are exactly:

```text
1d
1h
30m
15m
```

Unsupported timeframe values are rejected. They are never silently converted to `1d`.

For compatibility with the current Manager_Agent request body, `/analyze` also accepts `period` and `account_id`. `period` is deprecated for Technical_Agent and does not change the candle timeframe. Response metadata sets `deprecated_period_ignored=true` when it is supplied. Unknown request fields are rejected.

## Data quality gate

`POST /analyze` returns `data.data_quality` when market data has been fetched and evaluated.

The gate checks:

- at least 200 bars for SMA-200-based analysis
- finite latest High, Low, and Close values
- finite latest SMA-200, RSI-14, MACD line, MACD signal, and ATR-14 values
- Open and Volume as supplemental quality fields
- observation freshness using a timeframe-aware maximum age

Example:

```json
{
  "status": "complete",
  "completeness_score": 1.0,
  "timeframe": "1d",
  "bars_available": 502,
  "minimum_bars_required": 200,
  "latest_observed_at": "2026-08-15T00:00:00Z",
  "fresh": true,
  "freshness_max_age_seconds": 432000,
  "missing_fields": [],
  "reasons": ["technical_data_quality_complete"]
}
```

Critical quality failures return:

```text
status = error
action = hold
confidence_score = 0.0
error.code = INSUFFICIENT_TECHNICAL_DATA
data.data_quality.status = insufficient
```

This `hold` is a fail-closed transport value, not a normal advisory HOLD signal. Manager_Agent must use the response status and evidence status rather than treating it as a valid neutral recommendation.

Missing supplemental Open/Volume data produces `partial` quality. Partial quality is propagated into `technical-evidence-v1` even when the remaining indicator evidence would otherwise be complete.

Indicator-library failures must not manufacture neutral signal values. Technical_Agent uses deterministic mathematical fallbacks for SMA, RSI, MACD, and ATR; if the resulting critical indicator remains unavailable, the quality gate fails closed.

## Technical evidence

`POST /analyze` returns the `technical-evidence-v1` contract. The evidence is advisory and includes normalized scores, raw market metrics, completeness, missing fields, validation status, data-quality provenance, and provenance.

```text
strategy_bucket_hint = null
bucket_decision_authority = manager
manager_decision_required = true
```

## Liquidity evidence

`POST /analyze` also returns `liquidity-evidence-v1` under `data.liquidity_evidence`.

Historical OHLCV evidence includes:

```text
current_price
latest_volume
average_price
average_daily_volume
average_dollar_volume
volume_ratio
```

Bid, ask, and spread are included only when a valid quote snapshot is supplied. Missing quote evidence remains explicit and is never manufactured.

See `docs/LIQUIDITY_EVIDENCE.md` for formulas, status semantics, and provenance.

## Adaptive profit policy context

`POST /analyze` also returns a normalized, non-binding
`data.profit_policy_context`:

```json
{
  "context_version": "profit-technical-context.v1",
  "atr_pct": 0.025,
  "trend_strength": 0.8,
  "volume_strength": 0.8333,
  "observed_at": "2026-07-22T00:00:00Z",
  "evidence_status": "complete",
  "source": "technical-agent"
}
```

The projection reuses `technical-evidence-v1` and `liquidity-evidence-v1`:

- ATR is normalized to a ratio.
- trend strength is the existing normalized `trend_score`.
- volume strength is `min(1, volume_ratio / 1.5)`.
- observation time is the historical OHLCV `historical_as_of` value.

Missing evidence remains `null`; the agent never substitutes a generated time or invented score. Manager_Agent owns synthesis and Profit/Risk safety priority.

## Safety Rules

1. `Technical_Agent` only produces signals, evidence, quality reports, and validation data.
2. `Technical_Agent` must not submit broker orders.
3. `Technical_Agent` must not assign the final strategy bucket.
4. Missing benchmark, volume, quote, spread, or critical indicator data must be reported, not fabricated.
5. Unsupported timeframes must be rejected rather than silently normalized.
6. Insufficient or stale critical technical data must fail closed with zero confidence.
7. `Manager_Agent` remains responsible for investability thresholds, synthesis, and orchestration.
8. `Risk_Agent` must approve before any execution path.
9. Response metadata and correlation IDs must be preserved across Manager workflows.
