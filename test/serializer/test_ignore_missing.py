'''
Tests for the DataclassSerializer.deserialize special-case parameter ignore_missing
'''
from dataclasses import dataclass, field
from typing import Optional

import pytest

from jira_offline.utils.serializer import DeserializeError, DataclassSerializer


@dataclass
class Test(DataclassSerializer):
    m: str
    o: Optional[int] = field(default=100)


def test_deserialize_raises_when_missing_mandatory_field():
    """
    Test deserialize raises an exception when missing a mandatory field
    """
    with pytest.raises(DeserializeError):
        Test.deserialize({'o': 123})

def test_deserialize_ok_when_missing_mandatory_field_with_ignore_missing():
    """
    Test deserialize is successful with missing a mandatory field, when ignore_missing=True
    """
    Test.deserialize({'o': 123}, ignore_missing=True)
