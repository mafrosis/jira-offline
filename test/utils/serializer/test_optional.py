'''
Tests for the DataclassSerializer special-case where Optional fields must have a default configured
'''
from dataclasses import dataclass, field
from typing import Optional

import pytest

from jira_offline.utils.serializer import DeserializeError, DataclassSerializer


@dataclass
class TestOptionalWithDefault(DataclassSerializer):
    # GOOD
    s: Optional[str] = field(default='s')

@dataclass
class TestOptionalWithoutDefault(DataclassSerializer):
    # BAD
    s: Optional[str]


def test_optional_field_with_default_deserializes():
    """
    Test an Optional field with a configured default deserializes successfully
    """
    obj = TestOptionalWithDefault.deserialize({'s': 'teststring'})
    assert isinstance(obj.s, str)
    assert obj.s == 'teststring'

def test_optional_field_without_default_deserialize_raises_exception():
    """
    Test an Optional field WITHOUT a configured default raises an exception on deserialize
    """
    with pytest.raises(DeserializeError):
        TestOptionalWithoutDefault.deserialize({'s': 'teststring'})
