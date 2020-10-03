import functools

from jira_offline.auth import get_user_creds
from jira_offline.exceptions import FailedAuthError
from jira_offline.models import ProjectMeta


def auth_retry():
    '''
    This decorator will prompt for a username/password on the CLI, should the wrapped function raise
    a `FailedAuthError`.

    The first argument to the wrapped function *must* be an instance of ProjectMeta, so that the new
    auth credentials can be written to the config JSON.
    '''
    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            if not isinstance(args[1], ProjectMeta):
                raise TypeError('First argument to auth_retry decorator must be ProjectMeta instance')

            try:
                return f(*args, **kwargs)
            except FailedAuthError as e:
                print(e)
                # prompt for new credentials
                get_user_creds(args[1])
                args[1].config.write_to_disk()
                return f(*args, **kwargs)
        return wrapped
    return decorator
