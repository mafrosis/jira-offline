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


@pytest.mark.parametrize('operator,search_term,count', [
    ('==', "'eggcellent'", 1),
    ('==', 'eggcellent', 1),
    ('!=', 'eggcellent', 1),
    ('!=', 'missing', 2),
    ('==', "'This is the story summary'", 1),
])
def test_parse__primitive_str(mock_jira, operator, search_term, count):
    '''
    Test string field ==,!= value filter
    '''
    # Setup test fixtures to target in the filter query
    ISSUE_1['summary'] = 'This is the story summary'

    ISSUE_A = copy.deepcopy(ISSUE_1)
    ISSUE_A['summary'] = 'eggcellent'
    ISSUE_A['key'] = 'FILT-1'

    # Add test fixture and a spare to the local Jira storage
    mock_jira['FILT-1'] = Issue.deserialize(ISSUE_A)
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1)

    assert len(mock_jira) == 2

    filt = IssueFilter()
    filt.set(f"summary {operator} {search_term}")

    with mock.patch('jira_offline.jira.jira', mock_jira):
        df = filt.apply()

    assert len(df) == count


def test_parse__primitive_project_eq_str(mock_jira, project, project2):
    '''
    Test special-case project field EQUALS string filter
    The underlying field name is "project_key"
    '''
    # Setup test fixtures to target in the filter query
    ISSUE_A = copy.deepcopy(ISSUE_1)
    ISSUE_A['key'] = 'FILT-1'

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
    # Setup test fixtures to target in the filter query
    ISSUE_1['summary'] = 'This is the story summary'

    ISSUE_A = copy.deepcopy(ISSUE_1)
    ISSUE_A['summary'] = 'An eggcellent summarisation'
    ISSUE_A['key'] = 'FILT-1'

    mock_jira['FILT-1'] = Issue.deserialize(ISSUE_A)
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1)

    assert len(mock_jira) == 2

    filt = IssueFilter()
    filt.set(where)

    with mock.patch('jira_offline.jira.jira', mock_jira):
        df = filt.apply()

    assert len(df) == 1
    assert df.iloc[0]['key'] == 'FILT-1'


@pytest.mark.parametrize('fixture,operator,count', [
    (1111, '==', 1),
    (1111, '!=', 1),
    (1230, '<', 1),
    (1230, '<=', 2),
    (1232, '>', 1),
    (1232, '>=', 2),
])
def test_parse__primitive_int(mock_jira, fixture, operator, count):
    '''
    Test field ==,!=,<,<=,>,>= integer filter
    '''
    # Setup test fixtures to target in the filter query
    ISSUE_1['created'] = 1231

    ISSUE_A = copy.deepcopy(ISSUE_1)
    ISSUE_A['id'] = fixture
    ISSUE_A['key'] = 'FILT-1'

    mock_jira['FILT-1'] = Issue.deserialize(ISSUE_A)
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1)

    assert len(mock_jira) == 2

    filt = IssueFilter()
    filt.set(f"id {operator} 1231")

    with mock.patch('jira_offline.jira.jira', mock_jira):
        df = filt.apply()

    assert len(df) == count


@pytest.mark.parametrize('operator,fixture,count', [
    ('<', '2018-09-24T08:44:05', 1),
    ('<=', '2018-09-24T08:44:05', 2),
    ('>', '2018-09-24T08:44:07', 1),
    ('>=', '2018-09-24T08:44:07', 2),
])
@mock.patch('jira_offline.sql_filter.IssueFilter.tz', new_callable=mock.PropertyMock)
def test_parse__primitive_datetime(mock_tz, mock_jira, project, operator, fixture, count):
    '''
    Test field <,<=,>,>= datetime filter
    '''
    # Setup test fixtures to target in the filter query
    ISSUE_1['created'] = '2018-09-24T08:44:06'

    ISSUE_A = copy.deepcopy(ISSUE_1)
    ISSUE_A['created'] = fixture
    ISSUE_A['key'] = 'FILT-1'

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


