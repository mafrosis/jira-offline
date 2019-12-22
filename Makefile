.PHONY: test
test:
	docker-compose run --rm --entrypoint pytest jiracli --cov=jira_cli --cov-report term --cov-report html:cov_html --disable-pytest-warnings test/
