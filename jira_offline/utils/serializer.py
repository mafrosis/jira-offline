import dataclasses
import datetime
import decimal
import enum
from typing import Any, Optional
import uuid

import arrow
import pytz
import typing_inspect
from tzlocal import get_localzone
import numpy

from jira_offline.exceptions import DeserializeError


def unwrap_optional_type(type_):
    '''
    Unwrap typing.Optional around a type.

    The parameter evaluate=True _must_ be passed to `get_args` to ensure consistent behaviour across
    pythons:
        https://github.com/ilevkivskyi/typing_inspect/blob/master/typing_inspect.py#L410

    For example,
        typing.Optional[str] is str
        typing.Optional[dict] is dict
    '''
    if typing_inspect.is_optional_type(type_):
        # typing.Optional is sugar for representing an optional type as typing.Union[type, None]
        # this means the base type is the first arg in the return from typing_inspect.get_args()
        type_ = typing_inspect.get_args(type_, evaluate=True)[0]

    return type_


def get_base_type(type_):
    '''
    Attempt to get the base or "origin type" for a type. Handle Optional and generic types.

    For example,
        typing.Dict base type is dict
        typing.Optional[str] base type is str
        dict base type is simply dict

    This is based on `typing_inspect.get_origin(typ)`
    '''
    # unwrap any typing.Optional to expose the underlying type
    type_ = unwrap_optional_type(type_)

    # abort if type is not generic, (ie. not a typing.* type)
    if not typing_inspect.is_generic_type(type_):
        return type_

    try:
        return type_.__extra__  # Python 3.5 / 3.6
    except AttributeError:
        return type_.__origin__  # Python 3.7+


def get_enum(type_: type) -> Optional[type]:
    '''
    Return enum if type_ is a subclass of enum.Enum. Handle typing.Optional.
    '''
    type_ = get_base_type(type_)
    if issubclass(type_, enum.Enum):
        return type_
    return None


def istype(type_: type, typ: type) -> bool:
    '''
    Return True if type_ is typ, else return False. Handles Optional types.
    '''
    return typ is unwrap_optional_type(type_)


def deserialize_value(type_, value: Any, tz: datetime.tzinfo) -> Any:  # pylint: disable=too-many-branches, too-many-return-statements, too-many-statements
    '''
    Utility function to deserialize `value` into `type_`. Used by DataclassSerializer.

    Note that some JSON-compatible types do not need deserializing for JSON (int, dict, list)

    Params:
        type_:  The dataclass field type
        value:  Value to serialize to `type_`
        tz:     Timezone to apply to deserialized date/datetime
    '''
    if value is None:
        return None

    # unwrap any typing.Optional to expose the underlying type
    type_ = unwrap_optional_type(type_)

    # extract the base type (eg. typing.Dict becomes dict)
    base_type = get_base_type(type_)

    if dataclasses.is_dataclass(base_type):
        return base_type.deserialize(value)

    elif base_type is decimal.Decimal:
        try:
            return decimal.Decimal(value)
        except decimal.InvalidOperation:
            raise DeserializeError(f'Failed deserializing "{value}" to Decimal')

    elif base_type is uuid.UUID:
        try:
            return uuid.UUID(value)
        except ValueError:
            raise DeserializeError(f'Failed deserializing "{value}" to UUID')

    elif base_type is datetime.date:
        try:
            return arrow.get(value).replace(tzinfo=tz).datetime.date()
        except arrow.parser.ParserError:
            raise DeserializeError(f'Failed deserializing "{value}" to Arrow datetime.date')

    elif base_type is datetime.datetime:
        try:
            return arrow.get(value).replace(tzinfo=tz).datetime
        except arrow.parser.ParserError:
            raise DeserializeError(f'Failed deserializing "{value}" to Arrow datetime.datetime')

    elif base_type is datetime.tzinfo:
        return pytz.timezone(value)

    elif base_type is set:
        if not isinstance(value, (set, list, numpy.ndarray)):
            raise DeserializeError('Value passed to set type must be set, list or numpy.ndarray')
        return set(value)

    elif base_type is int:
        try:
            return int(value)
        except (TypeError, ValueError):
            raise DeserializeError(f'Failed deserializing {value} to int')

    elif base_type is dict and typing_inspect.is_generic_type(type_):
        # extract key and value types for the generic Dict
        generic_key_type, generic_value_type = type_.__args__[0], type_.__args__[1]

        try:
            # deserialize keys and values individually, constructing a new dict
            return {
                deserialize_value(generic_key_type, item_key, tz=tz):
                    deserialize_value(generic_value_type, item_value, tz=tz)
                for item_key, item_value in value.items()
            }
        except AttributeError:
            raise DeserializeError(f'Failed serializing "{value}" to {base_type}')

    elif base_type is dict:
        # additional error handling for non-generic dict type
        if not isinstance(value, dict):
            raise DeserializeError('Value passed for dict types must be dict')

        # a python dict is JSON-compatible, so no additional conversion necessary

    elif base_type is list and typing_inspect.is_generic_type(type_):
        if not isinstance(value, (list, numpy.ndarray)):
            # additional error handling is required here as python will iterate a string as though its
            # a list; causing subsequent code to produce incorrect results when a string is fed to
            # the deserializer
            raise DeserializeError('Value passed for list types must be list or numpy.ndarray')

        # extract value type for the generic List
        generic_type = type_.__args__[0]

        try:
            # deserialize values individually into a new list
            return [
                deserialize_value(generic_type, v, tz=tz) for v in value
            ]
        except (AttributeError, TypeError):
            raise DeserializeError(f'Failed serializing "{value}" to {type_}')

    elif base_type is list:
        # additional error handling for non-generic list type
        if not isinstance(value, (list, numpy.ndarray)):
            raise DeserializeError('Value passed for list types must be list or numpy.ndarray')

        return list(value)

    else:
        # handle enum
        enum_type = get_enum(base_type)
        if enum_type:
            try:
                # convert string to Enum instance
                return enum_type(value)
            except ValueError:
                raise DeserializeError(f'Failed deserializing {value} to {type_}')

    # no deserialize necessary
    return value


