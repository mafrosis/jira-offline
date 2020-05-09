import contextlib
import dataclasses
import datetime
import functools
import logging
import textwrap
from typing import Any, Optional, Tuple

import arrow
from tabulate import tabulate

from jira_offline.utils.serializer import get_enum, get_type_class


@functools.lru_cache()
def get_field_by_name(cls: type, field_name: str) -> dataclasses.Field:
    '''
    Retrieve a field from the supplied dataclass by name

    Params:
        cls:         The class which has `field_name` as an attrib
        field_name:  Dataclass field name to find
    Returns:
        Dataclass field
    '''
    for f in dataclasses.fields(cls):
        if f.metadata.get('property') == field_name or f.name == field_name:
            return f
    raise Exception


@functools.lru_cache()
def friendly_title(cls: type, field_name: str) -> str:
    '''
    Util function to convert a dataclass field name into a friendly title

    Params:
        cls:         The class which has `field_name` as an attrib
        field_name:  Dataclass field to create a title for
    Returns:
        Pretty field title
    '''
    f = get_field_by_name(cls, field_name)
    return f.metadata.get('friendly', field_name.replace('_', ' ').title())


def render_field(cls: type, field_name: str, value: Any, prefix: str=None) -> Tuple[str, str]:
    '''
    Single-field pretty formatting function supporting various types

    Params:
        cls:         The class which has `field_name` as an attrib
        field_name:  Dataclass field to render
        value:       Value to be rendered according to dataclass.field type
        prefix:      Arbitrary prefix to prepend during string format
    Returns:
        Pretty field title, formatted value
    '''
    title = friendly_title(cls, field_name)

    # determine the origin type for this field (thus handling Optional[type])
    type_ = get_type_class(get_field_by_name(cls, field_name).type)

    # format value as dataclass.field type
    value = render_value(value, type_)

    if prefix:
        value = f'{prefix} {value}'

    return title, value


def render_value(value: Any, type_: Optional[type]=None) -> str:
    '''
    Params:
        value:  Value to be rendered according to type_
        type_:  Optional supplied
    Returns:
        Formatted value
    '''
    if not type_:
        type_ = type(value)

    if value is None:
        return ''
    elif type_ in (set, list):
        return tabulate([('-', v) for v in value], tablefmt='plain')
    elif type_ is datetime.datetime:
        dt = arrow.get(value)
        return f'{dt.humanize()} [{dt.format()}]'
    elif get_enum(type_):
        return value.value
    elif value and type_ is str and len(value) > 100:
        return '\n'.join(textwrap.wrap(value, width=100))
    else:
        return value


@contextlib.contextmanager
def critical_logger(logger_):
    '''
    Context manager which sets a logger to CRITICAL.

    with critical_logger(logger):
        ...
    '''
    log_level = logger_.level
    logger_.setLevel(logging.CRITICAL)
    yield logger_
    logger_.setLevel(log_level)
