from dataclasses import dataclass
import datetime

from jira_cli.main import DataclassSerializer


@dataclass
class Test(DataclassSerializer):
    dt: datetime.date


def test_date_deserialize():
    """
    Test date deserializes
    """
    obj = Test.deserialize({'dt': '2018-09-24'})
    assert isinstance(obj.dt, datetime.date)
    assert obj.dt.year == 2018
    assert obj.dt.month == 9
    assert obj.dt.day == 24

def test_date_deserialize_roundtrip():
    """
    Test date deserializes/serializes in a loss-less roundtrip
    """
    json = Test.deserialize({'dt': '2018-09-24'}).serialize()
    assert json['dt'] == '2018-09-24'

def test_date_serialize():
    """
    Test date serializes
    """
    json = Test(dt=datetime.date(2018, 9, 24)).serialize()
    assert json['dt'] == '2018-09-24'

def test_date_serialize_roundtrip():
    """
    Test date serializes/deserializes in a loss-less roundtrip
    """
    obj = Test.deserialize(
        Test(dt=datetime.date(2018, 9, 24)).serialize()
    )
    assert obj.dt.year == 2018
    assert obj.dt.month == 9
    assert obj.dt.day == 24
