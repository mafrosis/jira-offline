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
    typing.Optional[typing.Dict],
    typing.Optional[typing.Dict[str, str]],
])
def test__get_base_type__dict(type_):
    '''Ensure the base type is dict'''
    assert get_base_type(type_) is dict


@pytest.mark.parametrize('type_', [
    list,
    typing.List,
    typing.List[str],
    typing.Optional[list],
    typing.Optional[typing.List],
    typing.Optional[typing.List[str]],
])
def test__get_base_type__list(type_):
    '''Ensure the base type is list'''
    assert get_base_type(type_) is list
