import dataclasses
import datetime
import decimal
import enum
from typing import Any, Optional
import uuid

import arrow
import typing_inspect

from jira_offline.exceptions import DeserializeError


def get_base_type(type_):
    '''
    Attempt to get the base or "origin type" for a type. Handle Optional and generic types.

    For example,
        typing.Dict base type is dict
        typing.Optional[str] base type is str
        dict base type is simply dict

    This is based on `typing_inspect.get_origin(typ)`
    '''
    if typing_inspect.is_optional_type(type_):
        # for typing.Optional, the real type is the first arg, and second is typing.NoneType
        return typing_inspect.get_args(type_)[0]

    # abort if type is not generic
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
    if typing_inspect.is_optional_type(type_):
        # for typing.Optional, the real type is the first arg, and second is typing.NoneType
        type_ = typing_inspect.get_args(type_)[0]
    return typ is type_


def deserialize_value(type_, value: Any) -> Any:  # pylint: disable=too-many-branches, too-many-return-statements
    '''
    Utility function to deserialize `value` into `type_`. Used by DataclassSerializer.

    Note that some JSON-compatible types do not need deserializing for JSON (int, dict, list)

    Params:
        type_:  The dataclass field type
        value:  Value to serialize to `type_`
    '''
    if value is None:
        return None

    if typing_inspect.is_optional_type(type_):
        # for typing.Optional, first arg is the real type and second arg is typing.NoneType
        type_ = typing_inspect.get_args(type_)[0]

    # extract the base type (eg. typing.Dict becomes dict)
    base_type = get_base_type(type_)

    if dataclasses.is_dataclass(base_type):
        return base_type.deserialize(value)  # type: ignore

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
            return arrow.get(value).datetime.date()
        except arrow.parser.ParserError:
            raise DeserializeError(f'Failed deserializing "{value}" to Arrow datetime.date')

    elif base_type is datetime.datetime:
        try:
            return arrow.get(value).datetime
        except arrow.parser.ParserError:
            raise DeserializeError(f'Failed deserializing "{value}" to Arrow datetime.datetime')

    elif base_type is set:
        if not isinstance(value, set) and not isinstance(value, list):
            raise DeserializeError('Value passed to set type must be set or list')
        return set(value)

    elif base_type is int:
        try:
            return int(value)
        except (TypeError, ValueError):
            raise DeserializeError(f'Failed deserializing {value} to int')

    elif base_type is dict:
        # extract key and value types for the Dict
        generic_key_type, generic_value_type = type_.__args__[0], type_.__args__[1]

        try:
            # deserialize keys and values individually, constructing a new dict
            return {
                deserialize_value(generic_key_type, item_key):
                    deserialize_value(generic_value_type, item_value)
                for item_key, item_value in value.items()  # type: ignore
            }
        except AttributeError:
            raise DeserializeError(f'Failed serializing "{value}" to {base_type}')

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
    if typing_inspect.is_optional_type(type_):
        # for typing.Optional, first arg is the real type and second arg is typing.NoneType
        type_ = typing_inspect.get_args(type_)[0]

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

    elif base_type in (set,):
        return sorted(list(value))

    elif base_type is dict:
        # extract key and value types for the Dict
        generic_key_type, generic_value_type = type_.__args__[0], type_.__args__[1]

        # serialize keys and values individually, constructing a new dict
        return {
            serialize_value(generic_key_type, item_key):
                serialize_value(generic_value_type, item_value)
            for item_key, item_value in value.items()  # type: ignore
        }

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
    if typing_inspect.is_optional_type(field.type) and \
        isinstance(field.default, dataclasses._MISSING_TYPE) and \
        isinstance(field.default_factory, dataclasses._MISSING_TYPE):  # pylint: disable=protected-access

        raise DeserializeError(f'Field {field.name} is Optional with no default configured')


@dataclasses.dataclass
class DataclassSerializer:
    @classmethod
    def deserialize(cls, attrs: dict) -> Any:
        '''
        Deserialize JSON-compatible dict to dataclass.

        Params:
            attrs:  Dict to deserialize into an instance of cls
        Returns:
            An instance of cls
        '''
        data = {}

        for f in dataclasses.fields(cls):
            # check for field read/write metadata, which determines if fields are ignored
            # if the "r" field is not present, do not deserialize this field
            rw_flag = f.metadata.get('rw', 'rw')
            if 'r' not in rw_flag:
                continue

            raw_value = None

            _validate_optional_fields_have_a_default(f)

            try:
                # pull value from dataclass field name, or by property name, if defined on the dataclass.field
                field_name = f.metadata.get('property', f.name)
                raw_value = attrs[field_name]

            except KeyError as e:
                # handle key missing from passed dict
                # if the missing key's type is non-optional, raise an exception
                if not typing_inspect.is_optional_type(f.type):
                    raise DeserializeError(f'Missing input data for mandatory key {f.name}')

                continue

            except TypeError as e:
                raise DeserializeError(f'Fatal TypeError for key {f.name} ({e})')

            data[f.name] = deserialize_value(f.type, raw_value)

        return cls(**data)  # type: ignore


    def serialize(self) -> dict:
        '''
        Serialize dataclass to JSON-compatible dict.

        Returns:
            A JSON-compatible dict
        '''
        data = {}

        for f in dataclasses.fields(self):
            # check for field read/write metadata, which determines if fields are ignored
            # if the "w" field is not present, do not serialize this field
            rw_flag = f.metadata.get('rw', 'rw')
            if 'w' not in rw_flag:
                continue

            # pull value from dataclass field name, or by property name, if defined on the dataclass.field
            write_field_name = f.metadata.get('property', f.name)

            serialized_value = serialize_value(f.type, self.__dict__.get(f.name))
            if serialized_value:
                data[write_field_name] = serialized_value

        return data
