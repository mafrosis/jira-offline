from dataclasses import dataclass

import pytest

from jira_offline.utils.serializer import DeserializeError, DataclassSerializer


@dataclass
class Test(DataclassSerializer):
    d: dict


def test_dict_deserialize():
    """
    Test dict deserializes
    """
    obj = Test.deserialize({
        'd': {
            'key1': {'x': 'abc'},
            'key2': {'x': 'def'},
        }
    })
    assert isinstance(obj.d, dict)
    assert obj.d == {
        'key1': {'x': 'abc'},
        'key2': {'x': 'def'},
    }

def test_dict_deserialize_roundrip():
    """
    Test dict deserializes/serializes in a loss-less roundrip
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

def test_dict_serialize():
    """
    Test dict serializes
    """
    json = Test(
        d={
            'key1': {'x': 'abc'},
            'key2': {'x': 'def'},
        }
    ).serialize()
    assert json['d'] == {
        'key1': {'x': 'abc'},
        'key2': {'x': 'def'},
    }

def test_dict_serialize_roundrip():
    """
    Test dict serializes/deserializes in a loss-less roundrip
    """
    obj = Test.deserialize(
        Test(
            d={
                'key1': {'x': 'abc'},
                'key2': {'x': 'def'},
            }
        ).serialize()
    )
    assert isinstance(obj.d, dict)
    assert obj.d == {
        'key1': {'x': 'abc'},
        'key2': {'x': 'def'},
    }

def test_dict_bad_deserialize():
    '''
    Test bad dict deserialize raises exception
    '''
    with pytest.raises(DeserializeError):
        Test.deserialize({'d': 'Egx'})
