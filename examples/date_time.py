"""
Datetime field descriptor usage example
"""
from dataclasses import dataclass, field
from datetime import datetime

from descriptors import DateTimeDescriptor
from mixins import ImportJsonMixin, ExportJsonMixin


@dataclass
class DateTimeModel(ImportJsonMixin, ExportJsonMixin):
    """ Datetime field descriptor usage example """
    current_date: datetime = field(default=DateTimeDescriptor(dt_format="%Y-%m-%d"))

    def __init__(self, **kwargs):
        """
        Initialize a ImportJsonMixin instance from keyword arguments.
        """
        ImportJsonMixin.__init__(self, **kwargs)


if __name__ == "__main__":
    data = {
        "current_date": "2022-01-01 00:00"
    }
    model = DateTimeModel(**data)
    print(f"input: {data}")
    print(model.to_json())
    print(model.to_json(stringify=True))