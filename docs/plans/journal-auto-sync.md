# Plan: Auto-Sync from Alpacalyzer to Stock Journal

## Problem

The integration between alpacalyzer (algo trader) and my-stock-journal (analytics/journal app) is currently manual: a CSV export script (`scripts/export-alpaca-to-csv.ts` in the journal repo) pulls from Alpaca's API and parses unstructured log files to reconstruct trade context. This means:

- Agent reasoning, confidence scores, and decision chains are lost or reduced to ad-hoc log parsing
- No visibility into _why_ the algo made a decision — only _what_ it traded
- Sync is manual and delayed — you run a script, get a CSV, import it
- The rich structured event data alpacalyzer already produces (`events.jsonl`) is completely unused

## Goal

Replace the manual CSV export/import flow with a real-time auto-sync that pushes structured trade decisions (with full agent reasoning and decision context) from alpacalyzer directly into the journal app's API.

---

## Source: What Alpacalyzer Already Has

Alpacalyzer has a mature event system (`src/alpacalyzer/events/`) that emits Pydantic-modeled events to `logs/events.jsonl` via a singleton `EventEmitter` with pluggable `EventHandler` instances. The relevant events for the journal:

| Event                  | Key Data                                                                              | When Emitted                                                                     |
| ---------------------- | ------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| `SignalGeneratedEvent` | ticker, action, confidence, source, strategy, reasoning                               | After hedge fund analysis produces a signal                                      |
| `AgentReasoningEvent`  | agent name, tickers, full reasoning dict                                              | Each agent (Technical, Fundamental, Sentiment, Buffett, etc.) completes analysis |
| `EntryTriggeredEvent`  | ticker, side, qty, entry/stop/target prices, reason                                   | Entry conditions met, order about to be placed                                   |
| `OrderFilledEvent`     | ticker, order_id, filled_qty, avg_price                                               | Order filled by broker                                                           |
| `ExitTriggeredEvent`   | ticker, entry/exit prices, P&L, P&L%, hold_duration, reason, urgency, exit_mechanism  | Position closed                                                                  |
| `PositionClosedEvent`  | ticker, side, qty, entry/exit prices, P&L, P&L%, hold_duration, strategy, exit_reason | Final trade outcome                                                              |
| `LLMCallEvent`         | agent, model, latency_ms, total_tokens, cost                                          | Each LLM call (cost tracking)                                                    |

The hedge fund pipeline also produces structured intermediate data:

- `AnalystSignal` per agent: `{signal, confidence, reasoning}` (9 agents: Technical, Fundamental, Sentiment, Ben Graham, Bill Ackman, Cathie Wood, Charlie Munger, Warren Buffett, Quant)
- `PortfolioDecision`: `{ticker, action, quantity, confidence (0-100), reasoning}`
- `TradingStrategy`: `{ticker, quantity, entry_point, stop_loss, target_price, risk_reward_ratio, strategy_notes, trade_type, entry_criteria[]}`

---

## Receiver: What the Journal App Has

The journal app (`kimrejstrom/my-stock-journal`) is a TypeScript monorepo:

```
my-stock-journal/
├── apps/
│   ├── api/          # Hono API server (Node.js), Clerk auth, rate limiting, pino logging
│   └── web/          # React/Vite frontend (Tailwind, shadcn/ui)
├── packages/
│   ├── db/           # Drizzle ORM + PostgreSQL (docker-compose)
│   └── types/        # Shared Zod schemas (@repo/types)
```

### Current Trade Schema (`packages/db/src/schema/trades.ts`)

```
id (uuid), userId (uuid FK→users), ticker, side (LONG|SHORT), status (OPEN|WIN|LOSS),
shares, entryPrice, exitPrice, entryTotal, exitTotal,
realizedPnl, realizedPnlPercent,
entryDate, exitDate,
targetPrice, stopPrice, setupNotes,
exitValidity, notes, tags (text[])
```

### Existing API (`apps/api/`)

- `POST /api/trades` — create trade (Zod-validated via `createTradeSchema`)
- `PUT /api/trades/:id` — update trade via `TradeUpdateService` (auto-calculates P&L, auto-derives WIN/LOSS status from P&L sign, uses `SELECT ... FOR UPDATE` row locking)
- `POST /api/trades/import` — CSV import via `CsvImportService` (deduplicates on `ticker + DATE(entryDate)`, batched inserts)
- `GET /api/trades` — list with filtering/pagination/sorting
- Auth: Clerk JWT → internal UUID lookup via `authMiddleware`. Can be disabled with `DISABLE_AUTH=true` (non-production only). Webhooks route uses Svix signature verification instead.
- Rate limiting: global (100/min), trades (30/min), import (5/min), webhooks (50/min)
- CORS: configurable via `ALLOWED_ORIGINS` env var

