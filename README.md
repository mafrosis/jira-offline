Git-like CLI for using Jira offline
=================


[![Github build status](https://img.shields.io/github/workflow/status/mafrosis/jira-offline/Build-Test-Publish)](https://github.com/mafrosis/jira-offline/actions?query=workflow%3ABuild-Test-Publish)
[![PyPI version](https://img.shields.io/pypi/v/jira-offline.svg)](https://pypi.python.org/pypi/jira-offline/)
[![PyPI status](https://img.shields.io/pypi/status/jira-offline.svg)](https://pypi.python.org/pypi/jira-offline/)
[![PyPI pyversions](https://img.shields.io/pypi/pyversions/jira-offline.svg)](https://pypi.python.org/pypi/jira-offline/)
[![PyPI license](https://img.shields.io/pypi/l/jira-offline.svg)](https://pypi.python.org/pypi/jira-offline/)

Work offline and sync your changes back to Jira later. Create issues, modify issues, view stats,
run Jira health queries.. All from a friendly git-like CLI.


Installation
------------

A few options exist:

  1. Use the quickstart to pull and run a docker image (see #quickstart)
  2. Install with pip into your current user account
  3. Clone the source code and use docker compose

### Quickstart

Using the docker image published on Github, the following will get you going very quickly:

    docker pull docker.pkg.github.com/mafrosis/jira-offline/jira-offline:dev
    docker run --rm -it docker.pkg.github.com/mafrosis/jira-offline/jira-offline:dev

### Install with pip

    pip install git+https://github.com/mafrosis/jira-offline.git@master

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
