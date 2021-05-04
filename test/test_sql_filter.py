import copy
from unittest import mock

import pytest

from fixtures import ISSUE_1
from jira_offline.exceptions import FilterQueryEscapingError
from jira_offline.models import Issue
from jira_offline.sql_filter import IssueFilter


def test_parse__bad_query__double_escaping():
    '''
    Ensure that a double escaped query string is escaped correctly
    '''
    filt = IssueFilter()
    with pytest.raises(FilterQueryEscapingError):
        filt.set("'summary == An eggcellent summarisation'")


@pytest.mark.parametrize('where', [
    "summary == 'eggcellent'",
    "summary == eggcellent",
])
def test_parse__primitive_eq_str(mock_jira, where):
    '''
    Test string field EQUALS value filter
    '''
    # Setup a test fixture to target in the filter query
    ISSUE_A = copy.deepcopy(ISSUE_1)
    ISSUE_A['summary'] = 'eggcellent'
    ISSUE_A['key'] = 'FILT-1'

    # Add test fixture and a spare to the local Jira storage
    mock_jira['FILT-1'] = Issue.deserialize(ISSUE_A)
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1)

    assert len(mock_jira) == 2

    filt = IssueFilter()
    filt.set(where)

    with mock.patch('jira_offline.jira.jira', mock_jira):
        df = filt.apply()

    assert len(df) == 1
    assert df.iloc[0]['key'] == 'FILT-1'


def test_parse__primitive_eq_str_multiword(mock_jira):
    '''
    Test field EQUALS 'multiple strings' filter
    '''
    # Setup a test fixture to target in the filter query
    ISSUE_A = copy.deepcopy(ISSUE_1)
    ISSUE_A['summary'] = 'An eggcellent summarisation'
    ISSUE_A['key'] = 'FILT-1'

    # Add test fixture and a spare to the local Jira storage
    mock_jira['FILT-1'] = Issue.deserialize(ISSUE_A)
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1)

    assert len(mock_jira) == 2

    filt = IssueFilter()
    filt.set("summary == 'An eggcellent summarisation'")

    with mock.patch('jira_offline.jira.jira', mock_jira):
        df = filt.apply()

    assert len(df) == 1
    assert df.iloc[0]['key'] == 'FILT-1'


def test_parse__primitive_neq_str(mock_jira):
    '''
    Test string field NOT EQUALS value filter
    '''
    # Setup a test fixture to target in the filter query
    ISSUE_A = copy.deepcopy(ISSUE_1)
    ISSUE_A['summary'] = 'eggcellent'
    ISSUE_A['key'] = 'FILT-1'

    # Add test fixture and a spare to the local Jira storage
    mock_jira['FILT-1'] = Issue.deserialize(ISSUE_A)
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1)

    assert len(mock_jira) == 2

    filt = IssueFilter()
    filt.set("summary != eggcellent")

    with mock.patch('jira_offline.jira.jira', mock_jira):
        df = filt.apply()

    assert len(df) == 1
    assert df.iloc[0]['key'] == 'TEST-71'


def test_parse__primitive_project_eq_str(mock_jira, project, project2):
    '''
    Test special-case project field EQUALS string filter
    The underlying field name is "project_key"
    '''
    # Setup a test fixture to target in the filter query
    ISSUE_A = copy.deepcopy(ISSUE_1)
    ISSUE_A['project'] = project2.key
    ISSUE_A['key'] = 'FILT-1'

    # Add test fixture and a spare to the local Jira storage
    mock_jira['FILT-1'] = Issue.deserialize(ISSUE_A, project=project2)
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1, project=project)

    assert len(mock_jira) == 2

    filt = IssueFilter()
    filt.set(f'project == {project2.key}')

    with mock.patch('jira_offline.jira.jira', mock_jira):
        df = filt.apply()

    assert len(df) == 1
    assert df.iloc[0]['key'] == 'FILT-1'


@pytest.mark.parametrize('where', [
    "summary LIKE 'eggcellent'",
    "summary LIKE eggcellent",
])
def test_parse__primitive_like_str(mock_jira, where):
    '''
    Test string field LIKE value filter
    '''
    # Setup a test fixture to target in the filter query
    ISSUE_A = copy.deepcopy(ISSUE_1)
    ISSUE_A['summary'] = 'An eggcellent summarisation'
    ISSUE_A['key'] = 'FILT-1'

    # Add test fixture and a spare to the local Jira storage
    mock_jira['FILT-1'] = Issue.deserialize(ISSUE_A)
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1)

    assert len(mock_jira) == 2

    filt = IssueFilter()
    filt.set(where)

    with mock.patch('jira_offline.jira.jira', mock_jira):
        df = filt.apply()

    assert len(df) == 1
    assert df.iloc[0]['key'] == 'FILT-1'


