# Prior Art Report: Student Financial Literacy & Money Management — Build with Gemma (GDG Embu, "The Campus Survival Guide")

## What we're solving

A build-an-app hackathon (GDG Embu chapter, hosted on Kaggle) themed **"The Campus Survival Guide"**, where the proposed solution helps university students manage their finances and make informed money decisions — cutting through the overwhelming, generic financial information online. The highest-weighted judging criterion (per Athena's reading of the rubric) is **meaningful use of the Gemma model**; based on the wider Gemma hackathon family (Gemma 3n Impact Challenge, Gemma 4 Good), sibling rubrics reward impact/vision, storytelling, and technical depth defined as *innovative use of Gemma's unique features* (on-device performance, fine-tuning/domain adaptation, multimodality, multilinguality, function calling) — not just calling an LLM API. Note: the exact GDG Embu rubric could not be scraped (Kaggle page is JS-rendered), so the criteria-fit section below leans on the Gemma competition family's published criteria; verify against the actual page.

This is *not* a leaderboard competition — "prior art" here means the full solution landscape for student/youth finance: fintechs, banks, universities, NGOs/informal community models, and LLM-specific research and projects.

## Search coverage

~10 web searches across four framings: (1) AI/conversational money apps (Cleo and clones), (2) Kenyan fintech for youth savings and M-Pesa expense tracking, (3) institutional and non-technical models (banks' student programs, HELB/HEF, chamas/table banking, US university peer-coaching centers, gamified education platforms), and (4) LLM/Gemma-specific prior art (fine-tuning Gemma on financial reasoning; academic evidence on LLM financial-literacy interventions). One source examined in depth: the 2026 MIT pre-registered study on LLM correction of financial misconceptions (arXiv:2604.27022). Gap: no confirmed past *Gemma hackathon winner* specifically in student personal finance was found — which is good news for differentiation, but means no direct replication target exists.

---

## Approach 1: Conversational AI money coach (the Cleo model)

- **Source:** meetcleo.com; reviews at thepennyhoarder.com/budgeting/cleo-app-review, theeverygirl.com/cleo-review
- **Core idea:** Chat-first personal finance. Instead of dashboards, the user texts an AI ("can I afford this?", "how much did I spend on takeout?") and gets plain-language answers grounded in their real transaction data, with a deliberately strong personality ("roast me" / "hype me" modes).
- **Mechanics:** Read-only bank connection via Plaid → automatic transaction categorisation → LLM chat layer answers questions and issues nudges (bill reminders, overspend alerts, savings challenges). Personality/gamification (roast mode, weekly quizzes) drives retention. Freemium: budgeting free, cash advances/credit builder paid.
- **Why they did it this way:** Their target (Gen Z, paycheck-to-paycheck) finds spreadsheet budgeting intimidating; the conversational + humour framing converts a chore into engagement. 8M+ users validates the psychology.
- **Requirements:** Bank-data aggregator (Plaid) — **does not exist meaningfully for Kenyan students**, whose money lives in M-Pesa, not bank accounts.
- **Strengths for this competition:** The interaction pattern (ask your own money questions in plain language, get personality-driven answers) is proven and demos brilliantly in a 3-min video.
- **Weaknesses / risks:** A pure chat wrapper is the most common LLM hackathon submission and scores low on "innovative use of Gemma." The Plaid-style data layer must be replaced with something Kenyan (see Approach 2). Cleo explicitly disclaims giving financial advice — a regulatory posture worth copying.

## Approach 2: On-device M-Pesa SMS parsing (PesaSense / Shmoney / PesaTrail / CountPesa)

- **Source:** pesasense.co.ke, shmoney.co.ke, pesatrail.com, countpesa.com, mpesa-tracker.growthlogic.co.ke
- **Core idea:** The Kenyan answer to Plaid: read M-Pesa confirmation SMS on-device, parse every transaction (send, receive, paybill, till, Fuliza, M-Shwari, fees), auto-categorise, and show budgets/insights — fully offline, private, no account, no server.
- **Mechanics:** Android SMS broadcast listener filtered to sender "MPESA" → regex/rule-based parsing of amounts, counterparties, fees → categorisation into Kenya-specific categories (Food, Transport, SHA, **HELB**, Airtime — PesaSense has 37-38) → local budgets with 80% amber / 100% red thresholds → insights (savings rate, fee breakdown, month-over-month). PesaSense adds community-learned categorisation patterns; CountPesa supports importing full M-Pesa statements for history.
- **Why they did it this way:** Kenya's money is mobile-money-first; every transaction already generates an SMS, so the data layer is free and universal. On-device processing solves the trust problem ("your data never leaves your phone") — every one of these apps leads with privacy.
- **Requirements:** Android SMS permissions; rule-based parsers are pure app code (no ML needed for the parsing itself).
- **Strengths for this competition:** This is the *load-bearing data layer* for any real Kenyan student finance app — without it you have a generic chatbot with no knowledge of the user's actual money. The on-device/privacy framing maps directly onto Gemma's signature pitch (local, private, offline AI). Notably, **none of these apps has a conversational/AI layer** — they stop at charts.
- **Weaknesses / risks:** SMS parsing is Android-only and permission-sensitive; regex parsers already solve extraction well, so using Gemma *only* to parse SMS is over-engineering. The differentiator is what sits *on top* of the parsed data.

## Approach 3: Goal-based micro-savings with nudges (Chumz / Koa / Cashlet model)

- **Source:** chumz.io, Play Store listing; envestreetfinancial.com and kiihela.com roundups
- **Core idea:** Behavioural saving, not education: create visual goals ("New Phone Fund"), save from as little as KES 5 via M-Pesa, get transaction-triggered reminders to save, funds sit in a regulated Money Market Fund (Chumz partners with Nabo Capital under CMA regulation). Group goals mirror chama dynamics digitally.
- **Mechanics:** Goal creation with image + target → M-Pesa paybill deposits → nudges timed to the user's mobile-money activity ("you just received money — save some?") → progress feedback, group accountability (everyone sees contributions), interest via partner MMF.
- **Why they did it this way:** The insight is that Kenyans' main barrier is habit and friction, not knowledge — so shrink minimums to KES 5 and hook prompts to real transaction moments.
- **Requirements:** For the real product, a CMA-licensed fund partner and M-Pesa paybill integration — out of scope for a hackathon prototype, but the *nudge logic* and *goal UX* are replicable.
- **Strengths for this competition:** Deeply Kenyan, student-relevant (HELB disbursement day is the classic "money arrives, then vanishes" moment). Nudge content is a natural place for Gemma to generate personalised, context-aware prompts instead of canned reminders.
- **Weaknesses / risks:** Users complain about withdrawal fees/delays — a cautionary tale about promising money movement in a demo. Handling actual money is not feasible or wise in a hackathon; treat this as a design pattern, not a feature to fully build.

## Approach 4: Gamified bite-sized financial education (the Zogo model)

- **Source:** zogo.com; nextcity.org coverage; multiple credit-union partner pages
- **Core idea:** Duolingo-for-money: 800-1,200+ bite-sized modules (opening accounts → crypto → "being a low-income student"), five concepts then a five-question quiz, points ("pineapples") redeemable for real gift cards. Banks/credit unions license co-branded versions to reach Gen Z; 96% of users self-report improved literacy.
- **Mechanics:** Fixed curriculum mapped to national financial-literacy standards → module → quiz → points → rewards; leaderboards, daily trivia, pre/post testing for measurable impact; sponsor institutions fund the rewards.
- **Why they did it this way:** Static content is cheap to QA and safe (no hallucination risk, no advice liability); gamification substitutes for personalisation as the engagement engine.
- **Strengths for this competition:** Quizzes/streaks demo well; a measurable pre/post literacy test is a strong "impact" story for a writeup. Gemma could *generate* localised modules and quizzes (HELB, Fuliza, chama constitutions, M-Pesa fee maths) — content that Zogo-style US curricula don't cover at all.
- **Weaknesses / risks:** Pure static content underuses Gemma (the highest criterion). The MIT study below suggests passive information delivery is exactly the intervention style with the weakest belief-change record.

## Approach 5: Institutional & non-technical models (banks, HELB, universities, chamas)

- **Source:** kba.co.ke (Chora Plan financial literacy program), Equity "Achievers" student accounts, KCB student accounts, hef.co.ke (HELB/Student-Centred Funding Model), Ohio State Scarlet & Gray Financial / University of Oregon Financial Wellness Center (peer coaching), citizen.digital on Gen Z chamas, fsdkenya.org on savings groups
- **Core idea (three sub-patterns):**
  1. **Banks**: student accounts bundled with financial-literacy content (Equity Achievers explicitly markets literacy; Kenya Bankers Association runs the "Chora Plan" national literacy program). Motivation: customer acquisition of future earners.
  2. **Universities (US model)**: trained *peer* financial coaches give free 1-on-1 sessions and workshops on the "big five" (earning, spending, saving/investing, borrowing, protecting). ~50 campuses; the load-bearing idea is that students trust *peers*, not institutions, and sessions are goal-driven, not lecture-driven.
  3. **Informal Kenyan structures**: chamas/table banking — group savings with social accountability, now going digital among Gen Z (M-Pesa-based contributions, flexible schedules for gig income). Roughly one in three Kenyans participates; financial literacy spreads *through the group*, embedded in a social practice.
- **Why it matters:** These are the incumbent "solutions" your target users actually encounter. HELB itself is a massive, specific student pain point (means-tested loans, CRB listing for default, the new Student-Centred Funding Model confusing everyone) — and no chatbot currently explains it well.
- **Strengths for this competition:** This is problem-statement gold: the gaps are concrete (bank content is generic marketing; peer coaching doesn't exist at Kenyan universities at scale; chama knowledge is oral and unstructured; HELB rules are opaque). An app that plays the role of the "peer coach" — same-level, non-judgmental, goal-driven — has direct evidence behind the interaction style.
- **Weaknesses / risks:** None of these are things to *build*; they're the landscape your writeup positions against.

## Approach 6: LLM-specific prior art — fine-tuned Gemma + the misconception-correction evidence

- **Source:** DataCamp "Fine-Tune Gemma 3 with Financial Q&A" tutorial (LoRA on TheFinAI/Fino1_Reasoning_Path_FinQA, runs on free Kaggle GPUs); Ross, So & Lo (MIT), "Breaking Bad Financial Habits: How LLM Conversations Correct Financial Misconceptions," arXiv:2604.27022 (Apr 2026); ACM ICAIF fairness study of LLM financial chatbots; RAG financial-literacy chatbot papers
- **Core idea (two halves):**
  1. **Technical**: Fine-tuning Gemma (2B/4B class) with LoRA on a financial-reasoning QA dataset is a well-trodden, replicable path on free Kaggle GPUs — load model from Kaggle Hub, PEFT/TRL, before/after comparison. This is exactly the "domain adaptation" judges in the Gemma hackathon family call out as high technical depth.
  2. **Evidence**: The MIT study (3 pre-registered experiments, n≈1,700 total) found LLM conversations durably reduce financial misconceptions (~30-point shift on a ±100 scale, persisting 10+ days) — **but only under two conditions**: (a) *explicit corrective intent* — an LLM prompted merely to "discuss" a misconception was no better than self-reflection and **actively entrenched misconceptions in 27.6% of users** (vs 10.8% baseline), because an undirected model often validates the false belief; (b) *sophistication matching* — arguments pitched below the user's level were dismissed as non-credible and corrected far less, while matched arguments produced the largest shifts (~54 points). Lower-literacy users found the bot more credible and shifted more.
- **Why it matters:** This is the strongest scientific grounding available for your exact concept — and it cuts both ways. It says a "friendly financial wellness chatbot" *without* deliberate design can make students' money beliefs *worse*. Designing around this (corrective system prompts, a misconception library seeded with expert rationales, complexity calibrated to the user's assessed literacy level) is both a safety story and a differentiator almost no hackathon team will have.
- **Requirements:** For fine-tuning: free Kaggle GPU/TPU, a QA dataset. Fino1/FinQA is US-investor-flavoured; a Kenyan student version (HELB, M-Pesa fees, Fuliza, chamas, MMFs, SHA) would need to be built — feasible as a few hundred synthetic-plus-curated pairs, and itself a publishable artifact.
- **Strengths for this competition:** Directly maximises the "use of Gemma" criterion: fine-tuning + on-device deployment + Swahili/Sheng multilinguality + grounding are all Gemma-family signature features. Citing pre-registered evidence in the writeup elevates it above vibes.
- **Weaknesses / risks:** Fine-tuning under deadline pressure can eat the whole timeline; a RAG-over-curated-Kenyan-sources design achieves grounding faster. Regulatory line: education and information, never personalised investment advice (Cleo's disclaimer pattern; the ICAIF study documents LLM inconsistency on financial facts).

---

## Where approaches agree

1. **Meet users where their money already is.** Cleo uses Plaid; every serious Kenyan app uses M-Pesa SMS. Advice not grounded in the user's real transactions is just another article on the internet — the exact problem you named.
2. **Privacy/on-device is the trust unlock for financial data.** All five Kenyan trackers lead with "never leaves your phone." This converges perfectly with Gemma's core identity.
3. **Behaviour beats information.** Chumz's nudges, Zogo's gamification, peer coaching's goal-driven sessions, chamas' social accountability, and the MIT finding that information delivery alone doesn't change beliefs — everyone has concluded the bottleneck is habit and belief, not access to facts.
4. **The trusted messenger matters.** Peer coaches over lecturers, Cleo's friend-persona over bank-speak, chamas over banks, and MIT's credibility-mediation result all point the same way: tone and perceived level-match drive whether guidance lands.
5. **Nobody gives personalised advice.** Every commercial product carefully positions as education/insight, not regulated financial advice.

## Where approaches diverge — the real decision points

1. **Grounding: user's own data vs curated knowledge vs both?** The trackers ground in M-Pesa SMS but have zero intelligence layer; education apps have knowledge but zero personal data; Cleo has both but no Kenyan equivalent exists. Building *both* (SMS-parsed spending + a Kenyan-finance knowledge base feeding Gemma) is the visible gap in the market — but doubles the build. How much of each can you realistically ship before the deadline?
2. **Gemma depth: fine-tune, RAG, or prompt-engineer?** Fine-tuning (LoRA on a Kenyan student-finance QA set) scores highest on the top criterion and follows a replicable tutorial path, but is the riskiest use of time. RAG over curated HELB/CMA/KBA content is faster and directly addresses hallucination/entrenchment. Prompting alone is fastest and weakest. The honest trade-off is criterion score vs execution risk — only you know your remaining calendar.
3. **On-device vs server?** Deploying Gemma small (270M–4B class, quantised) on-device via Google AI Edge / LiteRT tells the perfect "private financial data + offline campus" story and matches the special-technology angles the Gemma family rewards — but mobile deployment debugging is its own project. A Spring Boot-hosted Gemma (your home turf) is far safer to demo but tells a weaker Gemma story. A hybrid (on-device parsing + hosted Gemma, with a roadmap slide to full on-device) is a common compromise.
4. **Coach persona vs corrective tutor?** Cleo's data says personality drives engagement; MIT's data says undirected friendly chat *entrenches* misconceptions. These aren't actually incompatible — a personality-forward bot whose system prompt carries explicit corrective intent and level-matching — but which one leads in your demo video changes the whole pitch (fun campus companion vs evidence-based literacy intervention).

## Open questions / what I couldn't verify

- The **exact GDG Embu rubric and rules** (deadline, team size, allowed Gemma versions, submission format) — the Kaggle page is JS-rendered and returned only metadata. Paste the rubric text and I can score any concept against it point by point.
- Whether the competition expects **Gemma 3 vs Gemma 4** (Gemma 4 shipped with new on-device E2B/E4B variants and native function calling; a chapter event in July 2026 likely allows either).
- No public evidence of a prior Gemma-hackathon winner in *student* personal finance — treated here as a differentiation opportunity, but a finalists-page sweep of the Gemma 3n Impact Challenge before finalising the problem statement would confirm it.
- MIT study external validity: US adults, GPT-4o, self-reported beliefs — directionally strong for design principles, but don't overclaim it proves your app changes Kenyan student behaviour.

## Sources

**Products / fintech**
- Cleo — https://web.meetcleo.com/ ; https://www.thepennyhoarder.com/budgeting/cleo-app-review/ ; https://theeverygirl.com/cleo-review/
- PesaSense — https://pesasense.co.ke/ ; Shmoney — https://shmoney.co.ke/ ; PesaTrail — https://pesatrail.com/best-budget-apps-kenya.html ; CountPesa — https://www.countpesa.com/ ; M-Pesa Tracker — https://mpesa-tracker.growthlogic.co.ke/
- Chumz — https://chumz.io/ ; Koa/Cashlet/Zimele roundups — https://envestreetfinancial.com/some-of-the-best-money-saving-financial-management-apps-revolutionizing-personal-finance-in-kenyan/ ; https://kiihela.com/library/kenya/posts/finance/best-money-saving-apps-kenya/
- Zogo — https://zogo.com/ ; https://nextcity.org/urbanist-news/financial-literacy-app-helps-credit-unions-connect-with-gen-z

**Institutional / non-technical**
- Kenya Bankers Association Chora Plan — https://www.kba.co.ke/financial-literacy-and-education/
- HELB / Higher Education Financing — https://www.hef.co.ke/
- Peer financial coaching — https://swc.osu.edu/services/financial-coaching ; https://business.uoregon.edu/news/supporting-financial-health ; https://www.pbs.org/newshour/education/can-students-improve-financial-management-with-help-from-peers
- Chamas / savings groups — https://www.citizen.digital/article/gen-z-chamas-the-digital-evolution-of-kenyas-traditional-savings-groups-n359999 ; https://www.fsdkenya.org/finaccess/explainer-savings-groups-in-kenya/ ; https://en.wikipedia.org/wiki/Chama_(investment)

---

# Addendum: What innovators actually build at finance hackathons (and the POV they pitch)

*Added after the official rubric was confirmed: Gemma Integration 30%, Innovation & Impact 30%, Functionality 20%, Presentation & Writeup 20%. Tracks: Autonomous Agent ($350, function calling), Local Language & Culture ($250), Edge/On-Device ($400, offline privacy-first).*

## The five recurring builds

**1. The statement-upload budget chatbot (the saturated default).** Example: a lablab.ai DeepSeek hackathon entry — "AI-powered personal finance assistant built with Streamlit, analyzing credit card statements using the 50/30/20 rule, zero-based budgeting, and predictive analytics." POV pitched: "people don't know where their money goes; AI explains it in plain language." This is by far the most common finance-hackathon submission globally — judges have seen dozens. Its weaknesses are always the same: manual/CSV data entry, generic framework advice (50/30/20), no local context.

**2. The finance *agent* (the current meta).** Microsoft AI Agents Hackathon 2025 showcased a "Personal Finance Manager" agent: connects to financial data, answers "how much did I spend on groceries last month?", gives budgeting tips — the pitch is explicitly about the *agent architecture* (model + tools + APIs), not the finance. POV: finance is the ideal showcase for function calling because the questions map cleanly onto tool calls. This maps directly onto the GDG Embu Autonomous Agent track.

**3. The everything-campus-hub.** A Bright Data hackathon entry: "Chat-first AI hub that runs every Malaysian student's university life — schedule, assignments, budget, scholarships, internships." POV: student pain is *fragmentation*, so build one assistant for everything. Instructive as a direct "campus survival" competitor pattern — and as a warning: in a 1-day sprint, breadth kills demo depth; these entries rarely win because no single flow works convincingly.

**4. The narrow-mechanism winners (the actual pattern behind wins).** Looking at what *won* rather than what was submitted:
- Safaricom Fintech Innovation Week winner: an **M-PESA subscription manager** — one concrete pain (recurring payments you forgot about), one clean flow. KES 250,000 + Dubai trip.
- UCT/Interledger hackathon 2nd place: a **remittance-budgeting** tool — one specific money flow (money sent home), not "finances."
- UCT 2026 winner (Fireline, all-female team): **community micro-insurance for house-fire payouts within hours** — hyper-specific, hyper-local, judged on "creative problem framing, passion, understanding of the problem."
- A Belarus fintech hackathon's *financial literacy prize* (LinkedIn writeup by the winner): using depersonalized data from 500k bank accounts to **show users real success stories of "neighbors like them"** and match them to products. Their stated insight: literacy interventions fail on *motivation*, not information — peer proof beats tips. (Same conclusion as the MIT paper and the peer-coaching literature, arrived at independently.)
- bitcoin++ Nairobi 2026's strongest through-line, per organizers: **pragmatism** — winners used the rails already in people's hands (M-PESA, USSD, feature phones) instead of assuming ideal users.

**5. The student-budget builds specifically.** Devpost "AI Budget Planner" (student team: Google AI Studio + React, tracks spending, predicts costs, saving tips) and PennApps' "All-in-One College Finance Personal Assistant" (banking + budgeting + loan finder + financial coursework). Competent, but generic: manual data entry, US framing, no distinctive mechanism. Their writeups emphasize what the *team learned*, not what the *user gets* — a tell that separates participation posts from winner posts.

## How they pitch it (the LinkedIn/writeup POV)

Winner posts and writeups share a structure worth copying: (1) open with a *lived, specific* problem moment ("the money arrives, then vanishes"), not a statistic; (2) name the one mechanism that's new ("we show you neighbors' success stories," "we manage your forgotten subscriptions"); (3) show the working demo flow; (4) narrate one honest pivot/obstacle (the Belarus post's two pivots in 48 hours is the most-engaged part of it); (5) credit the team and tag the ecosystem. Participation-only posts, by contrast, lead with "excited to share" + tech-stack lists — the tech stack is never the story.

## What this means against the GDG Embu rubric

- **Innovation & Impact (30%)**: the global corpus is saturated with generic budget chatbots and empty on Kenyan-student specifics. Nobody in any gallery found has built around HELB disbursement day, Fuliza debt spirals, M-Pesa transaction fees eating a student allowance, or chama-style group accountability. One narrow Kenyan money moment beats "student finance manager."
- **Gemma Integration (30%)**: the judged question is "is the model *core* to the solution?" A chat wrapper fails this. Three defensible cores, one per track: (a) *Agent track* — Gemma's native function calling orchestrating real tools (parse M-Pesa SMS → structured JSON, fee calculator, HELB knowledge lookup, budget writer); (b) *Local Language track* — a coach that genuinely handles Sheng/Swahili code-switching about money, which frontier-API demos rarely attempt; (c) *Edge track* — Gemma running locally so financial SMS never leave the phone (the exact trust argument every Kenyan tracker app leads with; also the biggest prize at $400).
- **Functionality (20%)**: 1-day sprint + the winner pattern above → one flow, demoed end-to-end, over five flows half-built.
- **Presentation (20%)**: use the winner post structure — specific moment, one mechanism, honest pivot.

## Addendum sources
- Microsoft AI Agents Hackathon 2025 winners — https://techcommunity.microsoft.com/blog/azuredevcommunityblog/ai-agents-hackathon-2025-%E2%80%93-category-winners-showcase/4415088
- lablab.ai DeepSeek hackathon recap (finance assistant entry) — https://lablab.ai/ai-hackathons/fall-in-love-with-deepseek
- lablab.ai Bright Data hackathon recap (Malaysian campus hub) — https://lablab.ai/ai-hackathons/brightdata-ai-agents-web-data-hackathon
- lablab.ai winner-pattern guide — https://lablab.ai/guide/ai-hackathon-project-ideas
- Safaricom Fintech Innovation Week winners — https://newsroom.safaricom.co.ke/innovation/building-the-next-big-thing-on-the-m-pesa-app/ ; https://newsroom.safaricom.co.ke/innovation/how-we-built-the-next-big-feature-on-m-pesa/
- UCT/Interledger fintech hackathon — https://www.itweb.co.za/article/student-fintech-innovators-tackle-financial-challenges-at-uct-hackathon/KBpdgvpmGb67LEew
- Belarus fintech hackathon winner LinkedIn writeup — https://www.linkedin.com/pulse/fintech-hackathon-winners-adventure-notes-aliaksandr-smirnou
- bitcoin++ Nairobi 2026 recap — https://insider.btcpp.dev/p/bitcoin-nairobi-hackathon-garners
- Devpost AI Budget Planner (student project) — https://devpost.com/software/ai-budget-planner
- PennApps project gallery — https://pennapps-xxiv.devpost.com/project-gallery

**Research & Gemma-specific**
- Ross, So & Lo (MIT), Breaking Bad Financial Habits — https://arxiv.org/html/2604.27022
- LLMs for Financial Advisement (ACM ICAIF) — https://dl.acm.org/doi/abs/10.1145/3604237.3626867
- RAG financial-literacy chatbot (SLATE 2025) — https://drops.dagstuhl.de/storage/01oasics/oasics-vol135-slate2025/OASIcs.SLATE.2025.7/OASIcs.SLATE.2025.7.pdf
- Fine-tune Gemma 3 on financial QA — https://www.datacamp.com/tutorial/fine-tune-gemma-3
- Gemma hackathon family criteria — https://www.kaggle.com/competitions/google-gemma-3n-hackathon ; https://www.kaggle.com/competitions/gemma-4-good-hackathon