@pytest.mark.parametrize('operator,search_terms,count', [
    ('in', 'EGG', 1),
    ('in', 'BACON', 1),
    ('in', 'EGG, BACON', 1),
    ('in', '0.1', 2),
    ('in', 'EGG, BACON, 0.1', 2),
    ('in', 'MISSING', 0),

    ('not in', 'EGG', 1),
    ('not in', 'BACON', 1),
    ('not in', 'EGG, BACON', 1),
    ('not in', '0.1', 0),
    ('not in', 'EGG, BACON, 0.1', 0),
    ('not in', 'MISSING', 2),
])
def test_parse__primitive_list__set(mock_jira, operator, search_terms, count):
    '''
    Test set field IN/NOT IN a list of values
    '''
    # Setup test fixtures to target in the filter query
    ISSUE_1['fix_versions'] = ['0.1']

    ISSUE_A = copy.deepcopy(ISSUE_1)
    ISSUE_A['fix_versions'] = {'EGG', 'BACON', '0.1'}
    ISSUE_A['key'] = 'FILT-1'

    mock_jira['FILT-1'] = Issue.deserialize(ISSUE_A)
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1)

    assert len(mock_jira) == 2

    filt = IssueFilter()
    filt.set(f"fix_versions {operator} ({search_terms})")

    with mock.patch('jira_offline.jira.jira', mock_jira):
        df = filt.apply()

    assert len(df) == count


@pytest.mark.parametrize('operator,search_terms,count', [
    ('in', '"Story Done", Egg', 2),
    ('in', 'Egg', 1),
    ('in', '"Story Done"', 1),
    ('in', 'Missing', 0),

    ('not in', '"Story Done", Egg', 0),
    ('not in', 'Egg', 1),
    ('not in', '"Story Done"', 1),
    ('not in', 'Missing', 2),
])
def test_parse__primitive_list__string(mock_jira, operator, search_terms, count):
    '''
    Test string field IN/NOT IN a list of values
    '''
    # Setup test fixtures to target in the filter query
    ISSUE_1['status'] = 'Story Done'

    ISSUE_A = copy.deepcopy(ISSUE_1)
    ISSUE_A['status'] = 'Egg'
    ISSUE_A['key'] = 'FILT-1'

    mock_jira['FILT-1'] = Issue.deserialize(ISSUE_A)
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1)

    assert len(mock_jira) == 2

    filt = IssueFilter()
    filt.set(f"status {operator} ({search_terms})")

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
    # Setup test fixtures to target in the filter query
    ISSUE_1['summary'] = 'This is the story summary'
    ISSUE_1['creator'] = 'danil1'

    ISSUE_A = copy.deepcopy(ISSUE_1)
    ISSUE_A['summary'] = 'eggcellent'
    ISSUE_A['creator'] = 'dave'
    ISSUE_A['key'] = 'FILT-1'

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
    # Setup test fixtures to target in the filter query
    ISSUE_1['summary'] = 'This is the story summary'
    ISSUE_1['creator'] = 'danil1'

    ISSUE_A = copy.deepcopy(ISSUE_1)
    ISSUE_A['summary'] = 'eggcellent'
    ISSUE_A['creator'] = 'notarealcreator'
    ISSUE_A['key'] = 'FILT-1'

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
    # Setup test fixtures to target in the filter query
    ISSUE_1['creator'] = 'danil1'

    ISSUE_A = copy.deepcopy(ISSUE_1)
    ISSUE_A['created'] = '2018-09-24T08:44:07'
    ISSUE_A['key'] = 'FILT-1'

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


