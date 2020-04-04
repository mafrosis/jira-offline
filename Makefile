.PHONY: all
all: lint typecheck test
	@true

.PHONY: test
test:
	docker-compose run --rm --entrypoint=pytest test --cov=jira_cli --cov-report term --cov-report html:cov_html --disable-pytest-warnings test/

.PHONY: lint
lint:
	docker-compose run --rm --entrypoint=pylint test jira_cli/
	docker-compose run --rm --entrypoint=pylint test --rcfile=test/.pylintrc test/

.PHONY: typecheck
typecheck:
	docker-compose run --rm --entrypoint pytest test --mypy --mypy-ignore-missing-imports jira_cli/
