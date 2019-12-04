.PHONY: test
test:
	docker-compose run --rm --entrypoint pytest jira --cov=jira_cli --disable-pytest-warnings test/
