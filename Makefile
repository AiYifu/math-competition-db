.PHONY: build test run clean install help

help:
	@echo "Available commands:"
	@echo "  make install     - Install dependencies"
	@echo "  make build       - Build vector index"
	@echo "  make run         - Start services with docker-compose"
	@echo "  make test        - Run tests"
	@echo "  make clean       - Clean generated files"

install:
	pip install -r services/retrieval-service/requirements.txt
	pip install -r services/ocr-service/requirements.txt
	pip install -e shared/

build:
	python scripts/data_pipeline.py
	python scripts/build_index.py

run:
	docker-compose up -d

run-local:
	cd services/retrieval-service && uvicorn src.main:app --reload --port 8002 &
	cd services/ocr-service && uvicorn src.main:app --reload --port 8001

test:
	pytest services/retrieval-service/tests/ -v
	pytest services/ocr-service/tests/ -v

clean:
	rm -rf data/processed/*
	rm -rf data/indices/*
	docker-compose down -v