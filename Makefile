.PHONY: install lint test run build tf-plan tf-apply dbt

install:
	pip install -e ".[dev]"

lint:
	ruff check . && ruff format --check .

test:
	pytest

run:  ## local API on http://localhost:8000/docs (needs AWS creds or floci/LocalStack)
	uvicorn life_api.api.app:create_app --factory --reload

build:
	python scripts/build_lambda.py

tf-plan: build
	cd infra/terraform && terraform plan

tf-apply: build
	cd infra/terraform && terraform apply

dbt:
	cd dbt/life && dbt build --profiles-dir .
