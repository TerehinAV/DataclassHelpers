"""
Dataclass based serializer
+ export and import mixins
"""
import calendar
from typing import Optional, Callable, List
from dataclasses import dataclass, fields, MISSING, is_dataclass, field
from datetime import datetime, date


class FieldDescriptor:
    pass


class MissingRequiredFieldsError(Exception):
    """Raised when required fields are missing in input data."""


@dataclass
class ImportJsonMixin:
    """
    Add support for importing a dict object with any keys,
    even if they are not expected in the current dataclass.
    Only the fields defined in the dataclass will be used.
    """

    def __init__(self, **kwargs):
        """ from dict to object """
        self.validate_required_fields(kwargs)
        sf_fields = {sf_field.name: sf_field for sf_field in fields(self)}
        for name, sf_field in sf_fields.items():
            new_value = kwargs.get(name)
            # --- НОВАЯ ЛОГИКА ---
            if isinstance(sf_field.default, FieldDescriptor) and name not in kwargs:
                # если поле управляется дескриптором и ключа нет → передаём весь словарь
                setattr(self, name, kwargs)
                continue
            # --------------------
            if new_value is None and sf_field.default_factory is not MISSING:
                setattr(self, sf_field.name, sf_field.default_factory())
                continue
            elif new_value is not None and sf_field.default_factory is not MISSING:
                setattr(self, sf_field.name, new_value)
                continue
            _new_value = new_value
            if not _new_value and sf_field.default is not MISSING and not isinstance(sf_field.default, FieldDescriptor):
                _new_value = sf_field.default
            setattr(self, name, _new_value)

    def validate_required_fields(self, input_data: Dict[str, Any]):
        """
        Validates that all required fields are present in the input data.
        Raises an exception if any required field is missing.
        """
        missing_fields = []
        for field_obj in fields(self):
            has_default = field_obj.default is not MISSING
            has_factory = field_obj.default_factory is not MISSING
            if not has_default and not has_factory:
                if field_obj.name not in input_data or input_data[field_obj.name] is None:
                    missing_fields.append(field_obj.name)

        if missing_fields:
            raise MissingRequiredFieldsError(
                f"Missing required fields with no default values: {', '.join(missing_fields)}"
            )


@dataclass
class ExportJsonMixin:
    """
    Add support of recursive exporting
    """
    def to_json(self, stringify=False):
        def recursive_to_json(obj):
            obj_type = type(obj)
            instance_type = type(self)
            if hasattr(obj, 'to_json') and not obj_type == instance_type and callable(obj.to_json):
                # Use custom to_json method
                # NOTE: to use specified export implement "to_json/0" instance method
                return obj.to_json()
            elif is_dataclass(obj):
                return {field.name: recursive_to_json(getattr(obj, field.name)) for field in fields(obj)}
            elif isinstance(obj, list):
                return [recursive_to_json(item) for item in obj]
            elif isinstance(obj, dict):
                return {key: recursive_to_json(value) for key, value in obj.items()}
            else:
                return str(obj) if stringify is True else obj
        return recursive_to_json(self)


class FlatExportJsonMixin:
    """
    Export dataclass to flat dict.
    """
    def to_json(self, stringify: bool = False) -> Dict[str, Any]:
        def flatten(obj) -> Dict[str, Any]:
            out: Dict[str, Any] = {}
            if is_dataclass(obj):
                for f in fields(obj):
                    v = getattr(obj, f.name)
                    if is_dataclass(v):
                        out.update(flatten(v))
                    else:
                        if isinstance(v, bool):
                            out[f.name] = int(v)
                        else:
                            out[f.name] = str(v) if stringify and v is not None else v
            else:
                # не ожидается для верхнего вызова, но оставим на всякий
                out["value"] = int(obj) if isinstance(obj, bool) else (str(obj) if stringify else obj)
            return out
        return flatten(self)

# ---- datetime utils ----

COMMON_DATE_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S"

DATE_FORMATS = [
    COMMON_DATE_TIME_FORMAT,
    "%Y%m%dT%H%M%S",
    "%Y%m%dT%H%M",
    "%Y.%m.%d %H:%M",
    "%Y%m%dT%H%M%S"
]


class DateTimeDescriptor:
    """
    Datetime descriptor
        it supports:
            - datetime string values, datetime objects
            - several dt formats
    """
    def __init__(self, default: Optional[datetime] = None, default_factory: Optional[Callable] = None):
        if callable(default_factory):
            self.default_factory = default_factory
        elif isinstance(default, datetime):
            self.default_factory = lambda: default
        else:
            self.default_factory = self._default_time

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return instance.__dict__.get(self._name, self.default_factory())

    def __set__(self, instance, value):
        if not value:
            value = self.default_factory()
        elif isinstance(value, str):
            value = self._parse_date_string(value, self.default_factory())
        elif not isinstance(value, datetime):
            value = self.default_factory()
        instance.__dict__[self._name] = value

    def __set_name__(self, owner, name):
        self._name = name

    @staticmethod
    def _parse_date_string(value, default):
        for date_format in DATE_FORMATS:
            try:
                return datetime.strptime(value, date_format)
            except ValueError:
                continue
        return default

    @staticmethod
    def _default_time():
        """Default time: now."""
        return datetime.now()


# --- Calendar example---


@dataclass
class CalendarDay:
    current_day: datetime = field(default=DateTimeDescriptor())
    caption: str = field(default="")

    @property
    def day(self) -> int:
        return self.current_day.day

    @property
    def month(self) -> int:
        return self.current_day.month

    @property
    def year(self) -> int:
        return self.current_day.year

    def __init__(self, **kwargs):
        sf_fields = {sf_field.name: sf_field for sf_field in fields(self)}
        for name, sf_field in sf_fields.items():
            new_value = kwargs.get(name)
            if new_value is None and sf_field.default_factory is not MISSING:
                setattr(self, sf_field.name, sf_field.default_factory())
                continue
            elif new_value is not None and sf_field.default_factory is not MISSING:
                setattr(self, sf_field.name, new_value)
                continue
            setattr(self, name, new_value or sf_field.default)

    def to_json(self):
        return {
            "current_day": self.current_day.strftime(COMMON_DATE_TIME_FORMAT),
            "caption": self.caption,
        }


@dataclass
class CalendarDaysDescriptor(FieldDescriptor):
    """
    Event time descriptor, хранит значение отдельно для каждого экземпляра.
    """
    def __init__(self, default: Optional[List[CalendarDay]] = None, default_factory: Optional[Callable] = None):
        if callable(default_factory):
            self.default_factory = default
        elif isinstance(default, list):
            self.default_factory = lambda: default
        else:
            self.default_factory = self._default_calendar_day_factory

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return instance.__dict__.get(self._name, self.default_factory())

    def __set__(self, instance, value):
        if not value or not isinstance(value, list):
            value = self.default_factory()
        else:
            value = [CalendarDay(**day_data) for day_data in value]
        instance.__dict__[self._name] = value

    def __set_name__(self, owner, name):
        self._name = name

    @staticmethod
    def _default_calendar_day_factory():
        """ Empty search filter """
        return []


@dataclass
class Calendar(ImportJsonMixin):
    current_date: datetime = field(default=DateTimeDescriptor())
    days: List[CalendarDay] = field(default=CalendarDaysDescriptor())

    def __init__(self, **kwargs):
        ImportJsonMixin.__init__(self, **kwargs)

    def to_json(self):
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
