from dataclasses import dataclass
import uuid

import pytest

from jira_cli.utils import DeserializeError, DataclassSerializer


@dataclass
class Test(DataclassSerializer):
    u: uuid.UUID


def test_uuid_deserialize():
    """
    Test uuid deserializes
    """
    obj = Test.deserialize({'u': 'e5f6e923-436f-4e62-9ba4-8a808fea6e5a'})
    assert isinstance(obj.u, uuid.UUID)
    assert str(obj.u) == 'e5f6e923-436f-4e62-9ba4-8a808fea6e5a'

def test_uuid_deserialize_fail_on_not_valid():
    '''
    Test deserialize of invalid uuid raises exception
    '''
    with pytest.raises(DeserializeError):
        Test.deserialize({'u': 'Bacon'})

def test_uuid_deserialize_roundrip():
    """
    Test uuid deserializes/serializes in a loss-less roundrip
    """
    json = Test.deserialize({'u': 'e5f6e923-436f-4e62-9ba4-8a808fea6e5a'}).serialize()
    assert json['u'] == 'e5f6e923-436f-4e62-9ba4-8a808fea6e5a'

def test_uuid_serialize():
    """
    Test uuid serializes
    """
    json = Test(u='e5f6e923-436f-4e62-9ba4-8a808fea6e5a').serialize()
    assert json['u'] == 'e5f6e923-436f-4e62-9ba4-8a808fea6e5a'

def test_uuid_serialize_roundrip():
    """
    Test uuid serializes/deserializes in a loss-less roundrip
    """
    obj = Test.deserialize(
        Test(u='e5f6e923-436f-4e62-9ba4-8a808fea6e5a').serialize()
    )
    assert isinstance(obj.u, uuid.UUID)
    assert str(obj.u) == 'e5f6e923-436f-4e62-9ba4-8a808fea6e5a'