def serialize_value(type_, value: Any) -> Any:  # pylint: disable=too-many-return-statements
    '''
    Utility function to serialize `value` into `type_`. Used by DataclassSerializer.

    Note that some JSON-compatible types do not need serializing for JSON (int, dict, list)

    Params:
        type_:  The dataclass field type
        value:  Value to serialize to `type_`
    '''
    # unwrap any typing.Optional to expose the underlying type
    type_ = unwrap_optional_type(type_)

    # extract the base type (eg. typing.Dict becomes dict)
    base_type = get_base_type(type_)

    if value is None:
        return None

    elif dataclasses.is_dataclass(base_type):
        return value.serialize()

    elif base_type in (decimal.Decimal, uuid.UUID):
        return str(value)

    elif base_type in (datetime.date, datetime.datetime):
        return value.isoformat()

    elif base_type is datetime.tzinfo:
        return str(value)

    elif base_type is set:
        return sorted(list(value))

    elif base_type is dict and typing_inspect.is_generic_type(type_):
        # extract key and value types for the generic Dict
        generic_key_type, generic_value_type = type_.__args__[0], type_.__args__[1]

        # serialize keys and values individually, constructing a new dict
        return {
            serialize_value(generic_key_type, item_key):
                serialize_value(generic_value_type, item_value)
            for item_key, item_value in value.items()
        }

    elif base_type is list and typing_inspect.is_generic_type(type_):
        # extract value type for the generic List
        generic_type = type_.__args__[0]

        # serialize values individually into a new list
        return [serialize_value(generic_type, v) for v in value]

    elif base_type is numpy.bool_:
        return bool(value)

    else:
        # handle enum
        if get_enum(base_type):
            return value.value

    # no serialize necessary
    return value


def _validate_optional_fields_have_a_default(field):
    '''
    Validate optional fields have a dataclasses.field(default) configured
    '''
    if typing_inspect.is_optional_type(field.type) and  isinstance(field.default, dataclasses._MISSING_TYPE) and  isinstance(field.default_factory, dataclasses._MISSING_TYPE):  # pylint: disable=protected-access

        raise DeserializeError(f'Field {field.name} is Optional with no default configured')


@dataclasses.dataclass
class DataclassSerializer:
    @classmethod
    def deserialize(cls, attrs: dict, tz: Optional[datetime.tzinfo]=None, ignore_missing: bool=False,
                    constructor_kwargs: Optional[dict]=None) -> Any:
        '''
        Deserialize JSON-compatible dict to dataclass.

        Params:
            attrs:               Dict to deserialize into an instance of cls
            tz:                  Timezone to apply to deserialized date/datetime
            ignore_missing:      Continue deserialize even when mandatory fields are missing
            constructor_kwargs:  Additional kwargs to pass to `cls` dataclass constructor
        Returns:
            An instance of cls
        '''
        data = {}

        for f in dataclasses.fields(cls):
            # check for metadata on the field specifying not to serialize/deserialize this field
            serialize_flag = f.metadata.get('serialize', True)
            if not serialize_flag:
                continue

            raw_value = None

            _validate_optional_fields_have_a_default(f)

            try:
                # pull value from dataclass field name, or by property name, if defined on the dataclass.field
                raw_value = attrs[f.name]

            except KeyError as e:
                # handle key missing from passed dict
                if ignore_missing is False:
                    # if the missing key's type is non-optional, raise an exception
                    if not typing_inspect.is_optional_type(f.type):
                        raise DeserializeError(f'Missing input data for mandatory key "{f.name}"')
                    continue

            except TypeError as e:
                raise DeserializeError(f'Fatal TypeError for key "{f.name}" ("{e}")')

            try:
                data[f.name] = deserialize_value(
                    f.type,
                    raw_value,
                    tz=tz if tz else get_localzone()
                )

            except DeserializeError as e:
                raise DeserializeError(f'"{e}" on field "{f.name}"')

        # feed additional kwargs to the target class constructor
        if constructor_kwargs:
            data.update(constructor_kwargs)

        return cls(**data)  # type: ignore[call-arg]


    def serialize(self) -> dict:
        '''
        Serialize dataclass to JSON-compatible dict.

        Returns:
            A JSON-compatible dict
        '''
        data = {}

        for f in dataclasses.fields(self):
            # check for metadata on the field specifying not to serialize/deserialize this field
            serialize_flag = f.metadata.get('serialize', True)
            if not serialize_flag:
                continue

            serialized_value = serialize_value(f.type, getattr(self, f.name))
            if serialized_value:
                data[f.name] = serialized_value

        return data
