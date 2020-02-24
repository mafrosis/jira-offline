'''
A module for custom application exceptions.

Many exceptions inherit from ClickException, which gives us handling for free in entrypoint
functions.
'''
from click import ClickException
import jira as mod_jira


class EpicNotFound(Exception):
    pass


class EstimateFieldUnavailable(Exception):
    pass


class SummaryAlreadyExists(Exception):
    pass


class MissingFieldsForNewIssue(Exception):
    pass


class DeserializeError(ValueError):
    pass


class JiraApiError(mod_jira.exceptions.JIRAError):
    '''Custom exception wrapping Jira library base exception'''


class FailedPullingProjectMeta(ClickException):
    '''Jira library error pulling project meta data'''
    def format_message(self):
        return f'Failed pulling project meta data! ({self.message})'
