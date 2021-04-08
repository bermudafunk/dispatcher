import datetime

from croniter import croniter
from dateutil import tz

_next_hour_cron = croniter('0 * * * *')


def calc_next_hour(now=None):
    if not isinstance(now, datetime.datetime):
        now = datetime.datetime.now(tz=tz.UTC)
    else:
        now = now.astimezone(tz=tz.UTC)
    return _next_hour_cron.get_next(datetime.datetime, start_time=now)
