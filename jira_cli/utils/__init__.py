import contextlib
import dataclasses
import functools
import logging


@functools.lru_cache()
def friendly_title(field_name):
    '''
    Util function to convert a dataclass field name into a friendly title
    '''
    # late import prevents circular dependency
    from jira_cli.models import Issue  # pylint: disable=import-outside-toplevel,cyclic-import
    try:
        for f in dataclasses.fields(Issue):
            if f.name == field_name:
                return f.metadata['friendly']
    except KeyError:
        return field_name.replace('_', ' ').title()


class classproperty(property):
    def __get__(self, cls, owner):
        return classmethod(self.fget).__get__(None, owner)()


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