### Existing Frontend (`apps/web/`)

- `TradeTable.tsx` — main trade list
- `TradeDetailModal.tsx` — trade detail view with candle chart
- `TradeDetailChart.tsx` — candlestick chart for individual trades
- `ImportModal.tsx` — CSV import UI
- `Stats.tsx` — performance analytics page
- `Calendar.tsx` — calendar view of trades

### Existing CSV Export Flow (what we're replacing)

`scripts/export-alpaca-to-csv.ts` in the journal repo:

1. Fetches filled orders from Alpaca API
2. Parses `./logs/` directory for unstructured log lines to extract setup notes, targets, stops
3. Matches buy/sell orders into trades
4. Generates CSV → manual import via `POST /api/trades/import`

The log parsing is fragile — it regex-matches lines like `"Ticker: TSM, Trade Type: long, Quantity: 15, Entry Point: 315.58..."` and hopes the format doesn't change.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      ALPACALYZER                                 │
│                                                                  │
│  EventEmitter ──→ JournalSyncHandler (new EventHandler)         │
│                      │                                           │
│                      │ Collects events per-ticker into           │
│                      │ TradeDecisionRecord (new Pydantic model)  │
│                      │                                           │
│                      ▼                                           │
│               JournalSyncClient (new)                            │
│                 POST /api/sync/trades ──────────────────────┐    │
│                                                              │    │
└──────────────────────────────────────────────────────────────┼────┘
                                                               │
                                                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                    MY-STOCK-JOURNAL                               │
│                                                                  │
│  POST /api/sync/trades (new route, API key auth)                │
│    │                                                             │
│    ├─ Validates payload via Zod (syncTradeSchema)               │
│    ├─ Upserts trade (match on ticker + DATE(entryDate) + side)  │
│    │   ├─ No match → INSERT new OPEN trade with decisionContext │
│    │   └─ Match found → UPDATE with exit data + decisionContext │
│    ├─ P&L calculated by existing TradeUpdateService logic       │
│    └─ Returns created/updated trade                             │
│                                                                  │
│  Existing GET /api/trades now includes decisionContext field    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Push vs Pull

Push (alpacalyzer → journal API) because:

- Alpacalyzer already has the event system — we just add another `EventHandler`
- No polling, no cron, no stale data
- Events fire at the exact moment decisions happen
- The journal already has an API that accepts trade creation

### Why Not FastAPI in Alpacalyzer?

The algo is a long-running process with a `schedule` loop. Bolting an HTTP server onto it adds complexity for no gain. The journal already has an API. Push to it.

### Auth Model: How Push Works with Clerk

The journal app has two existing auth paths:

1. **Clerk JWT (user-facing)** — browser sends JWT, `authMiddleware` extracts the Clerk ID, looks up the internal user UUID via `SELECT id FROM users WHERE clerk_id = ?`, sets `userId` in context. All trade CRUD is scoped to that UUID.
2. **Webhooks (M2M)** — `POST /api/webhooks/clerk` bypasses Clerk entirely, verifies via Svix signature. No `userId` needed because it manages user records, not trades.

The sync endpoint follows the webhook pattern — it's machine-to-machine, not user-facing. Alpacalyzer doesn't have a Clerk session or JWT. So we use:

- **API key auth** (`X-API-Key` header) — simple shared secret, validated by the sync middleware
- **`SYNC_USER_ID` env var** on the journal side — maps all synced trades to a specific internal user UUID

In practice: you set `SYNC_USER_ID=<your-user-uuid>` in the journal's `.env`. That's the UUID of your user record (the one Clerk created via the webhook when you signed up). All trades pushed from alpacalyzer get `userId = SYNC_USER_ID`. When you log into the journal with Clerk, you see those trades because they belong to your user.

```
alpacalyzer (EntryTriggeredEvent fires)
  → JournalSyncHandler builds TradeDecisionRecord
  → JournalSyncClient POSTs to journal API with X-API-Key header
  → journal sync route validates API key
  → sets userId = SYNC_USER_ID from env
  → inserts trade with that userId
  → you see it in the journal UI (logged in via Clerk as that same user)
```

