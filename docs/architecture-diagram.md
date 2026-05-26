# Robinhood AI Advisor - Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              USER INTERFACE                                       │
│                                                                                 │
│  ┌──────────────────┐                    ┌──────────────────┐                   │
│  │   Telegram App   │                    │   Local Dev Bot  │                   │
│  │                  │                    │  (polling mode)   │                   │
│  │  - Natural lang  │                    │                  │                   │
│  │  - Commands      │                    │  - /score        │                   │
│  │  - Morning brief │                    │  - /portfolio    │                   │
│  └────────┬─────────┘                    └────────┬─────────┘                   │
│           │                                       │                              │
│           │ Webhook                               │ Direct                       │
│           │                                       │                              │
└───────────┼───────────────────────────────────────┼──────────────────────────────┘
            │                                       │
            ▼                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           AWS LAMBDA (Entry Point)                               │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  lambda_handler.py                                                       │   │
│  │                                                                          │   │
│  │  ┌─────────────────────┐  ┌─────────────────────┐                       │   │
│  │  │ handle_telegram_    │  │ run_morning_brief() │                       │   │
│  │  │ webhook()           │  │  - 7am daily        │                       │   │
│  │  │                     │  │  - Score portfolio  │                       │   │
│  │  │ - Route commands    │  │  - Save snapshot    │                       │   │
│  │  │ - Route to agents   │  │  - Send brief       │                       │   │
│  │  └──────────┬──────────┘  └──────────┬──────────┘                       │   │
│  │             │                        │                                  │   │
│  │             │                        │                                  │   │
│  │             │           ┌────────────▼────────────┐                      │   │
│  │             │           │ run_afternoon_scan()    │                      │   │
│  │             │           │  - 4pm daily           │                      │   │
│  │             │           │  - Stop-loss check     │                      │   │
│  │             │           │  - Alert if -15%       │                      │   │
│  │             │           └────────────────────────┘                      │   │
│  │             │                                                        │   │
│  │             └────────────────────────────────────────────────────┘    │   │
│  │                                                                          │   │
│  │  load_secrets() → AWS SSM Parameter Store                              │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
            │
            │ Natural language queries
            ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          LANGGRAPH AGENTS (Gemini 2.5 Flash)                    │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  Supervisor Agent (agents/supervisor.py)                                │   │
│  │                                                                          │   │
│  │  Classifies question using Gemini:                                       │   │
│  │  - PORTFOLIO  → portfolio_agent.py                                      │   │
│  │  - ROTATION   → rotation_agent.py                                       │   │
│  │  - SCREENER   → screener_agent.py                                       │   │
│  │  - TRADE      → record_trade()                                          │   │
│  │  - OTHER      → help message                                           │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│           │                    │                    │                          │
│           ▼                    ▼                    ▼                          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                   │
│  │ Portfolio    │    │ Rotation     │    │ Screener     │                   │
│  │ Agent        │    │ Agent        │    │ Agent        │                   │
│  │              │    │              │    │              │                   │
│  │ - Holdings   │    │ - Sell/buy   │    │ - Find new   │                   │
│  │ - Scores     │    │   decisions  │    │   stocks     │                   │
│  │ - Values     │    │ - Tax impact │    │ - Compare    │                   │
│  │ - Tax        │    │ - Position   │    │   stocks     │                   │
│  │ - Performance│    │   sizing     │    │              │                   │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘                   │
│         │                    │                    │                          │
└─────────┼────────────────────┼────────────────────┼──────────────────────────┘
          │                    │                    │
          ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            DATA SOURCES                                          │
│                                                                                 │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐              │
│  │ Robinhood API    │  │  yfinance        │  │  Finnhub API     │              │
│  │                  │  │                  │  │                  │              │
│  │ - Holdings       │  │ - Prices         │  │ - Analyst recs   │              │
│  │ - Total value    │  │ - History        │  │ - Earnings       │              │
│  │ - Session token  │  │ - Moving avg     │  │ - Buy/sell/hold  │              │
│  │   (SSM stored)   │  │ - RSI            │  │                  │              │
│  │                  │  │ - 52-week perf   │  │                  │              │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘              │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
          │                    │                    │
          ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        SCORING ENGINE                                            │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  scoring/engine.py                                                        │   │
