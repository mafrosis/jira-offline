from unittest import mock

import pytest

from fixtures import ISSUE_1
from jira_offline.exceptions import FilterQueryEscapingError, FilterQueryParseFailed
from jira_offline.models import CustomFields, Issue, ProjectMeta, Sprint
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
def test_parse__primitive_str(mock_jira, project, operator, search_term, count):
    '''
    Test string field ==,!= value filter
    '''
    # Setup test fixtures to target in the filter query
    with mock.patch.dict(ISSUE_1, {'summary': 'This is the story summary'}):
        mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1, project)

    with mock.patch.dict(ISSUE_1, {'summary': 'eggcellent', 'key': 'FILT-1'}):
        mock_jira['FILT-1'] = Issue.deserialize(ISSUE_1, project)

    assert len(mock_jira) == 2

    filt = IssueFilter()
    filt.set(f"summary {operator} {search_term}")

    with mock.patch('jira_offline.jira.jira', mock_jira):
        df = filt.apply()

    assert len(df) == count


def test_parse__primitive_project_eq_str(mock_jira, project):
    '''
    Test special-case project field EQUALS string filter
    The underlying field name is "project_key"
    '''
    # Setup test fixtures to target in the filter query
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1, project)

    project_2 = ProjectMeta.factory('http://example.com/EGG')

    with mock.patch.dict(ISSUE_1, {'key': 'FILT-1'}):
        mock_jira['FILT-1'] = Issue.deserialize(ISSUE_1, project_2)

    assert len(mock_jira) == 2

    filt = IssueFilter()
    filt.set(f'project == {project_2.key}')

    with mock.patch('jira_offline.jira.jira', mock_jira):
        df = filt.apply()

    assert len(df) == 1
    assert df.iloc[0]['key'] == 'FILT-1'


@pytest.mark.parametrize('where', [
    "summary LIKE 'eggcellent'",
    "summary LIKE eggcellent",
])
def test_parse__primitive_like_str(mock_jira, project, where):
    '''
    Test string field LIKE value filter
    '''
    # Setup test fixtures to target in the filter query
    with mock.patch.dict(ISSUE_1, {'summary': 'This is the story summary'}):
        mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1, project)

    with mock.patch.dict(ISSUE_1, {'summary': 'An eggcellent summarisation', 'key': 'FILT-1'}):
        mock_jira['FILT-1'] = Issue.deserialize(ISSUE_1, project)

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
def test_parse__primitive_int(mock_jira, project, fixture, operator, count):
    '''
    Test field ==,!=,<,<=,>,>= integer filter
    '''
    # Setup test fixtures to target in the filter query
    with mock.patch.dict(ISSUE_1, {'id': 1231}):
        mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1, project)

    with mock.patch.dict(ISSUE_1, {'id': fixture, 'key': 'FILT-1'}):
        mock_jira['FILT-1'] = Issue.deserialize(ISSUE_1, project)

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
def test_parse__primitive_datetime(mock_tz, mock_jira, timezone_project, operator, fixture, count):
    '''
    Test field <,<=,>,>= datetime filter
    '''
    # Setup test fixtures to target in the filter query
    with mock.patch.dict(ISSUE_1, {'created': '2018-09-24T08:44:06'}):
        mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1, project=timezone_project)

    with mock.patch.dict(ISSUE_1, {'created': fixture, 'key': 'FILT-1'}):
        mock_jira['FILT-1'] = Issue.deserialize(ISSUE_1, project=timezone_project)

    assert len(mock_jira) == 2

    filt = IssueFilter()
    filt.set(f"created {operator} '2018-09-24T08:44:06'")

    # Set the timezone of the date in the passed query (default is local system time)
    mock_tz.return_value = timezone_project.timezone

    with mock.patch('jira_offline.jira.jira', mock_jira):
        df = filt.apply()

    assert len(df) == count


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
def test_parse__primitive_list__set(mock_jira, project, operator, search_terms, count):
    '''
    Test set field IN/NOT IN a list of values
    '''
    # Setup test fixtures to target in the filter query
    with mock.patch.dict(ISSUE_1, {'fix_versions': ['0.1']}):
        mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1, project)

    with mock.patch.dict(ISSUE_1, {'fix_versions': ['EGG', 'BACON', '0.1'], 'key': 'FILT-1'}):
        mock_jira['FILT-1'] = Issue.deserialize(ISSUE_1, project)

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
    ('in', 'Egg, Missing', 1),
    ('in', 'Missing', 0),

    ('not in', '"Story Done", Egg', 0),
    ('not in', 'Egg', 1),
    ('not in', '"Story Done"', 1),
    ('not in', 'Egg, Missing', 1),
    ('not in', 'Missing', 2),
])
def test_parse__primitive_list__string(mock_jira, project, operator, search_terms, count):
    '''
    Test string field IN/NOT IN a list of values
    '''
    # Setup test fixtures to target in the filter query
    with mock.patch.dict(ISSUE_1, {'status': 'Story Done'}):
        mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1, project)

    with mock.patch.dict(ISSUE_1, {'status': 'Egg', 'key': 'FILT-1'}):
        mock_jira['FILT-1'] = Issue.deserialize(ISSUE_1, project)

    assert len(mock_jira) == 2

    filt = IssueFilter()
    filt.set(f"status {operator} ({search_terms})")

    with mock.patch('jira_offline.jira.jira', mock_jira):
        df = filt.apply()

    assert len(df) == count


