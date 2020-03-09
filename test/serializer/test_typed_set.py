from dataclasses import dataclass, field
from typing import Set

import pytest

from jira_cli.utils import DeserializeError, DataclassSerializer


@dataclass
class Test(DataclassSerializer):
    s: Set[str]

@dataclass
class TestWithDefaults(DataclassSerializer):
    s: Set[str] = field(default_factory=set)


def test_typed_set_deserialize():
    """
    Test typing.set deserializes
    """
    obj = Test.deserialize({
        's': ['abc', 'def']
    })
    assert isinstance(obj.s, set)
    assert obj.s == {'abc', 'def'}

def test_typed_set_with_defaults_deserialize():
    """
    Test typing.set with field(default_factory=set) deserializes
    """
    obj = TestWithDefaults.deserialize({})
    assert isinstance(obj.s, set)

def test_typed_set_deserialize_roundrip():
    """
    Test typing.set deserializes/serializes in a loss-less roundrip
    """
    json = Test.deserialize({
        's': ['abc', 'def']
    }).serialize()
    assert json['s'] == ['abc', 'def']

def test_typed_set_serialize():
    """
    Test typing.set serializes
    """
    json = Test(
        s={'abc', 'def'}
    ).serialize()
    assert json['s'] == ['abc', 'def']

def test_typed_set_serialize_roundrip():
    """
    Test typing.set serializes/deserializes in a loss-less roundrip
    """
    obj = Test.deserialize(
        Test(
            s={'abc', 'def'}
        ).serialize()
    )
    assert isinstance(obj.s, set)
    assert obj.s == {'abc', 'def'}

@pytest.mark.parametrize('bad_input', [
    {},
    {'s': 'key1'},
    {'s': {'key1': 'abc'}},
    {'s': 123},
])
def test_typed_set_bad_deserialize(bad_input):
    '''
    Test bad typing.set deserialize raises exception (exception raised when passed value is not a list)
    '''
    with pytest.raises(DeserializeError):
        Test.deserialize(bad_input)
