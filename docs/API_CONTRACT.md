# Technical_Agent API Contract

This document defines the baseline API contract for `Technical_Agent` in the multi-agent trading system.

`Technical_Agent` provides technical-analysis signals and validation reports for Manager orchestration. It should not submit orders or bypass Risk/Execution gates.

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
  "version": "1.3.0",
  "schema_version": "1.0",
  "timestamp": "2026-07-04T00:00:00Z",
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

## Analysis Endpoints

```http
POST /analyze
POST /validate/walk-forward
```

## Safety Rules

1. `Technical_Agent` only produces signals and validation data.
2. `Technical_Agent` must not submit broker orders.
3. `Manager_Agent` remains responsible for synthesis and orchestration.
4. `Risk_Agent` must approve before any execution path.
5. Response metadata and correlation IDs should be preserved across Manager workflows.
