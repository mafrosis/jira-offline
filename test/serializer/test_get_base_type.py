import typing

import pytest

from jira_offline.utils.serializer import get_base_type


@pytest.mark.parametrize('type_', [
    str,
    typing.Optional[str],
])
def test__get_base_type__str(type_):
    '''Ensure the base type is str'''
    assert get_base_type(type_) is str


@pytest.mark.parametrize('type_', [
    dict,
    typing.Dict,
    typing.Dict[str, str],
    typing.Optional[dict],
])
def test__get_base_type__dict(type_):
    '''Ensure the base type is dict'''
    assert get_base_type(type_) is dict
