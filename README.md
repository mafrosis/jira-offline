CLI for using Jira offline
=======

Work offline and sync your changes back upstream. View stats, generate reports, find errors in your
Jira setup.


Quickstart
----------

    docker-compose rm --rm jiracli


Adding a new field from Jira
----------------------------

It's very easy to include a new field from Jira. Two steps are required:

  1. Include the field in the Issue model in [models.py](./jira_cli/models.py)
  2. Include the field in the `_raw_issue_to_object` method in [sync.py](./jira_cli/sync.py)
