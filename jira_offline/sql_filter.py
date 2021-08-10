'''
Functions for parsing SQL where-clause syntax, and filtering the Pandas DataFrame.
'''
from dataclasses import dataclass, field
import datetime
import operator
from typing import cast, Hashable, Optional, Union
import warnings

import arrow
from dateutil.tz import gettz
import mo_parsing
from moz_sql_parser import parse as mozparse
import pandas as pd
from tzlocal import get_localzone

from jira_offline.exceptions import (FilterMozParseFailed, FilterUnknownOperatorException,
                                     FilterUnknownFieldException, FilterQueryEscapingError,
                                     FilterQueryParseFailed)
from jira_offline.models import Issue
from jira_offline.utils import get_field_by_name
from jira_offline.utils.serializer import istype


@dataclass
class IssueFilter:
    '''
    Encapsulates any filters passed in via CLI

    When the application is invoked on the CLI, a filter can be set via --filter on some commands.

    Accessing the data via `jira.df`, `jira.items`, `jira.keys` or `jira.values` on the Jira class
    will return issues filtered by the `apply` method in this class.
    '''
    filter: Optional[str] = field(default=None, init=False)
    _where: Optional[dict] = field(default=None, init=False)
    _tz: Optional[datetime.tzinfo] = field(default=None, init=False)
    _pandas_mask: Optional[pd.Series] = field(default=None, init=False)


    @property
    def tz(self):
        return self._tz or get_localzone()

    @tz.setter
    def tz(self, tz: str):
        self._tz = gettz(tz)

    @property
    def is_set(self) -> bool:
        return bool(self._where)


    def set(self, sql_filter: str):
        '''
        Parse the SQL "where" clause into an object for later use

        Params:
            sql_filter:  Raw SQL-like filter string passed from CLI
        '''
        self.filter = sql_filter

        try:
            self._where = mozparse(f'select count(1) from tbl where {sql_filter}')['where']

            # Reset the cached Pandas mask
            self._pandas_mask = None

            if self._where and self._where.get('literal'):
                raise FilterQueryEscapingError

        except mo_parsing.exceptions.ParseException as e:
            raise FilterMozParseFailed from e


    def apply(self) -> pd.DataFrame:
        '''
        Apply the current filter against the Jira DataFrame
        '''
        from jira_offline.jira import jira  # pylint: disable=cyclic-import, import-outside-toplevel

        if self._where is None:
            return jira._df  # pylint: disable=protected-access

        if self._pandas_mask is None:
            try:
                self._pandas_mask = self._build_mask(jira._df, self._where)  # pylint: disable=protected-access
            except (KeyError, IndexError, ValueError, TypeError) as e:
                raise FilterQueryParseFailed from e

        return jira._df[self._pandas_mask]  # pylint: disable=protected-access


    def _build_mask(self, df: pd.DataFrame, filter_: dict) -> pd.Series:
        '''
        Recurse the WHERE part of the result from `mozparse`, and build a logical Series mask to
        filter the central DataFrame

        Params:
            df:       DataFrame to use for creating masks
            filter_:  Dict object created by `mozparse` containing each part of the filter query
        '''
        def unpack_condition(obj):
            if isinstance(obj, dict) and obj.get('literal'):
                return obj['literal']
            else:
                return obj

        def midnight(dt: datetime.datetime) -> datetime.datetime:
            return dt + datetime.timedelta(hours=23, minutes=59, seconds=59)

        def handle_date_without_time(operator_: str, dt: datetime.datetime) -> Union[str, pd.Series]:
            '''
            Handle the special case where a date is passed as a filter without the time component.
            Eg. created == '01-04-2021' or updated > '06-05-2021'
            '''
            if operator_ == 'eq':
                # field greater than 00:00:00 AND less than or equal to 23:59:59 on value date
                return operator.and_(
                    operator.ge(df[column], dt),
                    operator.le(df[column], midnight(dt)),
                )
            elif operator_ == 'lt':
                # field less than 00:00:00 on value date
                return dt
            elif operator_ == 'gt':
                # field greater than 23:59:59 on value date
                return midnight(dt)
            elif operator_ == 'gte':
                # field greater than or equal to 00:00:00 on value date
                return dt
            elif operator_ == 'lte':
                # field less than or equal to 23:59:59 on value date
                return midnight(dt)
            elif operator_ == 'neq':
                # field less than 00:00:00 on value date, OR greater than 23:59:59 on value date
                return operator.or_(
                    operator.lt(df[column], dt),
                    operator.gt(df[column], midnight(dt)),
                )
            else:
                raise FilterUnknownOperatorException(operator_)


        for operator_, conditions in filter_.items():
            field_ = conditions[0]
            value = unpack_condition(conditions[1])

            # `operator_` is the comparator, eg. =, !=, AND etc
            # `field_` is the Issue attribute to filter on
            # `value` is the value to compare against

            # Recursive filter builing for AND and OR
            if operator_ == 'and':
                return operator.and_(*[self._build_mask(df, cnd) for cnd in conditions])
            elif operator_ == 'or':
                return operator.or_(*[self._build_mask(df, cnd) for cnd in conditions])

            if field_ == 'project':
                # Support "project" keyword for Issue.project_key, just like Jira
                column = 'project_key'
            else:
                try:
                    # Else, validate field keyword is a valid Issue model attribute
                    f = get_field_by_name(Issue, conditions[0])
                    column = f.name

                    # Cast for mypy as istype uses @functools.lru_cache
                    typ = cast(Hashable, f.type)

                except ValueError:
                    # A ValueError is raised by `get_field_by_name`, when the supplied field doesn't
                    # exist on the Issue model. Validate if the field is a user-defined customfield.
                    if f'extended.{conditions[0]}' in df:
                        column = f'extended.{conditions[0]}'
                        typ = str
                    else:
                        raise FilterUnknownFieldException(conditions[0])

                if istype(typ, int):
                    # Coerce supplied strings to int if more appropriate
                    value = int(value)

                elif istype(typ, (datetime.datetime, datetime.date)):
                    # Timezone adjust for query datetimes
                    # Dates are stored in UTC in the Jira DataFrame, but will be passed as the user's local
                    # timezone on the CLI. Alternatively users can pass a specific timezone via --tz.
                    dt = arrow.get(value).replace(tzinfo=self.tz).datetime

                    if (dt.hour, dt.minute, dt.second) == (0, 0, 0):
                        value = handle_date_without_time(operator_, dt)
                        if isinstance(value, pd.Series):
                            return value
                    else:
                        value = dt


            if operator_ == 'eq':
                return operator.eq(df[column], value)
            elif operator_ == 'lt':
                return operator.lt(df[column], value)
            elif operator_ == 'gt':
                return operator.gt(df[column], value)
            elif operator_ == 'gte':
                return operator.ge(df[column], value)
            elif operator_ == 'lte':
                return operator.le(df[column], value)
            elif operator_ == 'neq':
                return operator.ne(df[column], value)

            elif operator_ == 'like':
                return df[column].str.contains(value)

            elif operator_ in ('in', 'nin'):
                if not isinstance(value, list):
                    value = [value]

                # Probably correct solution here is to use Series.isin:
                #   df[column].isin(value)
                # However, currently that is broken:
                #   https://github.com/pandas-dev/pandas/issues/20883
                # Alternative approach triggers a Numpy warning, and may fail at some point in the future:
                #   https://stackoverflow.com/a/46721064/425050
                with warnings.catch_warnings():
                    warnings.simplefilter(action='ignore', category=FutureWarning)

                    # IN or NOT IN
                    if operator_ == 'in':
                        in_masks = [df[column].apply(lambda x, y=item: str(y) in x) for item in value]
                        logical_operator = operator.or_
                    else:
                        in_masks = [df[column].apply(lambda x, y=item: str(y) not in x) for item in value]
                        logical_operator = operator.and_

                # Combine multiple in-list masks with a logical OR
                if len(in_masks) > 1:
                    mask = in_masks.pop()
                    while True:
                        try:
                            mask = logical_operator(mask, in_masks.pop())
                        except IndexError:
                            break
                    return mask
                else:
                    return in_masks[0]

            else:
                raise FilterUnknownOperatorException(operator_)
