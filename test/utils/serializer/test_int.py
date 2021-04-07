from dataclasses import dataclass

import numpy as np
import pytest

from jira_offline.utils.serializer import DeserializeError, DataclassSerializer


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

def test_int_deserialize_str():
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

def test_int_serialize_from_numpy_int64():
    """
    Test int serializes from numpy.int64
    """
    json = Test(i=np.int64(123)).serialize()
    assert json['i'] == 123

def test_int_serialize_from_str():
    """
    Test int serializes from str
    """
    json = Test(i='123').serialize()
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
