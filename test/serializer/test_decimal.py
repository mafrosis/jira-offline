from dataclasses import dataclass
import decimal

from jira_cli.main import DataclassSerializer


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
