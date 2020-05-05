Git-like CLI for using Jira offline
=================

[![Github build status](https://github.com/mafrosis/jira-offline/workflows/build/badge.svg)](https://github.com/mafrosis/jira-offline/actions?query=workflow%3Abuild)
[![PyPI version](https://img.shields.io/pypi/v/jira-offline.svg)](https://pypi.python.org/pypi/jira-offline/)
[![PyPI status](https://img.shields.io/pypi/status/jira-offline.svg)](https://pypi.python.org/pypi/jira-offline/)
[![PyPI pyversions](https://img.shields.io/pypi/pyversions/jira-offline.svg)](https://pypi.python.org/pypi/jira-offline/)
[![PyPI license](https://img.shields.io/pypi/l/jira-offline.svg)](https://pypi.python.org/pypi/jira-offline/)

Work offline and sync your changes back to Jira later. Create issues, modify issues, view stats,
run Jira health queries.. All from a friendly git-like CLI.


Installation
------------

A few options exist:

  1. Install globally with pip (not recommended)
  2. Install with pip
  3. Pull and run the latest docker image
  4. Clone the source code and use docker compose

### Install with pip

    pip install jira-offline

### Install with pip, into a virtualenv

    python3 -m venv venv && source venv/bin/activate
    pip install jira-offline

### Docker image

Unfortunately you need an access token for even public packages hosted on Github. Get yours from
[your settings](https://github.com/settings/tokens). Pull the docker image and run it:

    echo "$GITHUB_TOKEN" | docker login -u mafrosis --password-stdin docker.pkg.github.com
    docker pull docker.pkg.github.com/mafrosis/jira-offline/jira-offline:dev
    docker run --rm -it docker.pkg.github.com/mafrosis/jira-offline/jira-offline:dev

### Clone and use compose

    git clone https://github.com/mafrosis/jira-offline.git
    cd jira-offline
    docker-compose build jira-offline
    docker-compose run --rm jira-offline


Known Limitations
-----------------

See the [Github Issues](https://github.com/mafrosis/jira-offline/issues) for a comprehensive list.

* You can't change the state of an issue (eg. In Progress -> Done)
([GH21](https://github.com/mafrosis/jira-offline/issues/21)).
* You can't change an issue's type from (for example) Bug -> Story
([GH20](https://github.com/mafrosis/jira-offline/issues/20)).
* There are mandatory fields required on Jira project screens
([GH16](https://github.com/mafrosis/jira-offline/issues/16)).
* It's slow. Reading and writing all data to a single JSONL file is inefficient, and the use of the
  Pandas library is making the CLI slow
([GH13](https://github.com/mafrosis/jira-offline/issues/13)).
* No support for the same project key from two different Jiras (an edge-case at this stage).
* There's a known race condition where a Jira project's issuetypes and priority values can be changed
  whilst working offline. This could mean that broken issues are created offline
([GH22](https://github.com/mafrosis/jira-offline/issues/22)).


Quick Start
-----------

**NB**: The following examples assume `jira` is available in `$PATH`

### Clone

The `clone` command is used to to setup a new project, which takes a single URI describing your
project.

### Authentication to Jira

There are two auth options, basic and oAuth.

#### Basic Auth

Basic auth is quick and takes your existing username and password. Beware that this will *write your
password into the config file on disk*.

    jira clone --username benji https://jira.atlassian.com/PROJ

You will be prompted for your password.

#### oAuth

oAuth is preferred, as it's token based and doesn't require your password. However it requires the
setup of an `Application Link` on the Jira server.

    jira clone --oauth-private-key=applink.pem https://jira.atlassian.com/PROJ


How To Use
----------

**NB**: The following examples assume `jira` is available in `$PATH`

### How to configure a new Jira project

Use `clone` to add a project:

    jira clone https://jira.atlassian.com/PROJ


Contributing
------------

In order to contribute, please fork this repo on Github and raise pull a request with your changes.

You can see a simple development/debugging workflow in the [debugging section](#debugging).


## Run The Tests

There are four types of testing/validation in the source code:

 1. Linting of syntactic code errors, and other Python style issues with [`pylint`](http://pylint.org)
 2. Typechecking of the python, based on the type-hints in the source using [`mypy`](http://mypy-lang.org)
 3. Unit testing via [`pytest`](https://docs.pytest.org/en/latest), by running all the [tests](./tests)
 4. Integration testing - which requires a local instance of Jira

The `Makefile` run the first three steps in order, when you invoke the `make` command on its own.
These three checks are also run on every pull request - and must pass for your code to mergeable.

You can invoke any individual stage directly with:

 1. `make lint`
 2. `make typecheck`
 3. `make test`
 4. `make integration`


## Debugging

The simplest way to debug before opening an issue or contributing is to run the application from
source code in a docker container, using the `test` image.

 1. Clone the source code to your machine

 2. Build the main & test docker images:

```
docker-compose build jira-offline
docker-compose build test
```

 3. Edit `docker-compose.yml` on line 5, to use the `-test` image:

```
jira-offline:
  image: mafrosis/jira-offline-test
```

 4. Add a breakpoint in the code with `import ipdb; ipdb.set_trace()`

 5. Run the main docker image, which will then break:

```
docker-compose run --rm jira-offline <CMD>
```


Comparison to other Jira CLIs
-----------------------------

None of the existing clients use the "offline" approach taken by this tool:

- [`danshumaker/jira-cli`](https://github.com/danshumaker/jira-cli) -
A full featured node.js CLI. This might be a better option if `jira-offline` lacks features you need.
- [`keepcosmos/terjira`](https://github.com/keepcosmos/terjira) -
Feature-rich Ruby CLI with a neat interactive query function.
- [`mikepea/go-jira-ui`](https://github.com/mikepea/go-jira-ui) -
A neat ncurses client focussed on listing issues and making simple changes.
- [`foxythemes/jira-cli`](https://github.com/foxythemes/jira-cli) -
A handsome node.js REPL-style interactive CLI. A very different approach from `jira-offline`.
- [`toabctl/jiracli`](https://github.com/toabctl/jiracli) -
A simple CLI for Jira. Not actively maintained.
- [`alisaifee/jira-cli`](https://github.com/alisaifee/jira-cli) -
Another unmaintained and poorly-documented CLI.
