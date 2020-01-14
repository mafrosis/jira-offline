from dataclasses import dataclass

import pytest

from jira_cli.utils import DeserializeError, DataclassSerializer


@dataclass
class Test(DataclassSerializer):
    i: int


def test_int_deserialize():
    """
    Test int deserializes
    """
    obj = Test.deserialize({'i': 123})
    assert isinstance(obj.i, int)
    assert obj.i == 123

def test_int_deserialize_from_str():
    """
    Test int deserializes from a string
    """
    obj = Test.deserialize({'i': '123'})
    assert isinstance(obj.i, int)
    assert obj.i == 123

def test_int_deserialize_roundrip():
    """
    Test int deserializes/serializes in a loss-less roundrip
    """
    json = Test.deserialize({'i': 123}).serialize()
    assert json['i'] == 123

def test_int_serialize():
    """
    Test int serializes
    """
    json = Test(i=123).serialize()
    assert json['i'] == 123

def test_int_serialize_roundrip():
    """
    Test int serializes/deserializes in a loss-less roundrip
    """
    obj = Test.deserialize(
        Test(i=123).serialize()
    )
    assert obj.i == 123

def test_int_bad_deserialize():
    '''
    Test bad int deserialize raises exception
    '''
    with pytest.raises(DeserializeError):
        Test.deserialize({'i': 'Egx'})
