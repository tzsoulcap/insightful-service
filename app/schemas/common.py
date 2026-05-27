from datetime import datetime, timedelta, timezone
from typing import Annotated

from pydantic import PlainSerializer

_TZ7 = timezone(timedelta(hours=7))


def _to_tz7(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_TZ7)


# Use this type for all datetime fields on *response* schemas.
# Serializes to UTC+7 when outputting JSON; does not affect stored values.
DatetimeTZ7 = Annotated[
    datetime,
    PlainSerializer(_to_tz7, return_type=datetime, when_used="json"),
]
