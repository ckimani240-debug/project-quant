# PRINCIPLE 001 — CAPITAL PRESERVATION

Project: Project Quant
Research status: PROPOSED — NOT YET VALIDATED
Category: Risk management
Initial markets: BTC/USDT and ETH/USDT

## 1. Research origins

Primary research source:

Jack Schwager interview:
Lessons Learned From Market Wizards
Charles Schwab, 30 January 2026

https://www.schwab.com/learn/story/lessons-learned-from-market-wizards-with-jack-schwager

Additional research source:

Stanley Druckenmiller:
Hard Lessons — Invest, Then Investigate
Morgan Stanley, 27 February 2026

https://www.morganstanley.com/insights/videos/hard-lessons/duquesne-stan-druckenmiller-iliana-bouzali

## 2. Extracted lessons

### Lesson A — Money management matters

Schwager explains that successful trading requires
sound money management, not merely a good methodology.

Project Quant interpretation:

A strategy must never be allowed to bypass risk controls.

### Lesson B — Define the exit before entry

Schwager highlights Bruce Kovner's principle:
know where you will exit before entering a position.

Project Quant interpretation:

Every proposed trade must have a predefined invalidation
level and exit plan before approval.

### Lesson C — Change your mind when evidence changes

Druckenmiller describes the importance of changing
course when the facts on the ground shift.

Project Quant interpretation:

A previous market prediction must not influence a new
analysis when the evidence has changed.

## 3. Proposed engineering requirements

1. Reject trades without a valid exit plan.
2. Calculate position size before trade approval.
3. Include estimated fees and slippage.
4. Enforce portfolio exposure limits.
5. Enforce daily loss limits.
6. Detect invalidated trade assumptions.
7. Reassess recommendations using fresh market data.
8. Permit WAIT and NO TRADE outcomes.
9. Never increase position size to recover losses.
10. Preserve an auditable record of every decision.

## 4. Proposed tests

Test A:
Attempt to approve a trade without a stop-loss.

Expected result:
The trade is rejected.

Test B:
Attempt a trade exceeding the maximum risk allowance.

Expected result:
The trade is rejected.

Test C:
Attempt a trade exceeding portfolio exposure limits.

Expected result:
The trade is rejected.

Test D:
Change market conditions so that the original trade
thesis is no longer valid.

Expected result:
The system flags the thesis for reassessment.

Test E:
Calculate position sizing after transaction costs.

Expected result:
The system reports the actual estimated risk,
including fees and slippage.

## 5. Research limitations

These principles are derived from interviews and
must not be interpreted as proof of profitability.

The proposed software rules are Project Quant's
interpretations, not necessarily the traders'
exact personal trading systems.

Stop-loss execution can differ from the intended
price during gaps, volatility and illiquid conditions.

## 6. Validation status

Source review: INITIAL
Engineering implementation: NOT STARTED
Backtesting: NOT STARTED
Out-of-sample validation: NOT STARTED

Final status: PROPOSED — NOT APPROVED FOR LIVE USE

## 7. Final research conclusion

Project Quant must calculate and understand risk
before considering a trading opportunity.

Capital preservation takes priority over generating
more trading signals.
