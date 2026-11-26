# Implementation Plan

## Goal

Build a file-backed AI stock trading experiment platform that can create experiments, execute one idempotent daily run from GitHub Actions, persist an auditable portfolio history, and fail clearly when market data, AI decisions, or trade execution cannot be completed.

The implementation should follow [SPEC.md](./SPEC.md), keep all dates and times in Eastern Time, use Finnhub for market data, use the OpenRouter Agents SDK with `nvidia/nemotron-3.5-lightning` for AI inference, and keep external API calls behind injectable clients so tests never require credentials or network access.

## Proposed repository layout

```text
ai_stock_trader/
├── ai_stock_trader/
│   ├── __init__.py
│   ├── config.py              # environment variables and runtime configuration
│   ├── models.py              # typed experiment, portfolio, state, and trade models
│   ├── storage.py             # experiment discovery and CSV/JSON/Markdown persistence
│   ├── market_data.py         # Finnhub adapter and market-data protocols
│   ├── trading.py             # validation and buy/sell state transitions
│   ├── ai_manager.py          # prompt construction, quote tools, and retry handling
│   ├── daily_run.py           # idempotent orchestration for the scheduled job
│   └── errors.py              # actionable domain and integration exceptions
├── tests/
│   ├── conftest.py
│   ├── test_models.py
│   ├── test_storage.py
│   ├── test_trading.py
│   ├── test_market_data.py
│   ├── test_ai_manager.py
│   ├── test_daily_run.py
│   └── test_create_new_experiment.py
├── create_new_experiment.py
├── run_daily.py
├── experiments/
│   ├── active/.gitkeep
│   └── finished/.gitkeep
└── .github/workflows/daily-run.yml
```

The exact module names may change during implementation, but the boundaries should remain: domain logic must be testable without the filesystem or network, and adapters should translate external data into typed internal objects.

## Phased implementation

### ~~1. Establish domain rules and typed data models~~ (Done)

- Define validated types for experiment names, dates, portfolio types, tickers, money, holdings, portfolio state, trades, and AI trade explanations.
- Represent dates as calendar dates and use a single Eastern-Time clock helper for “today”; do not derive business-day behavior from the machine’s local timezone.
- Enforce nonnegative available cash, nonnegative share quantities, valid buy/sell actions, and a portfolio state invariant: `total_value = cash + sum(shares * current_price)` when prices are supplied.
- Decide and document the precision/serialization policy for money, share quantities, and prices. Decimal arithmetic is preferred over binary floating point for balances and quantities.
- Define domain errors with enough context to make CI failures actionable.

### ~~2. Implement safe experiment storage~~ (Done)

- Discover experiments only in `experiments/active` and `experiments/finished`.
- Load each experiment from its `[experiment name].json` file and validate that its directory contents match the declared portfolios.
- Persist the required state and trade CSV files with stable headers and deterministic field formatting.
- Write JSON/CSV files atomically where practical to avoid partial records after an interrupted CI run.
- Treat strategy Markdown as immutable after creation; normal daily-run code must never rewrite it.
- Add path/name validation to prevent a name from escaping the experiment root or colliding ambiguously with another portfolio.
- Define how existing files are handled during creation: reject collisions by default rather than silently overwriting data.

### ~~3. Build the trading/state-transition layer~~ (Done)

- Implement buy and sell calculations for fractional shares with no fees.
- Reject invalid trades before mutation: unknown ticker, nonpositive quantity, insufficient cash for a buy, or insufficient holdings for a sell.
- Keep state transitions pure or transaction-like so a failed trade leaves the original state unchanged.
- Provide control-portfolio initialization that spends all available cash on the configured stock using the current quote; record the resulting holdings and residual balance deterministically.
- Provide valuation logic that uses current quotes and handles missing/invalid market data as a clear failure.

### ~~4. Add the Finnhub adapter~~ (Done)

- Load `FINNHUB_API_KEY` at startup and fail fast with a clear message if it is absent.
- Wrap the required Finnhub operations only: market status, market news, and current quote.
- Normalize Finnhub responses into internal models and validate missing, malformed, or stale values at the adapter boundary.
- Keep the adapter injectable behind protocols/interfaces so tests can provide a fake client and assert exact calls without network access.
- Centralize retry/error translation and never include the API key in exception text, logs, CSV files, or experiment data.

### ~~5. Add AI decision handling~~ (Done)

- Load `OPENROUTER_API_KEY` at startup and fail fast when it is missing.
- Use the OpenRouter Agents SDK and the required model `nvidia/nemotron-3.5-lightning`.
- Construct a prompt containing the immutable strategy document, current portfolio state, date, and market news. The prompt must explicitly constrain the AI to buy/sell actions, fractional quantities, available quote tools, and a concise summarized explanation.
- Expose a quote tool backed by the Finnhub adapter; the AI must request quotes through that tool rather than receiving an unbounded market snapshot.
- Parse and validate the AI response into a structured trade list plus explanation. Reject unsupported actions, malformed quantities, unknown fields as appropriate, and trades that violate portfolio constraints.
- Retry the complete “decision then validation/execution” attempt up to three times when a proposed set of trades fails. After the third failure, raise a CI-reportable error containing the reason without exposing credentials.
- Make the AI client injectable and test tool-call sequencing, malformed responses, retry limits, and successful responses with fakes.

