from dataclasses import dataclass
import datetime

from dateutil.tz import tzoffset

from jira_cli.main import DataclassSerializer


@dataclass
class Test(DataclassSerializer):
    dt: datetime.datetime


def test_datetime_deserialize():
    """
    Test datetime deserializes
    """
    obj = Test.deserialize({'dt': '2018-09-24T08:44:06.333777+10:00'})
    assert isinstance(obj.dt, datetime.datetime)
    assert obj.dt.year == 2018
    assert obj.dt.month == 9
    assert obj.dt.day == 24
    assert obj.dt.hour == 8
    assert obj.dt.minute == 44
    assert obj.dt.second == 6
    assert obj.dt.microsecond == 333777
    assert obj.dt.tzinfo == tzoffset(None, 36000)

def test_datetime_deserialize_roundtrip():
    """
    Test datetime deserializes/serializes in a loss-less roundtrip
    """
    json = Test.deserialize({'dt': '2018-09-24T08:44:06.333777+10:00'}).serialize()
    assert json['dt'] == '2018-09-24T08:44:06.333777+10:00'

def test_datetime_serialize():
    """
    Test datetime serializes
    """
    json = Test(dt=datetime.datetime(2018, 9, 24, 8, 44, 6, 333777, tzinfo=tzoffset('AEST', 36000))).serialize()
    assert json['dt'] == '2018-09-24T08:44:06.333777+10:00'

def test_datetime_serialize_roundtrip():
    """
    Test datetime serializes/deserializes in a loss-less roundtrip
    """
    obj = Test.deserialize(
        Test(dt=datetime.datetime(2018, 9, 24, 8, 44, 6, 333777, tzinfo=tzoffset('AEST', 36000))).serialize()
    )
    assert obj.dt.year == 2018
    assert obj.dt.month == 9
    assert obj.dt.day == 24
    assert obj.dt.hour == 8
    assert obj.dt.minute == 44
    assert obj.dt.second == 6
    assert obj.dt.microsecond == 333777
    assert obj.dt.tzinfo == tzoffset(None, 36000)
