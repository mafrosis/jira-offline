from dataclasses import dataclass, field
from typing import Optional, List

import pytest

from jira_offline.utils.serializer import DeserializeError, DataclassSerializer


@dataclass
class Nested(DataclassSerializer):
    x: str

@dataclass
class Test(DataclassSerializer):
    l: List[Nested]

@dataclass
class TestWithDefaults(DataclassSerializer):
    l: Optional[List[Nested]] = field(default_factory=list)


FIXTURES=[Test, TestWithDefaults]


@pytest.mark.parametrize('class_', FIXTURES)
def test_typed_list_deserialize(class_):
    """
    Test typing.List deserializes
    """
    obj = class_.deserialize({
        'l': [{'x': 'abc'}, {'x': 'def'}]
    })
    assert isinstance(obj.l, list)
    assert obj.l == [Nested(x='abc'), Nested(x='def')]


@pytest.mark.parametrize('class_', FIXTURES)
def test_typed_list_deserialize_roundrip(class_):
    """
    Test typing.List deserializes/serializes in a loss-less roundrip
    """
    json = class_.deserialize({
        'l': [{'x': 'abc'}, {'x': 'def'}]
    }).serialize()
    assert json['l'] == [{'x': 'abc'}, {'x': 'def'}]


@pytest.mark.parametrize('class_', FIXTURES)
def test_typed_list_serialize(class_):
    """
    Test typing.List serializes
    """
    json = class_(
        l=[Nested(x='abc'), Nested(x='def')]
    ).serialize()
    assert json['l'] == [{'x': 'abc'}, {'x': 'def'}]


@pytest.mark.parametrize('class_', FIXTURES)
def test_typed_list_serialize_roundrip(class_):
    """
    Test typing.List serializes/deserializes in a loss-less roundrip
    """
    obj = class_.deserialize(
        class_(
            l=[Nested(x='abc'), Nested(x='def')]
        ).serialize()
    )
    assert isinstance(obj.l, list)
    assert obj.l == [Nested(x='abc'), Nested(x='def')]


BAD_INPUT = [
    {'l': 'key1'},
    {'l': {'key1': 'abc'}},
    {'l': 123},
]

@pytest.mark.parametrize('class_,bad_input', [
    (f, i) for f in FIXTURES for i in BAD_INPUT
])
def test_typed_list_bad_deserialize(class_, bad_input):
    '''
    Test bad typing.List deserialize raises exception (exception raised when passed value is not a list)
    '''
    with pytest.raises(DeserializeError):
        class_.deserialize(bad_input)


def test_typed_list_with_defaults_deserializes_empty():
    """
    Test typing.List with a default configured deserializes
    """
    obj = TestWithDefaults.deserialize({})
    assert isinstance(obj.l, list)

def test_typed_list_without_defaults_fails_deserialize_empty():
    """
    Test typing.List WITHOUT a default configured FAILS to deserialize
    """
    with pytest.raises(DeserializeError):
        Test.deserialize({})
