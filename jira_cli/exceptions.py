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


class JiraNotConfigured(ClickException):
    '''Terminal. Raised if Jira is not setup correctly'''
    def format_message(self):
        return '''
Jira screens are not configured correctly. Unable to continue.

Go to your Jira project screens configuration:
http://{}/plugins/servlet/project-config/{}/screens

Ensure that "Story Points" is on the fields list.
'''.strip()


class JiraApiError(mod_jira.exceptions.JIRAError):
    '''Custom exception wrapping Jira library base exception'''


class FailedPullingProjectMeta(ClickException):
    '''Jira library error pulling project meta data'''
    def format_message(self):
        return f'Failed pulling project meta data! ({self.message})'


class FailedPullingIssues(ClickException):
    '''Jira library error pulling project issues'''
    def format_message(self):
        return f'Failed pulling project issues. Please try again! ({self.message})'
