# SPEC.md

## Idea

An AI stock trading experiment platform.

## Experiment

Each experiment has:

- One or more stock portfolios
- A start date and an end date
- Its own folder, containing the data for each portfolio involved
	- It should be placed either in the "experiments/active" directory or the "experiments/finished" directory, depending on its status

## Stock Portfolio

There are two types of stock portfolios: "AI-managed" and "control." An AI-managed portfolio is entirely managed by AI. A control portfolio simply holds a single stock for the length of the experiment.

Every type of stock portfolio has:

- An amount of money available to trade
- Stock holdings

An AI-managed portfolio also has:

- A read-only strategy document, stored as `[portfolio name]_strategy.md`

Portfolios can perform the following trade actions:

- Buy
- Sell

## Daily Run

A Github Actions job runs at 3:30 PM ET every day. It first checks if the stock market was open that day. If it wasn't, it ends there. If it was, then it does the following:

1. Get the active experiments
	1. If an experiment's end date has been reached, record the final state of its portfolios and end it
	2. If a control experiment is starting, spend all its available money on its specified stock.
2. For each portfolio:
	1. If it is an AI-managed portfolio:
		1. Record the date, its total value, holdings, and available balance in `[portfolio name]_state.csv`
		2. Give it the prompt alongside the market news
		3. Receive its trades and its summarized explanation
		4. Execute the trades
			1. If they fail, tell the AI to try again
		5. Record the date, trades, and explanation in `[portfolio name]_trades.csv`
	2. If it is a control portfolio:
		1. Record the date, its total value, holdings, and available balance in `[portfolio name]_state.csv`

A script in the repository called `create_new_experiment.py` sets up a new experiment. Configuration options include:

- How many days the experiment should run for
- For each portfolio:
	- What type of portfolio it is (AI-managed or control)
	- How much starting money it has
	- If AI-managed, its strategy
	- If control, the stock it should hold
