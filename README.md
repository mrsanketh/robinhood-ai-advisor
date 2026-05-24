# 🤖 Robinhood AI Advisor

An AI-powered stock portfolio management system that scores your holdings,
finds rotation opportunities, and delivers daily insights via Telegram.
Ask anything about your portfolio in natural language — powered by Gemini + LangGraph.

> ⚠️ **Not financial advice.** This is an educational project. Always do your own
> research and consult a financial advisor before making investment decisions.

---

## What it does

- Scores every stock on three signals — fundamentals, momentum, analyst sentiment
- Uses professional position sizing rules to find oversized positions
- Suggests exactly what to sell, what to buy, and how many shares
- Gives YES/WAIT recommendations with clear reasoning and next steps
- Calculates exact tax impact before any trade
- Delivers 7am morning brief to Telegram automatically every day
- Answers any portfolio question in natural language via AI agents
- Weekly cost check — confirms everything stays free
- Immediate alerts if costs exceed thresholds

---

## Natural Language Chat

Just ask anything in Telegram:

```
"How is NVDA doing?"
"Should I sell SHOP?"
"Find me a healthcare stock to buy"
"What is my portfolio worth?"
"Which stock can I sell and buy a growth stock?"
"How much tax if I sell NFLX?"
```

---

## Morning Brief (automatic, 7am ET daily)

```
🌅 Good morning — May 24 2026

💰 Portfolio value: $68,192
📊 Portfolio score: 6.7/10

✅ HOLD:   14
👀 WATCH:  18
🔄 ROTATE: 3

⚡ Action needed:
  → SHOP 4.57/10 — Trim 77% — reduce to max allowed $682
  → NFLX 6.02/10 — Trim 45% — reduce to max allowed $3,410
  👉 /rotate — full analysis + recommendation + next steps

⚠️ Earnings this week:
  → CRM — 2 days  → DELL — 3 days
  Hold these positions until after earnings

🏆 Top performers:
  → GOOGL 9.29/10  → NVDA 9.13/10  → AMZN 8.5/10
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
| Natural Language AI | Gemini 1.5 Flash (free tier) |
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

## Prerequisites

Before starting, you need:

- **Python 3.12** — via Anaconda/Miniconda recommended
- **Robinhood account** — with stocks in it
- **AWS account** — free tier is sufficient
- **AWS CLI** — installed and configured
- **4 free API keys** — all take under 5 minutes to get

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
1. Go to https://finnhub.io
2. Click Sign Up (free, no credit card)
3. Dashboard → copy your API key

**Gemini (AI brain):**
1. Go to https://aistudio.google.com
2. Sign in with Google account
3. Click "Create API Key" → copy it

**Telegram bot:**
1. Open Telegram → search `@BotFather`
2. Send `/newbot`
3. Follow instructions → copy the bot token
4. Search `@userinfobot` → send `/start` → copy your chat ID

### Step 3 — Configure your environment

```bash
cp .env.example .env
```

Open `.env` and fill in all values. Never commit this file.

### Step 4 — Configure AWS

```bash
# Install AWS CLI
brew install awscli   # Mac
# or download from https://aws.amazon.com/cli/

# Configure with your AWS credentials
aws configure
# Enter: Access Key ID, Secret Access Key, region (us-east-1), output (json)
```

To get AWS credentials:
1. AWS Console → IAM → Users → Create user
2. Attach these policies: `AWSLambdaFullAccess`, `AmazonDynamoDBFullAccess`,
   `AmazonSSMFullAccess`, `CloudWatchLogsFullAccess`, `AmazonEventBridgeFullAccess`,
   `AmazonS3FullAccess`, `IAMFullAccess`
3. Security credentials → Create access key → CLI → copy both values

### Step 5 — Store secrets in AWS

```bash
# Store all API keys in AWS SSM Parameter Store (encrypted)
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

This allows Lambda to read your portfolio without device approval every time:

```bash
python scripts/save_robinhood_token.py
```

Approve the device on your Robinhood phone app when prompted. Run this again
if authentication stops working (every few months).

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

Replace `YOUR_ACCOUNT_ID` with your AWS account ID (found in AWS Console top right).

