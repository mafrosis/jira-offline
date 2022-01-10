'''
A module for custom application exceptions.

Many exceptions inherit from ClickException, which gives us handling for free in entrypoint
functions.
'''
import logging
import traceback

import click


logger = logging.getLogger('jira')


class DeserializeError(ValueError):
    pass

class SerializeError(ValueError):
    pass


class JiraApiError(Exception):
    '''
    Custom base exception for handling error cases from the Jira API
    '''
    def __init__(self, message='', status_code=None, method=None, path=None):
        self.status_code = status_code
        self.method = method
        self.path = path
        self.message = message
        super().__init__(message)

    def __str__(self):
        if self.status_code:
            return f'{self.status_code} returned from {self.method} {self.path}\n\n{self.message}'
        else:
            return self.message


class BaseAppException(click.ClickException):
    '''
    Base exception inherited by all general usage execeptions.
    Inherits click.ClickException, so that when raised, these are conveniently handled by the click
    library and the output `format_message` is printed on the CLI.
    '''
    def __init__(self, message=None, extra_message=''):
        self.extra_message = str(extra_message).strip()

        # If a str is passed as the first parameter, then simply treat per a normal exception.
        # Else, call the exception objects __str__ method to return the message string.
        if message:
            super().__init__(message)
        else:
            super().__init__(str(self))

    def show(self):  # pylint: disable=arguments-differ
        super().show()
        # if --debug was passed on CLI, the global logger will be at logging.DEBUG.  In this case,
        # print a stack trace
        if logger.level == logging.DEBUG:
            traceback.print_exc()

    def format_message(self):
        # if --debug or --verbose were passed on CLI, the global logger will be at logging.INFO
        # or logging.DEBUG. In these cases, print the extra message.
        if self.extra_message and logger.level <= logging.INFO:
            return f'{self.message}\n\n{self.extra_message}'
        else:
            return self.message

    def __str__(self):
        '''
        Vanilla __str__ method which returns __doc__ without formatting. Should be overriden in
        child classes.
        '''
        return self.__doc__


# Raised when attempting map an issue to an epic that doesnt exist
class EpicNotFound(BaseAppException):
    """Epic {} doesn't exist!"""

    def __init__(self, epic_link):
        self.epic_link = epic_link
        super().__init__()

    def __str__(self):
        return self.__doc__.format(self.epic_link)


# Raised when Issue.__setattr__ is called when the Issue object has no reference to the central
# Jira instance
class CannotSetFieldOnIssueWithoutJira(BaseAppException):
    'Issue does not have a reference to Jira'


class InvalidIssueType(BaseAppException):
    '''
    Only a small set of issuetypes are available on each project. An error occurs if `create_issue`
    is called with an invalid issuetype
    '''


# Each issuetype has a number of configured statuses. It's an error to set an invalid status
class InvalidIssueStatus(BaseAppException):
    'Invalid status!\n\nYou have the following options:\n{}'

    def __init__(self, options):
        self.options = options
        super().__init__()

    def __str__(self):
        return self.__doc__.format(self.options)


# Each issuetype has a number of configured priorities. It's an error to set an invalid priority
class InvalidIssuePriority(BaseAppException):
    'Invalid priority!\n\nYou have the following options:\n{self.message}'

    def __init__(self, options):
        self.options = options
        super().__init__()

    def __str__(self):
        return self.__doc__.format(self.options)


class CliError(BaseAppException):
    'Raised when bad params are passed to a CLI command'


# Raised when load_config cannot read the config file
class UnreadableConfig(BaseAppException):
    def __init__(self, message, path: str=None):
        self.path = path
        super().__init__(message)

    def __str__(self):
        msg = self.message
        if self.path:
            msg += f' at {self.path}'
        return msg


# Raised when pull_issues is called without any projects setup to pull
class NoProjectsSetup(BaseAppException):
    'No projects setup, use the clone command.'


# Raised when specified project key doesnt exist in Jira
class ProjectDoesntExist(BaseAppException):
    'Project {} does not exist!'

    def __init__(self, project):
        self.project = project
        super().__init__()

    def __str__(self):
        return self.__doc__.format(self.project)


# Raised when trying to pull a project which has not been cloned
class ProjectNotConfigured(BaseAppException):
    'The project {key} is not currently configured! You must first load the project with this command:\n\n  jira clone https://jira.atlassian.com:8080/{key}'

    def __init__(self, key):
        self.key = key
        super().__init__()

    def __str__(self):
        return self.__doc__.format(key=self.key)


