'''
Tests for the DataclassSerializer.deserialize special-case parameter constructor_kwargs
'''
from dataclasses import dataclass, field

from jira_offline.utils.serializer import DataclassSerializer


@dataclass
class Test(DataclassSerializer):
    m: int
    r: int = field(repr=False, metadata={'serialize': False})


def test_deserialize_extra_kwargs_passed_to_target_class():
    """
    Test deserialize passes constructor_kwargs onto the target dataclass after deserialisation
    """
    obj = Test.deserialize({'m': 123}, constructor_kwargs={'r': 456})
    assert obj.r == 456
