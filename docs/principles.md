# Golden Principles

Code invariants that every contributor (human or agent) must uphold. These are not process rules — they are structural properties of the codebase that, if violated, cause bugs or financial loss.

## 1. Every Position Has a Stop Loss

Every `EntryDecision(should_enter=True)` must include a `stop_loss` price. No exceptions. Unprotected positions expose the account to unlimited downside.

Enforced by: `scripts/lint_architecture.py` (rule `SAFETY-STOP-LOSS`)

## 2. Validate at Boundaries

All external data enters the system through Pydantic models. No raw dict access from API responses, LLM outputs, or scanner results. Parse first, use typed fields after.

Key boundaries:

- Alpaca API → `alpacalyzer.data.models` (TopTicker, TradingStrategy)
- LLM responses → `complete_structured()` with Pydantic response models
- Scanner output → `Opportunity` model via `OpportunityAggregator`

## 3. No YOLO Data Access

Use typed SDKs and structured output — never raw HTTP calls or untyped JSON parsing.

- Alpaca: Use `alpacalyzer.trading.alpaca_client` functions, not raw REST
- LLM: Use `LLMClient.complete_structured()`, not raw completions
- Events: Use typed event classes (`OrderFilledEvent`, `ErrorEvent`), not dict literals

## 4. Exits Before Entries in Execution Cycle

The `ExecutionEngine.run_cycle()` processes exits before entries. This frees capital and prevents overexposure. Never reorder the cycle.

See: `src/alpacalyzer/execution/engine.py` → `run_cycle()`

## 5. Agents Propose, Strategies Validate

Agents (GPT-4) propose trade setups. Strategies validate that the setup fits their philosophy. Strategies never override agent-calculated parameters (entry, stop, target, size).

See: [Architecture Overview](architecture/overview.md#agent-vs-strategy-decision-authority)

## 6. Shared Utilities Over Hand-Rolled Helpers

Use existing utilities before writing new ones:

- Logging: `alpacalyzer.utils.logger.get_logger()`
- Events: `alpacalyzer.events.emit_event()`
- LLM: `alpacalyzer.llm.client.LLMClient`
- Config: `alpacalyzer.strategies.config` for strategy parameters

## Enforcement

| Principle           | Automated Check                                     |
| ------------------- | --------------------------------------------------- |
| Stop loss           | `scripts/lint_architecture.py` (SAFETY-STOP-LOSS)   |
| Import boundaries   | `scripts/lint_architecture.py` (IMPORT-BOUNDARY)    |
| Boundary validation | `scripts/audit_principles.py` (BOUNDARY-VALIDATION) |
| File size           | `scripts/lint_architecture.py` (SIZE-LIMIT)         |

Run all checks:

```bash
uv run python scripts/lint_architecture.py
uv run python scripts/audit_principles.py
```