class BadProjectMetaUri(BaseAppException):
    '''Badly formed Jira project URI passed, must be of the form:

https://jira.atlassian.com:8080/PROJ'''


# Raised if Jira is not setup correctly
class JiraNotConfigured(BaseAppException):
    'Jira screens are not configured correctly. Unable to continue.'

    def __init__(self, project_key, jira_server, extra_message=''):
        self.project_key = project_key
        self.jira_server = jira_server
        self.extra_message = extra_message
        super().__init__()

    def __str__(self):
        return self.__doc__.format(host=self.jira_server, proj=self.project_key)


class FailedPullingProjectMeta(BaseAppException):
    'Failed to fetch project metadata. Please try again!'


class FailedPullingIssues(BaseAppException):
    'Failed pulling project issues. Please try again!'


class FailedAuthError(BaseAppException):
    'Failed to authenticate with Jira'


class JiraUnavailable(BaseAppException):
    'Jira appears unavailable'


# Jira.connect was called with no authentication method configured
class NoAuthenticationMethod(BaseAppException):
    'No way to authenticate!'


# Raised when trying to link an epic by a summary/epic name that has been used multiple times
class EpicSearchStrUsedMoreThanOnce(BaseAppException):
    'Unable to link to the specified issue, as two issues match search string "{}". Please try referencing key (eg. JIRA-123)'

    def __init__(self, epic_summary):
        self.epic_summary = epic_summary
        super().__init__()

    def __str__(self):
        return self.__doc__.format(self.epic_summary)


# Failure when copying a custom CA cert into application config directory
class UnableToCopyCustomCACert(BaseAppException):
    'Failed copying certificate file'


# Failure when upgrading an app config from one schema to another
class FailedConfigUpgrade(BaseAppException):
    'Failed upgrading the app.config schema. Please re-run with --debug and report this bug.'


# Failure when importing a JSON object as an Issue
class ImportFailed(BaseAppException):
    pass


class NoInputDuringImport(BaseAppException):
    'No data was found in supplied file or STDIN during the import'


# Raised by Jira.update when a sync returns Issues with a different timezone to those already present
class MultipleTimezoneError(Exception):
    '''A change Jira of timezone is unsupported, please run:

jira pull --reset-hard
'''


class EditorFieldParseFailed(BaseAppException):
    'Failed parsing the return from the editor!'

class EditorRepeatFieldFound(EditorFieldParseFailed):
    'Field "{}" was found twice in the output from the editor!'

    def __init__(self, field_name):
        self.field_name = field_name
        super().__init__()

    def __str__(self):
        return self.__doc__.format(self.field_name)

class EditorNoChanges(EditorFieldParseFailed):
    'No changes made in the editor!'


class FilterMozParseFailed(BaseAppException):
    'Invalid SQL WHERE clause passed as filter string'

class FilterQueryParseFailed(BaseAppException):
    'Failed processing filter string: {}'

    def __init__(self, excp=None):
        self.message = str(excp) or ''
        super().__init__(self.message)

    def __str__(self):
        return self.__doc__.format(self.message)

class FilterQueryEscapingError(FilterQueryParseFailed):
    'Ensure your whole filter string is not double-escaped'

class FilterUnknownFieldException(BaseAppException):
    'Unknown field "{}" passed in SQL filter.'

    def __init__(self, field):
        self.field = field
        super().__init__()

    def __str__(self):
        return self.__doc__.format(self.field)

class FilterUnknownOperatorException(BaseAppException):
    'Unknown operator "{}" passed in SQL filter. Please report as an issue.'

    def __init__(self, operator_):
        self.operator = operator_
        super().__init__()

    def __str__(self):
        return self.__doc__.format(self.operator)


class UserConfigAlreadyExists(BaseAppException):
    'Config file already exists at {}!'

    def __init__(self, operator_):
        self.operator = operator_
        super().__init__()

    def __str__(self):
        return self.__doc__.format(self.operator)


class InvalidLsFieldInConfig(BaseAppException):
    'Invalid field specified in config.display.ls: {}'

    def __init__(self, field):
        self.field = field
        super().__init__()

    def __str__(self):
        return self.__doc__.format(self.field)


class BadParamsPassedToValidCustomfield(BaseAppException):
    'ValidCustomfield constructor must be passed `key` or `projectkey`'


class FieldNotOnModelClass(BaseAppException):
    '{} does not exist!'

    def __init__(self, field):
        self.field = field
        super().__init__()

    def __str__(self):
        return self.__doc__.format(self.field)

class MustFilterOnProjectWithSprint(BaseAppException):
    'You must filter on project when also filtering on sprint'