@pytest.mark.parametrize('value', [
    1111,
    "'1111'",
])
def test_parse__primitive_eq_int(mock_jira, value):
    '''
    Test integer field EQUALS value filter
    '''
    # Setup a test fixture to target in the filter query
    ISSUE_A = copy.deepcopy(ISSUE_1)
    ISSUE_A['id'] = 1111
    ISSUE_A['key'] = 'FILT-1'

    # Add test fixture and a spare to the local Jira storage
    mock_jira['FILT-1'] = Issue.deserialize(ISSUE_A)
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1)

    assert len(mock_jira) == 2

    filt = IssueFilter()
    filt.set(f'id == {value}')

    with mock.patch('jira_offline.jira.jira', mock_jira):
        df = filt.apply()

    assert len(df) == 1
    assert df.iloc[0]['key'] == 'FILT-1'


def test_parse__primitive_neq_int(mock_jira):
    '''
    Test integer field NOT EQUALS value filter
    '''
    # Setup a test fixture to target in the filter query
    ISSUE_A = copy.deepcopy(ISSUE_1)
    ISSUE_A['id'] = 1111
    ISSUE_A['key'] = 'FILT-1'

    # Add test fixture and a spare to the local Jira storage
    mock_jira['FILT-1'] = Issue.deserialize(ISSUE_A)
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1)

    assert len(mock_jira) == 2

    filt = IssueFilter()
    filt.set("id != 1111")

    with mock.patch('jira_offline.jira.jira', mock_jira):
        df = filt.apply()

    assert len(df) == 1
    assert df.iloc[0]['key'] == 'TEST-71'


@pytest.mark.parametrize('operator,count', [
    ('<', 1),
    ('<=', 2),
])
def test_parse__primitive_lt_int(mock_jira, operator, count):
    '''
    Test integer field LESS THAN value filter
    '''
    # Setup a test fixture to target in the filter query
    ISSUE_A = copy.deepcopy(ISSUE_1)
    ISSUE_A['id'] = '1230'
    ISSUE_A['key'] = 'FILT-1'

    # Add test fixture and a spare to the local Jira storage
    mock_jira['FILT-1'] = Issue.deserialize(ISSUE_A)
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1)

    assert len(mock_jira) == 2

    filt = IssueFilter()
    filt.set(f"id {operator} 1231")

    with mock.patch('jira_offline.jira.jira', mock_jira):
        df = filt.apply()

    assert len(df) == count
    assert df.iloc[0]['key'] == 'FILT-1'


@pytest.mark.parametrize('operator,count', [
    ('>', 1),
    ('>=', 2),
])
def test_parse__primitive_gt_int(mock_jira, operator, count):
    '''
    Test field GREATER THAN integer filter
    '''
    # Setup a test fixture to target in the filter query
    ISSUE_A = copy.deepcopy(ISSUE_1)
    ISSUE_A['id'] = '1232'
    ISSUE_A['key'] = 'FILT-1'

    # Add test fixture and a spare to the local Jira storage
    mock_jira['FILT-1'] = Issue.deserialize(ISSUE_A)
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1)

    assert len(mock_jira) == 2

    filt = IssueFilter()
    filt.set(f"id {operator} 1231")

    with mock.patch('jira_offline.jira.jira', mock_jira):
        df = filt.apply()

    assert len(df) == count
    assert df.iloc[0]['key'] == 'FILT-1'


@pytest.mark.parametrize('operator,count', [
    ('<', 1),
    ('<=', 2),
])
@mock.patch('jira_offline.sql_filter.IssueFilter.tz', new_callable=mock.PropertyMock)
def test_parse__primitive_lt_datetime(mock_tz, mock_jira, project, operator, count):
    '''
    Test field LESS THAN datetime filter
    '''
    # Setup a test fixture to target in the filter query
    ISSUE_A = copy.deepcopy(ISSUE_1)
    ISSUE_A['created'] = '2018-09-24T08:44:05'
    ISSUE_A['key'] = 'FILT-1'

    # Add test fixtures, passing project to ensure dates are deserialized with timezone set
    mock_jira['FILT-1'] = Issue.deserialize(ISSUE_A, project)
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1, project)

    assert len(mock_jira) == 2

    filt = IssueFilter()
    filt.set(f"created {operator} '2018-09-24T08:44:06'")

    # Set the timezone of the date in the passed query (default is local system time)
    mock_tz.return_value = project.timezone

    with mock.patch('jira_offline.jira.jira', mock_jira):
        df = filt.apply()

    assert len(df) == count
    assert df.iloc[0]['key'] == 'FILT-1'


