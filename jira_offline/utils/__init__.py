import contextlib
import dataclasses
import datetime
import decimal
import functools
import logging
import textwrap
from typing import Any, cast, Dict, Hashable, List, Optional, Tuple, TYPE_CHECKING
from tzlocal import get_localzone

import arrow
import click
import numpy
import pandas as pd
from tabulate import tabulate

from jira_offline.exceptions import DeserializeError, FieldNotOnModelClass, ProjectNotConfigured
from jira_offline.utils.serializer import deserialize_value, get_enum, get_base_type, istype

if TYPE_CHECKING:
    from jira_offline.models import ProjectMeta, Issue  # pylint: disable=cyclic-import
    from jira_offline.jira import Jira  # pylint: disable=cyclic-import


@functools.lru_cache()
def get_field_by_name(cls: type, field_name: str) -> dataclasses.Field:
    '''
    Lookup a field by name from the passed dataclass

    Params:
        cls:         The dataclass type on which to search
        field_name:  Filter for fields by this name
    Returns:
        Dataclass field
    '''
    for f in dataclasses.fields(cls):
        if f.name == field_name:
            return f
    raise FieldNotOnModelClass(f'{cls}.{field_name}')


@functools.lru_cache()
def iter_issue_fields_by_type(*args: type) -> List[dataclasses.Field]:
    '''
    Return list of Issue fields matching the passed type

    Params:
        field_type:  Filter for fields of this type
    Returns:
        List of dataclasses.Field objects
    '''
    # late import to avoid circular dependency
    from jira_offline.models import Issue  # pylint: disable=import-outside-toplevel

    return [f for f in dataclasses.fields(Issue) if istype(cast(Hashable, f.type), args)]


@functools.lru_cache()
def get_dataclass_defaults_for_pandas(cls: type) -> Dict[str, Any]:
    '''
    Return a mapping of Issue.field_name->default, where the default is compatible with pandas
    '''
    attrs: Dict[str, Any] = dict()

    for f in dataclasses.fields(cls):
        # Special case for Issue.modified where empty is stored as numpy.nan
        if f.name == 'modified':
            attrs['modified'] = numpy.nan
            continue

        if f.default != dataclasses.MISSING:
            # Cast for mypy as istype uses @functools.lru_cache
            typ_ = cast(Hashable, f.type)

            if istype(typ_, datetime.datetime):
                attrs[f.name] = pd.to_datetime(0).tz_localize('utc')
            elif istype(typ_, (list, decimal.Decimal)):
                attrs[f.name] = ''
            else:
                attrs[f.name] = get_base_type(typ_)()
    return attrs


def find_project(jira: 'Jira', project_key: str) -> 'ProjectMeta':
    '''
    Extract the project configuration object for the specified project key

    Params:
        jira:         Dependency-injected jira.Jira object
        project_key:  Short Jira project key
    '''
    try:
        return next(p for p in jira.config.projects.values() if p.key == project_key)
    except StopIteration:
        raise ProjectNotConfigured(project_key)


@functools.lru_cache()
def friendly_title(cls: type, field_name: str) -> str:
    '''
    Util function to convert a dataclass field name into a friendly title. If `field_name` does not
    exist as a field on the dataclass, return a capitalised string.

    Params:
        cls:         The class which has `field_name` as an attrib
        field_name:  Dataclass field to create a title for
    Returns:
        Pretty field title
    '''
    try:
        f = get_field_by_name(cls, field_name)
        title = f.metadata.get('friendly', field_name)

    except FieldNotOnModelClass:
        if field_name.startswith('extended.'):
            # Trim the 'extended.' prefix from Issue class extended customfields
            title = field_name[9:]
        else:
            title = field_name

    return str(title.replace('_', ' ').title())


def render_dataclass_field(cls: type, field_name: str, value: Any) -> Tuple[str, str]:
    '''
    A simple single-field pretty formatting function supporting various types.

    Params:
        cls:           The class which has `field_name` as an attrib
        field_name:    Dataclass attribute name to render
        value:         Value to be rendered according to dataclass.field type
    Returns:
        Tuple of field title, formatted value
    '''
    title = friendly_title(cls, field_name)

    try:
        f = get_field_by_name(cls, field_name)

        # Execute a pre-render util function on the field value, if one is defined
        prerender_func = f.metadata.get('prerender_func')
        if callable(prerender_func):
            value = prerender_func(value)

        # Determine the origin type for this field (thus handling Optional[type])
        type_ = get_base_type(cast(Hashable, f.type))

        # Format value as type specified by dataclass.field
        value = render_value(value, type_)

    except FieldNotOnModelClass:
        # Assume string type if `field_name` does not exist on the dataclass - likely it's an
        # extended field
        value = render_value(value, str)

    return title, value


def render_issue_field(
        issue: 'Issue', field_name: str, value: Any, value_template: Optional[str]=None,
        diff: Optional[str]=None
    ) -> Tuple[str, str]:
    '''
    A slighty more complicated single-field pretty formatting function, specifically for fields on an
    instance of the Issue dataclass.

    Params:
        issue:           Instance of Issue class with the field to render
        field_name:      Issue dataclass attribute name to render
        value:           Value to be rendered, the type of the dataclass.field
        value_template:  Optional f-string template to use to format the value
        diff:            A single char to prepend the field title, when rendering a diff
    Returns:
        Pretty field title, formatted value
    '''
    title, value = render_dataclass_field(type(issue), field_name, value)

    if value_template:
        value = value_template.format(value)

    if diff:
        if diff == '+':
            return f'[green]+{title}[/]', f'[green]{value}[/]'
        else:
            return f'[red]-{title}[/]', f'[red]{value}[/]'

    return f'[bright_black]{title}[/]', value


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
    elif type_ is dict:
        return tabulate(value.items(), tablefmt='plain')
    elif type_ is datetime.datetime:
        dt = arrow.get(value)
        return f'{dt.humanize()} [{dt.format()}]'
    elif get_enum(type_):
        return str(value.value)
    elif value and type_ is str and len(value) > 100:
        return '\n'.join(textwrap.wrap(value, width=100))
    else:
        return str(value)


def deserialize_single_issue_field(
        field_name: str, value: Optional[Any], project: Optional['ProjectMeta']=None,
        type_override: Optional[type]=None
    ) -> Any:
    '''
    Use DataclassSerializer.deserialize_value to convert from string to the correct type.

    Params:
        field_name:     Name of the field Issue dataclass
        value:          Value to deserialize to field_name's type
        project:        Properties of the project this issue belongs to
        type_override:  Deserialize to a different type than specified on the Issue model field
    '''
    if value is None:
        return

    try:
        # late import to avoid circular dependency
        from jira_offline.models import Issue  # pylint: disable=import-outside-toplevel

        if type_override:
            typ = type_override
        else:
            typ = get_field_by_name(Issue, field_name).type

        if not project:
            return deserialize_value(typ, value, tz=get_localzone())
        else:
            return deserialize_value(typ, value, tz=project.timezone, project=project)

    except DeserializeError as e:
        raise DeserializeError(f'Failed parsing "{field_name}" with value "{value}" ({e})')


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
