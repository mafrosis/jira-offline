import contextlib
import dataclasses
import datetime
import decimal
import enum
import functools
import logging
from typing import Any
import uuid

import arrow
from typing_inspect import is_generic_type


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


class DeserializeError(ValueError):
    pass


def get_type_class(typ):
    '''
    Get the origin class for a Generic type, supporting older pythons
    This is called `get_origin(typ)` in `typing_inspect` lib
    '''
    try:
        return typ.__extra__  # Python 3.5 / 3.6
    except AttributeError:
        return typ.__origin__  # Python 3.7+


@dataclasses.dataclass
class DataclassSerializer:
    @classmethod
    # pylint: disable=too-many-branches
    def deserialize(cls, attrs: dict) -> object:
        '''
        Deserialize JSON-compatible dict to dataclass. Supports the following types:
            - int
            - decimal.Decimal
            - datetime.date
            - datetime.datetime
            - enum.Enum
            - set
            - dataclass
        '''
        data = {}

        # pylint: disable=too-many-return-statements
        def deserialize_value(type_: type, value: Any) -> Any:
            if dataclasses.is_dataclass(type_):
                return type_.deserialize(value)

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

            elif issubclass(type_, enum.Enum):
                try:
                    # convert string to Enum instance
                    return type_(value)
                except ValueError:
                    raise DeserializeError(f'Failed deserializing {value} to {type_}')

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
                    raise DeserializeError(f'Value passed to set type must be JSON set or list')
                return set(value)

            elif type_ is int:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    raise DeserializeError(f'Failed deserializing {value} to int')
            else:
                return value


        for f in dataclasses.fields(cls):
            raw_value = None

            try:
                raw_value = attrs[f.name]

            except KeyError as e:
                # handle key missing from passed dict
                # pylint: disable=protected-access
                if isinstance(f.default, dataclasses._MISSING_TYPE) and isinstance(f.default_factory, dataclasses._MISSING_TYPE):
                    # raise exception if field has no defaults defined
                    raise DeserializeError(f'Missing input data for mandatory key {f.name}')

                continue

            except TypeError as e:
                raise DeserializeError(f'Fatal TypeError for key {f.name} ({e})')

            # determine if type is a Generic Dict
            if is_generic_type(f.type) and get_type_class(f.type) is dict:
                # extract key and value types for the Dict
                dict_key_type, dict_value_type = f.type.__args__[0], f.type.__args__[1]
                try:
                    # deserialize keys and values individually into a new dict
                    data[f.name] = {
                        deserialize_value(dict_key_type, item_key): deserialize_value(dict_value_type, item_value)
                        for item_key, item_value in raw_value.items()
                    }
                except AttributeError:
                    raise DeserializeError(f'Failed serializing "{raw_value}" to {f.type}')
            else:
                data[f.name] = deserialize_value(f.type, raw_value)

        return cls(**data)


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
        '''
        data = {}

        # pylint: disable=too-many-return-statements
        def serialize_value(type_: type, value: Any) -> Any:
            if value is None:
                return None
            elif dataclasses.is_dataclass(type_):
                return value.serialize()
            elif isinstance(value, (decimal.Decimal, uuid.UUID)):
                return str(value)
            elif issubclass(type_, enum.Enum):
                # convert Enum to raw string
                return value.value
            elif isinstance(value, (datetime.date, datetime.datetime)):
                return value.isoformat()
            elif isinstance(value, set):
                return sorted(list(value))
            else:
                return value


        for f in dataclasses.fields(self):
            if f.repr is False:
                continue

            raw_value = self.__dict__.get(f.name)

            # determine if type is a Generic Dict
            if is_generic_type(f.type) and get_type_class(f.type) is dict:
                # extract key and value types for the Dict
                dict_key_type, dict_value_type = f.type.__args__[0], f.type.__args__[1]
                # deserialize keys and values individually into a new dict
                data[f.name] = {
                    serialize_value(dict_key_type, item_key):
                        serialize_value(dict_value_type, item_value)
                    for item_key, item_value in raw_value.items()
                }
            else:
                serialized_value = serialize_value(f.type, raw_value)
                if serialized_value:
                    data[f.name] = serialized_value

        return data


@contextlib.contextmanager
def critical_logger(logger_):
    '''
    Context manager to set a logger to CRITICAL level only for the duration of the with block.

    with set_logger_level_critical(logger):
        ...
    '''
    log_level = logger_.level
    logger_.setLevel(logging.CRITICAL)
    yield logger_
    logger_.setLevel(log_level)
