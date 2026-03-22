from datetime import date, timedelta

import holidays


def _get_canadian_holidays(year: int, province: str = "ON") -> set[date]:
    """Return the set of Canadian statutory holidays for a given year and province."""
    ca_holidays = holidays.Canada(subdiv=province, years=year)
    return set(ca_holidays.keys())


def is_business_day(d: date, province: str = "ON") -> bool:
    """Return True if d is a Canadian business day (not weekend, not holiday)."""
    if d.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    holiday_dates = _get_canadian_holidays(d.year, province)
    return d not in holiday_dates


def add_business_days(start: date, n: int, province: str = "ON") -> date:
    """Return the date that is n business days after start (exclusive of start)."""
    current = start
    added = 0
    while added < n:
        current += timedelta(days=1)
        if is_business_day(current, province):
            added += 1
    return current


def business_days_between(start: date, end: date, province: str = "ON") -> int:
    """Count business days between start (exclusive) and end (inclusive)."""
    count = 0
    current = start
    while current < end:
        current += timedelta(days=1)
        if is_business_day(current, province):
            count += 1
    return count


def deadline_breached(
    transaction_date: date, filing_date: date, max_business_days: int = 5, province: str = "ON"
) -> bool:
    """
    Return True if the filing_date exceeds the allowed business day deadline
    from transaction_date.
    """
    allowed_deadline = add_business_days(transaction_date, max_business_days, province)
    return filing_date > allowed_deadline
