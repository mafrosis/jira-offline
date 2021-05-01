'''
Functions for parsing SQL where-clause syntax, and filtering the Pandas DataFrame.
'''
from dataclasses import dataclass, field
import datetime
import operator
from typing import Optional
import warnings

import arrow
from dateutil.tz import gettz
import mo_parsing
from moz_sql_parser import parse as mozparse
import pandas as pd
from tzlocal import get_localzone

from jira_offline.exceptions import (FilterMozParseFailed, FilterUnknownOperatorException,
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
    _where: Optional[dict] = field(default=None, init=False)
    _tz: Optional[datetime.tzinfo] = field(default=None, init=False)


    @property
    def tz(self):
        return self._tz or get_localzone()

    @tz.setter
    def tz(self, tz: str):
        self._tz = gettz(tz)


    def set(self, sql_filter: str):
        '''
        Parse the SQL "where" clause into an object for later use

        Params:
            sql_filter:  Raw SQL-like filter string passed from CLI
        '''
        try:
            self._where = mozparse(f'select count(1) from tbl where {sql_filter}')['where']

        except mo_parsing.exceptions.ParseException as e:
            raise FilterMozParseFailed from e


    def apply(self) -> pd.DataFrame:
        '''
        Apply the current filter against the Jira DataFrame
        '''
        from jira_offline.jira import jira  # pylint: disable=cyclic-import, import-outside-toplevel

        if self._where is None:
            return jira._df  # pylint: disable=protected-access

        try:
            pandas_mask = self._build_mask(jira._df, self._where)  # pylint: disable=protected-access
        except (KeyError, IndexError, ValueError, TypeError) as e:
            raise FilterQueryParseFailed from e

        return jira._df[pandas_mask]  # pylint: disable=protected-access


    def _build_mask(self, df: pd.DataFrame, filter_: dict) -> pd.Series:
        '''
        Recurse the WHERE part of the result from `mozparse`, and build a logical Series mask to
        filter the central DataFrame

        Params:
            df:       DataFrame to use for creating masks
            filter_:  Dict object created by `mozparse` containing each part of the filter query
        '''
        def unpack_condition(obj):
            if isinstance(obj, dict):
                return obj['literal']
            else:
                return obj

        for operator_, conditions in filter_.items():
            if operator_ == 'and':
                return operator.and_(*[self._build_mask(df, cnd) for cnd in conditions])
            elif operator_ == 'or':
                return operator.or_(*[self._build_mask(df, cnd) for cnd in conditions])

            value = unpack_condition(conditions[1])

            if conditions[0] == 'project':
                column = 'project_key'
            else:
                f = get_field_by_name(Issue, conditions[0])
                column = f.name

                if istype(f.type, int):
                    # Coerce supplied strings to int if more appropriate
                    value = int(value)

                elif istype(f.type, (datetime.datetime, datetime.date)):
                    # Timezone adjust for query datetimes
                    # Dates are stored in UTC in the Jira DataFrame, but will be passed as the user's local
                    # timezone on the CLI. Alternatively users can pass a specific timezone via --tz.
                    value = arrow.get(value).replace(tzinfo=self.tz).datetime


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

            elif operator_ == 'in':
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
                    in_masks = [df[column].apply(lambda x, y=item: str(y) in x) for item in value]

                # Combine multiple in-list masks with a logical OR
                if len(in_masks) > 1:
                    return operator.or_(*in_masks)
                else:
                    return in_masks[0]

            else:
                raise FilterUnknownOperatorException(operator_)
