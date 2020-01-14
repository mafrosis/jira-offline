import copy
import dataclasses
import datetime
import decimal
import enum

import arrow


class DeserializeError(ValueError):
    pass


@dataclasses.dataclass
class DataclassSerializer:
    @classmethod
    # pylint: disable=too-many-branches
    def deserialize(cls, attrs: dict) -> object:
        '''
        Deserialize JSON-compatible dict to dataclass

        Support int, decimal, date/datetime, enum & set
        '''
        data = copy.deepcopy(attrs)

        for f in dataclasses.fields(cls):
            v = attrs.get(f.name)
            if v is None:
                continue

            if dataclasses.is_dataclass(f.type):
                data[f.name] = f.type.deserialize(v)
            elif f.type is decimal.Decimal:
                try:
                    data[f.name] = decimal.Decimal(v)
                except decimal.InvalidOperation:
                    raise DeserializeError(f'Failed deserializing "{v}" to {f.type}')
            elif issubclass(f.type, enum.Enum):
                try:
                    # convert string to Enum instance
                    data[f.name] = f.type(v)
                except ValueError:
                    raise DeserializeError(f'Failed deserializing "{v}" to {f.type}')
            elif f.type is datetime.date:
                try:
                    data[f.name] = arrow.get(v).datetime.date()
                except arrow.parser.ParserError:
                    raise DeserializeError(f'Failed deserializing "{v}" to Arrow datetime.date')
            elif f.type is datetime.datetime:
                try:
                    data[f.name] = arrow.get(v).datetime
                except arrow.parser.ParserError:
                    raise DeserializeError(f'Failed deserializing "{v}" to Arrow datetime.datetime')
            elif f.type is set:
                if not isinstance(v, set) and not isinstance(v, list):
                    raise DeserializeError(f'Value passed to set type must be JSON set or list')
                data[f.name] = set(v)
            elif f.type is int:
                try:
                    data[f.name] = int(v)
                except ValueError:
                    raise DeserializeError(f'Failed deserializing "{v}" to {f.type}')

        return cls(**data)

    def serialize(self) -> dict:
        '''
        Serialize dataclass to JSON-compatible dict

        Supports int, decimal, date/datetime, enum & set
        Include only fields with repr=True (dataclass.field default)
        Int-type does not need serializing for JSON
        '''
        data = {}

        for f in dataclasses.fields(self):
            if f.repr is False:
                continue

            v = self.__dict__.get(f.name)

            if v is None:
                data[f.name] = None
            elif dataclasses.is_dataclass(f.type):
                data[f.name] = v.serialize()
            elif isinstance(v, decimal.Decimal):
                data[f.name] = str(v)
            elif issubclass(f.type, enum.Enum):
                # convert Enum to raw string
                data[f.name] = v.value
            elif isinstance(v, (datetime.date, datetime.datetime)):
                data[f.name] = v.isoformat()
            elif isinstance(v, set):
                data[f.name] = sorted(list(v))
            else:
                data[f.name] = v

        return data
