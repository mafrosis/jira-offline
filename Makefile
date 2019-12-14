.PHONY: test
test:
	docker-compose run --rm --entrypoint pytest jiracli --cov=jira_cli --disable-pytest-warnings test/