This works because it's a single-user setup — one algo instance, one journal user. If multi-user is ever needed (multiple algo instances → different journal accounts), add a `user_id` field to the sync payload and validate it against the API key's permissions. Not the current need.

---

## Changes — Alpacalyzer Side

### 1. New Pydantic Models

Location: `src/alpacalyzer/sync/models.py`

```python
class AgentSignalRecord(BaseModel):
    """One agent's contribution to the decision."""
    agent: str                          # e.g. "technical_analyst", "warren_buffett"
    signal: str | None                  # "bullish", "bearish", "neutral"
    confidence: float | None            # 0-100
    reasoning: dict | str | None        # Full reasoning output

class DecisionContext(BaseModel):
    """The full decision chain for a trade."""
    agent_signals: list[AgentSignalRecord]       # All 9 agents' votes
    portfolio_decision: dict | None              # PortfolioDecision as dict
    risk_assessment: dict | None                 # Risk manager output
    strategy_params: dict | None                 # TradingStrategy as dict (entry_criteria, risk_reward_ratio, etc.)
    scanner_source: str | None                   # "reddit", "social", "technical", "finviz"
    scanner_reasoning: str | None                # Why this ticker was surfaced
    llm_costs: list[dict] | None                 # LLMCallEvent summaries [{agent, model, latency_ms, tokens, cost}]

class TradeDecisionRecord(BaseModel):
    """Complete trade record for journal sync. Sent on entry and updated on exit."""
    # Trade identification
    ticker: str
    side: str                           # "LONG" or "SHORT"
    shares: int

    # Pricing (decimal strings for precision, matching journal's format)
    entry_price: str
    exit_price: str | None = None
    target_price: str | None = None
    stop_price: str | None = None

    # Timing (ISO 8601)
    entry_date: str
    exit_date: str | None = None

    # Outcome (populated on close)
    status: str = "OPEN"                # "OPEN", "WIN", "LOSS"
    realized_pnl: str | None = None
    realized_pnl_pct: str | None = None
    hold_duration_hours: float | None = None
    exit_reason: str | None = None
    exit_mechanism: str | None = None   # "dynamic_exit" or "bracket_order"

    # Decision context — the key differentiator
    decision_context: DecisionContext

    # Metadata
    strategy_name: str
    setup_notes: str | None = None      # TradingStrategy.strategy_notes
    tags: list[str] = ["alpaca", "automated"]
```

### 2. New EventHandler: `JournalSyncHandler`

Location: `src/alpacalyzer/sync/handler.py`

Plugs into the existing `EventEmitter` singleton. Collects events per-ticker and pushes to the journal API at key moments:

- Accumulates `AgentReasoningEvent` and `SignalGeneratedEvent` into a per-ticker `DecisionContext` buffer during the analysis phase
- On `EntryTriggeredEvent` → builds `TradeDecisionRecord` with full context, POSTs to journal (creates OPEN trade)
- On `ExitTriggeredEvent` / `PositionClosedEvent` → POSTs update with exit data (journal derives WIN/LOSS from P&L)
- Clears the per-ticker buffer after successful sync

```python
class JournalSyncHandler(EventHandler):
    def __init__(self, client: JournalSyncClient):
        self.client = client
        self._pending_context: dict[str, DecisionContext] = {}  # ticker → accumulated context
        self._synced_trades: dict[str, str] = {}                # ticker → journal trade ID (for updates)

    def handle(self, event: TradingEvent) -> None:
        try:
            if event.event_type == "AGENT_REASONING":
                self._accumulate_reasoning(event)
            elif event.event_type == "SIGNAL_GENERATED":
                self._accumulate_signal(event)
            elif event.event_type == "ENTRY_TRIGGERED":
                self._sync_entry(event)
            elif event.event_type in ("EXIT_TRIGGERED", "POSITION_CLOSED"):
                self._sync_exit(event)
            elif event.event_type == "LLM_CALL":
                self._accumulate_llm_cost(event)
        except Exception as e:
            logger.warning(f"journal sync failed | error={e}")
            # Never crash the trading loop
```

### 3. New Client: `JournalSyncClient`

Location: `src/alpacalyzer/sync/client.py`

Simple HTTP client using `requests` (already a dependency). POSTs `TradeDecisionRecord` to the journal API.

- Retry with exponential backoff (3 attempts)
- 10s timeout per request
- Failed syncs logged to `logs/sync_failures.jsonl` for manual replay
- All exceptions caught — sync failure never impacts trading

