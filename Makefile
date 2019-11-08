.PHONY: test
test:
	docker-compose run --rm --entrypoint pytest jira --disable-pytest-warnings test/
