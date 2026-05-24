# 🤖 Robinhood AI Advisor

An AI-powered stock portfolio management system that scores your holdings,
finds rotation opportunities, and delivers daily insights via Telegram.
Ask anything about your portfolio in natural language — powered by Gemini 2.5 Flash + LangGraph.

> ⚠️ **Not financial advice.** This is an educational project. Always do your own
> research and consult a financial advisor before making investment decisions.

> ⚠️ **robin_stocks disclaimer.** This app uses [robin_stocks](https://github.com/jmfernandes/robin_stocks),
> an unofficial third-party library that reverse-engineers Robinhood's private API.
> It is not endorsed by Robinhood. Robinhood could change their API at any time and break this integration,
> or in theory restrict accounts that use it. Use at your own risk.
> **Never share your Robinhood credentials with anyone or commit them to GitHub.**

---

## What it does

- Scores every stock on three signals — fundamentals, momentum, analyst sentiment
- Uses professional position sizing rules to find oversized positions
- Suggests exactly what to sell, what to buy, and how many shares
- Gives YES/WAIT recommendations with clear reasoning and next steps
- Calculates exact tax impact before any trade
- Delivers 7am morning brief to Telegram automatically every day
- Answers any portfolio question in natural language via AI agents
- Records trades you execute and tracks portfolio history
- Benchmarks your portfolio vs S&P 500
- Weekly cost check — confirms everything stays free
- Immediate alerts if costs exceed thresholds
- All running 24/7 on AWS — no laptop needed

---

## How to use it

Just talk to your Telegram bot naturally:

```
"Should I sell SHOP?"
"Find me a healthcare stock to buy"
"How is NVDA doing?"
"What is my portfolio worth?"
"How is my portfolio doing vs S&P 500?"
"I sold 23 shares of SHOP at $103"
"What should I do with my NFLX position?"
"Find me an AI stock I don't own"
```

---

## Morning Brief (automatic, 7am ET daily)

```
🌅 Good morning — May 24 2026

💰 Portfolio value: $68,540
  ▲ +348 from yesterday
📊 Portfolio score: 6.8/10
  ▲ +0.1 from last week

✅ HOLD:   14
👀 WATCH:  18
🔄 ROTATE: 3

⚡ Action needed:
  → SHOP 4.57/10 — Trim 77% — reduce to max allowed $682
  → NFLX 6.02/10 — Trim 45% — reduce to max allowed $3,410
  👉 Ask me: "Should I sell SHOP?"

⚠️ Earnings this week:
  → CRM — 2 days  → DELL — 3 days
  Hold these positions until after earnings

🏆 Top performers:
  → GOOGL 9.29/10  → NVDA 9.13/10  → AMZN 8.5/10

─────────────────────
Just ask me anything in natural language
"Should I sell SHOP?"  "Find me a healthcare stock"
```

---

## Daily Routine

**Every morning when the brief arrives (30 seconds):**

```
1. Any Action needed?
   → Ask: "Should I sell TICKER?"
   → Bot gives full analysis + YES/WAIT recommendation
   → Ask: "What is my tax if I sell TICKER?"
   → Decide and execute in Robinhood at 9:30am
   → Tell bot: "I sold X shares of TICKER at $PRICE"

2. Any Earnings warnings?
   → Do nothing with those stocks until after earnings
   → Day after: "How is TICKER doing after earnings?"

3. Nothing urgent?
   → Close Telegram. Go on with your day.
```

**Most mornings you do nothing.** The brief just confirms everything is healthy.

---

## Important — Use Your Judgment

The app is a research assistant, not a portfolio manager.

- It gives you data and a recommendation
- You make the final decision
- Always check tax impact before selling
- Consider your full financial picture
- Override the app if you have a good reason the app cannot see

For each ROTATE suggestion ask yourself:
**"Do I have a reason to keep this that the app cannot see?"**
If yes → keep it. If no → trust the data.

---

## Rotation Suggestions

```
🔄 ROTATION

SELL: SHOP
  Score:          4.57/10
  Action:         Trim 77% — reduce to max allowed $682
  Shares to sell: 23  |  Shares to keep: 7
  Capital freed:  $2,369

BUY: LLY — Eli Lilly and Company
  Score:      8.12/10  |  Price: $1,065
  Shares: 2  |  Cost: $2,130

✅ RECOMMENDATION: DO THE ROTATION
Why:
  → LLY scores 3.55 points higher than SHOP
  → No earnings risk for SHOP

📋 Next steps:
  1️⃣  Ask: "What is my tax if I sell SHOP?"
  2️⃣  Sell 23 shares of SHOP at 9:30am
  3️⃣  Buy 2 shares of LLY with proceeds
  4️⃣  Tell me: "I sold 23 shares of SHOP at $103"
```

---

## Scoring System

| Signal | Weight | What it checks |
|---|---|---|
| **F** Fundamental | 40% | Revenue growth, earnings, PE ratio, profit margin |
| **M** Momentum | 35% | 50/200-day moving averages, RSI, 52-week performance |
| **S** Sentiment | 25% | Analyst buy/sell/hold recommendations (Finnhub) |

**Categories:** `7.0+` → HOLD · `5.0–6.9` → WATCH · `below 5.0` → ROTATE

---

## Position Sizing

| Score | Max % of portfolio |
|---|---|
| 8.0 – 10.0 | 12% |
| 7.0 – 8.0 | 8% |
| 6.0 – 7.0 | 5% |
| 5.0 – 6.0 | 3% |
| 4.0 – 5.0 | 1% |
| 0.0 – 4.0 | Exit completely |

Only suggests trades freeing $1,000+ to avoid small pointless trades.

---

## Tech Stack — $0/month

| Component | Technology |
|---|---|
| Natural Language AI | Gemini 2.5 Flash (free tier) |
| Agent Orchestration | LangGraph (open source) |
| Chat + Alerts | Telegram Bot API (free) |
| Serverless Compute | AWS Lambda (1M req/month free) |
| Scheduler | AWS EventBridge (free) |
| Database | AWS DynamoDB (25GB free) |
| Secrets | AWS SSM Parameter Store (free) |
| Portfolio Data | robin_stocks (open source) |
| Stock Data | yfinance (free) |
| Analyst Data | Finnhub API (free tier) |

---

## Project Structure

```
robinhood-ai-advisor/
├── config.py
├── requirements.txt
├── .env.example
│
├── agents/
│   ├── supervisor.py          ← routes questions to right agent
│   ├── portfolio_agent.py     ← portfolio questions + trade recording
│   ├── rotation_agent.py      ← sell/buy decisions
│   └── screener_agent.py      ← finds new stocks (550-stock universe)
│
├── data/
│   ├── yfinance_client.py     ← free stock data
│   ├── finnhub_client.py      ← analyst recommendations + earnings
│   └── robinhood_client.py    ← reads your real Robinhood portfolio
│
├── scoring/
│   ├── fundamental_scorer.py  ← F score
│   ├── momentum_scorer.py     ← M score
│   ├── sentiment_scorer.py    ← S score
│   └── engine.py              ← combines all three
│
├── portfolio/
│   ├── rotation_engine.py     ← position sizing + rotation logic
│   ├── cost_basis_store.py    ← tax calculations (DynamoDB backed)
│   ├── benchmarking.py        ← tracks alpha vs S&P 500
│   ├── trade_history.py       ← records trades you execute
│   └── stock_universe.py      ← 550 quality stocks by sector
│
├── notifications/
│   ├── telegram_bot.py        ← Telegram bot with agent integration
│   └── morning_brief.py       ← 7am daily digest with trend indicators
│
├── monitoring/
│   └── cost_monitor.py        ← weekly cost check + daily alerts
│
├── infra/
│   ├── lambda_handler.py      ← AWS Lambda + Telegram webhook handler
│   └── dynamo_store.py        ← DynamoDB operations
│
├── scripts/
│   ├── save_robinhood_token.py ← one-time token setup for Lambda
│   └── teardown.py            ← clean removal of all AWS resources
│
├── dashboard/
│   └── app.py                 ← Streamlit UI (local only, optional)
│
└── docs/
    ├── architecture.svg
    └── dashboard.png
```

---

## Build Status

| Phase | What | Status |
|---|---|---|
| Phase 1 | Scoring engine — F + M + S signals | ✅ Complete |
| Phase 2 | Finnhub sentiment + Robinhood connector + rotation engine | ✅ Complete |
| Phase 3 | Streamlit dashboard + Telegram bot | ✅ Complete |
| Phase 4 | AWS Lambda + EventBridge + DynamoDB + LangGraph agents | ✅ Complete |
| Phase 5 | Webhook 24/7 + screener + benchmarking + trade history | ✅ Complete |

---

## Prerequisites

- Python 3.12 — via Anaconda/Miniconda recommended
- Robinhood account — with stocks in it
- AWS account — free tier is sufficient
- AWS CLI — installed and configured
- 4 free API keys — all take under 5 minutes to get

---

## Step-by-Step Setup

### Step 1 — Clone the repo

```bash
git clone https://github.com/mrsanketh/robinhood-ai-advisor.git
cd robinhood-ai-advisor
conda create -n robinhood-ai python=3.12
conda activate robinhood-ai
pip install -r requirements.txt
```

### Step 2 — Get your free API keys

**Finnhub (analyst data):**
1. https://finnhub.io → Sign up → copy API key

**Gemini (AI brain):**
1. https://aistudio.google.com → Create API Key → copy it

**Telegram bot:**
1. Open Telegram → search `@BotFather` → send `/newbot`
2. Follow instructions → copy the bot token
3. Search `@userinfobot` → send `/start` → copy your chat ID

### Step 3 — Configure your environment

```bash
cp .env.example .env
# fill in all values — never commit this file
```

### Step 4 — Configure AWS CLI

```bash
brew install awscli   # Mac
aws configure         # enter your AWS credentials
```

To get AWS credentials:
1. AWS Console → IAM → Users → Create user
2. Attach policies: `AWSLambdaFullAccess`, `AmazonDynamoDBFullAccess`,
   `AmazonSSMFullAccess`, `CloudWatchLogsFullAccess`, `AmazonEventBridgeFullAccess`,
   `AmazonS3FullAccess`, `IAMFullAccess`, `AWSBillingReadOnlyAccess`
3. Security credentials → Create access key → CLI → copy both values

### Step 5 — Store secrets in AWS SSM

```bash
aws ssm put-parameter --name "/robinhood-ai/finnhub_api_key" \
  --value "YOUR_KEY" --type "SecureString" --region us-east-1

aws ssm put-parameter --name "/robinhood-ai/gemini_api_key" \
  --value "YOUR_KEY" --type "SecureString" --region us-east-1

aws ssm put-parameter --name "/robinhood-ai/telegram_bot_token" \
  --value "YOUR_TOKEN" --type "SecureString" --region us-east-1

aws ssm put-parameter --name "/robinhood-ai/telegram_chat_id" \
  --value "YOUR_CHAT_ID" --type "SecureString" --region us-east-1

aws ssm put-parameter --name "/robinhood-ai/robinhood_username" \
  --value "YOUR_EMAIL" --type "SecureString" --region us-east-1

aws ssm put-parameter --name "/robinhood-ai/robinhood_password" \
  --value 'YOUR_PASSWORD' --type "SecureString" --region us-east-1
```

### Step 6 — Save Robinhood session token

```bash
python scripts/save_robinhood_token.py
```

Approve the device on your Robinhood phone app when prompted.
Re-run this script if authentication stops working (every few months).

### Step 7 — Create DynamoDB tables

```bash
aws dynamodb create-table \
  --table-name robinhood-ai-portfolio \
  --attribute-definitions \
    AttributeName=date,AttributeType=S \
    AttributeName=ticker,AttributeType=S \
  --key-schema \
    AttributeName=date,KeyType=HASH \
    AttributeName=ticker,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST --region us-east-1

aws dynamodb create-table \
  --table-name robinhood-ai-costbasis \
  --attribute-definitions AttributeName=ticker,AttributeType=S \
  --key-schema AttributeName=ticker,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST --region us-east-1
```

### Step 8 — Create Lambda IAM role

```bash
aws iam create-role \
  --role-name robinhood-ai-lambda-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{"Effect": "Allow",
      "Principal": {"Service": "lambda.amazonaws.com"},
      "Action": "sts:AssumeRole"}]}'

aws iam attach-role-policy --role-name robinhood-ai-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
aws iam attach-role-policy --role-name robinhood-ai-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonSSMReadOnlyAccess
aws iam attach-role-policy --role-name robinhood-ai-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess
aws iam attach-role-policy --role-name robinhood-ai-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/AWSBillingReadOnlyAccess
```

### Step 9 — Build and deploy Lambda

Replace `YOUR_ACCOUNT_ID` with your AWS account ID.

```bash
# Build dependencies
mkdir lambda_build
pip install yfinance==1.4.0 python-dotenv==1.2.2 requests==2.34.2 \
  robin-stocks==3.4.0 finnhub-python==2.4.28 boto3==1.43.14 \
  langchain==1.3.1 langgraph==1.2.1 langchain-google-genai==4.2.3 \
  --platform manylinux2014_x86_64 --target lambda_build/ \
  --implementation cp --python-version 3.12 --only-binary=:all: --quiet

# Remove numpy/pandas (provided by layer)
rm -rf lambda_build/numpy lambda_build/numpy.libs
rm -rf lambda_build/pandas lambda_build/pandas.libs
rm -rf lambda_build/pygments lambda_build/pygments-*.dist-info
rm -rf lambda_build/curl_cffi lambda_build/curl_cffi-*.dist-info
rm -rf lambda_build/zstandard lambda_build/zstandard-*.dist-info

# Copy app code
cp -r agents data scoring portfolio notifications infra monitoring lambda_build/
cp config.py lambda_build/config.py

# Create pandas layer
mkdir -p pandas_layer/python
pip install pandas==2.2.3 numpy==2.2.6 \
  --platform manylinux2014_x86_64 --target pandas_layer/python/ \
  --implementation cp --python-version 3.12 --only-binary=:all: --quiet
cd pandas_layer && zip -r ../pandas-layer.zip . --quiet && cd ..

aws lambda publish-layer-version \
  --layer-name robinhood-ai-pandas \
  --zip-file fileb://pandas-layer.zip \
  --compatible-runtimes python3.12 --region us-east-1

# Deploy Lambda
cd lambda_build && zip -r ../robinhood-ai-lambda.zip . --quiet && cd ..

aws lambda create-function \
  --function-name robinhood-ai-morning-brief \
  --runtime python3.12 \
  --role arn:aws:iam::YOUR_ACCOUNT_ID:role/robinhood-ai-lambda-role \
  --handler infra.lambda_handler.handler \
  --zip-file fileb://robinhood-ai-lambda.zip \
  --timeout 300 --memory-size 512 --region us-east-1

aws lambda update-function-configuration \
  --function-name robinhood-ai-morning-brief \
  --layers arn:aws:lambda:us-east-1:YOUR_ACCOUNT_ID:layer:robinhood-ai-pandas:1 \
  --region us-east-1

# Cleanup
rm -rf lambda_build pandas_layer robinhood-ai-lambda.zip pandas-layer.zip
```

### Step 10 — Set up Lambda Function URL (Telegram webhook)

```bash
aws lambda create-function-url-config \
  --function-name robinhood-ai-morning-brief \
  --auth-type NONE --region us-east-1 \
  --query "FunctionUrl"

# Note the URL returned, then add permissions
aws lambda add-permission \
  --function-name robinhood-ai-morning-brief \
  --statement-id allow-public-url \
  --action lambda:InvokeFunctionUrl \
  --principal "*" \
  --function-url-auth-type NONE --region us-east-1

aws lambda add-permission \
  --function-name robinhood-ai-morning-brief \
  --statement-id allow-invoke \
  --action lambda:InvokeFunction \
  --principal "*" --region us-east-1

# Register webhook with Telegram (replace YOUR_URL and YOUR_BOT_TOKEN)
curl "https://api.telegram.org/botYOUR_BOT_TOKEN/setWebhook?url=YOUR_LAMBDA_URL"
```

### Step 11 — Schedule with EventBridge

Replace `YOUR_ACCOUNT_ID` with your AWS account ID.

```bash
# 7am ET morning brief
aws events put-rule --name robinhood-ai-morning-brief \
  --schedule-expression "cron(0 11 * * ? *)" --state ENABLED --region us-east-1

aws lambda add-permission --function-name robinhood-ai-morning-brief \
  --statement-id eventbridge-morning-brief --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:us-east-1:YOUR_ACCOUNT_ID:rule/robinhood-ai-morning-brief \
  --region us-east-1

aws events put-targets --rule robinhood-ai-morning-brief \
  --targets '[{"Id":"1","Arn":"arn:aws:lambda:us-east-1:YOUR_ACCOUNT_ID:function:robinhood-ai-morning-brief","Input":"{\"task\":\"morning_brief\"}"}]' \
  --region us-east-1

# 4pm ET stop-loss scan
aws events put-rule --name robinhood-ai-afternoon-scan \
  --schedule-expression "cron(0 20 * * ? *)" --state ENABLED --region us-east-1

aws lambda add-permission --function-name robinhood-ai-morning-brief \
  --statement-id eventbridge-afternoon-scan --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:us-east-1:YOUR_ACCOUNT_ID:rule/robinhood-ai-afternoon-scan \
  --region us-east-1

aws events put-targets --rule robinhood-ai-afternoon-scan \
  --targets '[{"Id":"1","Arn":"arn:aws:lambda:us-east-1:YOUR_ACCOUNT_ID:function:robinhood-ai-morning-brief","Input":"{\"task\":\"afternoon_scan\"}"}]' \
  --region us-east-1
```

### Step 12 — Enable Cost Explorer

AWS Console → search "Cost Explorer" → Launch Cost Explorer
Wait 24 hours for data to populate.

---

## Updating Lambda After Code Changes

```bash
cd your-project-directory

mkdir lambda_build
pip install yfinance==1.4.0 python-dotenv==1.2.2 requests==2.34.2 \
  robin-stocks==3.4.0 finnhub-python==2.4.28 boto3==1.43.14 \
  langchain==1.3.1 langgraph==1.2.1 langchain-google-genai==4.2.3 \
  --platform manylinux2014_x86_64 --target lambda_build/ \
  --implementation cp --python-version 3.12 --only-binary=:all: --quiet

rm -rf lambda_build/numpy lambda_build/numpy.libs
rm -rf lambda_build/pandas lambda_build/pandas.libs
rm -rf lambda_build/pygments lambda_build/pygments-*.dist-info
rm -rf lambda_build/curl_cffi lambda_build/curl_cffi-*.dist-info
rm -rf lambda_build/zstandard lambda_build/zstandard-*.dist-info

cp -r agents data scoring portfolio notifications infra monitoring lambda_build/
cp config.py lambda_build/config.py

cd lambda_build && zip -r ../robinhood-ai-lambda.zip . --quiet && cd ..

aws lambda update-function-code \
  --function-name robinhood-ai-morning-brief \
  --zip-file fileb://robinhood-ai-lambda.zip --region us-east-1

sleep 15 && aws lambda update-function-configuration \
  --function-name robinhood-ai-morning-brief \
  --layers arn:aws:lambda:us-east-1:YOUR_ACCOUNT_ID:layer:robinhood-ai-pandas:1 \
  --region us-east-1

rm -rf lambda_build robinhood-ai-lambda.zip
```

---

## Teardown

To remove all AWS resources:

```bash
python scripts/teardown.py
```

This backs up your cost basis to Telegram first, then deletes everything.

---

## Troubleshooting

**Morning brief stopped arriving:**
```
Cause: Robinhood token expired (every few months)
Fix:   python scripts/save_robinhood_token.py
       Approve on Robinhood phone app when prompted
```

**Bot not responding in Telegram:**
```
Cause: Webhook URL may have changed
Fix:   aws lambda get-function-url-config \
         --function-name robinhood-ai-morning-brief --region us-east-1
       Then re-register: curl "https://api.telegram.org/botTOKEN/setWebhook?url=NEW_URL"
```

**"Gemini quota exceeded" error:**
```
Cause: Hit free tier limit (1,500 req/day after Dec 2025 reduction)
Fix:   Wait until midnight — quota resets automatically
       Avoid heavy use (multiple /rotate calls) that day
```

**Score looks wrong (e.g. 175% profit margin):**
```
Cause: yfinance sometimes returns bad data for unusual companies
Fix:   App handles gracefully — uses neutral scores for bad data
```

**Cost Explorer shows "not enabled":**
```
Fix:   AWS Console → search "Cost Explorer" → Launch Cost Explorer
       Wait 24 hours for data
```

**Robin_stocks returns wrong avg cost:**
```
Cause: Adjusted cost basis for split stocks
Fix:   Use natural language: "What is my tax if I sell TICKER?"
       Enter your real avg cost from Robinhood app when prompted
       Saved to DynamoDB for future calculations
```

---

## Cost Monitoring

Every Monday the brief includes:

```
💸 Weekly Cost Check
  AWS this month:    $0.00  ✅
  Lambda calls:      62 / 1,000,000 per month  (0.006%)
  Gemini calls:      15 / 1500 per day  (1.0%) ✅
  DynamoDB rows:     245 portfolio + 3 cost basis (25GB free)
  yfinance:          free ✅  Finnhub: free ✅  Telegram: free ✅
```

Immediate alert sent if AWS charges detected or Gemini approaches 80% of daily limit — with exact next steps.

---

## Security

- All API keys in AWS SSM Parameter Store (AES-256 encrypted)
- `.env` file is gitignored — never committed
- Robinhood session token stored encrypted in SSM — never in code
- Lambda IAM role has minimum required permissions only
- Telegram bot only responds to your personal chat ID
- Lambda Function URL uses random string — effectively secret

---

## Limitations

**robin_stocks cost basis:** May return adjusted avg cost for split stocks.
Always verify in Robinhood app. Use natural language tax queries — saved to DynamoDB.

**Robinhood token:** Expires every few months. Re-run
`python scripts/save_robinhood_token.py` when morning briefs stop working.

**Gemini free tier:** 1,500 requests/day (reduced December 2025). Heavy use may hit limits.
App alerts you when approaching 80% of daily limit.

**Stock universe:** 550 curated stocks. Add new tickers manually to
`portfolio/stock_universe.py` when needed.

**Benchmarking:** Needs 7+ days of data before showing meaningful trends.

---

## Disclaimer

This project is for educational purposes only. It is not financial advice.
Past performance does not guarantee future results. Always consult a qualified
financial advisor before making investment decisions. The author is not responsible
for any financial losses.

---

## Author

[mrsanketh](https://github.com/mrsanketh)