Config via env vars:

- `JOURNAL_API_URL` — e.g. `http://localhost:3000`
- `JOURNAL_SYNC_API_KEY` — shared secret for M2M auth

### 4. Wire It Up

In `EventEmitter.get_instance()` or CLI startup, conditionally add the handler:

```python
if os.getenv("JOURNAL_API_URL"):
    from alpacalyzer.sync.client import JournalSyncClient
    from alpacalyzer.sync.handler import JournalSyncHandler
    client = JournalSyncClient(
        base_url=os.environ["JOURNAL_API_URL"],
        api_key=os.environ.get("JOURNAL_SYNC_API_KEY", ""),
    )
    emitter.add_handler(JournalSyncHandler(client))
```

Completely opt-in. No env vars = no sync = zero impact on existing behavior.

---

## Changes — Journal App Side

### 1. New DB Column: `decisionContext` (JSONB)

Migration for `packages/db/src/schema/trades.ts`:

```typescript
import { jsonb } from 'drizzle-orm/pg-core';

// Add to trades table:
decisionContext: jsonb('decision_context'),  // Full algo decision chain
```

JSONB because:

- Queryable (`WHERE decision_context->>'scanner_source' = 'reddit'`)
- Schema-flexible — additive changes in alpacalyzer don't require journal migrations
- PostgreSQL handles it efficiently

### 2. New Zod Schema: `syncTradeSchema`

Location: `packages/types/src/sync.ts`

TypeScript equivalent of `TradeDecisionRecord` for validation on the receiving end. Uses `.passthrough()` on the `decisionContext` object for forward compatibility.

```typescript
export const agentSignalRecordSchema = z.object({
  agent: z.string(),
  signal: z.string().nullable(),
  confidence: z.number().nullable(),
  reasoning: z.union([z.record(z.unknown()), z.string()]).nullable(),
});

export const decisionContextSchema = z
  .object({
    agent_signals: z.array(agentSignalRecordSchema),
    portfolio_decision: z.record(z.unknown()).nullable(),
    risk_assessment: z.record(z.unknown()).nullable(),
    strategy_params: z.record(z.unknown()).nullable(),
    scanner_source: z.string().nullable(),
    scanner_reasoning: z.string().nullable(),
    llm_costs: z.array(z.record(z.unknown())).nullable(),
  })
  .passthrough(); // Forward compat

export const syncTradeSchema = z.object({
  ticker: z.string().min(1).max(10),
  side: z.enum(["LONG", "SHORT"]),
  shares: z.number().int().positive(),
  entry_price: z.string(),
  exit_price: z.string().optional().nullable(),
  target_price: z.string().optional().nullable(),
  stop_price: z.string().optional().nullable(),
  entry_date: z.string().datetime(),
  exit_date: z.string().datetime().optional().nullable(),
  status: z.enum(["OPEN", "WIN", "LOSS"]).default("OPEN"),
  realized_pnl: z.string().optional().nullable(),
  realized_pnl_pct: z.string().optional().nullable(),
  hold_duration_hours: z.number().optional().nullable(),
  exit_reason: z.string().optional().nullable(),
  exit_mechanism: z.string().optional().nullable(),
  decision_context: decisionContextSchema,
  strategy_name: z.string(),
  setup_notes: z.string().optional().nullable(),
  tags: z.array(z.string()).default(["alpaca", "automated"]),
});
```

### 3. New API Route: `POST /api/sync/trades`

Location: `apps/api/src/routes/sync.ts`

A dedicated sync endpoint (separate from user-facing CRUD) that:

- Authenticates via `X-API-Key` header (simple shared secret, not Clerk — this is M2M, not user-facing)
- Accepts `syncTradeSchema` JSON body
- Upserts: matches on `ticker + DATE(entryDate) + side` (same dedup pattern as existing `CsvImportService`)
  - No match → INSERT new trade with `decisionContext` JSONB
  - Match found + exit data present → UPDATE existing trade with exit price, P&L (reuse `TradeUpdateService` logic), and merge `decisionContext`
- Returns the created/updated trade

Auth middleware for sync:

```typescript
const apiKeyAuth = createMiddleware(async (c, next) => {
  const apiKey = c.req.header("X-API-Key");
  const expected = process.env.SYNC_API_KEY;
  if (!expected || apiKey !== expected) {
    return c.json({ error: "Unauthorized" }, 401);
  }
  // Set userId to the configured sync user
  c.set("userId", process.env.SYNC_USER_ID || DEV_TEST_USER_ID);
  await next();
});
```