@pytest.mark.parametrize('operator,count', [
    ('>', 1),
    ('>=', 2),
])
@mock.patch('jira_offline.sql_filter.IssueFilter.tz', new_callable=mock.PropertyMock)
def test_parse__primitive_gt_datetime(mock_tz, mock_jira, project, operator, count):
    '''
    Test field GREATER THAN datetime filter
    '''
    # Setup a test fixture to target in the filter query
    ISSUE_A = copy.deepcopy(ISSUE_1)
    ISSUE_A['created'] = '2018-09-24T08:44:07'
    ISSUE_A['key'] = 'FILT-1'

    # Add test fixtures, passing project to ensure dates are deserialized with timezone set
    mock_jira['FILT-1'] = Issue.deserialize(ISSUE_A, project)
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1, project)

    assert len(mock_jira) == 2

    filt = IssueFilter()
    filt.set(f"created {operator} '2018-09-24T08:44:06'")

    # Set the timezone of the date in the passed query (default is local system time)
    mock_tz.return_value = project.timezone

    with mock.patch('jira_offline.jira.jira', mock_jira):
        df = filt.apply()

    assert len(df) == count
    assert df.iloc[0]['key'] == 'FILT-1'


@pytest.mark.parametrize('search_terms,count', [
    ('EGG', 1),
    ('BACON', 1),
    ('EGG, BACON', 1),
    ('0.1', 2),
    ('MISSING', 0),
])
def test_parse__primitive_in_list(mock_jira, search_terms, count):
    '''
    Test field IN list filter
    '''
    # Setup a test fixture to target in the filter query
    ISSUE_A = copy.deepcopy(ISSUE_1)
    ISSUE_A['fix_versions'] = {'EGG', 'BACON', '0.1'}
    ISSUE_A['key'] = 'FILT-1'

    # Add test fixture and a spare to the local Jira storage
    mock_jira['FILT-1'] = Issue.deserialize(ISSUE_A)
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1)

    assert len(mock_jira) == 2

    filt = IssueFilter()
    filt.set(f"fix_versions in ({search_terms})")

    with mock.patch('jira_offline.jira.jira', mock_jira):
        df = filt.apply()

    assert len(df) == count


@pytest.mark.parametrize('where,count', [
    ('summary == eggcellent and creator == dave', 1),
    ('summary == notarealsummary and creator == dave', 0),
])
def test_parse__compound_and_eq_str(mock_jira, where, count):
    '''
    Test field EQUALS string AND otherfield EQUALS otherstring filter
    '''
    # Setup a test fixture to target in the filter query
    ISSUE_A = copy.deepcopy(ISSUE_1)
    ISSUE_A['summary'] = 'eggcellent'
    ISSUE_A['creator'] = 'dave'
    ISSUE_A['key'] = 'FILT-1'

    # Add test fixture and a spare to the local Jira storage
    mock_jira['FILT-1'] = Issue.deserialize(ISSUE_A)
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1)

    assert len(mock_jira) == 2

    filt = IssueFilter()
    filt.set(where)

    with mock.patch('jira_offline.jira.jira', mock_jira):
        df = filt.apply()

    assert len(df) == count


@pytest.mark.parametrize('where,count', [
    ('summary == eggcellent or creator == dave', 1),
    ('summary == notarealsummary or creator == dave', 0),
])
def test_parse__compound_or_eq_str(mock_jira, where, count):
    '''
    Test field EQUALS string OR otherfield EQUALS otherstring filter
    '''
    # Setup a test fixture to target in the filter query
    ISSUE_A = copy.deepcopy(ISSUE_1)
    ISSUE_A['summary'] = 'eggcellent'
    ISSUE_A['creator'] = 'notarealcreator'
    ISSUE_A['key'] = 'FILT-1'

    # Add test fixture and a spare to the local Jira storage
    mock_jira['FILT-1'] = Issue.deserialize(ISSUE_A)
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1)

    assert len(mock_jira) == 2

    filt = IssueFilter()
    filt.set(where)

    with mock.patch('jira_offline.jira.jira', mock_jira):
        df = filt.apply()

    assert len(df) == count


@pytest.mark.parametrize('where,count', [
    ("created > '2018-09-24T08:44:06' and created < '2018-09-24T08:44:08'", 1),
    ("created > '2018-09-24T08:44:06' and created <= '2018-09-24T08:44:07'", 1),
    ("created >= '2018-09-24T08:44:07' and created < '2018-09-24T08:44:08'", 1),
])
@mock.patch('jira_offline.sql_filter.IssueFilter.tz', new_callable=mock.PropertyMock)
def test_parse__compound_in_daterange(mock_tz, mock_jira, project, where, count):
    '''
    Test field BETWEEN two datetimes
    '''
    # Setup a test fixture to target in the filter query
    ISSUE_A = copy.deepcopy(ISSUE_1)
    ISSUE_A['created'] = '2018-09-24T08:44:07'
    ISSUE_A['key'] = 'FILT-1'

    # Add test fixtures, passing project to ensure dates are deserialized with timezone set
    mock_jira['FILT-1'] = Issue.deserialize(ISSUE_A, project)
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1, project)

    assert len(mock_jira) == 2

    filt = IssueFilter()
    filt.set(where)

    # Set the timezone of the date in the passed query (default is local system time)
    mock_tz.return_value = project.timezone

    with mock.patch('jira_offline.jira.jira', mock_jira):
        df = filt.apply()

    assert len(df) == count
