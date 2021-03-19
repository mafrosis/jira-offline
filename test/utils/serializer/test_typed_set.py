from dataclasses import dataclass, field
from typing import Optional, Set

import pytest

from jira_offline.utils.serializer import DeserializeError, DataclassSerializer


@dataclass
class Test(DataclassSerializer):
    s: Set[str]

@dataclass
class TestWithDefaults(DataclassSerializer):
    s: Optional[Set[str]] = field(default_factory=set)


FIXTURES=[Test, TestWithDefaults]


@pytest.mark.parametrize('class_', FIXTURES)
def test_typed_set_deserialize(class_):
    """
    Test typing.set deserializes
    """
    obj = class_.deserialize({
        's': ['abc', 'def']
    })
    assert isinstance(obj.s, set)
    assert obj.s == {'abc', 'def'}


@pytest.mark.parametrize('class_', FIXTURES)
def test_typed_set_deserialize_roundrip(class_):
    """
    Test typing.set deserializes/serializes in a loss-less roundrip
    """
    json = class_.deserialize({
        's': ['abc', 'def']
    }).serialize()
    assert json['s'] == ['abc', 'def']


@pytest.mark.parametrize('class_', FIXTURES)
def test_typed_set_serialize(class_):
    """
    Test typing.set serializes
    """
    json = class_(
        s={'abc', 'def'}
    ).serialize()
    assert json['s'] == ['abc', 'def']


@pytest.mark.parametrize('class_', FIXTURES)
def test_typed_set_serialize_roundrip(class_):
    """
    Test typing.set serializes/deserializes in a loss-less roundrip
    """
    obj = class_.deserialize(
        class_(
            s={'abc', 'def'}
        ).serialize()
    )
    assert isinstance(obj.s, set)
    assert obj.s == {'abc', 'def'}


BAD_INPUT = [
    {'s': 'key1'},
    {'s': {'key1': 'abc'}},
    {'s': 123},
]

@pytest.mark.parametrize('class_,bad_input', [
    (f, i) for f in FIXTURES for i in BAD_INPUT
])
def test_typed_set_bad_deserialize(class_, bad_input):
    '''
    Test bad typing.set deserialize raises exception (exception raised when passed value is not a list)
    '''
    with pytest.raises(DeserializeError):
        class_.deserialize(bad_input)


def test_typed_set_with_defaults_deserializes_empty():
    """
    Test typing.Set with a default configured deserializes
    """
    obj = TestWithDefaults.deserialize({})
    assert isinstance(obj.s, set)

def test_typed_set_without_defaults_fails_deserialize_empty():
    """
    Test typing.Set WITHOUT a default configured FAILS to deserialize
    """
    with pytest.raises(DeserializeError):
        Test.deserialize({})
