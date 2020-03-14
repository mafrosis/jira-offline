from dataclasses import dataclass, field
from typing import Dict

import pytest

from jira_cli.utils.serializer import DeserializeError, DataclassSerializer


@dataclass
class Nested(DataclassSerializer):
    x: str

@dataclass
class Test(DataclassSerializer):
    d: Dict[str, Nested]

@dataclass
class TestWithDefaults(DataclassSerializer):
    d: Dict[str, Nested] = field(default_factory=dict)


def test_typed_dict_deserialize():
    """
    Test typing.Dict deserializes
    """
    obj = Test.deserialize({
        'd': {
            'key1': {'x': 'abc'},
            'key2': {'x': 'def'},
        }
    })
    assert isinstance(obj.d, dict)
    assert obj.d == {
        'key1': Nested(x='abc'),
        'key2': Nested(x='def'),
    }

def test_typed_dict_with_defaults_deserialize():
    """
    Test typing.Dict with field(default_factory=dict) deserializes
    """
    obj = TestWithDefaults.deserialize({})
    assert isinstance(obj.d, dict)

def test_typed_dict_deserialize_roundrip():
    """
    Test typing.Dict deserializes/serializes in a loss-less roundrip
    """
    json = Test.deserialize({
        'd': {
            'key1': {'x': 'abc'},
            'key2': {'x': 'def'},
        }
    }).serialize()
    assert json['d'] == {
        'key1': {'x': 'abc'},
        'key2': {'x': 'def'},
    }

def test_typed_dict_serialize():
    """
    Test typing.Dict serializes
    """
    json = Test(
        d={
            'key1': Nested(x='abc'),
            'key2': Nested(x='def'),
        }
    ).serialize()
    assert json['d'] == {
        'key1': {'x': 'abc'},
        'key2': {'x': 'def'},
    }

def test_typed_dict_serialize_roundrip():
    """
    Test typing.Dict serializes/deserializes in a loss-less roundrip
    """
    obj = Test.deserialize(
        Test(
            d={
                'key1': Nested(x='abc'),
                'key2': Nested(x='def'),
            }
        ).serialize()
    )
    assert isinstance(obj.d, dict)
    assert obj.d == {
        'key1': Nested(x='abc'),
        'key2': Nested(x='def'),
    }

@pytest.mark.parametrize('bad_input', [
    {},
    {'d': 'key1'},
    {'d': {'key1': 'abc'}},
    {'d': {'key1': {'y': 'abc'}}},
])
def test_typed_dict_bad_deserialize(bad_input):
    '''
    Test bad typing.Dict deserialize raises exception
    '''
    with pytest.raises(DeserializeError):
        Test.deserialize(bad_input)
