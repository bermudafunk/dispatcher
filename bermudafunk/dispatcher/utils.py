import datetime

from dateutil import tz
from dateutil.relativedelta import relativedelta


def calc_next_hour(now=None):
    if not isinstance(now, datetime.datetime):
        now = datetime.datetime.now(tz=tz.UTC)
    else:
        now = now.astimezone(tz=tz.UTC)
    delta = relativedelta(hours=1, minute=0, second=0, microsecond=0)

    next_hour = now + delta

    if next_hour - now > datetime.timedelta(hours=1):
        next_hour -= datetime.timedelta(hours=1)

    return next_hour