│  │                                                                          │   │
│  │  score_stock(ticker) → final_score (0-10)                                 │   │
│  │                                                                          │   │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐       │   │
│  │  │ Fundamental      │  │ Momentum         │  │ Sentiment        │       │   │
│  │  │ Scorer (40%)     │  │ Scorer (35%)     │  │ Scorer (25%)     │       │   │
│  │  │                  │  │                  │  │                  │       │   │
│  │  │ - Revenue growth │  │ - 50/200 MA      │  │ - Analyst recs   │       │   │
│  │  │ - Earnings       │  │ - RSI            │  │ - Buy/sell/hold  │       │   │
│  │  │ - PE ratio       │  │ - 52-week perf   │  │                  │       │   │
│  │  │ - Profit margin  │  │                  │  │                  │       │   │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘       │   │
│  │           │                    │                    │                  │   │
│  │           └────────────────────┼────────────────────┘                  │   │
│  │                                ▼                                     │   │
│  │                    Combined score → Category:                          │   │
│  │                    - 7.0+      → HOLD                                   │   │
│  │                    - 5.0-6.9   → WATCH                                  │   │
│  │                    - <5.0      → ROTATE                                 │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      PORTFOLIO MANAGEMENT                                         │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  portfolio/rotation_engine.py                                           │   │
│  │                                                                          │   │
│  │  Position Sizing Rules:                                                   │   │
│  │  - Score 8-10  → max 12% of portfolio                                    │   │
│  │  - Score 7-8   → max 8% of portfolio                                     │   │
│  │  - Score 6-7   → max 5% of portfolio                                     │   │
│  │  - Score 5-6   → max 3% of portfolio                                     │   │
│  │  - Score 4-5   → max 1% of portfolio                                     │   │
│  │  - Score <4    → exit completely                                         │   │
│  │                                                                          │   │
│  │  get_rotation_candidates() → Find oversized positions                    │   │
│  │  find_replacements()      → Suggest better stocks                        │   │
│  │  get_recommendation()      → YES/WAIT decision logic                      │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  portfolio/cost_basis_store.py                                          │   │
│  │                                                                          │   │
│  │  - Track average cost per stock (manual entry)                           │   │
│  │  - Calculate tax impact (short-term 22%, long-term 15%)                 │   │
│  │  - Stored in DynamoDB (replaces API cost basis)                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        STORAGE & INFRASTRUCTURE                                  │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  AWS DynamoDB                                                           │   │
│  │                                                                        │   │
│  │  Table: robinhood-ai-portfolio                                         │   │
│  │  - Daily score snapshots (date, ticker, score, category, price)        │   │
│  │  - Portfolio trend analysis (7-day, 30-day)                            │   │
│  │                                                                        │   │
│  │  Table: robinhood-ai-costbasis                                        │   │
│  │  - Manual cost basis entries (ticker, avg_cost, updated)               │   │
│  │  - Used for tax calculations                                            │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  AWS SSM Parameter Store (Encrypted Secrets)                           │   │
│  │                                                                        │   │
│  │  /robinhood-ai/finnhub_api_key                                         │   │
│  │  /robinhood-ai/gemini_api_key                                          │   │
│  │  /robinhood-ai/telegram_bot_token                                       │   │
│  │  /robinhood-ai/telegram_chat_id                                         │   │
│  │  /robinhood-ai/robinhood_username                                       │   │
│  │  /robinhood-ai/robinhood_password                                       │   │
│  │  /robinhood-ai/session_token (Robinhood session, refreshed manually)     │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  AWS EventBridge (Scheduling)                                           │   │
│  │                                                                        │   │
│  │  Rule 1: 7:00 AM ET daily → morning_brief                             │   │
│  │  Rule 2: 4:00 PM ET daily → afternoon_scan                             │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        NOTIFICATIONS                                             │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  notifications/morning_brief.py                                         │   │
│  │                                                                          │   │
│  │  send_morning_brief():                                                   │   │
│  │  - Portfolio value + change from yesterday                              │   │
│  │  - Portfolio score + 7-day trend                                         │   │
│  │  - HOLD/WATCH/ROTATE counts                                              │   │
│  │  - Action needed (oversized positions)                                   │   │
│  │  - Earnings warnings (within 14 days)                                    │   │
│  │  - Top 3 performers                                                     │   │
│  │  - Cost monitoring (Mondays only)                                       │   │
│  │  - Sent via Telegram Bot API                                            │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  monitoring/cost_monitor.py                                             │   │
│  │                                                                          │   │
│  │  - Track AWS costs (Lambda, DynamoDB, SSM)                             │   │
│  │  - Alert if approaching free tier limits                                │   │
│  │  - Weekly cost summary (Mondays)                                        │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘

===================================================================================

DATA FLOW EXAMPLES:

1. MORNING BRIEF (7am scheduled):
   EventBridge → Lambda → run_morning_brief()
     → Robinhood API (holdings, total value)
     → Scoring Engine (score all stocks)
     → DynamoDB (save snapshot)
     → Morning Brief (format message)
     → Telegram API (send message)

2. USER QUERY: "Should I sell SHOP?"
   Telegram → Lambda Webhook → Supervisor Agent
     → Route to Rotation Agent
       → Robinhood API (current holdings)
       → Scoring Engine (score SHOP)
       → Rotation Engine (position sizing, find replacement)
       → Cost Basis Store (tax impact)
       → Format recommendation
     → Telegram API (send response)

3. STOP-LOSS SCAN (4pm scheduled):
   EventBridge → Lambda → run_afternoon_scan()
     → Robinhood API (holdings)
     → Cost Basis Store (avg cost)
     → yfinance (current price)
     → Calculate % change from avg cost
     → If ≤ -15%: Alert via Telegram

===================================================================================

COST STRUCTURE ($0/month):

- AWS Lambda: Free tier (1M requests/month, 400K GB-sec/month)
  - Runs ~3 minutes/day total → well within limits

- AWS DynamoDB: Free tier (25GB storage, 200M read/write units/month)
  - Few hundred rows → well within limits

- AWS SSM Parameter Store: Free tier (10K parameters)
  - 7 parameters → well within limits

- AWS EventBridge: Free tier (1M custom events/month)
  - 2 events/day → well within limits

- Gemini 2.5 Flash: Free tier (1,500 requests/day)
  - ~50-100 requests/day → well within limits

- yfinance: Free (no API key needed)

- Finnhub: Free tier (60 calls/minute)
  - Rate limiting added (1.5s delay between calls)

- Telegram Bot API: Free

===================================================================================
