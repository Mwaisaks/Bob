# Bob: An Offline M-Pesa Finance Agent for Kenyan University Students

## The Moment That Built This

It's a Thursday afternoon in Nairobi. HELB has disbursed — KES 40,000, meant to cover the whole semester, three months. KES 40,000 hits your M-Pesa. You send KES 5,000 home, clear a friend's debt, buy food, airtime, and a pair of shoes you'd been putting off. By the following Tuesday, you have KES 3,200 left — and the next disbursement isn't due for another three months. By Friday, Fuliza has been activated twice.

This is not an edge case. This is the default experience for a significant portion of Kenya's 700,000+ university students. The money did not disappear — it was spent on real things. But the student had no tool that could show them, in real time, *what their pattern was*, what it would cost them, and what an alternative looked like.

Every M-Pesa transaction generates a structured SMS. The data is there. The problem is that no tool has ever reasoned over it locally, with the student's actual numbers, without requiring them to hand their data to a server.

Bob is that tool.

### A note on the synthetic data

Bob uses no real user transaction data — every SMS in the repository is synthetic. To ensure the synthetic data reflects real-world patterns, I studied the actual SMS formats that Safaricom sends for all 8 transaction types (send money, receive, buy goods, paybill, airtime, Fuliza borrow/repay, Ziidi) from my own inbox and those of contacts who shared their formats. The generator replicates the exact text structure, transaction code format, amount formatting, and fee structure. The result is data a Kenyan M-Pesa user would read as authentic.

---

## What Bob Does

Bob is a local-first financial agent. You load your M-Pesa statement — the PDF you already get by dialing `*334#`, or one of the synthetic demo personas — ask a question in plain language, and Bob returns a grounded answer, backed by your own transaction data, computed entirely on your device.

The core demonstration:

```
You: where does my money leak?

  ⚙  get_income_vs_spending(days=30)   [Gemma called this tool]
  ⚙  get_fee_analysis(days=30)         [and this one, unprompted]

Bob: Your main leak is spending KES 1,785 more than you earned last month.
     On top of that, KES 52.50 went to Fuliza daily charges — money that
     bought you nothing. Start with a weekly budget and repay Fuliza in
     full the moment money arrives.
```

Gemma autonomously decided that answering "where does my money leak?" required *two* tool calls — income vs spending, *and* fee analysis. It made that decision without being told. The answer it gave back is grounded in the actual numbers, not a general statement about budgeting.

No data left the machine. The whole exchange ran on an 8-year-old laptop's CPU.

---

## How Gemma 4 Is Core to This Project

Gemma 4 is not decorative here. It does real work in three places:

### 1. SMS Parser (structured output)

Every M-Pesa transaction SMS arrives as unstructured text:

```
QH3D21XBKL Confirmed. KES1,500.00 received from WANJIKU KAMAU 
0712345678 on 5/7/26 at 3:14 PM. New M-PESA balance is KES3,420.00. 
Transaction cost, KES0.00.
```

Bob parses this into a structured `ParsedTransaction` object: `{type: "receive", amount: 1500.00, fee: 0.0, counterparty: "WANJIKU KAMAU", balance_after: 3420.00, timestamp: "2026-07-05T15:14:00"}`.

The design is a hybrid: a regex classifier handles the 8 known M-Pesa SMS formats deterministically (fast, 100% accurate on known formats), and Gemma 4 handles the fallback for genuinely ambiguous or new format SMS. This is an intentional architectural choice — not a workaround.

**Eval result: 191/191 synthetic messages parsed correctly (100% on all 5 fields).**

The honest pivot: Gemma-only parsing at ~3 minutes per SMS on CPU was impractical. The hybrid approach takes seconds on the full dataset. We documented this tradeoff explicitly because it's the right engineering decision, and because hiding it would be dishonest.

### 1b. Statement Parser — the real onboarding path

The demo above uses synthetic SMS, but a real Kenyan user doesn't hand Bob individual messages. The actual journey is: dial `*334#` → My Account → M-PESA Statement → a password-protected PDF arrives. So `tools/statement_parser.py` applies the same hybrid design to that PDF: `pdftotext -layout` decrypts and extracts the fixed-column transaction table (no new Python dependency — poppler's `pdftotext` binary is already ubiquitous), a regex classifier maps each row's `Details` text to a transaction type, and Gemma 4 is the fallback for anything unmatched.

There's no ground-truth label set for real financial data, so accuracy is verified differently than the SMS parser: by reconciling the parser's own summed totals against the numbers Safaricom prints on the statement itself. On the one real statement used to build and test this (98 transactions, 15 days, never committed to this repository — see `.gitignore`), that reconciliation is exact: **KES 0.00 delta on both Paid In and Withdrawn, 98/98 transactions classified via regex alone, zero Gemma fallbacks needed.** Bob then answered real questions grounded in that data end-to-end (e.g. "where does my money go?" → correctly cited the real KES 21,285.20 total spend, broken down by category).

