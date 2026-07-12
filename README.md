# Bob — Your Offline Financial Peer

> *"HELB lands on Thursday. By Sunday you're on Fuliza. By week three you're broke and you don't even know where it went."*
>
> Bob does.

**Bob is a local AI financial agent for Kenyan university students.** He reads your M-Pesa SMS history, reasons over your real spending, and answers "can I afford this?" with your actual numbers — not generic budgeting advice. He runs entirely on your laptop or phone. Your M-Pesa messages never leave your device.

---

## The Problem

Every Kenyan student finance app stops at charts. PesaSense shows you the pie chart. CountPesa shows you the bar graph. Then you close the app and make the same decision anyway.

The intelligence layer — *"why are you always broke by week three? Here's the exact pattern"* — doesn't exist yet. Bob is that layer.

And the trust problem is real: no student is going to hand their M-Pesa history to a server they've never heard of. Bob solves this by running the model locally. Gemma 4 reasons over your data on your own machine. Nothing is sent anywhere.

---

## What Bob Does

Bob is a conversational agent built on **Gemma 4**, running locally via Ollama. Ask him a real question about your money:

- *"Can I afford this KES 3,500 jacket right now?"*
- *"Where does my money actually go every month?"*
- *"Is my Fuliza usage getting worse or better?"*
- *"How much am I losing to M-Pesa fees every month?"*

He answers by calling real tools — a local ledger built from your parsed M-Pesa SMS, a fee calculator with the live Safaricom tariff, a HELB knowledge base, an affordability checker — and then reasoning over those tool results to give you a grounded answer. He will never quote a number he didn't get from a tool. That's a hard rule baked into his design.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Bob (agent loop)                  │
│               Gemma 4 via Ollama (local)             │
│         native function calling / tool dispatch      │
└────────┬────────────────────────────────────────────┘
         │ calls
         ▼
┌────────────────────────────────────────────────────────────────┐
│                         Tool Layer                             │
│  sms_parser  │  ledger  │  fee_calculator  │  affordability   │
│  budget      │  categorizer               │  knowledge_lookup │
│  live_rates (online-optional, degrades gracefully offline)     │
└────────────────────────┬───────────────────────────────────────┘
                         │ reads
                         ▼
┌─────────────────────────────────────────────────────┐
│              Local Data (never uploaded)             │
│   M-Pesa SMS  │  SQLite ledger  │  knowledge/ corpus │
└─────────────────────────────────────────────────────┘
```

**Two Gemma models, both local:**
- `gemma4:instruct` — the reasoning and function-calling brain
- `gemma4:embedding` — powers the offline knowledge retrieval (RAG)

**Offline-first by design:**
Kill the WiFi. Bob still works. The only feature that degrades gracefully is live MMF/tariff rate fetching — and when it does, Bob tells you exactly which cached date he's working from.

---

## Quickstart

> ⚠️ Requires [Ollama](https://ollama.com) installed and Gemma 4 pulled locally. See setup below.

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/Bob.git
cd Bob

# Install dependencies
pip install -e .

# Pull the model (first time only — ~3GB)
ollama pull gemma4:instruct

# Smoke test — confirm tool calling works
python demo/smoke_test.py

# Run Bob with a persona
python demo/run.py --persona brian
```

*Full setup instructions coming as the project progresses.*

---

## Personas (Demo Data)

Bob ships with three synthetic student personas — realistic M-Pesa histories, zero real data in the repo.

| Persona | Story | Core pain |
|---|---|---|
| **Brian** | HELB boom-bust cycle — 40% gone in week one | Disbursement-day discipline |
| **Wanjiku** | Hustler with irregular income (mitumba + family sends) | Fee bleed, no buffer |
| **Athman** | Disciplined saver leaking money quietly | Subscriptions, "it's only 50 bob" |

Switch between them: `--persona brian \| wanjiku \| athman`

---

## Why Bob Corrects, Not Just Informs

The system prompt carries explicit **corrective intent**, designed around a 2026 MIT pre-registered study ([Ross, So & Lo, arXiv:2604.27022](https://arxiv.org/abs/2604.27022)) which found:

> An LLM prompted merely to "discuss" a financial misconception **entrenched that misconception in 27.6% of users** — worse than doing nothing. Corrective intent + argument matched to the user's level produced ~54-point belief shifts persisting 10+ days.

Bob is not a wellness chatbot. When you say something financially wrong, he engages and explains why — at your level. That's a design choice, not a personality quirk.

---

## Project Structure

```
Bob/
├── agent/          # Agent loop, prompts, trace logger
├── tools/          # All deterministic tools (ledger, parser, fees, etc.)
├── data/
│   ├── synthetic/  # Persona SMS dumps (safe to commit)
│   └── real/       # ← gitignored, never committed
├── knowledge/      # Curated Kenyan student finance corpus (HELB, Fuliza, MMFs, M-Pesa tariffs)
├── eval/           # Parser accuracy harness + results
├── demo/           # Smoke tests, run script, recorded transcripts
├── PLAN.md         # Full phased build plan
└── pyproject.toml
```

---

## Eval Results

*(Will be populated after Phase 2 — parser accuracy on synthetic SMS)*

| Model | Messages parsed | Accuracy | Fuliza edge cases |
|---|---|---|---|
| gemma4:instruct (E4B) | — | — | — |
| gemma4:instruct (E2B) | — | — | — |

---

## Limitations & Roadmap

**Out of scope (explicitly):**
- Real M-Pesa API integration or money movement of any kind
- Investment advice (Bob is information and education only — see [Cleo's disclaimer posture](https://web.meetcleo.com/))
- iOS/Android app

**Roadmap (post-submission):**
- LiteRT / AI Edge on-device deployment → financial SMS never leave the phone, not just the laptop
- Gemma-assisted dynamic transaction categorization (replace static map)
- Sheng/Swahili code-switching demo transcripts
- Weekly "money debrief" the agent generates unprompted from the ledger (agent-initiated behaviour)

---

## Track

**GDG Embu — Build with Gemma | Autonomous Agent Track**
Gemma 4 native function calling, local-first.

---

## License

MIT — see [LICENSE](LICENSE)

*Bob is a financial education tool. He is not a licensed financial adviser. All insights are based on your own data and publicly available information.*
