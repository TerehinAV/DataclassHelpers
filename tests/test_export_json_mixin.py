from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from descriptors import (
    DateTimeDescriptor,
    IntStringDescriptor,
    MapObjectDescriptor,
    ObjectListDescriptor,
    SingleObjectDescriptor,
)
from mixins import ExportJsonMixin, ImportJsonMixin


@dataclass
class AliasExportModel(ImportJsonMixin):
    foo: Any = field(default=IntStringDescriptor())
    a_foo: Any = field(
        default=IntStringDescriptor(default_factory=lambda: None, alias="@foo")
    )

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)

    to_json = ExportJsonMixin.to_json


@dataclass
class DateTimeModel(ImportJsonMixin):
    current_date: Any = field(
        default=DateTimeDescriptor(
            default_factory=lambda: datetime(2001, 2, 3, 4, 5, 6),
            dt_format="%Y-%m-%d",
        )
    )

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)

    to_json = ExportJsonMixin.to_json


@dataclass
class CalendarDayExport(ImportJsonMixin):
    current_day: Any = field(default=DateTimeDescriptor())
    caption: str = ""

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)

    to_json = ExportJsonMixin.to_json


@dataclass
class CalendarExport(ImportJsonMixin):
    current_date: Any = field(default=DateTimeDescriptor())
    days: Any = field(default=ObjectListDescriptor(CalendarDayExport))
    day_map: Any = field(default=MapObjectDescriptor(CalendarDayExport))

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)

    to_json = ExportJsonMixin.to_json


@dataclass
class NestedLeafExport(ImportJsonMixin):
    leaf_value: Any = field(default=IntStringDescriptor())

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)

    to_json = ExportJsonMixin.to_json


@dataclass
class NestedMiddleExport(ImportJsonMixin):
    nested_leaf: Any = field(
        default=SingleObjectDescriptor(NestedLeafExport, optional=False)
    )

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)

    to_json = ExportJsonMixin.to_json


@dataclass
class NestedRootExport(ImportJsonMixin):
    nested_middle: Any = field(
        default=SingleObjectDescriptor(NestedMiddleExport, optional=False)
    )
    root_name: str = "root"

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)

    to_json = ExportJsonMixin.to_json


def test_export_alias_keys_when_enabled() -> None:
    model = AliasExportModel(foo="103", **{"@foo": "102"})

    assert model.to_json() == {"foo": 103, "a_foo": 102}
    assert model.to_json(use_alias=True) == {"foo": 103, "@foo": 102}


def test_datetime_import_and_export_stringify_behavior() -> None:
    model = DateTimeModel(current_date="2022-01-01 00:00")

    raw = model.to_json()
    text = model.to_json(stringify=True)
    assert isinstance(raw, dict)
    assert isinstance(text, dict)
    assert raw.get("current_date") == datetime(2001, 2, 3, 4, 5, 6)
    assert text.get("current_date") == "2001-02-03"


def test_recursive_export_with_nested_objects_lists_and_maps() -> None:
    model = CalendarExport(
        current_date="2024-02-10T09:00:00",
        days=[
            {"current_day": "2024-02-11T09:00:00", "caption": "one"},
            {"current_day": "2024-02-12T09:00:00", "caption": "two"},
        ],
        day_map={"x": {"current_day": "2024-02-13T09:00:00", "caption": "mapped"}},
    )

    result = model.to_json(stringify=True)
    assert isinstance(result, dict)
    assert result.get("current_date") == "2024-02-10T09:00:00"

    days = result.get("days")
    day_map = result.get("day_map")
    assert isinstance(days, list)
    assert isinstance(day_map, dict)
    assert days[0]["current_day"] == "2024-02-11T09:00:00"
    assert days[1]["caption"] == "two"
    assert day_map["x"]["current_day"] == "2024-02-13T09:00:00"


def test_exported_nested_object_structure_is_importable_by_same_model() -> None:
    original = NestedRootExport(
        nested_middle={"nested_leaf": {"leaf_value": "21"}},
        root_name="round-trip",
    )

    exported = original.to_json()
    restored = NestedRootExport(**exported)

    assert exported == {
        "nested_middle": {"nested_leaf": {"leaf_value": 21}},
        "root_name": "round-trip",
    }
    assert restored.to_json() == exported


def test_exported_calendar_structure_is_importable_by_same_model() -> None:
    original = CalendarExport(
        current_date="2024-02-10T09:00:00",
        days=[{"current_day": "2024-02-11T09:00:00", "caption": "one"}],
        day_map={"x": {"current_day": "2024-02-13T09:00:00", "caption": "mapped"}},
    )

    exported = original.to_json(stringify=True)
    restored = CalendarExport(**exported)

    assert restored.to_json(stringify=True) == exported
