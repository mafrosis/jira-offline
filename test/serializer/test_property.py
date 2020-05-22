'''
Tests for the DataclassSerializer fields which are implemented as a private class attribute, with a
getter/setter @property exposing the field.
'''
from dataclasses import dataclass, field
from typing import Optional

from jira_offline.utils.serializer import DataclassSerializer


@dataclass
class Test(DataclassSerializer):
    _s: str = field(metadata={'property': 's'})

    @property
    def s(self) -> Optional[str]:  # pylint: disable=missing-function-docstring
        return self._s

    @s.setter
    def s(self, value: str):
        self._s = value


def test_property_deserialize():
    """
    Test property deserializes
    """
    obj = Test.deserialize({'s': 'teststring'})
    assert isinstance(obj.s, str)
    assert obj.s == 'teststring'

def test_property_deserialize_roundrip():
    """
    Test property deserializes/serializes in a loss-less roundrip
    """
    json = Test.deserialize({'s': 'teststring'}).serialize()
    assert json['s'] == 'teststring'

def test_property_serialize():
    """
    Test property serializes
    """
    json = Test(_s='teststring').serialize()
    assert json['s'] == 'teststring'

def test_property_serialize_roundrip():
    """
    Test property serializes/deserializes in a loss-less roundrip
    """
    obj = Test.deserialize(
        Test(_s='teststring').serialize()
    )
    assert obj.s == 'teststring'
