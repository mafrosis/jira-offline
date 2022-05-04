from dataclasses import dataclass

import numpy as np
import pytest

from jira_offline.utils.serializer import DeserializeError, DataclassSerializer


@dataclass
class Test(DataclassSerializer):
    l: list


def test_list_deserialize_from_list():
    """
    Test list deserializes from list (JSON compatible)
    """
    obj = Test.deserialize({
        'l': ['abc', 'def']
    })
    assert isinstance(obj.l, list)
    assert obj.l == ['abc', 'def']

def test_list_deserialize_from_commaseparated():
    """
    Test list deserializes from comma-separated string
    """
    obj = Test.deserialize({
        'l': 'abc,def'
    })
    assert isinstance(obj.l, list)
    assert obj.l == ['abc', 'def']

def test_list_deserialize_roundrip():
    """
    Test list deserializes/serializes in a loss-less roundrip
    """
    json = Test.deserialize({
        'l': ['abc', 'def']
    }).serialize()
    assert json['l'] == ['abc', 'def']

def test_list_serialize():
    """
    Test list serializes
    """
    json = Test(
        l=['abc', 'def']
    ).serialize()
    assert json['l'] == ['abc', 'def']

def test_list_serialize_from_numpy_ndarray():
    """
    Test list serializes from numpy.ndarray
    """
    json = Test(
        l=np.arange(2, 4, dtype=int)
    ).serialize()
    assert json['l'] == [2, 3]

def test_list_serialize_roundrip():
    """
    Test list serializes/deserializes in a loss-less roundrip
    """
    obj = Test.deserialize(
        Test(
            l=['abc', 'def']
        ).serialize()
    )
    assert isinstance(obj.l, list)
    assert obj.l == ['abc', 'def']

def test_list_bad_deserialize():
    '''
    Test bad list deserialize raises exception
    '''
    with pytest.raises(DeserializeError):
        Test.deserialize({'l': {'Egg'}})
