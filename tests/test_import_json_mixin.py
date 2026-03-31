from dataclasses import dataclass, field
from typing import Any

import pytest

from descriptors import (
    DateTimeDescriptor,
    IntStringDescriptor,
    MapObjectDescriptor,
    ObjectListDescriptor,
)
from mixins import ImportJsonMixin, MissingRequiredFieldsError


@dataclass
class AliasModel(ImportJsonMixin):
    foo: Any = field(default=IntStringDescriptor())
    a_foo: Any = field(
        default=IntStringDescriptor(default_factory=lambda: None, alias="@foo")
    )

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class CalendarDayImport(ImportJsonMixin):
    current_day: Any = field(default=DateTimeDescriptor())
    caption: str = ""

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class CalendarImport(ImportJsonMixin):
    days: Any = field(default=ObjectListDescriptor(CalendarDayImport))
    day_map: Any = field(default=MapObjectDescriptor(CalendarDayImport))

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class RequiredModel(ImportJsonMixin):
    required_name: str
    optional_name: str = "ok"

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class AliasObjectListModel(ImportJsonMixin):
    values: Any = field(
        default=ObjectListDescriptor(CalendarDayImport, alias="@values")
    )

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class DescriptorMissingSemanticsModel(ImportJsonMixin):
    missing_required: Any = field(default=IntStringDescriptor())
    explicit_none_default: Any = field(default=IntStringDescriptor(default=None))
    explicit_none_factory: Any = field(
        default=IntStringDescriptor(default_factory=lambda: None)
    )

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


def test_required_field_validation_raises_on_missing_field() -> None:
    error: Any = None
    try:
        RequiredModel(optional_name="present")
    except MissingRequiredFieldsError as exc:
        error = exc

    assert error is not None
    assert "required_name" in str(error)


def test_alias_import_and_ignore_unexpected_keys() -> None:
    model = AliasModel(foo="103", **{"@foo": "102"}, ignored_field="ignored")

    assert model.foo == 103
    assert model.a_foo == 102
    assert not hasattr(model, "ignored_field")


def test_calendar_style_nested_object_list_and_map_import() -> None:
    payload = {
        "days": [
            {"current_day": "2024-01-01T10:00:00", "caption": "first"},
            {"current_day": "2024-01-02T10:00:00", "caption": "second"},
        ],
        "day_map": {
            "a": {"current_day": "2024-01-03T10:00:00", "caption": "mapped"},
        },
    }

    model = CalendarImport(**payload)

    assert len(model.days) == 2
    assert model.days[0].caption == "first"
    assert model.days[1].current_day.day == 2
    assert model.day_map["a"].caption == "mapped"


def test_current_import_semantics_for_object_descriptor_alias_key_only() -> None:
    with pytest.raises(MissingRequiredFieldsError) as exc_info:
        AliasObjectListModel(**{"@values": [{"caption": "x"}]})

    assert "current_day" in str(exc_info.value)


def test_descriptor_backed_required_missing_field_raises_on_init() -> None:
    with pytest.raises(MissingRequiredFieldsError) as exc_info:
        DescriptorMissingSemanticsModel()

    assert "missing_required" in str(exc_info.value)


def test_descriptor_default_none_and_factory_none_are_valid_defaults() -> None:
    model = DescriptorMissingSemanticsModel(missing_required="11")

    assert model.missing_required == 11
    assert model.explicit_none_default is None
    assert model.explicit_none_factory is None


def test_descriptor_explicit_none_input_is_not_treated_as_missing() -> None:
    model = DescriptorMissingSemanticsModel(
        missing_required=1,
        explicit_none_default=None,
        explicit_none_factory=None,
    )

    assert model.missing_required == 1
    assert model.explicit_none_default is None
    assert model.explicit_none_factory is None
