import copy
import dataclasses
import datetime
import decimal
import enum
import functools

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


@dataclasses.dataclass
class DataclassSerializer:
    @classmethod
    def deserialize(cls, attrs: dict) -> object:
        """
        Deserialize JIRA API dict to dataclass
        Support decimal, date/datetime, enum & set
        """
        data = copy.deepcopy(attrs)

        for f in dataclasses.fields(cls):
            v = attrs.get(f.name)
            if v is None:
                continue

            if dataclasses.is_dataclass(f.type):
                data[f.name] = f.type.deserialize(v)
            elif f.type is decimal.Decimal:
                data[f.name] = decimal.Decimal(v)
            elif issubclass(f.type, enum.Enum):
                # convert string to Enum instance
                data[f.name] = f.type(v)
            elif f.type is datetime.date:
                data[f.name] = arrow.get(v).datetime.date()
            elif f.type is datetime.datetime:
                data[f.name] = arrow.get(v).datetime
            elif f.type is set:
                data[f.name] = set(v)

        return cls(**data)

    def serialize(self) -> dict:
        """
        Serialize dataclass to JIRA API dict
        Support decimal, date/datetime, enum & set
        Include only fields with repr=True (dataclass.field default)
        """
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