@pytest.mark.parametrize('operator,fixture,count', [
    ('==', '2018-09-23T12:00:00', 0),
    ('==', '2018-09-23T23:59:59', 0),
    ('==', '2018-09-24T00:00:00', 1),
    ('==', '2018-09-24T00:00:01', 1),
    ('==', '2018-09-24T12:00:00', 1),
    ('==', '2018-09-24T23:59:59', 1),
    ('==', '2018-09-25T00:00:00', 0),
    ('==', '2018-09-25T12:00:00', 0),

    ('<', '2018-09-23T12:00:00', 1),
    ('<', '2018-09-23T23:59:59', 1),
    ('<', '2018-09-24T00:00:00', 0),
    ('<', '2018-09-24T00:00:01', 0),
    ('<', '2018-09-24T12:00:00', 0),
    ('<', '2018-09-24T23:59:59', 0),
    ('<', '2018-09-25T00:00:00', 0),
    ('<', '2018-09-25T12:00:00', 0),

    ('<=', '2018-09-23T12:00:00', 1),
    ('<=', '2018-09-23T23:59:59', 1),
    ('<=', '2018-09-24T00:00:00', 1),
    ('<=', '2018-09-24T00:00:01', 1),
    ('<=', '2018-09-24T12:00:00', 1),
    ('<=', '2018-09-24T23:59:59', 1),
    ('<=', '2018-09-25T00:00:00', 0),
    ('<=', '2018-09-25T12:00:00', 0),

    ('>', '2018-09-23T12:00:00', 0),
    ('>', '2018-09-23T23:59:59', 0),
    ('>', '2018-09-24T00:00:00', 0),
    ('>', '2018-09-24T00:00:01', 0),
    ('>', '2018-09-24T12:00:00', 0),
    ('>', '2018-09-24T23:59:59', 0),
    ('>', '2018-09-25T00:00:00', 1),
    ('>', '2018-09-25T12:00:00', 1),

    ('>=', '2018-09-23T12:00:00', 0),
    ('>=', '2018-09-23T23:59:59', 0),
    ('>=', '2018-09-24T00:00:00', 1),
    ('>=', '2018-09-24T00:00:01', 1),
    ('>=', '2018-09-24T12:00:00', 1),
    ('>=', '2018-09-24T23:59:59', 1),
    ('>=', '2018-09-25T00:00:00', 1),
    ('>=', '2018-09-25T12:00:00', 1),

    ('!=', '2018-09-23T12:00:00', 1),
    ('!=', '2018-09-23T23:59:59', 1),
    ('!=', '2018-09-24T00:00:00', 0),
    ('!=', '2018-09-24T00:00:01', 0),
    ('!=', '2018-09-24T12:00:00', 0),
    ('!=', '2018-09-24T23:59:59', 0),
    ('!=', '2018-09-25T00:00:00', 1),
    ('!=', '2018-09-25T12:00:00', 1),
])
@mock.patch('jira_offline.sql_filter.IssueFilter.tz', new_callable=mock.PropertyMock)
def test_parse__primitive_date_special_case(mock_tz, mock_jira, project, operator, fixture, count):
    '''
    Test special-case datetime field ==,>,>=,<,<= to specific day date
    '''
    # Setup test fixtures to target in the filter query
    ISSUE_1['creator'] = 'danil1'

    ISSUE_A = copy.deepcopy(ISSUE_1)
    ISSUE_A['created'] = fixture
    ISSUE_A['key'] = 'FILT-1'

    mock_jira['FILT-1'] = Issue.deserialize(ISSUE_A, project)

    filt = IssueFilter()
    filt.set(f"created {operator} '2018-09-24'")

    # Set the timezone of the date in the passed query (default is local system time)
    mock_tz.return_value = project.timezone

    with mock.patch('jira_offline.jira.jira', mock_jira):
        df = filt.apply()

    assert len(df) == count


def test_parse__build_mask_caching(mock_jira):
    '''
    Ensure that _build_mask is not called repeatedly, as it can be expensive
    '''
    # Add single test fixture to the local Jira storage
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1)

    filt = IssueFilter()
    filt.set("summary == 'This is a story or issue'")

    with mock.patch.object(IssueFilter, '_build_mask', wraps=filt._build_mask) as mock_build_mask:
        with mock.patch('jira_offline.jira.jira', mock_jira):
            filt.apply()
            filt.apply()
            filt.apply()

    assert mock_build_mask.call_count == 1
