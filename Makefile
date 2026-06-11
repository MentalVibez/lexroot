.PHONY: dev test test-all migrate import-senses import-gcide import-frequency import-common-words import-common-words-next import-morphemes sync-neo4j make-snapshot lint typecheck help

PYTHON ?= python
COMMON_WORD_ARGS ?=

## Start Docker services and the API app
dev:
	docker compose up -d postgres neo4j ollama
	docker compose up app

## Run the fast test suite (no Neo4j/Ollama required)
test:
	$(PYTHON) -m pytest tests/ test_word_detective.py test_shipley_importer.py \
	       test_senses_importer.py test_data_quality_validator.py -v

## Run the full test suite across all testpaths
test-all:
	$(PYTHON) -m pytest -v

## Apply all pending Alembic migrations
migrate:
	$(PYTHON) -m alembic upgrade head

## Import senses from the default CSV path
import-senses:
	$(PYTHON) -m ingestor.senses_importer

## Import Webster's 1913 (GCIDE) words and senses into PostgreSQL
import-gcide:
	$(PYTHON) -m ingestor.gcide_importer

## Import morpheme decompositions from CSV (Words/morphemes.csv)
import-morphemes:
	$(PYTHON) -m ingestor.morphemes_importer

## Sync PostgreSQL words → Neo4j graph (run after any bulk import)
sync-neo4j:
	$(PYTHON) -m ingestor.neo4j_sync

## Load wordfreq Zipf scores into the PostgreSQL words table
import-frequency:
	$(PYTHON) -m ingestor.frequency_pg_importer

## Import top 5,000 common English words into PostgreSQL
import-common-words:
	$(PYTHON) -m ingestor.common_words_pg_importer --start-rank 1 --limit 5000 $(COMMON_WORD_ARGS)

## Import a later common-word tier: make import-common-words-next START=5001 LIMIT=5000
import-common-words-next:
	$(PYTHON) -m ingestor.common_words_pg_importer --start-rank $(START) --limit $(LIMIT) $(COMMON_WORD_ARGS)

## Create a citable dataset snapshot (requires ADMIN_API_TOKEN + running API)
make-snapshot:
	@echo "POST /pg/snapshots to create a snapshot — set TAG and DESC:"
	@echo "  curl -X POST http://localhost:8000/pg/snapshots \\"
	@echo "    -H 'Authorization: Bearer $$ADMIN_API_TOKEN' \\"
	@echo "    -H 'Content-Type: application/json' \\"
	@echo "    -d '{\"tag\": \"v$$(date +%Y-%m-%d)\", \"description\": \"Auto snapshot\"}'"

## Lint all source packages
lint:
	$(PYTHON) -m ruff check living_lexicon/ ingestor/ api/ langchain_plugin/

## Type-check the SDK package
typecheck:
	$(PYTHON) -m mypy living_lexicon/ --ignore-missing-imports

## Print available targets
help:
	@grep -E '^## ' Makefile | sed 's/^## //'
