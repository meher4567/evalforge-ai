# Phase 2 Evaluators Design

## Goal

Phase 2 adds the first AI-specific behavior: a deterministic RAG demo adapter and an evaluator engine. This lets EvalForge score an app output without depending on paid APIs or nondeterministic model calls.

## Why Deterministic First

The full project may later support Ollama, sentence-transformers, and external models. The first working evaluator path should be deterministic so tests, benchmarks, and interview demos are reproducible. This phase uses lexical retrieval and token-overlap similarity as local stand-ins for heavier semantic components.

## Adapter Contract

The adapter returns:

- `answer`
- `retrieved_chunks`
- `prompt_used`
- `model_used`
- `latency_ms`
- `estimated_cost_usd`
- `trace_steps`

This matches the build plan contract and gives the future trace viewer useful data from the first implementation.

## Evaluator Contract

Every evaluator receives:

- immutable eval case payload,
- adapter output,
- evaluator-specific config.

Every evaluator returns:

- score in `[0, 1]` or `None` if skipped,
- pass/fail or `None` if skipped,
- details explaining the score,
- error/skipped flags.

## Evaluators In This Phase

- exact match
- contains expected facts
- token-overlap semantic similarity
- retrieval hit rate
- forbidden claim
- latency threshold
- cost threshold

## Learning Target

After this phase, the user should be able to explain:

- what an adapter is,
- why EvalForge separates adapter execution from evaluation,
- why deterministic local evaluation is useful before real LLM integration,
- why evaluator results need details, skipped, and errored states,
- why not every evaluator applies to every case.