```bash
# Build dependencies
mkdir lambda_build
pip install yfinance==1.4.0 python-dotenv==1.2.2 requests==2.34.2 \
  robin-stocks==3.4.0 finnhub-python==2.4.28 boto3==1.43.14 \
  langchain==1.3.1 langgraph==1.2.1 langchain-google-genai==4.2.3 \
  --platform manylinux2014_x86_64 --target lambda_build/ \
  --implementation cp --python-version 3.12 --only-binary=:all: --quiet

# Copy app code
cp -r agents/ data/ scoring/ portfolio/ notifications/ infra/ monitoring/ lambda_build/
cp config.py lambda_build/config.py

# Create pandas layer (numpy + pandas for Linux)
mkdir -p pandas_layer/python
pip install pandas==2.2.3 numpy==2.2.6 \
  --platform manylinux2014_x86_64 --target pandas_layer/python/ \
  --implementation cp --python-version 3.12 --only-binary=:all: --quiet
cd pandas_layer && zip -r ../pandas-layer.zip . --quiet && cd ..

# Publish pandas layer
aws lambda publish-layer-version \
  --layer-name robinhood-ai-pandas \
  --zip-file fileb://pandas-layer.zip \
  --compatible-runtimes python3.12 --region us-east-1

# Remove pandas from main zip (provided by layer)
rm -rf lambda_build/numpy lambda_build/numpy.libs
rm -rf lambda_build/pandas lambda_build/pandas.libs

# Create zip and deploy
cd lambda_build && zip -r ../robinhood-ai-lambda.zip . --quiet && cd ..

aws lambda create-function \
  --function-name robinhood-ai-morning-brief \
  --runtime python3.12 \
  --role arn:aws:iam::YOUR_ACCOUNT_ID:role/robinhood-ai-lambda-role \
  --handler infra.lambda_handler.handler \
  --zip-file fileb://robinhood-ai-lambda.zip \
  --timeout 300 --memory-size 512 --region us-east-1

# Attach pandas layer
aws lambda update-function-configuration \
  --function-name robinhood-ai-morning-brief \
  --layers arn:aws:lambda:us-east-1:YOUR_ACCOUNT_ID:layer:robinhood-ai-pandas:1 \
  --region us-east-1
```

### Step 10 — Schedule with EventBridge

```bash
# 7am ET morning brief (11:00 UTC)
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

# 4pm ET stop-loss scan (20:00 UTC)
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

### Step 11 — Run locally

```bash
# Telegram bot (for chat)
python notifications/telegram_bot.py

# Test morning brief
python notifications/morning_brief.py

# Streamlit dashboard (optional, local only)
streamlit run dashboard/app.py
```

---

## Telegram Commands

```
/score NVDA    — score any stock
/portfolio     — full portfolio breakdown
/rotate        — position sizing analysis
/tax SHOP      — tax impact if you sell
/status        — quick portfolio summary
/help          — show all commands
```

Or just ask naturally — the AI handles the rest.

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

Immediate alert sent if AWS charges detected or Gemini approaches daily limit.

---

## Security Notes

- All API keys stored in AWS SSM Parameter Store (AES-256 encrypted)
- `.env` file is gitignored — never committed
- Robinhood session token stored encrypted in SSM — never in code
- Lambda IAM role has minimum required permissions only
- Telegram bot only responds to your personal chat ID

---

## Important Limitations

- **Cost basis:** robin_stocks may return incorrect avg cost for stocks with splits
  or multiple purchase lots. Always verify in Robinhood app → your position → Average Cost.
  Use `/tax TICKER` to enter your real avg cost — saved to DynamoDB.

- **Robinhood token:** expires every few months. Re-run
  `python scripts/save_robinhood_token.py` when morning briefs stop working.

- **Gemini free tier:** 1,500 requests/day. Heavy conversational use may hit limits.
  The app alerts you when approaching 80% of the daily limit.

---

## Disclaimer

This project is for educational purposes only. It is not financial advice.
Past performance of any strategy does not guarantee future results.
Always consult a qualified financial advisor before making investment decisions.
The author is not responsible for any financial losses.

---

## Author

[mrsanketh](https://github.com/mrsanketh)

---

## Daily Routine

**Every morning when the brief arrives (takes 30 seconds):**

```
1. Read the brief
2. Any new ROTATE or Action needed?
   → Run /rotate in Telegram
   → See full analysis + recommendation
   → Run /tax TICKER to see tax impact
   → If YES recommendation → execute in Robinhood at 9:30am
3. Any earnings warnings?
   → Hold those stocks until after earnings
   → Run /score TICKER the day after earnings
4. Portfolio score trending down?
   → Ask "Why is my portfolio score dropping?"
   → Agent will investigate and explain
5. Nothing urgent?
   → Close Telegram, go on with your day
```

**Most mornings you do nothing.** The brief just confirms everything is healthy.

**Weekly on Monday:**
- Check the cost summary at the bottom of the brief
- Confirm AWS $0.00, Gemini within limits

---

## Updating Lambda After Code Changes

When you change any Python file, redeploy to Lambda:

```bash
# Rebuild zip
rm -rf lambda_build robinhood-ai-lambda.zip
mkdir lambda_build

