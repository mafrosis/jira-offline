import contextlib
import dataclasses
import functools
import logging


@functools.lru_cache()
def get_field_by_name(field_name):
    '''
    Retrieve a field from the Issue dataclass by name
    '''
    # late import prevents circular dependency
    from jira_offline.models import Issue  # pylint: disable=import-outside-toplevel,cyclic-import
    for f in dataclasses.fields(Issue):
        if f.metadata.get('property') == field_name or f.name == field_name:
            return f


@functools.lru_cache()
def friendly_title(field_name):
    '''
    Util function to convert an Issue dataclass attribute name into a friendly title
    '''
    f = get_field_by_name(field_name)
    return f.metadata.get('friendly', field_name.replace('_', ' ').title())


@contextlib.contextmanager
def critical_logger(logger_):
    '''
    Context manager which sets a logger to CRITICAL.

    with set_logger_level_critical(logger):
        ...
    '''
    log_level = logger_.level
    logger_.setLevel(logging.CRITICAL)
    yield logger_
    logger_.setLevel(log_level)
