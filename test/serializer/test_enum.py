from dataclasses import dataclass
from enum import Enum

import pytest

from jira_cli.utils.serializer import DeserializeError, DataclassSerializer


class TestEnum(Enum):
    Egg = 'Egg'

@dataclass
class Test(DataclassSerializer):
    e: TestEnum


def test_enum_deserialize():
    """
    Test enum deserializes
    """
    obj = Test.deserialize({'e': 'Egg'})
    assert isinstance(obj.e, Enum)
    assert obj.e == TestEnum.Egg

def test_enum_deserialize_fail_on_not_valid():
    """
    Test enum deserialize fails when value not defined in Enum
    """
    with pytest.raises(DeserializeError) as e:
        Test.deserialize({'e': 'Bacon'})
        assert str(e) == "'Bacon' is not a valid TestEnum"

def test_enum_deserialize_roundrip():
    """
    Test enum deserializes/serializes in a loss-less roundrip
    """
    json = Test.deserialize({'e': 'Egg'}).serialize()
    assert json['e'] == 'Egg'

def test_enum_serialize():
    """
    Test enum serializes
    """
    json = Test(e=TestEnum.Egg).serialize()
    assert json['e'] == 'Egg'

def test_enum_serialize_roundrip():
    """
    Test enum serializes/deserializes in a loss-less roundrip
    """
    obj = Test.deserialize(
        Test(e=TestEnum.Egg).serialize()
    )
    assert obj.e == TestEnum.Egg
