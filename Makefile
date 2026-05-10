.PHONY: dev test test-all migrate import-senses import-gcide import-frequency import-morphemes import-word-relations sync-neo4j make-snapshot lint typecheck help

## Start Docker services and the API app
dev:
	docker compose up -d postgres neo4j ollama
	docker compose up app

## Run the fast test suite (no Neo4j/Ollama required)
test:
	pytest tests/ test_word_detective.py test_shipley_importer.py \
	       test_senses_importer.py test_data_quality_validator.py -v

## Run the full test suite across all testpaths
test-all:
	pytest -v

## Apply all pending Alembic migrations
migrate:
	alembic upgrade head

## Import senses from the default CSV path
import-senses:
	python -m ingestor.senses_importer

## Import Webster's 1913 (GCIDE) words and senses into PostgreSQL
import-gcide:
	python -m ingestor.gcide_importer

## Import morpheme decompositions from CSV (Words/morphemes.csv)
import-morphemes:
	python -m ingestor.morphemes_importer

## Import semantic and derivational word relations from CSV (Words/sources/word_relations.csv)
import-word-relations:
	python -m ingestor.word_relations_importer

## Sync PostgreSQL words → Neo4j graph (run after any bulk import)
sync-neo4j:
	python -m ingestor.neo4j_sync

## Load wordfreq Zipf scores into the PostgreSQL words table
import-frequency:
	python -m ingestor.frequency_pg_importer

## Create a citable dataset snapshot (requires ADMIN_API_TOKEN + running API)
make-snapshot:
	@echo "POST /pg/snapshots to create a snapshot — set TAG and DESC:"
	@echo "  curl -X POST http://localhost:8000/pg/snapshots \\"
	@echo "    -H 'Authorization: Bearer $$ADMIN_API_TOKEN' \\"
	@echo "    -H 'Content-Type: application/json' \\"
	@echo "    -d '{\"tag\": \"v$$(date +%Y-%m-%d)\", \"description\": \"Auto snapshot\"}'"

## Lint all source packages
lint:
	ruff check living_lexicon/ ingestor/ api/ langchain_plugin/

## Type-check the SDK package
typecheck:
	mypy living_lexicon/ --ignore-missing-imports

## Print available targets
help:
	@grep -E '^## ' Makefile | sed 's/^## //'
