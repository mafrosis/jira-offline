from dataclasses import dataclass, field
from typing import Optional, Dict

import pytest

from jira_offline.utils.serializer import DeserializeError, DataclassSerializer


@dataclass
class Nested(DataclassSerializer):
    x: str

@dataclass
class Test(DataclassSerializer):
    d: Dict[str, Nested]

@dataclass
class TestWithDefaults(DataclassSerializer):
    d: Optional[Dict[str, Nested]] = field(default_factory=dict)

@dataclass
class TestWithNestedDefault(DataclassSerializer):
    d: Dict[str, Optional[Nested]]


FIXTURES=[Test, TestWithDefaults, TestWithNestedDefault]


@pytest.mark.parametrize('class_', FIXTURES)
def test_typed_dict_deserialize(class_):
    """
    Test typing.Dict deserializes
    """
    obj = class_.deserialize({
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


@pytest.mark.parametrize('class_', FIXTURES)
def test_typed_dict_deserialize_roundrip(class_):
    """
    Test typing.Dict deserializes/serializes in a loss-less roundrip
    """
    json = class_.deserialize({
        'd': {
            'key1': {'x': 'abc'},
            'key2': {'x': 'def'},
        }
    }).serialize()
    assert json['d'] == {
        'key1': {'x': 'abc'},
        'key2': {'x': 'def'},
    }


@pytest.mark.parametrize('class_', FIXTURES)
def test_typed_dict_serialize(class_):
    """
    Test typing.Dict serializes
    """
    json = class_(
        d={
            'key1': Nested(x='abc'),
            'key2': Nested(x='def'),
        }
    ).serialize()
    assert json['d'] == {
        'key1': {'x': 'abc'},
        'key2': {'x': 'def'},
    }


@pytest.mark.parametrize('class_', FIXTURES)
def test_typed_dict_serialize_roundrip(class_):
    """
    Test typing.Dict serializes/deserializes in a loss-less roundrip
    """
    obj = class_.deserialize(
        class_(
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


BAD_INPUT = [
    {'d': 'key1'},
    {'d': {'key1': 'abc'}},
    {'d': {'key1': {'y': 'abc'}}},
]

@pytest.mark.parametrize('class_,bad_input', [
    (f, i) for f in FIXTURES for i in BAD_INPUT
])
def test_typed_dict_bad_deserialize(class_, bad_input):
    '''
    Test bad typing.Dict deserialize raises exception
    '''
    with pytest.raises(DeserializeError):
        class_.deserialize(bad_input)


def test_typed_dict_with_defaults_deserializes_empty():
    """
    Test typing.Dict with a default configured deserializes
    """
    obj = TestWithDefaults.deserialize({})
    assert isinstance(obj.d, dict)

def test_typed_dict_without_defaults_fails_deserialize_empty():
    """
    Test typing.Dict WITHOUT a default configured FAILS to deserialize
    """
    with pytest.raises(DeserializeError):
        Test.deserialize({})
