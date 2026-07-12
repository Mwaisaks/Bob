# PLAN.md — Offline-First Student Finance Agent (Build with Gemma: GDG Embu)

**Track:** Autonomous Agent (Gemma 4 native function calling, local-first)
**Pitch in one line:** A financial agent for Kenyan students that never sends your M-Pesa messages anywhere — local Gemma 4 reasons over your real spending, calls real tools, and answers "can I afford this?" with your actual numbers.
**Working title ideas:** PesaAgent / Hela Msee / CampusPesa (decide in Phase 0, don't bikeshed past 10 minutes)

**How we work:** Claude Code writes, Athena oversees, reviews diffs, and makes all product decisions. Every phase ends with a git checkpoint — the commit history IS part of the submission story (judges verify authenticity via the repo; a 7-day trail of honest commits beats a single day-before dump).

**Git rhythm (applies to every phase):**
- Commit at every ✅ acceptance criterion, not just at phase end
- Conventional-ish messages: `feat: gemma sms parser with structured output`, `fix: fuliza sms format edge case`, `docs: architecture diagram`
- 🔴 **PUSH REMINDER** markers below = push to GitHub *now*, don't batch
- Never commit: real M-Pesa SMS exports, `.env`, model weights

---

## Phase 0 — Repo & environment skeleton

**Goal:** Empty-but-professional public repo + Gemma running locally.

- [ ] Create public GitHub repo with README stub (problem statement, one-line pitch, planned architecture diagram placeholder), MIT license, `.gitignore` (Python + `data/real/` + `.env`)
- [ ] Python project scaffold: `uv` or `pip` + `pyproject.toml`; folders: `agent/`, `tools/`, `data/synthetic/`, `knowledge/`, `eval/`, `demo/`
- [ ] Install Ollama, pull quantized Gemma 4 (start with E4B-class instruct variant; also pull the smaller E2B to compare — *note both in writeup as intentional model selection*)
- [ ] Smoke test: script that sends "hello" through Ollama's Python client and prints the reply
- [ ] Smoke test 2: confirm tool/function calling works through Ollama with a dummy `get_weather` tool. **This is the highest-risk unknown in the whole project — do it on day one.**
  - *Fallback if native tool calling is flaky through Ollama:* prompt-enforced JSON mode ("respond ONLY with `{tool: ..., args: ...}`") + a Python dispatcher. Works with any model, and the writeup can honestly describe the tradeoff.
- [ ] Copy this PLAN.md into the repo root

✅ **Done when:** `python demo/smoke_test.py` gets a tool call round-trip from local Gemma.
🔴 **PUSH REMINDER:** push now — repo creation date + smoke test = proof the work started early.

---

## Phase 1 — Synthetic M-Pesa data & student personas

**Goal:** Realistic, shareable demo data that shows *different kinds of students* benefit — this is a product decision as much as a technical one.

- [ ] Collect the real M-Pesa SMS *formats* (from Athena's own inbox, formats only — never commit real messages): send money, receive, paybill, buy goods (till), withdraw, airtime, Fuliza borrow/repay, M-Shwari, HELB/bank disbursement credit
- [ ] Write `data/generate_synthetic.py` — parameterized generator producing 60–90 days of SMS per persona, with realistic fees from the current Safaricom tariff table
- [ ] Define 3 personas (each gets a JSON profile + generated SMS file):
  1. **Brian, HELB boom-bust:** loan lands, 40% gone in week one (food, entertainment), Fuliza dependency by week three — the classic disbursement-day story
  2. **Wanjiku, hustler:** irregular income (mitumba resale + M-Pesa from parents), many small sends — her problem is *fee bleed* and no buffer
  3. **Athman, the saver failing quietly:** disciplined but leaks money through subscriptions, airtime, and small "it's only 50 bob" transactions
- [ ] Validate: generated SMS strings round-trip through the format checker (a simple regex sanity pass — NOT the parser, that's Phase 2)

✅ **Done when:** `data/synthetic/` has three persona SMS dumps a Kenyan would read as authentic.
🔴 **PUSH REMINDER:** push the generator + data. This commit is quotable in the writeup ("we built a persona-driven synthetic data generator so no real financial data ever touches the repo").

---

## Phase 2 — Gemma as the SMS parser (structured output)

**Goal:** Gemma 4 extracts structured transactions from messy SMS text — first *core* model use.

- [ ] `tools/sms_parser.py`: prompt Gemma to emit strict JSON per SMS: `{type, amount, fee, counterparty, balance_after, timestamp, raw_ref}`
- [ ] Pydantic schema validation on every output; retry-once-then-flag on invalid JSON
- [ ] Build `eval/parser_eval.py`: run parser over all synthetic SMS, compare against generator ground truth → **accuracy number for the writeup** (e.g., "Gemma 4 E4B parsed 97% of 240 messages correctly, including Fuliza edge cases")
- [ ] Test deliberately-messy cases: truncated SMS, reversed transaction, new format variant
- [ ] Decision gate: if Gemma parsing < ~90% accurate or too slow, keep Gemma for *hard/ambiguous* messages and add a fast regex path for standard ones — hybrid is an honest, defensible architecture (say so in writeup)

✅ **Done when:** eval script prints an accuracy table; all three personas parse into clean transaction lists.
🔴 **PUSH REMINDER:** push parser + eval harness + results markdown. An eval harness in a 1-week hackathon repo is rare and screams rigor.

---

## Phase 3 — Ledger & deterministic tools (the agent's hands)

**Goal:** Everything the agent can *do*, as plain tested Python. No LLM in this phase.

- [ ] `tools/ledger.py`: SQLite store; `ingest(transactions)`, `spending_summary(period, category=None)`, `income_summary`, `fee_total(period)`, `fuliza_status()`
- [ ] `tools/categorizer.py`: counterparty → category map (food, transport, airtime, entertainment, rent, savings, family) — static map first; Gemma-assisted categorization only if time allows later
- [ ] `tools/fee_calculator.py`: Safaricom tariff table → `cost_of(amount, tx_type)`, `batching_savings(list_of_sends)` ("your 5 sends cost KES 62 more than 1 batched send")
- [ ] `tools/budget.py`: `set_budget(category, amount)`, `check_budget()`, `days_of_runway(balance, burn_rate)`
- [ ] `tools/affordability.py`: `can_i_afford(amount)` → combines runway + upcoming pattern (e.g., weekly rent send) + Fuliza exposure
- [ ] Unit tests for fee calculator and runway math (these produce the numbers said out loud in the demo — they must be right)

✅ **Done when:** `pytest` green; a script can ingest Brian's SMS and print his runway, fee bleed, and Fuliza status.
🔴 **PUSH REMINDER:** push tools + tests.

---

## Phase 4 — The agent loop (the heart)

**Goal:** Gemma 4 orchestrating tools autonomously — the thing the track judges.

- [ ] `agent/loop.py`: conversation loop — user msg → Gemma (with tool schemas) → execute tool call(s) → feed results back → final grounded answer. Support multi-step chains (question may need 2–3 tool calls)
- [ ] `agent/prompts.py`: system prompt with three jobs:
  1. **Persona:** warm, peer-level, Kenyan campus register — a peer coach, not a bank
  2. **Grounding rule:** never state a number that didn't come from a tool result
  3. **Corrective intent:** when the user states a money misconception, engage and correct it with reasoning matched to their level — *cite the MIT finding in the writeup: undirected "wellness" chat entrenches misconceptions; ours is deliberately corrective by design*
- [ ] Trace logging: every tool call + args + result written to a visible trace (this becomes the demo's "look, real function calling" moment and the writeup's proof)
- [ ] Golden-path transcripts for all three personas: "can I afford X?", "where does my money go?", "why am I always broke by week 3?", "is Fuliza bad?"
- [ ] Latency check on target laptop; if sluggish, test E2B vs E4B and record the comparison (→ writeup's "intentional model selection" paragraph)

✅ **Done when:** one unscripted question from Athena produces a correct multi-tool answer she'd trust.
🔴 **PUSH REMINDER:** push agent + example transcripts in `demo/transcripts/`. This is the mid-project milestone — consider a short LinkedIn teaser post here too ("building in public" reads well and the judges are the local GDG community).

---

## Phase 5 — Offline knowledge layer (RAG) + the offline/online split

**Goal:** The agent knows *Kenyan student finance facts*, offline; network becomes optional, not required.

- [ ] `knowledge/`: small curated corpus in markdown — HELB basics (application, disbursement, repayment, CRB consequences), Fuliza terms and daily fees, M-Pesa tariff explanations, MMF basics (what Chumz/Ziidi actually are), chama mechanics
- [ ] `tools/knowledge_lookup.py`: embed corpus with **EmbeddingGemma** (second Gemma model — deliberate; one line in writeup: "two Gemma models, one for reasoning, one for retrieval, both local") → local vector store (sqlite-vec or FAISS) → top-k chunks into context
- [ ] Grounding rule extended: knowledge answers must cite which document chunk they came from
- [ ] **Online-optional tool:** `tools/live_rates.py` — fetch current MMF rates / tariff updates when online; on failure return cached values with a `stale_since` date the agent must mention
- [ ] The kill-the-WiFi test: run the golden-path transcripts with networking disabled → everything except live rates works; live-rate question degrades gracefully ("using cached rates from <date>")

✅ **Done when:** airplane-mode demo passes; a HELB question gets a correct, chunk-cited answer.
🔴 **PUSH REMINDER:** push knowledge base + RAG tool + the airplane-mode test script.

---

## Phase 6 — Demo surface & persona switching

**Goal:** Something judges can *feel* in 60 seconds. Prototype-grade per the rubric — do not gold-plate.

- [ ] Pick ONE: (a) rich terminal UI (Textual/rich — fast, shows tool-call traces beautifully, plays to "local agent" aesthetic) or (b) minimal Streamlit chat. Recommendation: **terminal UI** — it's honest about local-first and demos tool traces natively
- [ ] Persona switcher: `--persona brian|wanjiku|athman` loads that ledger — this is how the demo shows "different kinds of students find this helpful"
- [ ] Visible tool-call trace panel (collapsed by default, one keypress to reveal)
- [ ] Connectivity indicator (online/offline) so the airplane-mode moment is visually obvious
- [ ] Startup banner: model name, quantization, "running locally — no data leaves this machine"

✅ **Done when:** cold start → persona load → question → grounded answer, in under 60 seconds, recorded once end-to-end.
🔴 **PUSH REMINDER:** push UI. Repo should now look like the finished project.

---

## Phase 7 — Submission assets (treat as a build phase, not an afterthought — it's 20% of the score directly and gates the other 80%)

- [ ] **Kaggle Writeup (≤1,500 words — count them):**
  - Open with the lived moment (HELB lands Thursday, gone by week 3) — NOT a statistic, NOT "excited to share"
  - The one mechanism: local agent + real tools over your own M-Pesa data, offline
  - How Gemma is core (parser accuracy number, function-calling loop, EmbeddingGemma RAG, E2B-vs-E4B selection reasoning)
  - The honest pivot/challenge paragraph (whatever actually went wrong — flaky tool calling, parsing edge cases; winners narrate this)
  - Evidence: MIT corrective-design finding, the gap in Kenyan trackers (no intelligence layer), fee-bleed numbers from Wanjiku's persona
  - Architecture diagram (draw once, reuse in README)
- [ ] **Live demo asset:** terminal recording (asciinema or clean screen capture) of the golden path *including the airplane-mode moment* — plus the repo runnable via `make demo` / one documented command. If a hosted option is wanted, a Kaggle notebook that replays the agent loop is acceptable per the rules
- [ ] **README final pass:** problem → demo GIF → architecture → quickstart (test the quickstart on a clean clone — judges will) → persona explanations → eval results → limitations & roadmap (LiteRT on-device as the stated next step)
- [ ] Attach repo + demo in the Writeup's "Project Links", select the **Autonomous Agent** track, and **click Submit** (drafts don't count — the rules are explicit)
- [ ] Submit at least a few hours before deadline, then keep polishing and re-submit (un-submit/edit/re-submit is allowed)

✅ **Done when:** writeup submitted, links resolve in an incognito window (no login walls), quickstart works on a clean machine.
🔴 **PUSH REMINDER:** final push, then tag `v1.0-submission`. Post the LinkedIn writeup after the deadline using the winner formula: lived moment → mechanism → demo clip → honest pivot → team/community tags.

---

## Phase 8 — Stretch (only if Phases 0–7 are fully done)

Ordered by score-per-hour:
1. Gemma-assisted transaction categorization (replace static map for unknown counterparties)
2. Sheng/Swahili code-switching in the persona prompt + 2–3 demo transcripts (borrows the Local Language track's story without leaving the Agent track)
3. Weekly "money debrief" the agent generates unprompted from the ledger (agent-initiated behavior = stronger "autonomous" claim)
4. LiteRT/AI Edge on-device spike — timebox hard; broken mobile demo is worse than a roadmap slide

**Explicitly out of scope (write in README limitations):** real money movement, real M-Pesa API integration, investment advice of any kind (education/information only — copy Cleo's disclaimer posture), iOS/Android app.

---

## Standing risk register

| Risk | Mitigation |
|---|---|
| Gemma tool calling unreliable via Ollama | Phase 0 smoke test day one; JSON-mode dispatcher fallback |
| Local inference too slow for live demo | E2B fallback, shorter context, pre-warmed model; record demo video as insurance |
| Parser accuracy embarrassing | Hybrid regex+Gemma path; report honest numbers — rigor beats perfection |
| Scope creep (the everything-hub trap) | One golden-path flow is the demo; everything else is stretch |
| Writeup rushed on final day | Phase 7 is a real phase; draft the writeup skeleton the moment Phase 4 works |
