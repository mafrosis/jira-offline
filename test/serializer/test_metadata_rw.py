'''
Tests for the DataclassSerializer when fields have the "rw" metadata property set.
'''
from typing import Optional

from dataclasses import dataclass, field

from jira_offline.utils.serializer import DataclassSerializer


@dataclass
class Test(DataclassSerializer):
    r: Optional[str]    = field(default=None, metadata={'rw': 'r'})
    w: Optional[str]    = field(default=None, metadata={'rw': 'w'})
    rw: Optional[str]   = field(default=None, metadata={'rw': 'rw'})
    none: Optional[str] = field(default=None, metadata={'rw': ''})


def test_r_field_metadata_field_succeeds_deserialize():
    """
    Test fields with metadata rw=r SUCCEEDs deserialize
    """
    assert Test.deserialize({'r': 'teststring'}).r == 'teststring'

def test_w_field_metadata_field_fails_deserialize():
    """
    Test fields with metadata rw=w FAILs deserialize
    """
    assert Test.deserialize({'w': 'teststring'}).w is None

def test_rw_field_metadata_field_succeeds_deserialize():
    """
    Test fields with metadata rw=rw SUCCEEDs deserialize
    """
    assert Test.deserialize({'rw': 'teststring'}).rw == 'teststring'

def test_none_field_metadata_field_fails_deserialize():
    """
    Test fields with metadata rw=none FAILs deserialize
    """
    assert Test.deserialize({'none': 'teststring'}).none is None


def test_r_field_metadata_field_fails_serialize():
    """
    Test fields with metadata rw=r SUCCEEDs deserialize
    """
    assert 'r' not in Test(r='teststring').serialize()

def test_w_field_metadata_field_succeeds_serialize():
    """
    Test fields with metadata rw=w SUCCEEDs serialize
    """
    assert Test(w='teststring').serialize()['w'] == 'teststring'

def test_rw_field_metadata_field_fails_serialize():
    """
    Test fields with metadata rw=rw SUCCEEDs deserialize
    """
    assert Test(rw='teststring').serialize()['rw'] == 'teststring'

def test_none_field_metadata_field_succeeds_serialize():
    """
    Test fields with metadata rw=none SUCCEEDs serialize
    """
    assert 'none' not in Test(none='teststring').serialize()
