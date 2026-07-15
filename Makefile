VENV := bob-venv
PYTHON := $(VENV)/bin/python

.PHONY: install pull-models demo demo-wanjiku demo-athman eval clean

# --- Setup -------------------------------------------------------------

install:
	python3 -m venv $(VENV)
	$(PYTHON) -m pip install -e .

pull-models:
	ollama pull gemma4:e2b
	ollama pull nomic-embed-text

# --- Data (file-based targets — only rebuild what's stale) -------------

data/synthetic/brian.jsonl: data/generate_synthetic.py
	$(PYTHON) data/generate_synthetic.py

data/bob.db: data/synthetic/brian.jsonl tools/ingest.py tools/sms_parser.py
	$(PYTHON) tools/ingest.py --reset

data/knowledge_embeddings.pkl: tools/knowledge_lookup.py knowledge/*.md
	$(PYTHON) tools/knowledge_lookup.py --build

# --- Demo ----------------------------------------------------------------
# One command from a clean clone (after `make install` + `make pull-models`):
#   make demo

demo: data/bob.db data/knowledge_embeddings.pkl
	$(PYTHON) demo/terminal_ui.py --persona brian

demo-wanjiku: data/bob.db data/knowledge_embeddings.pkl
	$(PYTHON) demo/terminal_ui.py --persona wanjiku

demo-athman: data/bob.db data/knowledge_embeddings.pkl
	$(PYTHON) demo/terminal_ui.py --persona athman

# --- Eval / housekeeping -------------------------------------------------

eval: data/bob.db
	$(PYTHON) eval/parser_eval.py

clean:
	rm -f data/bob.db data/knowledge_embeddings.pkl data/cached_rates.json
	rm -f data/synthetic/*.jsonl
