# Project Quant

A semi-automated crypto research, analysis and **paper-trading** assistant.
You approve every simulated trade. Real-money trading is disabled.

> Research tool only. Nothing here is financial advice or a promise of profit.

## Status
Foundation only: structure, rules (`CLAUDE.md`), settings and tests.
Next: virtual portfolio, then the paper-trading engine.

## Setup (Ubuntu WSL)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
```

## Structure
`config/` settings, `market_data/` data collection, `analysis/` indicators,
`strategies/` short- and long-term, `risk_management/`, `trading/` portfolio and
paper engine, `backtesting/`, `dashboard/` Streamlit, `tests/`, `data/` and `logs/` (git-ignored contents)

## Configuration
All settings are documented in `config/settings.py` (balance, fees, slippage, exposure
and loss limits). Future API credentials go in environment variables; see `.env.example`.
