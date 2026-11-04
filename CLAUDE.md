# Project Quant — Development Rules

Project Quant is a semi-automated cryptocurrency research and paper-trading
assistant. The user must approve every simulated trade.

## Non-negotiable safety rules

1. Real-money trading is disabled. Never implement live order execution.
2. Never execute a simulated trade without explicit user approval.
3. No leverage, margin, futures or borrowing.
4. Never hard-code or commit API keys, passwords or other secrets.
5. Use public market data initially. Do not request exchange credentials.
6. Display a clear NO TRADE recommendation when evidence is insufficient.
7. Never promise profits or describe a strategy as guaranteed to work.

## Trading configuration

- Starting virtual balance: 1,000 USDT.
- Initial assets: BTC/USDT and ETH/USDT.
- Trading styles: short-term and long-term research.
- Maximum portfolio exposure: 50%.
- Maximum risk per trade: 1% of portfolio value.
- Maximum daily simulated loss: 3%.
- Maximum drawdown: 15%.
- Simulated fee: 0.1% per trade side.
- Simulated slippage: 0.05% per trade side.

## Development standards

1. Build the application incrementally. Do not generate the entire system at once.
2. Explain the purpose of new files and important changes.
3. Keep modules small, readable and independently testable.
4. Validate inputs and handle missing or invalid market data.
5. Use historical data carefully. Never use future information in a backtest.
6. Include realistic fees and slippage in backtests.
7. Compare strategy results with a buy-and-hold benchmark.
8. Report drawdown, win rate, number of trades and other relevant risk metrics.
9. Write automated tests for important calculations and safety controls.
10. Do not silently change the project's existing architecture or settings.

## Workflow

- Inspect existing files before modifying them.
- Make one logical change at a time.
- Run relevant tests after each change.
- Explain test failures instead of hiding or bypassing them.
- Ask the user before making significant architectural changes.
- Never remove safety checks to make a test pass.

## Current development stage

The project is at its foundation stage. Build and test the virtual
portfolio and paper-trading components before developing advanced strategies.
