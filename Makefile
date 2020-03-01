.PHONY: all
all: lint typecheck test
	@true

.PHONY: test
test:
	docker-compose run --rm --entrypoint=pytest jiracli --cov=jira_cli --cov-report term --cov-report html:cov_html --disable-pytest-warnings test/

.PHONY: lint
lint:
	docker-compose run --rm --entrypoint=pylint jiracli jira_cli/
	docker-compose run --rm --entrypoint=pylint jiracli --rcfile=test/.pylintrc test/

.PHONY: typecheck
typecheck:
	docker-compose run --rm --entrypoint pytest jiracli --mypy --mypy-ignore-missing-imports jira_cli/
