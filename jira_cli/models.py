from dataclasses import dataclass, field
import datetime
import enum
import textwrap

import dictdiffer
from tabulate import tabulate

from jira_cli.utils import DataclassSerializer


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
    assignee: str
    created: datetime.datetime
    creator: str
    description: str
    fixVersions: set
    issuetype: str
    key: str
    labels: set
    priority: str
    project: str
    reporter: str
    status: IssueStatus
    summary: str
    updated: datetime.datetime
    estimate: int = field(default=None)
    epic_ref: str = field(default=None)
    epic_name: str = field(default=None)

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

    def __str__(self):
        '''Pretty print this Issue'''
        if self.issuetype == 'Epic':
            epicdetails = ('Epic Short Name', f'{self.epic_name}')
        else:
            epicdetails = ('Epic Ref', f'{self.epic_ref}')

        return tabulate([
            ('Summary', f'[{self.key}] {self.summary}'),
            ('Type', self.issuetype),
            epicdetails,
            ('Status', self.status.value),
            ('Priority', self.priority),
            ('Assignee', self.assignee),
            ('Estimate', self.estimate),
            ('Description', '\n'.join(textwrap.wrap(self.description, width=100))),
            ('Fix Version', tabulate([('-', v) for v in self.fixVersions], tablefmt='plain')),
            ('Labels', tabulate([('-', l) for l in self.labels], tablefmt='plain')),
            ('Reporter', self.reporter),
            ('Creator', self.creator),
            ('Created', self.created),
            ('Updated', self.updated),
        ])
