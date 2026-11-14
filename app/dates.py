"""Parse explicit dates without guessing a missing year or day."""
from datetime import datetime, timezone


def explicit_date(value):
    if not value:
        return None
    value = value.strip()
    try:
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        stamp = None
        for fmt in ('%d %b %Y', '%d %B %Y', '%B %d, %Y', '%b %d, %Y', '%Y/%m/%d'):
            try:
                stamp = datetime.strptime(value, fmt)
                break
            except ValueError:
                continue
        if stamp is None:
            return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)
