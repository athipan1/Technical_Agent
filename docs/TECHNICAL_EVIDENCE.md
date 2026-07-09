# Technical Evidence Contract

Technical_Agent publishes normalized, non-binding market evidence for Scanner_Agent and Manager_Agent.

It does **not** assign a strategy bucket. Manager_Agent remains the final classification authority.

## Version

```text
technical-evidence-v1
```

## Response fields

Every `StandardAgentData` response includes:

- `technical_score`
- `raw_scores`
- `technical_evidence`
- `evidence_version`
- `evidence_status`
- `evidence_completeness_score`
- `strategy_bucket_hint=null`
- `manager_decision_required=true`
- `bucket_decision_authority=manager`

## Normalized scores

The evidence contract emits values in the `0.0–1.0` range when the underlying data is available:

- `technical_score`
- `trend_score`
- `momentum_score`
- `relative_strength_score`
- `indicator_score`
- `technical_vote_score`
- `volatility_score`

It also emits raw market-structure ratios such as:

- `breakout_ratio`
- `volume_ratio` when supported by the upstream analysis path

## Evidence metrics

The payload preserves:

- trend
- RSI
- MACD line and signal
- ATR and ATR percentage
- current price
- support and resistance levels
- breakout ratio
- volatility regime
- stop-loss and stop method
- timeframe

## Relative-strength limitation

Technical_Agent currently has no benchmark series in the `/analyze` path. Therefore `relative_strength_score` is explicitly calculated as a **local swing-range proxy**:

```text
(current_price - swing_low) / (swing_high - swing_low)
```

The provenance field records:

```text
relative_strength_method=local_swing_range_proxy
```

This value must not be represented as benchmark-relative performance.

## Validation behavior

Walk-forward validation is used to calibrate confidence:

- `walk_forward_passed=true` records validated evidence.
- `walk_forward_passed=false` applies a 30% penalty to `technical_score`.
- `walk_forward_passed=null` records validation as pending.

The existing confidence cap remains `0.80`.

## Evidence status

```text
complete     completeness >= 0.80
partial      completeness >= 0.45
insufficient completeness < 0.45
```

Missing fields are listed explicitly. If technical indicators are unavailable, the response contains no manufactured `technical_score` and reports:

```text
technical_indicators_unavailable
```

## Safety properties

- No ticker-specific rules.
- No strategy-bucket assignment.
- No fabricated score when indicators are missing.
- Missing volume or benchmark data is reported instead of guessed.
- Risk and Execution gates remain mandatory.

## System flow

```text
Technical evidence
  -> Scanner non-binding hints
  -> Manager final classification
  -> Risk approval
  -> Execution validation
  -> Database persistence
```
