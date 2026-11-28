# AI Stock Trader

This project runs file-backed stock portfolio experiments. Each daily run uses Finnhub for market status, news, and current quotes. AI-managed portfolios receive decisions from the OpenRouter Agents SDK using `nvidia/nemotron-3.5-lightning`. The project records portfolio states and trades for review; it does not place orders with a brokerage.

## Requirements

- Python 3.14
- [`uv`](https://docs.astral.sh/uv/)
- Finnhub and OpenRouter API keys for live runs. Tests use fakes and do not need either key.

Install the locked dependencies:

```sh
uv sync --locked
```

## Local credentials

For local development, put the API keys in a project-root `.env` file:

```dotenv
FINNHUB_API_KEY=your_finnhub_key
OPENROUTER_API_KEY=your_openrouter_key
```

The CLI loads `.env` without replacing variables already set in the environment. Keep this file private; it is ignored by Git. Do not put credentials in experiment names, strategies, or other experiment data. GitHub Actions should provide the keys through the `FINNHUB_API_KEY` and `OPENROUTER_API_KEY` repository secrets.

## Create an experiment

Run the interactive creator from the repository root:

```sh
uv run python create_new_experiment.py
```

It asks for an experiment name, inclusive start and end dates, and one or more portfolios. AI-managed portfolios need starting money and a Markdown strategy. Control portfolios need starting money and a ticker that Finnhub can quote. The creator validates all inputs before it writes files. Existing experiment names are rejected rather than overwritten.

The optional `--experiments-root` argument changes the data directory:

```sh
uv run python create_new_experiment.py --experiments-root experiments
```

## Experiment files

Experiments live in `experiments/active/<name>/` until their end date, then move to `experiments/finished/<name>/`. Each folder contains:

- `<experiment name>.json`: dates and portfolio configuration.
- `<portfolio name>_state.csv`: daily date, cash, total value, and holdings.
- `<portfolio name>_strategy.md`: the AI portfolio's strategy, created once and treated as immutable by daily runs.
- `<portfolio name>_trades.csv`: AI trade actions, tickers, fractional quantities, and the summarized explanation.

CSV headers are stable. Money and total values are written to two decimal places, share quantities to six decimal places, and holdings are stored as deterministic JSON in the state CSV. Control portfolios have state files but no trade or strategy file. The hidden `experiments/.daily_state/` directory stores the latest portfolio snapshot and processed date used to resume runs and prevent duplicate daily processing. `.daily_run.lock` prevents concurrent local runs. Do not edit snapshots or generated records while a run is in progress.

The GitHub Actions workflow commits experiment files so the next scheduled run can continue from the saved state. Treat the repository and its experiment history as private if strategies or results are sensitive. Keep credentials out of all experiment files.

## Daily runs

Run the workflow once for the current Eastern Time date:

```sh
uv run python run_daily.py
```

To use a different experiment root, pass `--experiments-root`. Scheduled runs use `--scheduled`; this ignores the alternate UTC cron slot unless it corresponds to 9:30 AM Eastern Time. The workflow has separate 13:30 UTC and 14:30 UTC schedules to cover daylight and standard time because GitHub cron uses UTC. Manual workflow dispatch runs immediately.

The runner first finalizes experiments whose inclusive end date has arrived, then checks whether the market is open. On an open market day, it initializes starting control portfolios by investing their available cash, then records the daily state and processes AI portfolios. Finalization uses the last successfully saved quote values so it can finish after market close. Dates and schedule checks use `America/New_York` (Eastern Time), not the machine's local timezone.

Daily processing is idempotent by ET date: saved snapshots mark portfolios as processed, and CSV date checks avoid duplicate state rows. An exclusive lock stops overlapping local processes. In AI decisions, quote access is limited to the Finnhub quote tool. A proposed decision is checked against cash and holdings; invalid decisions or failed executions are retried up to three times. If a required credential is missing, an API call fails, or validation still fails after retries, the CLI exits nonzero and prints an actionable error without printing API keys.

## Checks

Run the project checks before submitting changes:

```sh
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest --cov
```

The coverage configuration requires at least 70% coverage. Tests use mocked market and AI clients and should not contact external services.
