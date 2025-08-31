"""
Calendar example
"""
import calendar
from typing import List
from dataclasses import dataclass, field
from datetime import datetime, date
from descriptors import DateTimeDescriptor, COMMON_DATE_TIME_FORMAT, ObjectListDescriptor
from mixins import ImportJsonMixin


@dataclass
class CalendarDay(ImportJsonMixin):
    """
    Represents a single day in a calendar.

    Attributes:
        current_day: The date and time of this calendar day
        caption: A text caption for this day
    """
    current_day: datetime = field(default=DateTimeDescriptor())
    caption: str = field(default="")

    @property
    def day(self) -> int:
        """
        Get the day of the month.

        Returns:
            The day of the month as an integer
        """
        return self.current_day.day

    @property
    def month(self) -> int:
        """
        Get the month.

        Returns:
            The month as an integer (1-12)
        """
        return self.current_day.month

    @property
    def year(self) -> int:
        """
        Get the year.

        Returns:
            The year as an integer
        """
        return self.current_day.year

    def __init__(self, **kwargs):
        """
        Initialize a ImportJsonMixin instance from keyword arguments.
        """
        ImportJsonMixin.__init__(self, **kwargs)

    def to_json(self):
        """
        Convert the CalendarDay instance to a JSON-serializable dictionary.

        Returns:
            A dictionary with the current_day formatted as a string and the caption
        """
        return {
            "current_day": self.current_day.strftime(COMMON_DATE_TIME_FORMAT),
            "caption": self.caption,
        }


@dataclass
class Calendar(ImportJsonMixin):
    """
    Represents a calendar with a current date and a list of calendar days.

    Attributes:
        current_date: The current date and time of the calendar
        days: A list of CalendarDay objects
    """
    current_date: datetime = field(default=DateTimeDescriptor())
    days: List[CalendarDay] = field(default=ObjectListDescriptor(CalendarDay))

    def __init__(self, **kwargs):
        """
        Initialize a ImportJsonMixin instance from keyword arguments.
        """
        ImportJsonMixin.__init__(self, **kwargs)

    def to_json(self):
        """
        Convert the Calendar instance to a JSON-serializable dictionary.

        Returns:
            A dictionary with the current_date formatted as a string and a list of serialized days
        """
        return {
            "current_date": self.current_date.strftime(COMMON_DATE_TIME_FORMAT),
            "days": [calendar_day.to_json() for calendar_day in self.days],
        }


if __name__ == "__main__":
    today = date.today()
    year = today.year
    month = today.month
    num_days = calendar.monthrange(year, month)[1]
    current_month_days = [date(year, month, day) for day in range(1, num_days + 1)]

    dt_now = datetime.now()

    calendar_data = {
        "current_date": dt_now,
        "days": [
            {
                "current_day": _dt.strftime(COMMON_DATE_TIME_FORMAT),
                "caption": f"{_dt.day}",
            } for _dt in current_month_days
        ],
    }

    calendar_obj = Calendar(**calendar_data)
    print(calendar)
    print()
    calendar_dto = calendar_obj.to_json()
    print(calendar_dto)
    print()
    print(Calendar(**calendar_dto))
