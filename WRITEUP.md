# Bob: An Offline M-Pesa Finance Agent for Kenyan University Students

## The Moment That Built This

It's a Thursday afternoon in Nairobi. HELB has disbursed: KES 40,000, meant to cover the whole semester, hits your M-Pesa. You send KES 5,000 home, clear a friend's debt, buy food, airtime, and a pair of shoes you'd been putting off. By the following Tuesday, you have KES 3,200 left — and the next disbursement isn't due for another three months. By Friday, Fuliza has been activated twice.

This isn't an edge case — it's the default experience for a significant share of Kenya's 700,000+ university students. The money didn't disappear, it was spent on real things. The student just had no tool to show them, in real time, *what their pattern was* and what it cost.

Every M-Pesa transaction generates a structured SMS — the data is there. No tool has ever reasoned over it locally, with the student's own numbers, without handing that data to a server. Existing Kenyan trackers stop at the transaction list; they don't name a pattern, cost it out, or correct it. MIT AgeLab research on financial coaching found undirected "wellness" chat about money actually *entrenches* existing beliefs — correction requires specific, data-grounded challenge.

Bob is that tool.

### A note on the synthetic data

No real user transaction data is committed here — the demo SMS is synthetic, generated from Safaricom's real 8 SMS formats (studied from my own inbox and contacts') so it reads as authentic to a Kenyan M-Pesa user.

---

## What Bob Does

Load your M-Pesa statement (the PDF from `*334#`, or a synthetic demo persona), ask a question in plain language, get a grounded answer — backed by your own transaction data, computed entirely on your device.

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

Gemma autonomously decided that answering "where does my money leak?" required *two* tool calls, unprompted, and grounded its answer in the actual numbers rather than generic budgeting advice. No data left the machine — the whole exchange ran on an 8-year-old laptop's CPU.

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

Bob parses this into a structured `ParsedTransaction`: `{type: "receive", amount: 1500.00, fee: 0.0, counterparty: "WANJIKU KAMAU", balance_after: 3420.00, timestamp: "2026-07-05T15:14:00"}`.

The design is a hybrid: a regex classifier handles the 8 known SMS formats deterministically, Gemma 4 handles genuinely ambiguous or new-format SMS — an intentional architectural choice, not a workaround. **Eval result: 191/191 synthetic messages parsed correctly (100%, all 5 fields).** The honest pivot: Gemma-only parsing at ~3 minutes per SMS on CPU was impractical; the hybrid runs the full dataset in seconds.

### 1b. Statement Parser — the real onboarding path

A real Kenyan user doesn't hand Bob individual messages — the actual journey is `*334#` → My Account → M-PESA Statement → a password-protected PDF. `tools/statement_parser.py` applies the same hybrid design to that PDF: `pdftotext -layout` decrypts and extracts the fixed-column transaction table (no new Python dependency), a regex classifier maps each row's `Details` text to a type, and Gemma 4 is the fallback for anything unmatched.

There's no ground-truth label set for real financial data, so accuracy is verified by reconciling the parser's summed totals against the numbers Safaricom prints on the statement itself. On the one real statement used to test this (98 transactions, 15 days, never committed — see `.gitignore`), that reconciliation is exact: **KES 0.00 delta on both Paid In and Withdrawn, 98/98 classified via regex alone.** Bob then answered real questions grounded in that data end-to-end (one modeling simplification is named in Limitations).

### 2. Native Function Calling (the agent loop)

Gemma 4 orchestrates six financial analysis tools via native function calling: `get_spending_summary`, `get_balance_trend`, `get_top_counterparties`, `get_fee_analysis`, `get_fuliza_summary`, `get_income_vs_spending`.

When a user asks "why am I always broke by week 3?", Gemma decides which tools to call, executes them, and synthesises an answer grounded in the JSON results. Tool-call traces are shown inline in the terminal UI — the "real function calling" moment the track asks for.

### 3. Local RAG (knowledge layer)

A second local model, `nomic-embed-text`, embeds a curated 59-chunk knowledge corpus (HELB, Fuliza, M-Pesa tariffs, Ziidi/M-Shwari, budgeting frameworks). Gemma calls `search_knowledge`, retrieves top-k chunks by cosine similarity, and cites its source. Two local models, two jobs: Gemma 4 reasons, nomic-embed-text retrieves. Both offline.

---

## The Offline-First Design Decision

Most financial apps require a network connection; Bob treats the network as optional. `tools/live_rates.py` tries a live fetch, falls back to disk-cached values, then to hardcoded reference rates — and is required to disclose when it's using cached data rather than presenting it as current. Every feature except live rate updates works in airplane mode.

---

## Why This Problem Is Real — Primary Research

Before building, I validated that the HELB boom-bust pattern and M-Pesa tracking gap weren't just my personal experience — informal conversations, then an anonymous 8-question survey (no name, phone, or email collected — the same privacy stance as Bob itself), closed at 30 responses due to the submission deadline. Respondents skewed regionally (mostly Meru University of Science and Technology and neighbours, plus single responses from Strathmore, Kenyatta University, and UoN) — a function of who the link reached in a week, not a deliberate cross-section, worth stating plainly rather than dressed up as more representative than it is.

Of the 23 HELB recipients, 87% run out of money before the next disbursement at least "sometimes" (43% "almost always"). Only 37% check their M-Pesa spending regularly. Fuliza usage was common (67%), but 85% of those users had no idea how much they'd paid in fees last month. Asked if they'd use a private, local-only tool with no login: 73% yes outright, 93% yes-or-maybe.

The numbers prove what I expected but hadn't shown before building: the boom-bust pattern isn't a personal quirk, self-tracking is rare, Fuliza's cost is genuinely invisible, and privacy-first isn't a nice-to-have — it's what students said they want.

---

**Wanjiku Kamau**, a USIU mitumba reseller, lost KES 297 to fees over 60 days — mostly 12 small sends that batching into 4 would have cut by KES 165, her single largest week of profit. No generic tracker names that number for her specific pattern; Bob does.

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

- No live M-Pesa API integration — real data is imported manually (PDF or SMS export) or a synthetic persona is used. No background auto-sync yet.
- Agent-till deposits and M-Shwari withdrawals are counted as income-equivalent inflows, though they're the user's own money moving between accounts, not new income.
- CPU inference at E2B is 30–90 seconds per turn (~2 minutes for a full real-statement run) — fine for a look-at-your-data use case, not instant messaging.
- Knowledge corpus is manually curated and will drift as tariffs change. No investment advice — education only.

---

## Roadmap

- **Automatic SMS access via Termux:API:** `--sms-file` already accepts `termux-sms-list`'s JSON output today; a Termux wrapper script (installed from F-Droid, not the Play Store) would close the loop with no new parsing logic. Deliberately not a native app: Play Store restricts `READ_SMS` to default SMS/dialer apps, a bigger trust ask than this project's privacy pitch should require.
- **LiteRT on-device:** E2B weights are small enough to target, for sub-5 second responses on a mid-range Android.
- **Transaction categorization:** counterparty names → spending categories (groceries, food, airtime), static map + Gemma for the rest. Turns "KES 5,940 on buy_goods" into a real breakdown.
- Further out: multi-institution support, Sheng/Swahili code-switching, an agent-initiated weekly debrief, CMA-compliant investment education.

---

*Repo: https://github.com/Mwaisaks/Bob*  
*Demo video: https://youtu.be/B8S_3AQ4qTs*  
*No real financial data is committed to this repository. The statement parser was built and verified locally against one real, never-committed M-Pesa statement.*