pip install yfinance==1.4.0 python-dotenv==1.2.2 requests==2.34.2 \
  robin-stocks==3.4.0 finnhub-python==2.4.28 boto3==1.43.14 \
  langchain==1.3.1 langgraph==1.2.1 langchain-google-genai==4.2.3 \
  --platform manylinux2014_x86_64 --target lambda_build/ \
  --implementation cp --python-version 3.12 --only-binary=:all: --quiet

rm -rf lambda_build/numpy lambda_build/numpy.libs
rm -rf lambda_build/pandas lambda_build/pandas.libs

cp -r agents/ data/ scoring/ portfolio/ notifications/ infra/ monitoring/ lambda_build/
cp config.py lambda_build/config.py

cd lambda_build && zip -r ../robinhood-ai-lambda.zip . --quiet && cd ..

# Deploy (replace YOUR_ACCOUNT_ID)
aws lambda update-function-code \
  --function-name robinhood-ai-morning-brief \
  --zip-file fileb://robinhood-ai-lambda.zip \
  --region us-east-1

# Reattach pandas layer after update
sleep 15 && aws lambda update-function-configuration \
  --function-name robinhood-ai-morning-brief \
  --layers arn:aws:lambda:us-east-1:YOUR_ACCOUNT_ID:layer:robinhood-ai-pandas:1 \
  --region us-east-1

# Clean up
rm -rf lambda_build robinhood-ai-lambda.zip
```

---

## Troubleshooting

**Morning brief stopped arriving:**
```
Most likely cause: Robinhood token expired (happens every few months)
Fix: python scripts/save_robinhood_token.py
     Approve device on Robinhood phone app when prompted
```

**"Gemini quota exceeded" error in Telegram:**
```
Cause: Hit free tier limit of 1,500 requests/day
Fix: Wait until midnight — quota resets automatically
     Avoid heavy use (multiple /rotate or /portfolio calls) that day
     Long term: add billing to Google AI Studio ($0 until $10 in usage)
```

**Agent answers with raw JSON instead of text:**
```
Cause: Gemini API returning metadata in response
Fix: Already handled in code — pull latest from GitHub and redeploy
```

**Lambda timeout error:**
```
Cause: Scoring 35 stocks + Finnhub rate limiting takes ~3 minutes
Fix: Timeout is already set to 300 seconds (5 min) — should not happen
     If it does: check CloudWatch logs in AWS Console → Lambda → Monitor
```

**Score looks wrong for a stock (e.g. 175% profit margin):**
```
Cause: yfinance sometimes returns bad data for small/unusual companies
Fix: Run /score TICKER manually to check
     The app handles this gracefully — if data looks suspicious it uses neutral scores
```

**"No module named X" error after pulling new code:**
```
Fix: pip install -r requirements.txt
     Then redeploy Lambda if the fix is needed in production
```

**Robinhood shows different avg cost than /tax shows:**
```
Cause: robin_stocks returns adjusted cost basis for split stocks
Fix: Use /tax TICKER → enter your real avg cost from Robinhood app
     It saves to DynamoDB and uses that going forward
```

**Cost Explorer shows "not enabled" error:**
```
Fix: AWS Console → search "Cost Explorer" → Launch Cost Explorer
     Wait 24 hours for data to populate
```

---

## Architecture

```
Your Phone (Telegram)
        ↓ ↑
Telegram Bot API
        ↓ ↑
AWS Lambda (robinhood-ai-morning-brief)
    ├── Morning brief (7am via EventBridge)
    ├── Stop-loss scan (4pm via EventBridge)
    └── Chat responses (webhook — coming soon)
        ↓
LangGraph Supervisor
    ├── Portfolio Agent  → answers portfolio questions
    ├── Rotation Agent   → handles sell/buy decisions
    └── Screener Agent   → finds new stocks
        ↓
Data Layer
    ├── yfinance         → stock prices + fundamentals
    ├── Finnhub          → analyst recommendations
    └── robin_stocks     → your Robinhood holdings
        ↓
Storage
    ├── DynamoDB         → portfolio history + cost basis
    └── SSM Parameter    → all secrets (encrypted)
```

---

## Roadmap

- [ ] Telegram webhook deployment (bot works 24/7 without laptop)
- [ ] Conviction-based position sizing for 3-month growth strategy
- [ ] Stock screener scanning 550-stock universe daily
- [ ] Portfolio benchmarking vs S&P 500
- [ ] Trade history tracking in DynamoDB
- [ ] Teardown script for clean AWS resource removal
