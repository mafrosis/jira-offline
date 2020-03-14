from dataclasses import dataclass
import decimal

import pytest

from jira_cli.utils.serializer import DeserializeError, DataclassSerializer


@dataclass
class Test(DataclassSerializer):
    d: decimal.Decimal


def test_decimal_deserialize():
    """
    Test decimal deserializes
    """
    obj = Test.deserialize({'d': '123.45'})
    assert isinstance(obj.d, decimal.Decimal)
    assert obj.d == decimal.Decimal('123.45')

def test_decimal_deserialize_roundrip():
    """
    Test decimal deserializes/serializes in a loss-less roundrip
    """
    json = Test.deserialize({'d': '123.45'}).serialize()
    assert json['d'] == '123.45'

def test_decimal_serialize():
    """
    Test decimal serializes
    """
    json = Test(d=decimal.Decimal('123.45')).serialize()
    assert json['d'] == '123.45'

def test_decimal_serialize_roundrip():
    """
    Test decimal serializes/deserializes in a loss-less roundrip
    """
    obj = Test.deserialize(
        Test(d=decimal.Decimal('123.45')).serialize()
    )
    assert obj.d == decimal.Decimal('123.45')

def test_decimal_bad_deserialize():
    '''
    Test bad decimal deserialize raises exception
    '''
    with pytest.raises(DeserializeError):
        Test.deserialize({'d': 'Egx'})
