'''
A module for custom application exceptions.

Many exceptions inherit from ClickException, which gives us handling for free in entrypoint
functions.
'''
from click import ClickException
import jira as mod_jira

# pylint: disable=no-self-use


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


class BaseAppException(ClickException):
    '''Wrapper exception around click.ClickException'''
    def __init__(self, msg=''):  # pylint: disable=useless-super-delegation
        super().__init__(msg)


class UnreadableConfig(BaseAppException):
    '''Terminal. Raised when load_config cannot read the config file'''


class NoProjectsSetup(BaseAppException):
    '''Terminal. Raised when pull_issues is called without any projects setup to pull'''
    def format_message(self):
        return 'No projects setup, use the clone command.'


class ProjectDoesntExist(BaseAppException):
    '''Terminal. Raised when specified project key doesnt exist in Jira'''
    def format_message(self):
        return f'Project {self.message} does not exist!'


class ProjectNotConfigured(BaseAppException):
    '''Terminal. Raised when trying to pull a project which has not been cloned'''
    def format_message(self):
        return (
            'The project {key} is not currently configured! You must first load the project with '
            'this command:\n\n  jiracli clone {key}\n'.format(key=self.message)
        )


class JiraNotConfigured(BaseAppException):
    '''Terminal. Raised if Jira is not setup correctly'''
    def format_message(self):
        return '''
Jira screens are not configured correctly. Unable to continue.

Go to your Jira project screens configuration:
http://{}/plugins/servlet/project-config/{}/screens

Ensure that "Story Points" is on the fields list.
'''.strip()


class FailedPullingProjectMeta(BaseAppException):
    '''Jira library error pulling project meta data'''
    def format_message(self):
        return f'Failed to clone the project. Please try again! ({self.message})'


class FailedPullingIssues(BaseAppException):
    '''Jira library error pulling project issues'''
    def format_message(self):
        return f'Failed pulling project issues. Please try again! ({self.message})'


class FailedAuthError(BaseAppException):
    '''Failed oAuth flow'''
    def format_message(self):
        return f'Failed to authenticate with Jira ({self.message})'


class JiraUnavailable(BaseAppException):
    '''Couldnt talk to Jira'''
    def format_message(self):
        return f'Jira appears unavailable ({self.message})'


class NoAuthenticationMethod(BaseAppException):
    '''Jira.connect was called with no authentication method configured'''
    def format_message(self):
        return f'No way to authenticate!'
