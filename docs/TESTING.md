Testing Guide
=============

There are four types of testing/validation in the source code:

 1. Typechecking of the python, based on the type-hints in the source using [`mypy`](http://mypy-lang.org)
 2. Linting of syntactic code errors, and other Python style issues with [`pylint`](http://pylint.org)
 3. Unit testing via [`pytest`](https://docs.pytest.org/en/latest), by running all the [tests](./tests)
 4. Integration testing - which requires a local instance of Jira

The `Makefile` run the first three steps in order, when you invoke the `make` command on its own.
These three checks are also run on every pull request - and must pass for your code to mergeable.

You can invoke any individual stage directly with:

 1. `make typecheck`
 2. `make lint`
 3. `make test`
 4. `make integration`


Type Hinting with mypy
----------------------


Linting with pylint
-------------------


Unit tests with pytest
----------------------


Integration tests in docker
---------------------------

