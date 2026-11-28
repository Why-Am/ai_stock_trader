# SPEC.md

## Idea

An AI stock trading experiment platform.

## Dates

- All dates and times are in ET unless otherwise specified

## Experiment

Each experiment has:

- One or more stock portfolios
- A start date and an end date
- Its own folder, containing the data for each portfolio involved
	- It should be placed either in the "experiments/active" directory or the "experiments/finished" directory, depending on its status
    - Inside there should be a file `[experiment name].json` containing the start date and end date

## Stock Portfolio

There are two types of stock portfolios: "AI-managed" and "control." An AI-managed portfolio is entirely managed by AI. A control portfolio simply holds a single stock for the length of the experiment.

Every type of stock portfolio has:

- An amount of money available to trade
    - This must be nonnegative.
- Stock holdings

An AI-managed portfolio also has:

- A strategy document, stored as `[portfolio name]_strategy.md`
    - After creation, this document should not be changed by the program.

A portfolio's state is defined as its total value, holdings, and available balance.

Portfolios can only perform the following trade actions:

- Buy
- Sell

Fractional shares are allowed and fees are disregarded for simplicity.

## Daily Run

A Github Actions job runs at 9:30 AM ET every day.

First, it checks if the current date is greater than or equal to any of the end dates of the experiments. If so, it records the final state of those experiments and ends them.

Then it checks if the stock market is open. If it isn't, it ends the run there.

Then it checks if any experiments are starting (start date <= current date). If so, then it initializes any control portfolios within those experiments by spending all their available money on their specified stocks.

Finally, for each portfolio:

1. If it is an AI-managed portfolio:
    1. Before making trades, record the date and the portfolio's state in `[portfolio name]_state.csv`
    2. Give it the prompt alongside the market news
    3. AI requests stock quotes via tool calls
    4. Receive its trades and its summarized explanation
    5. Execute the trades
        1. If they fail, tell the AI to try again. If it still fails after three tries, the CI run should report failure.
    6. Record the date, trades, and explanation in `[portfolio name]_trades.csv`
2. If it is a control portfolio:
    1. Record the date and the portfolio's state in `[portfolio name]_state.csv`

Daily runs should be idempotent.

If failure occurs, the CI run should report failure, including the reason for it.

## Experiment Creation

A script in the repository called `create_new_experiment.py` sets up a new experiment. Configuration options include:

- Name of the experiment
- Start date and end date
- For each portfolio:
    - Its name
	- What type of portfolio it is (AI-managed or control)
	- How much starting money it has
	- If AI-managed, its strategy
	- If control, the stock it should hold (validate the ticker)

It should create the experiment's folder and initialize the files within.