One honest simplification: a couple of real-statement transaction types (agent till cash deposits, M-Shwari withdrawals back into M-Pesa) are counted as income-equivalent inflows for balance-flow purposes, even though they're really the user's own money moving between accounts, not new income. This is called out explicitly in the README's Limitations section rather than left implicit.

There's also a lighter-weight path for users who'd rather not request a full statement: `--sms-file` ingests M-Pesa SMS pasted directly as text (or exported as JSON from Termux:API's `termux-sms-list` — see Roadmap), running through the same `tools/sms_parser.py` used for the synthetic personas.

### 2. Native Function Calling (the agent loop)

Gemma 4 orchestrates six financial analysis tools via native function calling:

- `get_spending_summary` — KES spent by category, last N days
- `get_balance_trend` — running balance over time
- `get_top_counterparties` — top merchants and recipients
- `get_fee_analysis` — fees paid by transaction type
- `get_fuliza_summary` — Fuliza borrow/repay/charge history
- `get_income_vs_spending` — net positive or negative, period-over-period

When a user asks "why am I always broke by week 3?", Gemma decides which tools to call, calls them, receives the JSON results, and synthesises a natural language answer grounded in those exact numbers. The tool-call traces are shown inline in the terminal UI — the "look, real function calling" moment the track asks for.

### 3. Local RAG (knowledge layer)

A second local model — `nomic-embed-text` — embeds a curated 59-chunk knowledge corpus (HELB mechanics, Fuliza daily fees, M-Pesa tariff table, Ziidi/M-Shwari explained, student budgeting frameworks). When a user asks about Fuliza terms or HELB repayment, Gemma calls `search_knowledge`, retrieves the top-k relevant chunks via cosine similarity, and answers with citations.

**Two local models, two jobs:** Gemma 4 for reasoning and function calling; nomic-embed-text for retrieval. Both run offline.

---

## The Offline-First Design Decision

Most financial apps require a network connection. Bob treats the network as optional.

The live rates tool (`tools/live_rates.py`) follows a three-tier fallback:
1. Fetch from Safaricom's public rates page (if online)
2. Use disk-cached values from the last successful fetch
3. Use hardcoded reference rates (always available, even on a plane)

When the fallback is used, the agent is required to mention that rates are cached and provide the date. The agent cannot silently present stale data as current.

The result: every feature except live rate updates works in airplane mode. The knowledge corpus, the ledger queries, the function calling loop, the RAG — all local.

---

## The Problem With Existing Tools

Kenyan personal finance apps exist. The gap is not the ledger — it's the intelligence layer.

Current tools (Pesapal, Kopo Kopo, Jenga, various M-Pesa statement exporters) show you a transaction list. They do not:
- Identify your personal spending pattern and name it
- Tell you that your Fuliza use this month is higher than last month and calculate what it cost you
- Explain that your 5 separate sends to your mother this month cost KES 35 in fees when one send of KES 2,500 would have cost KES 33
- Connect your spending behaviour to corrective advice grounded in how you specifically spend

Bob's corrective design is deliberate. Research from MIT's AgeLab on financial coaching tools found that undirected "wellness" chat — asking how someone feels about their money — actually *entrenches* existing beliefs rather than changing behaviour. Correction requires specific, personalised, data-grounded challenge. That is what the query tools + agent loop are designed to deliver.

---

## Why This Problem Is Real — Primary Research

Before building, I validated that the HELB boom-bust pattern and M-Pesa tracking gap were not just my personal experience. I spoke informally with university students about their relationship with their M-Pesa data, then backed those conversations with an anonymous survey.

I ran an anonymous, 8-question survey (no name, phone, or email collected — the same privacy stance as Bob itself) and closed it at 30 responses, due to time constraints ahead of the submission deadline. Most respondents were from Meru University of Science and Technology and neighboring institutions, with single responses from Strathmore, Kenyatta University, and the University of Nairobi. The sample skews regionally — it reflects who the survey link actually reached in a week, not a deliberate cross-section — but the pattern inside it is consistent enough to be worth reporting honestly rather than dressed up as more representative than it is.

Of the 23 respondents who receive HELB, 87% said they run out of money before the next disbursement at least "sometimes," and 43% said "almost always." Only 37% of all respondents said they check where their M-Pesa money goes regularly — most only look after the fact, or only after a bad decision. Fuliza usage was common (67%), but among those users, 85% had no idea how much they'd paid in fees the previous month. And when asked directly whether they'd use a private, local-only tool with no login and no data leaving their phone, 73% said yes outright, 93% said yes or maybe.

The numbers say what I expected them to say, but hadn't proven before building: the HELB boom-bust pattern isn't a personal quirk, self-tracking is rare, Fuliza's cost is genuinely invisible to the people paying it, and the privacy-first design isn't a nice-to-have — it's what students said they actually want.

---


Wanjiku Kamau is a USIU Year 3 student running a small mitumba resale business. Her income is irregular: sometimes KES 3,000 in a day, sometimes nothing for a week. Her M-Pesa history shows 72 transactions over 60 days.

Bob's fee analysis for Wanjiku's data:
- Total fees paid: KES 297 over 60 days
- Primary driver: 12 separate send_money transactions averaging KES 280 each
- Batching those 12 sends into 4 would have cost KES 132 instead of KES 297 — a saving of KES 165

KES 165 is not a lot. Annualised, it is KES 1,000 — which is Wanjiku's single largest week of mitumba profit. The fee bleed problem is not about large amounts. It is about the accumulation of individually invisible small decisions.

Bob can show Wanjiku that specific number, for her specific pattern, in her specific context. No generic app does that.

---

## Eval Results

| Metric | Result |
|---|---|
| Parser accuracy (all 5 fields) | 100% — 191/191 records |
| Parse failures (invalid JSON) | 0 |
| Personas with 100% accuracy | 3/3 (Brian, Wanjiku, Athman) |
| Tool calls in evaluation session | Multi-tool turns working (2 tools called per question in demo) |
| Real statement reconciliation (Paid In / Withdrawn vs Safaricom's own printed totals) | KES 0.00 / KES 0.00 delta — 98/98 real transactions, 0 Gemma fallbacks |
| Inference location | Local CPU — no API calls |

---

## Limitations (Honest)

- No live M-Pesa API integration — a real statement is imported manually as a PDF (the actual `*334#` journey), or one of the three synthetic demo personas is used. There's no background auto-sync.
- The statement parser treats agent till cash deposits and M-Shwari withdrawals as income-equivalent inflows for balance-flow purposes, even though they're the user's own money moving between accounts, not new income. Named explicitly rather than left implicit.
- CPU inference at E2B is 30–90 seconds per turn in the synthetic demo; a full end-to-end run against a real 98-transaction statement took ~2 minutes on the development laptop. This is acceptable for a demo and a use case where the user is looking at financial data, not instant messaging. E4B is slower and was deprioritised after testing.
- Knowledge corpus is manually curated and will drift as Safaricom updates tariffs.
- No investment advice — education and information only.

---

## Roadmap

### Near-term (next 3 months)
- **LiteRT on-device:** E2B weights are small enough to target. The stated next step is moving inference from Ollama/CPU to LiteRT for sub-5 second responses on a mid-range Android.
- **Automatic SMS access via Termux:API:** statement import and manual SMS-paste both already work end-to-end; `--sms-file` already accepts `termux-sms-list`'s JSON output today, so a Termux (installed from F-Droid, not the Play Store) wrapper script that runs `termux-sms-list -f mpesa` and pipes it into Bob would close the loop with no new parsing logic. This deliberately avoids the native-app path: Google Play Store restricts `READ_SMS` to default SMS/dialer apps, and asking users to make a hackathon finance app their default texting app is a bigger trust ask than this project's privacy pitch should require.
- **Transaction categorization:** counterparty names (NAIVAS SUPERMARKET, JAVA HOUSE, SAFARICOM DATA) map to categories (groceries, food/entertainment, airtime). A static map covers 80% of cases; Gemma handles the rest. This turns "you spent KES 5,940 on buy_goods" into "you spent KES 2,100 at supermarkets, KES 1,800 on food out, KES 900 on WiFi/data."

### Medium-term
- **Multi-institution support:** students also use Equity, KCB, Cooperative Bank, and MMFs. The same SMS parsing pipeline applies — each institution has a consistent SMS format. M-Pesa was first because every student has it; the others are additive.
- **Sheng/Swahili:** the prompt layer supports code-switching. 2–3 curated example conversations would unlock the Local Language track's audience.
- **Weekly money debrief:** an agent-initiated summary generated from the ledger unprompted — the agent tells you how your week went without you having to ask.

### Future (with appropriate caution)
- **Investment guidance:** pointing students toward Ziidi, Chumz, and M-Shwari based on their actual balance patterns — not generic advice, but *"your average daily balance over the last 30 days was KES 800; if you had auto-saved KES 50/day to Ziidi, you would have earned KES 12 in interest and never needed Fuliza."* Any investment guidance would comply with CMA regulations and be framed as education, not advice.

---

*Repo: https://github.com/Mwaisaks/Bob*  
*All data in the repository is synthetic. No real M-Pesa transactions were used.*
