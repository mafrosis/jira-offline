from dataclasses import dataclass

import numpy as np
import pytest

from jira_offline.utils.serializer import DeserializeError, DataclassSerializer


@dataclass
class Test(DataclassSerializer):
    s: set


def test_set_deserialize_from_list():
    """
    Test set deserializes from list (JSON compatible)
    """
    obj = Test.deserialize({
        's': ['1', '2', '3']
    })
    assert isinstance(obj.s, set)
    assert obj.s == {'1', '2', '3'}

def test_set_deserialize_from_set():
    """
    Test set deserializes from set
    """
    obj = Test.deserialize({
        's': {'1', '2', '3'}
    })
    assert isinstance(obj.s, set)
    assert obj.s == {'1', '2', '3'}

def test_set_deserialize_roundtrip():
    """
    Test set deserializes/serializes in a loss-less roundtrip
    """
    json = Test.deserialize({'s': ['1', '2', '3']}).serialize()
    assert json['s'] == ['1', '2', '3']

def test_set_serialize():
    """
    Test set serializes
    """
    json = Test(s={'1', '2', '3'}).serialize()
    assert json['s'] == ['1', '2', '3']

def test_set_serialize_from_list():
    """
    Test set seserializes from list
    """
    json = Test(s=['1', '2', '3']).serialize()
    assert json['s'] == ['1', '2', '3']

def test_set_serialize_from_numpy_ndarray():
    """
    Test set seserializes from numpy.ndarray
    """
    json = Test(s=np.arange(2, 4, dtype=int)).serialize()
    assert json['s'] == [2, 3]

def test_set_serialize_roundtrip():
    """
    Test set serializes/deserializes in a loss-less roundtrip
    """
    obj = Test.deserialize(
        Test(s={'1', '2', '3'}).serialize()
    )
    assert obj.s == {'1', '2', '3'}

def test_set_bad_deserialize():
    '''
    Test bad set deserialize raises exception (exception raised when passed value is not a list)
    '''
    with pytest.raises(DeserializeError):
        Test.deserialize({'s': 'Egx'})
