import contextlib
import dataclasses
import functools
import logging


@functools.lru_cache()
def get_field_by_name(cls, field_name: str) -> dataclasses.Field:
    '''
    Retrieve a field from the supplied dataclass by name
    '''
    for f in dataclasses.fields(cls):
        if f.metadata.get('property') == field_name or f.name == field_name:
            return f
    raise Exception


@functools.lru_cache()
def friendly_title(cls, field_name: str) -> str:
    '''
    Util function to convert a dataclass field name into a friendly title
    '''
    f = get_field_by_name(cls, field_name)
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
