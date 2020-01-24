import dataclasses
from dataclasses import dataclass, field
import datetime
import enum
import textwrap
from typing import Tuple

import arrow
import dictdiffer
from tabulate import tabulate

from jira_cli.utils import DataclassSerializer, friendly_title


class IssueStatus(enum.Enum):
    Backlog = 'Backlog'
    ToDo = 'To Do'
    InProgress = 'In Progress'
    StoryInProgress = 'Story in Progress'
    EpicInProgress = 'Epic in Progress'
    EpicInReview = 'Epic in Review'
    EpicWithSquad = 'Epic with Squad'
    EpicReadyforSquad = 'Epic Ready for Squad'
    InRelease = 'In Release'
    Done = 'Done'
    StoryDone = 'Story Done'
    EpicDone = 'Epic Done'
    Closed = 'Closed'
    RiskClosed = 'Risk Closed'
    RiskIdentified = 'Risk Identified'
    NotAssessed = 'Not Assessed'
    Resolved = 'Resolved'
    Accepted = 'Accepted'


# pylint: disable=too-many-instance-attributes
@dataclass
class Issue(DataclassSerializer):
    issuetype: str = field(metadata={'friendly': 'Type'})
    project: str
    summary: str
    assignee: str = field(default=None)
    created: datetime.datetime = field(default=None, metadata={'readonly': True})
    creator: str = field(default=None, metadata={'readonly': True})
    epic_name: str = field(default=None, metadata={'friendly': 'Epic Short Name'})
    epic_ref: str = field(default=None)
    estimate: int = field(default=None)
    description: str = field(default=None)
    fixVersions: set = field(default=None, metadata={'friendly': 'Fix Version'})
    id: str = field(default=None, metadata={'readonly': True})
    key: str = field(default=None, metadata={'readonly': True})
    labels: set = field(default=None)
    priority: str = field(default=None)
    reporter: str = field(default=None)
    status: IssueStatus = field(default=None)
    updated: datetime.datetime = field(default=None, metadata={'readonly': True})

    # local-only dict which represents serialized Issue last seen on JIRA server
    # this property is not written to cache and is created at runtme from diff_to_original
    original: dict = field(default=None, repr=False)

    # patch of current Issue to dict last seen on JIRA server
    diff_to_original: list = field(default=None, repr=False)

    @property
    def is_open(self) -> bool:
        if self.is_inprogress or self.is_todo:
            return True
        elif self.is_done or self.is_closed:
            return False
        else:
            raise AttributeError('Issue cannot be determined open or closed!')

    @property
    def is_todo(self) -> bool:
        if self.status in (IssueStatus.Backlog, IssueStatus.ToDo, IssueStatus.RiskIdentified,
                           IssueStatus.NotAssessed, IssueStatus.EpicReadyforSquad):
            return True
        return False

    @property
    def is_inprogress(self) -> bool:
        if self.status in (IssueStatus.InProgress, IssueStatus.InRelease, IssueStatus.Accepted,
                           IssueStatus.EpicInProgress, IssueStatus.StoryInProgress,
                           IssueStatus.EpicWithSquad, IssueStatus.EpicInReview):
            return True
        return False

    @property
    def is_done(self) -> bool:
        if self.status in (IssueStatus.Done, IssueStatus.StoryDone, IssueStatus.EpicDone,
                           IssueStatus.Resolved):
            return True
        return False

    @property
    def is_closed(self) -> bool:
        if self.is_done or self.status in (IssueStatus.Closed, IssueStatus.RiskClosed):
            return True
        return False

    @classmethod
    def deserialize(cls, attrs: dict) -> object:
        '''
        Deserialize a dict into an Issue object. Inflate the original Jira issue from the
        diff_to_original property
        '''
        # deserialize supplied dict into an Issue object
        issue = super().deserialize(attrs)

        # pylint: disable=no-member
        if issue.diff_to_original is None:
            issue.diff_to_original = []

        # apply the diff_to_original patch to the serialized version of the issue, which recreates
        # the issue dict as last seen on the JIRA server
        # pylint: disable=no-member
        issue.original = dictdiffer.patch(issue.diff_to_original, issue.serialize())

        return issue

    def serialize(self) -> dict:
        '''
        Serialize this Issue object to a dict. Generate the diff_to_original field which enables
        local changes to be written to the offline cache file.
        '''
        # serialize self (Issue object) into a dict
        data = super().serialize()

        if self.original:
            # if this Issue object has the original property set, render the diff between self and
            # the original property. This is written to storage to track changes made offline.
            data['diff_to_original'] = list(
                dictdiffer.diff(data, self.original, ignore=set(['diff_to_original']))
            )

        return data

    def __str__(self, conflicts: dict=None):
        '''
        Pretty print this Issue

        Params:
            conflicts:  A conflict object
        '''
        # create dict of Issue dataclass fields
        issue_fields = {f.name:f for f in dataclasses.fields(Issue)}

        def fmt(field_name, prefix: str=None) -> Tuple[Tuple]:
            '''
            Pretty formatting with support for conflicts

            Params:
                field_name: Dataclass field being formatted
                prefix:     Arbitrary prefix to prepend during string format
            Returns:
                tuple:      Tuple of formatted-pair tuples
            '''
            if conflicts and field_name in conflicts:
                return (
                    ('<<<<<<< base', ''),
                    render(field_name, conflicts[field_name]['base'], prefix),
                    ('=======', ''),
                    render(field_name, conflicts[field_name]['updated'], prefix),
                    ('>>>>>>> updated', ''),
                )
            else:
                return (render(field_name, getattr(self, field_name), prefix),)

        def render(field_name, value: str, prefix: str) -> Tuple[str, str]:
            '''
            Single-field pretty formatting function supporting various types

            Params:
                field_name: Dataclass field to render
                value:      Data to be rendered according to format
                prefix:     Arbitrary prefix to prepend during string format
            Returns:
                tuple:      Pretty field title, formatted value
            '''
            title = friendly_title(field_name)

            if value is None:
                value = ''
            elif issue_fields[field_name].type is set:
                value = tabulate([('-', v) for v in value], tablefmt='plain')
            elif issue_fields[field_name].type is datetime.datetime:
                dt = arrow.get(self.created)
                value = f'{dt.humanize()} [{dt.format()}]'
            elif issubclass(issue_fields[field_name].type, enum.Enum):
                value = value.value
            elif value and issue_fields[field_name].type is str and len(value) > 100:
                value = '\n'.join(textwrap.wrap(value, width=100))

            if prefix:
                value = f'{prefix} {value}'

            return title, value

        if self.issuetype == 'Epic':
            epicdetails = fmt('epic_name')
        else:
            epicdetails = fmt('epic_ref')

        attrs = [
            *fmt('summary', prefix=f'[{self.key}]'),
            *fmt('issuetype'),
            *epicdetails,
            *fmt('status'),
            *fmt('priority'),
            *fmt('assignee'),
            *fmt('estimate'),
            *fmt('description'),
            *fmt('fixVersions'),
            *fmt('labels'),
            *fmt('reporter'),
            *fmt('creator'),
            *fmt('created'),
            *fmt('updated'),
        ]
        return tabulate(attrs)