Mount in `apps/api/src/index.ts`:

```typescript
// Sync routes - API key auth (no Clerk)
baseApp.use("/api/sync/*", syncRateLimiter);
const app = baseApp
  .route("/api/sync", syncRouter) // new
  .route("/api/webhooks", webhooksRouter);
// ... existing routes
```

### 4. Update Trade Response to Include `decisionContext`

Update `formatTradeResponse()` in `apps/api/src/utils/formatters.ts` to pass through the new JSONB field. Update the `tradeSchema` in `packages/types/src/index.ts` to include `decisionContext: z.record(z.unknown()).nullable()`.

### 5. New Env Vars for Journal App

Add to `.env.example`:

```bash
# Algo Sync Configuration
# API key for machine-to-machine sync from alpacalyzer
SYNC_API_KEY=your_shared_secret_here
# Internal user UUID that synced trades belong to
SYNC_USER_ID=00000000-0000-0000-0000-000000000001
```

---

## Implementation Order

This is a cross-repo feature. Split into focused PRs:

### Phase 1: Alpacalyzer — Sync Client (this repo)

1. [#166](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/166) — `TradeDecisionRecord`, `DecisionContext`, `AgentSignalRecord` Pydantic models
2. [#167](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/167) — `JournalSyncClient` (HTTP client with retry/timeout/failure logging)
3. [#168](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/168) — `JournalSyncHandler` (EventHandler that accumulates context and pushes) + wire into EventEmitter (opt-in via `JOURNAL_API_URL` env var) + update `.env.example`

### Phase 2: Journal App — Sync Endpoint (my-stock-journal repo)

1. [my-stock-journal#118](https://github.com/kimrejstrom/my-stock-journal/issues/118) — DB migration (`decisionContext` JSONB column) + `syncTradeSchema` types + `POST /api/sync/trades` endpoint with API key auth and upsert logic + env vars
2. [my-stock-journal#119](https://github.com/kimrejstrom/my-stock-journal/issues/119) — Expose `decisionContext` in existing trade API responses and types

### Phase 3: Journal App — Decision Visibility UI (my-stock-journal repo)

- [my-stock-journal#120](https://github.com/kimrejstrom/my-stock-journal/issues/120) — `TradeDetailModal` decision context UI (agent signals, decision chain timeline, strategy params, LLM costs)
- (Not blocking Phase 1-2)

---

## What This Unlocks

Per-trade in the journal:

- Which agents voted bullish/bearish/neutral and their confidence scores
- Portfolio manager's final reasoning
- Risk manager's assessment
- Trading strategist's entry criteria and risk/reward ratio
- Which scanner surfaced the ticker and why
- LLM model, latency, token count, and cost per agent call
- Exit mechanism (bracket order vs dynamic exit) and reason
- Hold duration and P&L — all structured, all queryable

---

## Risks & Mitigations

| Risk                                       | Mitigation                                                                                                                                                                        |
| ------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Sync failure crashes trading loop          | Handler catches all exceptions, logs warning, continues. Trading always takes priority.                                                                                           |
| Journal API down during trading            | Client retries with backoff. Failed syncs logged to `logs/sync_failures.jsonl` for manual replay.                                                                                 |
| Schema drift between repos                 | `decisionContext` stored as JSONB — additive changes don't break. Zod uses `.passthrough()` for forward compat.                                                                   |
| Auth between services                      | Simple API key for M2M (both run locally or same network). Separate from Clerk user auth. Can upgrade to mTLS later.                                                              |
| Duplicate trades on re-sync                | Upsert on `ticker + DATE(entryDate) + side`. Same dedup pattern as existing `CsvImportService`. Idempotent by design.                                                             |
| Large decision context payloads            | Agent reasoning dicts can be verbose. JSONB handles it fine. Can add size cap if needed.                                                                                          |
| Same ticker traded multiple times same day | The dedup key `ticker + DATE(entryDate) + side` matches the existing CSV import behavior. If this becomes an issue, add `client_order_id` to the sync payload for exact matching. |

## Out of Scope

- No-go decisions (explicitly excluded per requirements)
- Journal app frontend changes (Phase 3, separate issues)
- Historical backfill of existing trades (follow-up script)
- Real-time websocket streaming to journal (HTTP push is sufficient)