@pytest.mark.parametrize('operator,search_terms,count', [
    ('in', '"Sprint 1", "Sprint 2"', 2),
    ('in', '"Sprint 1"', 1),
    ('in', '"Sprint 2"', 1),

    ('not in', '"Sprint 1", "Sprint 2"', 0),
    ('not in', '"Sprint 1"', 1),
    ('not in', '"Sprint 2"', 1),
])
def test_parse__primitive_list__sprint(mock_jira, operator, search_terms, count):
    '''
    Test sprint string IN/NOT IN a list of sprint objects.

    This is a special case as sprint is stored in the DataFrame as a list of objects, not a simple list of string.
    '''
    # Setup the project configuration with sprint customfield, and two sprints on the project
    project = ProjectMeta(
        key='TEST',
        jira_id='10000',
        customfields=CustomFields(sprint='customfield_10300'),
        sprints={
            1: Sprint(id=1, name='Sprint 1', active=True),
            2: Sprint(id=2, name='Sprint 2', active=False),
        },
    )
    mock_jira.config.projects = {project.id: project}

    # Setup test fixtures to target in the filter query
    with mock.patch.dict(ISSUE_1, {'sprint': 'Sprint 1'}):
        mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1, project)

    with mock.patch.dict(ISSUE_1, {'sprint': 'Sprint 2', 'key': 'FILT-1'}):
        mock_jira['FILT-1'] = Issue.deserialize(ISSUE_1, project)

    assert len(mock_jira) == 2

    filt = IssueFilter()
    filt.set(f"sprint {operator} ({search_terms}) AND project = TEST")

    with mock.patch('jira_offline.jira.jira', mock_jira):
        df = filt.apply()

    assert len(df) == count


def test_parse__primitive_list__sprint_error(mock_jira):
    '''
    Test error raised when sprint is not valid for the supplied project.
    '''
    # Setup the project configuration with sprint customfield, and two sprints on the project
    project = ProjectMeta(
        key='TEST',
        jira_id='10000',
        customfields=CustomFields(sprint='customfield_10300'),
        sprints={
            1: Sprint(id=1, name='Sprint 1', active=True),
        },
    )
    mock_jira.config.projects = {project.id: project}

    # Setup test fixtures to target in the filter query
    with mock.patch.dict(ISSUE_1, {'sprint': 'Sprint 1'}):
        mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1, project)

    assert len(mock_jira) == 1

    filt = IssueFilter()
    filt.set("sprint IN (BadSprint) AND project = TEST")

    with mock.patch('jira_offline.jira.jira', mock_jira):
        with pytest.raises(FilterQueryParseFailed):
            filt.apply()


