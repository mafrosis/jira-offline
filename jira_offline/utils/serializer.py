import dataclasses
import datetime
import decimal
import enum
from typing import Any, Optional
import uuid

import arrow
import typing_inspect

from jira_offline.exceptions import DeserializeError


def get_type_class(type_):
    '''
    Attempt to get the origin class for a type. Handle Optional and generic types.

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
    type_ = get_type_class(type_)
    if issubclass(type_, enum.Enum):
        return type_
    return None


def is_optional_type(type_: type, typ: type) -> bool:
    '''
    Return True if type_ is typ, else return False
    '''
    if typing_inspect.is_optional_type(type_):
        # for typing.Optional, the real type is the first arg, and second is typing.NoneType
        type_ = typing_inspect.get_args(type_)[0]
    return typ is type_


def deserialize_value(type_: type, value: Any) -> Any:  # pylint: disable=too-many-branches, too-many-return-statements
    '''
    Utility function to deserialize `value` into `type_`. Used by DataclassSerializer.
    '''
    if typing_inspect.is_optional_type(type_):
        # for typing.Optional, first arg is the real type and second arg is typing.NoneType
        type_ = typing_inspect.get_args(type_)[0]

    if dataclasses.is_dataclass(type_):
        return type_.deserialize(value)  # type: ignore

    elif type_ is decimal.Decimal:
        try:
            return decimal.Decimal(value)
        except decimal.InvalidOperation:
            raise DeserializeError(f'Failed deserializing "{value}" to Decimal')

    elif type_ is uuid.UUID:
        try:
            return uuid.UUID(value)
        except ValueError:
            raise DeserializeError(f'Failed deserializing "{value}" to UUID')

    elif type_ is datetime.date:
        try:
            return arrow.get(value).datetime.date()
        except arrow.parser.ParserError:
            raise DeserializeError(f'Failed deserializing "{value}" to Arrow datetime.date')

    elif type_ is datetime.datetime:
        try:
            return arrow.get(value).datetime
        except arrow.parser.ParserError:
            raise DeserializeError(f'Failed deserializing "{value}" to Arrow datetime.datetime')

    elif type_ is set:
        if not isinstance(value, set) and not isinstance(value, list):
        #if not is_typing_instance(value, set) and not is_typing_instance(value, list):
            raise DeserializeError('Value passed to set type must be JSON set or list')
        return set(value)

    elif type_ is int:
        try:
            return int(value)
        except (TypeError, ValueError):
            raise DeserializeError(f'Failed deserializing {value} to int')
    else:
        # handle enum
        enum_type = get_enum(type_)
        if enum_type:
            try:
                # convert string to Enum instance
                return enum_type(value)
            except ValueError:
                raise DeserializeError(f'Failed deserializing {value} to {type_}')

        # no deserialize necessary
        return value


def serialize_value(type_: type, value: Any) -> Any:  # pylint: disable=too-many-return-statements
    '''
    Utility function to serialize `value` into `type_`. Used by DataclassSerializer.
    '''
    if typing_inspect.is_optional_type(type_):
        # for typing.Optional, first arg is the real type and second arg is typing.NoneType
        type_ = typing_inspect.get_args(type_)[0]

    if value is None:
        return None
    elif dataclasses.is_dataclass(type_):
        return value.serialize()
    elif isinstance(value, (decimal.Decimal, uuid.UUID)):
        return str(value)
    elif isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    elif isinstance(value, set):
        return sorted(list(value))
    else:
        # handle enum
        if get_enum(type_):
            return value.value

        # no serialize necessary
        return value


@dataclasses.dataclass
class DataclassSerializer:
    @classmethod
    def deserialize(cls, attrs: dict) -> Any:
        '''
        Deserialize JSON-compatible dict to dataclass. Supports the following types:
            - int
            - decimal.Decimal
            - datetime.date
            - datetime.datetime
            - enum.Enum
            - set
            - dataclass

        Params:
            attrs:  Dict to deserialize into an instance of cls
        Returns:
            An instance of cls
        '''
        data = {}

        for f in dataclasses.fields(cls):
            raw_value = None

            try:
                # pull value from dataclass field name, or by property name, if defined on the dataclass.field
                field_name = f.metadata.get('property', f.name)
                raw_value = attrs[field_name]

            except KeyError as e:
                # handle key missing from passed dict
                if isinstance(f.default, dataclasses._MISSING_TYPE) and \
                   isinstance(f.default_factory, dataclasses._MISSING_TYPE):  # type: ignore # pylint: disable=protected-access
                    # raise exception if field has no defaults defined
                    raise DeserializeError(f'Missing input data for mandatory key {f.name}')

                continue

            except TypeError as e:
                raise DeserializeError(f'Fatal TypeError for key {f.name} ({e})')

            # extract the base type for a generic type
            base_type = get_type_class(f.type)

            # special handling for generic Dict
            if base_type is dict:
                # extract key and value types for the Dict
                dict_key_type, dict_value_type = f.type.__args__[0], f.type.__args__[1]
                try:
                    # deserialize keys and values individually into a new dict
                    data[f.name] = {
                        deserialize_value(dict_key_type, item_key): deserialize_value(dict_value_type, item_value)
                        for item_key, item_value in raw_value.items()  # type: ignore
                    }
                except AttributeError:
                    raise DeserializeError(f'Failed serializing "{raw_value}" to {f.type}')
            else:
                data[f.name] = deserialize_value(base_type, raw_value)

        return cls(**data)  # type: ignore


    def serialize(self) -> dict:
        '''
        Serialize dataclass to JSON-compatible dict. Supports the following types:
            - int
            - decimal.Decimal
            - datetime.date
            - datetime.datetime
            - enum.Enum
            - set
            - dataclass

        Notes:
            - includes only fields with repr=True (the dataclass.field default)
            - int type does not need serializing for JSON

        Returns:
            A JSON-compatible dict
        '''
        data = {}

        for f in dataclasses.fields(self):
            if f.repr is False:
                continue

            # pull value from dataclass field name, or by property name, if defined on the dataclass.field
            write_field_name = f.metadata.get('property', f.name)

            raw_value = self.__dict__.get(f.name)

            # extract the base type for a generic type
            base_type = get_type_class(f.type)

            # special handling for generic Dict
            if base_type is dict:
                # extract key and value types for the Dict
                dict_key_type, dict_value_type = f.type.__args__[0], f.type.__args__[1]
                # deserialize keys and values individually into a new dict
                data[write_field_name] = {
                    serialize_value(dict_key_type, item_key):
                        serialize_value(dict_value_type, item_value)
                    for item_key, item_value in raw_value.items()  # type: ignore
                }
            else:
                serialized_value = serialize_value(base_type, raw_value)
                if serialized_value:
                    data[write_field_name] = serialized_value

        return data
