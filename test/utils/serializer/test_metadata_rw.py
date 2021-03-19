'''
Tests for the DataclassSerializer when fields have the "serialize" metadata property set.
'''
from typing import Optional

from dataclasses import dataclass, field

from jira_offline.utils.serializer import DataclassSerializer


@dataclass
class Test(DataclassSerializer):
    f1: Optional[str] = field(default=None, metadata={'serialize': False})
    f2: Optional[str] = field(default=None, metadata={'serialize': True})
    f3: Optional[str] = field(default=None)


def test_deserialize_fails__metadata_serialize_is_false():
    """
    Test a field with metadata serialize=False IS NOT deserialized from passed dict
    """
    assert Test.deserialize({'f1': 'teststring'}).f1 is None

def test_deserialize_succeeds__metadata_serialize_is_true():
    """
    Test a field with metadata serialize=True IS deserialized from passed dict
    """
    assert Test.deserialize({'f2': 'teststring'}).f2 == 'teststring'

def test_deserialize_succeeds__metadata_serialize_is_absent():
    """
    Test a field with absent metadata serialize IS deserialized from passed dict
    """
    assert Test.deserialize({'f3': 'teststring'}).f3 == 'teststring'


def test_serialize_fails__metadata_serialize_is_false():
    """
    Test a field with metadata serialize=False IS NOT serialized from passed dict
    """
    assert 'f1' not in Test(f1='teststring').serialize()

def test_serialize_succeeds__metadata_serialize_is_true():
    """
    Test a field with metadata serialize=True IS serialized from passed dict
    """
    assert Test(f2='teststring').serialize()['f2'] == 'teststring'

def test_serialize_succeeds__metadata_serialize_is_absent():
    """
    Test a field with absent metadata serialize IS serialized from passed dict
    """
    assert Test(f3='teststring').serialize()['f3'] == 'teststring'