### ~~6. Implement idempotent daily orchestration~~ (Done)

Run the workflow in the specification’s order:

1. Determine the current ET date.
2. Finalize experiments whose end date has arrived or passed, recording final state and moving them from `experiments/active` to `experiments/finished` safely.
3. Query Finnhub market status and stop successfully if the market is closed.
4. Initialize newly starting control portfolios by buying their configured stock with all available cash.
5. Process each portfolio deterministically.
   - AI-managed: record pre-trade state, obtain/validate AI trades, execute them, then record trades and explanation.
   - Control: record current state only.
6. Exit nonzero on any unrecoverable error, with the experiment/portfolio and reason in the CI-visible message.

For idempotency, define a daily-run marker or inspect the relevant CSV records before each write. Re-running the same ET date must not duplicate state rows, trade rows, control initialization, finalization, or active-to-finished moves. Use a lock or equivalent single-run guard if GitHub Actions could overlap scheduled/manual runs.

The exact meaning of “starting” and “ending” on a date should be implemented consistently as inclusive (`start_date <= today`, `end_date <= today`) and covered by boundary tests. Finalization must not prevent already-due experiment records from being complete and auditable.

### ~~7. Add command-line entry points and GitHub Actions~~

- `create_new_experiment.py` should accept or prompt for the experiment name, inclusive start/end dates, and one or more portfolios.
- Validate end date ordering, portfolio uniqueness, starting money, portfolio type, required strategy/control ticker fields, and control tickers via Finnhub quote lookup.
- Create the directory and initial JSON/Markdown/CSV files only after all input validation passes; leave no partial experiment on failure.
- `run_daily.py` should be a thin entry point that configures dependencies, invokes the orchestrator, and returns a nonzero exit code for expected operational failures.
- Add a GitHub Actions workflow scheduled for `15:30` ET equivalent in UTC, plus a manual dispatch option. Document that GitHub Actions cron is UTC and account for daylight-saving changes rather than hard-coding a single UTC time if exact 3:30 PM ET is required year-round.
- Keep API keys in GitHub Actions Secrets and pass them only as environment variables.

### ~~8. Documentation and operational safeguards~~

- Replace the empty README with setup, `.env` usage for local development, experiment layout, creation, daily-run behavior, and failure/retry semantics.
- Document the data format and the immutability rule for strategy files.
- Add comments where decisions are non-obvious, especially idempotency, date boundaries, atomic persistence, and AI retry behavior.
- Ensure `.env`, generated experiment data containing sensitive material, caches, and local artifacts are ignored appropriately; verify no credential is committed.

## Test-first sequence

Write each test group before its implementation and run the focused tests after each phase:

1. Model validation and serialization, including money/share precision and date boundaries.
2. Storage loading, atomic writes, immutable strategies, malformed files, and path safety.
3. Buy/sell transitions, insufficient resources, control initialization, and valuation.
4. Finnhub adapter mappings, market-open/closed responses, quote validation, and missing credentials using mocked clients.
5. AI parsing, quote-tool requests, prompt contents, retry behavior, and credential failures using mocked SDK clients.
6. Daily-run orchestration for market closed, experiment start/end, AI/control portfolios, partial failures, and repeated same-day execution.
7. Experiment creation validation, ticker validation, collision handling, and no-partial-output guarantees.
8. CLI exit codes and a small end-to-end test using temporary directories and fake market/AI services.

Run the required suite with:

```text
uv run pytest
```

Measure coverage during implementation and keep it at or above the required 70%, with special attention to failure paths and idempotency branches.

## Open decisions to settle during implementation

- Whether a control portfolio’s initial purchase should be recorded as a trade row or only reflected in its first state row. The specification requires initialization and state recording but does not define a control trades file; default to state-only unless the project owner wants a complete trade audit.
- Whether an AI-managed portfolio may trade tickers outside its initial holdings. The quote tool and generic buy/sell rules suggest yes; enforce that every traded ticker has a valid quote and is recorded in state/holdings.
- What “current price” means for a fractional purchase when Finnhub returns bid/ask or delayed data. Default to Finnhub’s `quote` current price (`c`) and reject zero/unavailable values.
- Whether final-state recording should use the last available market price on a closed market or the current quote at finalization. Define this explicitly before implementing finalization.
- Whether daily-run files need a durable run identifier in addition to date-based deduplication. Date-based deduplication is the minimum required behavior; a marker can strengthen protection against overlapping jobs.

## Completion checklist

- All requirements in [SPEC.md](./SPEC.md) have a corresponding implementation and test.
- No production path calls Finnhub or OpenRouter directly without an injectable adapter.
- Missing credentials fail fast and secrets are absent from logs and generated data.
- Repeating a daily run for the same ET date produces no duplicate records or state changes.
- `uv run pytest` passes with at least 70% coverage.
- A GitHub Actions run can create/finalize experiments and reports failures with useful context.
- README and inline comments explain the operational and data-integrity decisions.
