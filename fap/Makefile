PYTHON ?= python
HOST ?= 127.0.0.1
COORDINATOR_PORT ?= 8011
DOCS_PORT ?= 8012
KB_PORT ?= 8013
LOGS_PORT ?= 8014
LLM_PORT ?= 8015

.PHONY: install-dev verify demo-run demo-coordinator demo-coordinator-llm demo-docs demo-kb demo-logs demo-llm

install-dev:
	$(PYTHON) -m pip install -e ".[dev]"

verify:
	$(PYTHON) -m pytest
	$(PYTHON) -m ruff check .
	$(PYTHON) -m mypy apps packages tests

demo-run:
	$(PYTHON) examples/demo_scenario/run_demo.py --coordinator-url http://$(HOST):$(COORDINATOR_PORT)

demo-coordinator:
	$(PYTHON) -c "import uvicorn; from coordinator_api.main import create_app; uvicorn.run(create_app(participant_docs_evaluate_url='http://$(HOST):$(DOCS_PORT)/evaluate', participant_docs_execute_url='http://$(HOST):$(DOCS_PORT)/execute', participant_kb_evaluate_url='http://$(HOST):$(KB_PORT)/evaluate', participant_kb_execute_url='http://$(HOST):$(KB_PORT)/execute', participant_logs_evaluate_url='http://$(HOST):$(LOGS_PORT)/evaluate', participant_logs_execute_url='http://$(HOST):$(LOGS_PORT)/execute'), host='$(HOST)', port=$(COORDINATOR_PORT))"

demo-coordinator-llm:
	$(PYTHON) -c "import uvicorn; from coordinator_api.main import create_app; uvicorn.run(create_app(participant_docs_evaluate_url='http://$(HOST):$(DOCS_PORT)/evaluate', participant_docs_execute_url='http://$(HOST):$(DOCS_PORT)/execute', participant_kb_evaluate_url='http://$(HOST):$(KB_PORT)/evaluate', participant_kb_execute_url='http://$(HOST):$(KB_PORT)/execute', participant_logs_evaluate_url='http://$(HOST):$(LOGS_PORT)/evaluate', participant_logs_execute_url='http://$(HOST):$(LOGS_PORT)/execute', participant_llm_evaluate_url='http://$(HOST):$(LLM_PORT)/evaluate', participant_llm_execute_url='http://$(HOST):$(LLM_PORT)/execute'), host='$(HOST)', port=$(COORDINATOR_PORT))"

demo-docs:
	$(PYTHON) -m uvicorn participant_docs.main:app --host $(HOST) --port $(DOCS_PORT)

demo-kb:
	$(PYTHON) -m uvicorn participant_kb.main:app --host $(HOST) --port $(KB_PORT)

demo-logs:
	$(PYTHON) -m uvicorn participant_logs.main:app --host $(HOST) --port $(LOGS_PORT)

demo-llm:
	$(PYTHON) -m uvicorn participant_llm.main:app --host $(HOST) --port $(LLM_PORT)