@pytest.mark.parametrize('where,count', [
    ('summary == eggcellent and creator == dave', 1),
    ('summary == notarealsummary and creator == dave', 0),
    ('summary == eggcellent and creator == dave and description == 1', 1),
    ('summary == eggcellent and creator == dave and description == 0', 0),
])
def test_parse__compound_and_eq_str(mock_jira, project, where, count):
    '''
    Test field EQUALS string AND otherfield EQUALS otherstring filter
    '''
    # Setup test fixtures to target in the filter query
    with mock.patch.dict(ISSUE_1, {'summary': 'This is the story summary', 'creator': 'danil1', 'description': '1'}):
        mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1, project)

    with mock.patch.dict(ISSUE_1, {'summary': 'eggcellent', 'creator': 'dave', 'description': '1', 'key': 'FILT-1'}):
        mock_jira['FILT-1'] = Issue.deserialize(ISSUE_1, project)

    assert len(mock_jira) == 2

    filt = IssueFilter()
    filt.set(where)

    with mock.patch('jira_offline.jira.jira', mock_jira):
        df = filt.apply()

    assert len(df) == count


@pytest.mark.parametrize('where,count', [
    ('summary == eggcellent or creator == dave', 1),
    ('summary == notarealsummary or creator == dave', 0),
    ('summary == notarealsummary or creator == dave or description == 1', 2),
    ('summary == notarealsummary or creator == noone or description == 0', 0),
])
def test_parse__compound_or_eq_str(mock_jira, project, where, count):
    '''
    Test field EQUALS string OR otherfield EQUALS otherstring filter
    '''
    # Setup test fixtures to target in the filter query
    with mock.patch.dict(ISSUE_1, {'summary': 'This is the story summary', 'creator': 'danil1', 'description': '1'}):
        mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1, project)

    with mock.patch.dict(ISSUE_1, {'summary': 'eggcellent', 'creator': 'notarealcreator', 'description': '1', 'key': 'FILT-1'}):
        mock_jira['FILT-1'] = Issue.deserialize(ISSUE_1, project)

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
def test_parse__compound_in_daterange(mock_tz, mock_jira, timezone_project, where, count):
    '''
    Test field BETWEEN two datetimes
    '''
    # Setup test fixtures to target in the filter query
    with mock.patch.dict(ISSUE_1, {'created': '2018-09-24T08:44:06'}):
        mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1, project=timezone_project)

    with mock.patch.dict(ISSUE_1, {'created': '2018-09-24T08:44:07', 'key': 'FILT-1'}):
        mock_jira['FILT-1'] = Issue.deserialize(ISSUE_1, project=timezone_project)

    assert len(mock_jira) == 2

    filt = IssueFilter()
    filt.set(where)

    # Set the timezone of the date in the passed query (default is local system time)
    mock_tz.return_value = timezone_project.timezone

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
def test_parse__primitive_date_special_case(mock_tz, mock_jira, timezone_project, operator, fixture, count):
    '''
    Test special-case datetime field ==,>,>=,<,<= to specific day date
    '''
    # Setup test fixture to target in the filter query
    with mock.patch.dict(ISSUE_1, {'created': fixture, 'key': 'FILT-1'}):
        mock_jira['FILT-1'] = Issue.deserialize(ISSUE_1, project=timezone_project)

    filt = IssueFilter()
    filt.set(f"created {operator} '2018-09-24'")

    # Set the timezone of the date in the passed query (default is local system time)
    mock_tz.return_value = timezone_project.timezone

    with mock.patch('jira_offline.jira.jira', mock_jira):
        df = filt.apply()

    assert len(df) == count


def test_parse__build_mask_caching(mock_jira, project):
    '''
    Ensure that _build_mask is not called repeatedly, as it can be expensive
    '''
    # Add single test fixture to the local Jira storage
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1, project)

    filt = IssueFilter()
    filt.set("summary == 'This is a story or issue'")

    with mock.patch.object(IssueFilter, '_build_mask', wraps=filt._build_mask) as mock_build_mask:
        with mock.patch('jira_offline.jira.jira', mock_jira):
            filt.apply()
            filt.apply()
            filt.apply()

    assert mock_build_mask.call_count == 1
