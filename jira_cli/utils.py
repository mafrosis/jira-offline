import contextlib
import dataclasses
import datetime
import decimal
import enum
import functools
import logging

import arrow


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
                    raise DeserializeError(f'Failed deserializing "{value}" to {type_}')

            elif issubclass(type_, enum.Enum):
                try:
                    # convert string to Enum instance
                    return type_(value)
                except ValueError:
                    raise DeserializeError(f'Failed deserializing "{value}" to {type_}')

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
                except ValueError:
                    raise DeserializeError(f'Failed deserializing "{value}" to {type_}')
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

            except TypeError as e:
                raise DeserializeError(f'Fatal TypeError for key {f.name} ({e})')

            if raw_value is None:
                data[f.name] = None
                continue

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
            elif isinstance(value, decimal.Decimal):
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

            data[f.name] = serialize_value(f.type, raw_value)

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
