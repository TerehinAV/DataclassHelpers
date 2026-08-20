from dataclasses import dataclass, field
from typing import Any

import pytest

from descriptors import (
    DateTimeDescriptor,
    IntStringDescriptor,
    MapObjectDescriptor,
    ObjectListDescriptor,
    SingleObjectDescriptor,
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


@dataclass
class NestedLeafImport(ImportJsonMixin):
    leaf_value: Any = field(default=IntStringDescriptor())

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class NestedMiddleImport(ImportJsonMixin):
    nested_leaf: Any = field(
        default=SingleObjectDescriptor(NestedLeafImport)
    )

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class NestedRootImport(ImportJsonMixin):
    nested_middle: Any = field(
        default=SingleObjectDescriptor(NestedMiddleImport)
    )
    root_name: str = "root"

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


def test_single_object_descriptor_supports_nested_structured_input() -> None:
    model = NestedRootImport(
        nested_middle={"nested_leaf": {"leaf_value": "12"}},
        root_name="structured",
    )

    assert model.root_name == "structured"
    assert model.nested_middle.nested_leaf.leaf_value == 12


def test_single_object_descriptor_supports_flat_input_for_nested_models() -> None:
    model = NestedRootImport(leaf_value="15", root_name="flat")

    assert model.root_name == "flat"
    assert model.nested_middle.nested_leaf.leaf_value == 15


@dataclass
class FlatDefaultAddress(ImportJsonMixin):
    street: Any = field(default=None)
    city: Any = field(default=None)

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class FlatDefaultPerson(ImportJsonMixin):
    name: Any = field(default=None)

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class NestedRootWithDefault(ImportJsonMixin):
    root_name: str = "root"
    address: Any = field(
        default=SingleObjectDescriptor(FlatDefaultAddress, default=None)
    )

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class NestedRootWithFactory(ImportJsonMixin):
    root_name: str = "root"
    address: Any = field(
        default=SingleObjectDescriptor(
            FlatDefaultAddress,
            default_factory=lambda: FlatDefaultAddress(street="unknown"),
        )
    )

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class PseudoFillRoot(ImportJsonMixin):
    name: Any = field(default=None)
    person: Any = field(
        default=SingleObjectDescriptor(FlatDefaultPerson, default=None)
    )

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class NestedRootNoDefault(ImportJsonMixin):
    address: Any = field(default=SingleObjectDescriptor(FlatDefaultAddress))

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


def test_object_descriptor_default_none_wins_over_flat_input() -> None:
    model = NestedRootWithDefault(street="Main", root_name="x")

    assert model.root_name == "x"
    assert model.address is None


def test_object_descriptor_default_factory_used_when_key_absent() -> None:
    model = NestedRootWithFactory()

    assert model.address.street == "unknown"
    assert model.address.city is None


def test_object_descriptor_no_pseudo_fill_from_same_named_root_field() -> None:
    model = PseudoFillRoot(name="order-1")

    assert model.name == "order-1"
    assert model.person is None


def test_object_descriptor_nested_key_still_overrides_default() -> None:
    model = NestedRootWithDefault(
        address={"street": "Main", "city": "X"}, root_name="x"
    )

    assert model.address.street == "Main"
    assert model.address.city == "X"


def test_object_descriptor_without_default_still_maps_flat_input() -> None:
    model = NestedRootNoDefault(street="Main", city="X")

    assert model.address.street == "Main"
    assert model.address.city == "X"


@dataclass
class PlainFactoryModel(ImportJsonMixin):
    name: str = "n"
    tags: Any = field(default_factory=lambda: ["t"])

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


def test_plain_default_factory_field_filled_when_key_absent() -> None:
    model = PlainFactoryModel(name="x")

    assert model.name == "x"
    assert model.tags == ["t"]


def test_has_required_fields_detects_required_fields() -> None:
    assert ImportJsonMixin.has_required_fields() is False
    assert RequiredModel.has_required_fields() is True


def test_mask_secrets_masks_matching_keys_recursively() -> None:
    data = {
        "password": "secret",
        "visible": "keep",
        "user_email": "a@b.c",
        "nested": {"api_key": "k", "ok": 1},
        "items": [{"token": "t"}, "plain"],
        "pair": ({"auth": "a"},),
        1: "non-str-key",
    }

    masked = ImportJsonMixin.mask_secrets(data)

    assert masked["password"] == "********"
    assert masked["visible"] == "keep"
    assert masked["user_email"] == "********"
    assert masked["nested"] == {"api_key": "********", "ok": 1}
    assert masked["items"][0] == {"token": "********"}
    assert masked["items"][1] == "plain"
    assert masked["pair"][0] == {"auth": "********"}
    assert masked[1] == "non-str-key"
    assert data["password"] == "secret"


def test_mask_secrets_accepts_custom_secret_keys() -> None:
    masked = ImportJsonMixin.mask_secrets(
        {"custom": "v", "password": "keep"}, secret_keys=["custom"]
    )

    assert masked == {"custom": "********", "password": "keep"}
