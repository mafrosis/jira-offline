'''
A module for custom application exceptions.

Many exceptions inherit from ClickException, which gives us handling for free in entrypoint
functions.
'''
from click import ClickException
import jira as mod_jira


class DeserializeError(ValueError):
    pass


class JiraApiError(mod_jira.exceptions.JIRAError):
    '''Custom exception wrapping Jira library base exception'''


class BaseAppException(ClickException):
    '''Wrapper exception around click.ClickException'''
    def __init__(self, msg=''):  # pylint: disable=useless-super-delegation
        super().__init__(msg)


class EpicNotFound(BaseAppException):
    '''Raised when attempting map an issue to an epic that doesnt exist'''
    def format_message(self):
        return f"Epic doesn't exist! ({self.message})"


class SummaryAlreadyExists(BaseAppException):
    '''Raised when creating an issue where the summary text is already used in another issue'''
    def format_message(self):
        return 'The exact summary text supplied is already in use.'


class MissingFieldsForNewIssue(BaseAppException):
    pass


class InvalidIssueType(BaseAppException):
    '''
    Only a small set of issuetypes are available on each project. An error occurs if create_issue is
    called with an invalid issuetype
    '''


class CliError(BaseAppException):
    '''Raised when bad params are passed to a CLI command'''


class UnreadableConfig(BaseAppException):
    '''Raised when load_config cannot read the config file'''


class NoProjectsSetup(BaseAppException):
    '''Raised when pull_issues is called without any projects setup to pull'''
    def format_message(self):
        return 'No projects setup, use the clone command.'


class ProjectDoesntExist(BaseAppException):
    '''Raised when specified project key doesnt exist in Jira'''
    def format_message(self):
        return f'Project {self.message} does not exist!'


class ProjectNotConfigured(BaseAppException):
    '''Raised when trying to pull a project which has not been cloned'''
    def format_message(self):
        return (
            'The project {key} is not currently configured! You must first load the project with '
            'this command:\n\n  jiracli clone https://jira.atlassian.com:8080/{key}\n'.format(
                key=self.message
            )
        )


class JiraNotConfigured(BaseAppException):
    '''
    Raised if Jira is not setup correctly
    '''
    def __init__(self, project_key, jira_server, msg=''):  # pylint: disable=useless-super-delegation
        'Special constructor to make the Jira server details available in a friendly error message'
        self.project_key = project_key
        self.jira_server = jira_server
        super().__init__(msg)

    def format_message(self):
        msg = '''Jira screens are not configured correctly. Unable to continue.

Go to your Jira project screens configuration:
{host}/plugins/servlet/project-config/{proj}/screens

Ensure that "Story Points" is on the fields list.'''.strip().format(
    host=self.jira_server, proj=self.project_key
)

        if self.message:
            msg += f'\n\n  > {msg}'

        return msg


class EstimateFieldUnavailable(JiraNotConfigured):
    '''Raised when Story Points field is missing'''


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


class IssuePriorityInvalid(BaseAppException):
    '''Setting Issue.priority to an invalid string will cause this exception'''
    def format_message(self):
        return f'Invalid priority setting!\n\nYou have the following options:\n{self.message}'
