from dataclasses import dataclass
import datetime

from dateutil.tz import gettz, tzoffset, tzutc
import pytest

from jira_offline.utils.serializer import DataclassSerializer


@dataclass
class Test(DataclassSerializer):
    dt: datetime.datetime


@pytest.mark.parametrize('tz_iso,tz_obj', [
    ('+00:00', tzutc()),
    ('+10:00', tzoffset(None, 36000)),
])
def test_datetime_deserialize(tz_iso, tz_obj):
    """
    Test datetime deserializes
    """
    obj = Test.deserialize({'dt': f'2018-09-24T08:44:06.333777{tz_iso}'})
    assert isinstance(obj.dt, datetime.datetime)
    assert obj.dt.year == 2018
    assert obj.dt.month == 9
    assert obj.dt.day == 24
    assert obj.dt.hour == 8
    assert obj.dt.minute == 44
    assert obj.dt.second == 6
    assert obj.dt.microsecond == 333777
    assert obj.dt.tzinfo == tz_obj

@pytest.mark.parametrize('tz_iso', [
    ('+00:00'),
    ('+10:00'),
])
def test_datetime_deserialize_roundtrip(tz_iso):
    """
    Test datetime deserializes/serializes in a loss-less roundtrip
    """
    json = Test.deserialize({'dt': f'2018-09-24T08:44:06.333777{tz_iso}'}).serialize()
    assert json['dt'] == f'2018-09-24T08:44:06.333777{tz_iso}'

@pytest.mark.parametrize('tz_iso,tz_obj', [
    ('+00:00', tzutc()),
    ('+10:00', tzoffset(None, 36000)),
])
def test_datetime_serialize(tz_iso, tz_obj):
    """
    Test datetime serializes
    """
    json = Test(dt=datetime.datetime(2018, 9, 24, 8, 44, 6, 333777, tzinfo=tz_obj)).serialize()
    assert json['dt'] == f'2018-09-24T08:44:06.333777{tz_iso}'

@pytest.mark.parametrize('tz_obj', [
    (tzutc()),
    (tzoffset(None, 36000)),
])
def test_datetime_serialize_roundtrip(tz_obj):
    """
    Test datetime serializes/deserializes in a loss-less roundtrip
    """
    obj = Test.deserialize(
        Test(dt=datetime.datetime(2018, 9, 24, 8, 44, 6, 333777, tzinfo=tz_obj)).serialize()
    )
    assert obj.dt.year == 2018
    assert obj.dt.month == 9
    assert obj.dt.day == 24
    assert obj.dt.hour == 8
    assert obj.dt.minute == 44
    assert obj.dt.second == 6
    assert obj.dt.microsecond == 333777
    assert obj.dt.tzinfo == tz_obj
