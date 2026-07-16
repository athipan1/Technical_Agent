# Technical_Agent API Contract

This document defines the baseline API contract for `Technical_Agent` in the multi-agent trading system.

`Technical_Agent` provides technical-analysis signals, versioned technical evidence, versioned liquidity evidence, and validation reports for Manager orchestration. It must not submit orders or bypass Risk/Execution gates.

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
  "version": "1.5.0",
  "schema_version": "1.0",
  "timestamp": "2026-07-16T00:00:00Z",
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

Operational endpoints advertise both:

```text
technical-evidence-v1
liquidity-evidence-v1
```

## Analysis Endpoints

```http
POST /analyze
POST /validate/walk-forward
```

## Technical evidence

`POST /analyze` returns the `technical-evidence-v1` contract. The evidence is advisory and includes normalized scores, raw market metrics, completeness, missing fields, validation status, and provenance.

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

## Safety Rules

1. `Technical_Agent` only produces signals, evidence, and validation data.
2. `Technical_Agent` must not submit broker orders.
3. `Technical_Agent` must not assign the final strategy bucket.
4. Missing benchmark, volume, quote, or spread data must be reported, not fabricated.
5. `Manager_Agent` remains responsible for investability thresholds, synthesis, and orchestration.
6. `Risk_Agent` must approve before any execution path.
7. Response metadata and correlation IDs must be preserved across Manager workflows.
