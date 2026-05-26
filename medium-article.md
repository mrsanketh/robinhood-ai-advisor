# How I Built a $0/Month Agentic AI System That Manages My Stock Portfolio

It was a long weekend. Rain was hammering the windows. I had no plans.

I opened my brokerage app out of boredom and stared at my portfolio. Dozens of stocks. Some green. Some red. Some I bought because I read an article. Some because a friend mentioned them. Some I honestly could not remember why I owned.

I had no idea what to do with any of them.

I am a senior data engineer. I spend my days building AI pipelines and data platforms for a living. And yet I was completely clueless about my own portfolio.

So I did the only logical thing.

I closed my brokerage, opened my laptop, and started building.

---

## What I Wanted

I did not want a fancy dashboard I would never open. I did not want another app with alerts I would ignore.

I wanted something simple. Something that would text me every morning and tell me exactly what to do — or tell me to do nothing at all.

And I wanted to be able to ask it questions in plain English. Not click through menus. Not run scripts. Just type "should I sell [e-commerce stock]?" and get a real answer.

By Sunday evening, I had it.

## What I Built

Every morning at 7am, I get this in Telegram:

🌅 Good morning — May 24 2026
💰 Portfolio value: $XX,XXX
 ▲ +$348 from yesterday
📊 Portfolio score: 6.8/10
 ▲ +0.1 from last week
✅ HOLD: 14
👀 WATCH: 18
🔄 ROTATE: 3
⚡ Action needed:
 → [e-commerce stock] 4.57/10 — oversized position, consider trimming
 → [streaming stock] 6.02/10 — oversized position, consider trimming
⚠️ Earnings this week:
 → [software stock] — 2 days
 → [hardware stock] — 3 days
 Hold these positions until after earnings
🏆 Top performers:
 → Top scorer: 9.29/10
 → Second: 9.13/10
 → Third: 8.50/10

And then I can just ask:

"Should I sell [ticker]?"

The AI looks at [e-commerce stock]'s fundamentals, its price momentum, what analysts are saying, how big my position is relative to what it should be — and gives me a clear answer with reasoning and next steps.

My phone. No laptop. No manual research. 30 seconds every morning.

## How It Works

Scoring every stock

Every stock gets scored on three signals:

- Fundamentals (40%) — Is the business actually growing? Revenue trend, earnings, profit margins, PE ratio.
- Momentum (35%) — Is the price moving in the right direction? 50 and 200-day moving averages, RSI, 52-week performance.
- Sentiment (25%) — What do analysts think? Buy/hold/sell recommendations from Finnhub.

Combined into a score from 0 to 10. [top holding] scores 9.29. This stock scores 4.57. The difference is real — you can see it in the data.

Position sizing — the insight that changed everything

My first version flagged everything below a score of 5.0 as "sell immediately." This was wrong.

A stock can score 4.5 with a tiny position that is not worth selling. The real question is not just "is this stock weak?" — it is "is my position too big for what this stock deserves?"

Professional fund managers think in terms of position limits:

- Score 8.0–10.0: Max 12% of portfolio
- Score 7.0–8.0: Max 8% of portfolio
- Score 6.0–7.0: Max 5% of portfolio
- Score 5.0–6.0: Max 3% of portfolio
- Score 4.0–5.0: Max 1% of portfolio
- Score below 4.0: Exit position

This stock scores 4.57 — allowed maximum 1% of portfolio. If I hold 4.5% in it, that is the real problem. Trim it to the limit. Free up the capital. Put it somewhere better.

This one change made the recommendations genuinely useful.

LangGraph agents

Four AI agents handle all the natural language:

- Supervisor reads your message and figures out what you are asking
- Portfolio agent answers questions about your holdings and performance
- Rotation agent handles sell and buy decisions with full context
- Screener agent searches 550 quality stocks to find opportunities you do not own

All powered by Gemini 2.5 Flash. When you ask "should I sell [e-commerce stock]?" the supervisor routes it to the rotation agent, which checks the position size, estimates tax impact, finds the best replacement, and returns a clear recommendation.

The infrastructure — and why it costs $0

The system flows like this:

Your phone (Telegram) connects to AWS Lambda (Telegram webhook, always on)

Lambda routes to LangGraph agents, which use Gemini 2.5 Flash for AI

Agents pull data from yfinance and Finnhub (free market data)

Portfolio history and cost basis are stored in AWS DynamoDB

Secrets are encrypted in AWS SSM Parameter Store

Scheduling is handled by AWS EventBridge (7am and 4pm triggers)

Lambda runs for maybe 3 minutes a day total. DynamoDB stores a few hundred rows. Gemini free tier handles the AI calls. Everything within free tiers. $0/month permanently.

## The Hard Parts Nobody Talks About

Authentication is not trivial

The portfolio data API uses device-based authentication. AWS Lambda is not a persistent device — every invocation is a fresh container. The solution was to extract the session token after an approved login on my laptop, store it encrypted in AWS SSM, and have Lambda use the token directly. It expires every few months and takes 2 minutes to refresh.

Data quality issues

Stock splits cause API cost basis errors. Built a separate cost basis tracker where I enter my real average cost once and it saves to DynamoDB permanently. The API is used only for current prices.

Gemini rate limits changed

In December 2025, Google reduced free tier limits significantly — now 1,500 requests per day. During testing I hit the limit multiple times by running rapid tests. Added usage tracking and alerts at 80% of the daily limit.

Lambda zip size limits

AWS Lambda has a 250MB unzipped size limit. numpy and pandas alone take up 116MB. Solution: create a custom Lambda layer with just numpy and pandas, and exclude them from the main zip. Keeps the deployment under the limit.

## What I Learned

Building this in one rainy weekend forced me to move fast and make decisions.

The biggest lesson: the AI part was not the hard part. LangGraph is well-designed. Gemini 2.5 Flash is accurate and fast. The hard part was everything else — authentication edge cases, data quality issues, deployment size constraints, API rate limits.

This is always true in production AI. The model is 20% of the work. The plumbing is 80%.

The second lesson: agents are genuinely better than rule-based systems for this use case. My first bot used keyword matching. It broke constantly. LangGraph agents that understand intent with Gemini made the app feel like a real assistant instead of a fragile script.

The third lesson: ship something that works, then improve it. I could have spent another week adding features. Instead I deployed what I had on Sunday night. The next morning the brief arrived in Telegram automatically. That feeling is worth more than another week of planning.

## Does It Actually Help?

Honestly — more than I expected.

Before building this I had no framework for any decision. Now every morning I know:

- Which stocks are healthy and why
- Which positions are oversized and need trimming
- What the tax impact would be before I do anything
- Whether earnings are coming up that I should watch out for

Most mornings the brief tells me to do nothing. Everything is fine. That clarity alone is worth it.

The app does not replace judgment. I still decide whether to follow its recommendations. But it gives me real data instead of gut feelings — and that changes how I think about each position.

## The Stack

- LangGraph — agent orchestration
- Gemini 2.5 Flash — natural language understanding
- AWS Lambda — serverless compute
- AWS DynamoDB — portfolio history and cost basis
- AWS EventBridge — scheduling
- AWS SSM — encrypted secrets
- yfinance — stock data (free, no API key)
- Finnhub — analyst recommendations (free tier)
- Telegram Bot API — notifications and chat

*Built over one rainy weekend — Friday evening to Sunday night. Total cost: $0/month.*

*This is a personal project for educational purposes. Not financial advice.*
