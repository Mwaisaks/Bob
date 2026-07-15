# Bob — Offline M-Pesa Finance Agent

> **HELB lands Thursday, meant to last the whole semester. By Tuesday it's gone.** Not because students are irresponsible — because a KES 40,000 lump sum arriving into a single M-Pesa account with no structure is a design problem, not a discipline problem. Bob fixes the information gap.

Bob is an offline-first financial agent for Kenyan university students. It reads your real M-Pesa statement (the one you already get by dialing `*334#`), runs it through Gemma 4 locally, and answers *"where does my money go?"* with your actual numbers — no server, no account, no data leaving your machine.

**Track:** Autonomous Agent — Build with Gemma Challenge (GDG Embu)  
**Model:** Gemma 4 E2B (local via Ollama, CPU-only)  
**Privacy:** all inference runs on-device; your M-Pesa data never leaves your machine

---

## Demo

[![asciicast](https://asciinema.org/a/ewKl1zzRgpCGOouT.svg)](https://asciinema.org/a/ewKl1zzRgpCGOouT)

A real, unedited terminal recording — cold start, a multi-tool question, a live-rates question, then the network is killed and the same question is asked again to show the offline fallback (Phase 5's "kill-the-WiFi" test). Every wait is real Gemma 4 CPU inference, not sped up. Reproducible via `demo/record_demo.py` (drives the same `terminal_ui.py` a human would run, with scripted typing instead of manual).

```
You: where does my money leak?

  ⚙  get_income_vs_spending(days=30)
  ✓  Income KES 1,500  ·  Spend KES 3,285  ·  net negative
  ⚙  get_fee_analysis(days=30)
  ✓  Total fees: KES 52

╭─ Bob ───────────────────────────────────────────────────────────────╮
│  Your main leak is spending KES 1,785 more than you earned last     │
│  month. On top of that, KES 52.50 went to Fuliza daily charges —    │
│  that's money that bought you nothing. Start with a weekly budget   │
│  and repay Fuliza in full the moment money arrives.                 │
╰─────────────────────────────────────────────────────────────────────╯
```

---

## Architecture

```
Raw M-Pesa SMS               Real M-Pesa Statement PDF
(demo personas)               (*334# → password-protected)
      │                             │
      ▼                             ▼
┌─────────────────────────┐  ┌──────────────────────────┐
│  Hybrid SMS Parser      │  │  Hybrid Statement Parser │
│  tools/sms_parser.py    │  │  tools/statement_parser.py│
│  ① Regex classifier    │  │  ① pdftotext -layout    │
│  ② Regex extractor     │  │     (password-decrypt)   │
│  ③ Gemma 4 fallback    │  │  ② Regex classifier +   │
│  → 191/191 correct      │  │     Gemma 4 fallback     │
└────────────┬─────────────┘  └─────────────┬─────────────┘
             │ ParsedTransaction (Pydantic)  │
             └───────────────┬───────────────┘
                             ▼
         ┌───────────────┐
         │  SQLite       │  agent/ledger.py
         │  Ledger       │  data/bob.db
         └───────┬───────┘
                 │
      ┌──────────▼──────────────┐
      │                         │
      │   Gemma 4 E2B           │  agent/bob.py
      │   Agent Loop            │  ollama.chat(tools=...)
      │                         │
      │  ┌─────────────────┐    │
      │  │ Native Function │    │
      │  │ Calling         │    │
      │  └────────┬────────┘    │
      └───────────┼─────────────┘
                  │ calls
        ┌─────────┼─────────┐
        │         │         │
        ▼         ▼         ▼
  6 Ledger   Knowledge   Live Rates
  Tools      RAG         (w/ offline
             nomic-      fallback)
             embed-text
```

**Two Gemma models, both local:**
- `gemma4:e2b` — agent reasoning + native function calling
- `nomic-embed-text` — knowledge corpus embedding (59 chunks, 5 files)

---

## Quickstart

### Prerequisites
- Python 3.10+
- [Ollama](https://ollama.com) v0.20+
- `poppler-utils` (provides `pdftotext`, used to read your real M-Pesa statement PDF — not needed for the synthetic demo personas) — `apt install poppler-utils` (Linux) or `brew install poppler` (macOS)

### 1. Install models
```bash
ollama pull gemma4:e2b
ollama pull nomic-embed-text
```

### 2. Clone and install
```bash
git clone https://github.com/Mwaisaks/Bob.git
cd Bob
python -m venv bob-venv
source bob-venv/bin/activate
pip install -e .
```

### 3. Generate demo data and build the index
```bash
# Generate synthetic M-Pesa histories for 3 student personas
python data/generate_synthetic.py

# Ingest into the SQLite ledger
python tools/ingest.py --reset

# Build the knowledge embedding index (runs once, ~60s on CPU)
python tools/knowledge_lookup.py --build
```

### 4. Run
```bash
# Brian — HELB boom-bust student
python demo/terminal_ui.py --persona brian

# Wanjiku — irregular income, fee bleed
python demo/terminal_ui.py --persona wanjiku

# Athman — disciplined but leaking quietly
python demo/terminal_ui.py --persona athman
```

### Try these questions
- *"Where does my money go?"*
- *"Why am I always broke by week 3?"*
- *"How much have I paid in Fuliza fees?"*
- *"Is Fuliza bad for me?"*
- *"What's the current Ziidi interest rate?"*
- *"Am I spending more than I earn?"*

---

## Using Your Own M-Pesa Data

The three personas above are synthetic — a reproducible demo any judge can run without needing an M-Pesa account. But Bob also reads your **real** M-Pesa history, the way you'd actually get it:

1. On your phone, dial **`*334#`** → **My Account** → **M-PESA Statement** → choose a date range and request the statement.
2. Safaricom emails you a **password-protected PDF**; the password itself arrives separately by SMS.
3. Save the PDF somewhere on your machine (never commit it to a repo — `.gitignore` already excludes `data/real/` and any `*.pdf`).
4. Run:
   ```bash
   python demo/terminal_ui.py --statement path/to/your_statement.pdf
   ```
   You'll be prompted for the password (it's never written to disk, logged, or stored in shell history).

`tools/statement_parser.py` parses the statement table with the same hybrid regex + Gemma 4 fallback design as the SMS parser, then reconciles its totals against the statement's own printed SUMMARY block — on the statement used to build this, that reconciliation is exact (KES 0.00 delta on both Paid In and Withdrawn, 98/98 transactions classified by regex alone). Everything after that — every query tool, the RAG knowledge lookup, the agent loop — runs identically whether your data came from a demo persona or your own statement.

### Alternative: your own SMS directly

If you'd rather not request a full statement, Bob can also ingest your M-Pesa SMS directly — either pasted as text or exported programmatically:

```bash
python demo/terminal_ui.py --sms-file path/to/messages.txt
```

Two accepted formats:
- **Plain text** — copy/forward your M-Pesa messages from your phone into a `.txt` file, one message per paragraph (a blank line between each).
- **JSON** — the exact output of [Termux:API](https://wiki.termux.com/wiki/Termux:API)'s `termux-sms-list` command (see Roadmap below for the automated version of this path).

Both go through the same hybrid regex + Gemma 4 `tools/sms_parser.py` used for the synthetic personas.

---

## The Three Personas

| Persona | Profile | Financial story |
|---|---|---|
| **Brian Otieno** | KU, Year 2, HELB student | HELB lands, 40% gone week one (food, entertainment), Fuliza by week three — the classic disbursement-day pattern |
| **Wanjiku Kamau** | USIU, Year 3, mitumba hustler | Irregular income from resale sales + family top-ups. Her problem is *fee bleed*: many small sends, no buffer |
| **Athman Hassan** | Strathmore, Year 4, part-time dev | Disciplined but leaks through subscriptions, airtime, and *"it's only 50 bob"* transactions |

---

## Eval Results

The hybrid SMS parser was evaluated against 191 synthetic M-Pesa messages with ground-truth labels:

| Field | Accuracy |
|---|---|
| Transaction type | 100% (191/191) |
| Amount | 100% (191/191) |
| Fee | 100% (191/191) |
| Counterparty | 100% (191/191) |
| Balance after | 100% (191/191) |
| **Fully correct** | **100% (191/191)** |

**Path breakdown:** 191 via regex, 0 via Gemma fallback.

Key finding: Gemma-only parsing at ~3 min/SMS on CPU was impractical for a 191-record dataset. The hybrid design (regex for known formats, Gemma for genuinely ambiguous ones) runs the full eval in seconds while keeping Gemma available for future format changes. This is documented as an intentional architectural decision, not a workaround.

Run the eval yourself:
```bash
python eval/parser_eval.py
```

---

## Project Structure

```
Bob/
├── agent/
│   ├── bob.py              # Agent loop — BobAgent class + CLI REPL
│   └── ledger.py           # SQLite wrapper
├── data/
│   ├── generate_synthetic.py   # Synthetic M-Pesa SMS generator
│   ├── validate_synthetic.py   # Regex sanity checker
│   └── synthetic/              # Generated JSONL files (3 personas)
├── demo/
│   ├── smoke_test.py       # Phase 0 tool-call validation
│   ├── terminal_ui.py      # Rich terminal demo interface
│   ├── record_demo.py      # Reproduces the submission demo recording
│   └── recordings/         # asciinema .cast files
├── eval/
│   └── parser_eval.py      # Per-field accuracy evaluation harness
├── knowledge/
│   ├── helb.md             # HELB basics, disbursement, repayment, CRB
│   ├── fuliza.md           # Fuliza terms, fees, dependency trap
│   ├── mpesa_tariffs.md    # Full M-Pesa fee table + batching strategies
│   ├── savings_products.md # Ziidi, Chumz, M-Shwari explained
│   └── student_finance.md  # Budgeting frameworks, runway concept
└── tools/
    ├── sms_parser.py       # Hybrid SMS parser (regex + Gemma 4 fallback)
    ├── statement_parser.py # Hybrid PDF statement parser (*334# journey)
    ├── ingest.py           # SMS or statement → ledger pipeline
    ├── query_tools.py      # 6 financial query functions + Ollama schemas
    ├── knowledge_lookup.py # nomic-embed-text RAG over knowledge/
    └── live_rates.py       # Online rates fetch with 3-tier offline fallback
```

---

## Limitations & Roadmap

**Current limitations (honest, as required):**
- No live, automatic M-Pesa access — you import a statement PDF, paste/export your own SMS, or use the synthetic demo personas; there's no background auto-sync yet (see roadmap below)
- The statement parser treats a few transaction types as simplifications for balance-flow purposes: agent till deposits and M-Shwari withdrawals are counted as income-equivalent inflows, even though they're really your own cash or savings moving, not new money
- CPU inference on E2B is 30–90 seconds per turn (real-data test above ran ~2 minutes on this laptop); E4B is slower still
- Knowledge corpus is manually curated; no automatic updates when Safaricom changes tariffs
- No investment advice of any kind — education and information only

**Stated next steps:**
- **Automatic SMS access via Termux:API (near-term, concretely scoped):** install [Termux](https://f-droid.org/packages/com.termux/) + [Termux:API](https://f-droid.org/packages/com.termux.api/) from F-Droid (not the Play Store — this sidesteps Google's policy restricting `READ_SMS` to default SMS/dialer apps, since the permission is granted to Termux, not Bob), then `termux-sms-list -l 200 -f mpesa > messages.json` dumps matching SMS as JSON. `--sms-file` already accepts exactly that format today (see "Using Your Own M-Pesa Data" above) — what's missing is only a wrapper script/cron job to automate the dump-and-ingest step, not new parsing logic. Deliberately not a native Play Store app: that path requires Bob to become the user's default SMS handler, a far bigger trust ask than this project's "no data leaves your device" pitch should require.
- LiteRT/AI Edge on-device deployment (the `gemma4:e2b` weights are already small enough to target) — pairs naturally with the Termux path for a fully on-phone pipeline
- Sheng/Swahili code-switching (the prompt layer supports it; needs curated conversation examples)
- Weekly "money debrief" generated unprompted from the ledger (agent-initiated behaviour)

---

## License

MIT — see [LICENSE](LICENSE)

---

*Built for the Build with Gemma Challenge, GDG Embu, July 2026.*  
*No real financial data is committed to this repository. The statement parser was built and verified locally against one real (never-committed, gitignored) M-Pesa statement — see "Using Your Own M-Pesa Data" above.*
