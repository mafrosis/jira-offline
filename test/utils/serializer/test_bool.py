'''
Tests for serialize/deserialize with bool type
'''
from dataclasses import dataclass

import pytest

from jira_offline.utils.serializer import DeserializeError, DataclassSerializer


@dataclass
class Test(DataclassSerializer):
    b: bool


@pytest.mark.parametrize('val', [
    True,
    False,
])
def test_bool_deserialize(val):
    """
    Test bool deserializes
    """
    obj = Test.deserialize({'b': val})
    assert isinstance(obj.b, bool)
    assert obj.b == val

@pytest.mark.parametrize('val', [
    True,
    False,
])
def test_bool_deserialize_roundrip(val):
    """
    Test bool deserializes/serializes in a loss-less roundrip
    """
    json = Test.deserialize({'b': val}).serialize()
    assert json['b'] == val

@pytest.mark.parametrize('val', [
    True,
    False,
])
def test_bool_serialize(val):
    """
    Test bool serializes
    """
    json = Test(b=val).serialize()
    assert json['b'] == val

@pytest.mark.parametrize('val', [
    True,
    False,
])
def test_bool_serialize_roundrip(val):
    """
    Test bool serializes/deserializes in a loss-less roundrip
    """
    obj = Test.deserialize(
        Test(b=val).serialize()
    )
    assert obj.b == val

def test_bool_bad_deserialize():
    '''
    Test bad bool deserialize raises exception
    '''
    with pytest.raises(DeserializeError):
        Test.deserialize({'b': 'Egx'})
