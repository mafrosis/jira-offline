.PHONY: all
all: lint typecheck test
	@true

.PHONY: test
test:
	docker-compose run --rm test \
		-m 'not integration' \
		--cov=jira_offline --cov-report term --cov-report html:cov_html \
		--disable-pytest-warnings \
		test/

.PHONY: integration
integration:
	docker-compose run --rm test \
		-m 'integration' \
		--hostname=locke:8666 \
		--username=blackm \
		--password=eggseggs \
		--cwd=$$(pwd) \
		test/integration

.PHONY: lint
lint:
	docker-compose run --rm --entrypoint=pylint test jira_offline/
	docker-compose run --rm --entrypoint=pylint test --rcfile=test/.pylintrc test/

.PHONY: typecheck
typecheck:
	docker-compose run --rm test --mypy --mypy-ignore-missing-imports jira_offline/


.PHONY: package
package:
	rm -rf jira_offline.egg-info dist
	python3 setup.py sdist bdist_wheel

.PHONY: publish
publish:
	twine check dist/*
	twine upload --repository=test dist/*
