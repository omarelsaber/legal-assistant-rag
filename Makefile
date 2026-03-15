.PHONY: test ingest evaluate up down

test:
	pytest

ingest:
	python scripts/ingest.py

evaluate:
	python scripts/run_evaluation.py

up:
	docker-compose up -d

down:
	docker-compose down