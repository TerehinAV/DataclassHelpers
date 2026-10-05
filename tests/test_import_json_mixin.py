from collections import UserDict
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pytest

from descriptors import (
    DateTimeDescriptor,
    IntStringDescriptor,
    JsonDumpObjectDescriptor,
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
class RequiredModel(ImportJsonMixin):
    required_name: str
    optional_name: str = "ok"

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
class DeepNestedModel(ImportJsonMixin):
    val: Any = field(default=IntStringDescriptor())

    def __init__(self, **kwargs):
        ImportJsonMixin.__init__(self, **kwargs)

@dataclass
class MidModel(ImportJsonMixin):
    deep: Any = field(default=SingleObjectDescriptor(DeepNestedModel))

    def __init__(self, **kwargs):
        ImportJsonMixin.__init__(self, **kwargs)

@dataclass
class TopModel(ImportJsonMixin):
    mid: Any = field(default=SingleObjectDescriptor(MidModel))

    def __init__(self, **kwargs):
        ImportJsonMixin.__init__(self, **kwargs)

def test_deep_flat_mapping() -> None:
    # Verify recursive flat mapping through multiple nested models.
    model = TopModel(val="42")
    assert model.mid.deep.val == 42


def test_deep_explicit_object_key_selects_parent_branch_for_flat_mapping() -> None:
    # "deep" is an explicit object key of the active mid branch, so its dict
    # value is exempt from shape detection and selects that parent branch.
    model = TopModel(deep={"val": "7"})

    assert model.mid.deep.val == 7

@dataclass
class MultiFieldNested(ImportJsonMixin):
    a: Any = field(default=IntStringDescriptor())
    b: Any = field(default=IntStringDescriptor())

    def __init__(self, **kwargs):
        ImportJsonMixin.__init__(self, **kwargs)

@dataclass
class MultiNestedRoot(ImportJsonMixin):
    nested: Any = field(default=SingleObjectDescriptor(MultiFieldNested))

    def __init__(self, **kwargs):
        ImportJsonMixin.__init__(self, **kwargs)

def test_flat_mapping_partial_data_fails() -> None:
    # Partial flat data cannot initialize a required nested model.
    with pytest.raises(MissingRequiredFieldsError):
        MultiNestedRoot(a="1")  # b is missing

def test_flat_mapping_precedence() -> None:
    # An explicit nested value takes precedence over flat fields.
    data = {
        "nested": {"a": "1", "b": "2"},
        "a": "3",
        "b": "4"
    }
    model = MultiNestedRoot(**data)
    assert model.nested.a == 1
    assert model.nested.b == 2

@dataclass
class OptionalNestedModel(ImportJsonMixin):
    opt_nested: Any = field(
        default=SingleObjectDescriptor(MultiFieldNested, default_factory=lambda: None)
    )

    def __init__(self, **kwargs):
        ImportJsonMixin.__init__(self, **kwargs)

def test_optional_nested_no_data() -> None:
    # The descriptor factory is used when no nested data is present.
    model = OptionalNestedModel()
    assert model.opt_nested is None

def test_optional_nested_flat_data() -> None:
    # Complete flat data overrides the descriptor's default factory.
    model = OptionalNestedModel(a="10", b="20")
    assert model.opt_nested.a == 10
    assert model.opt_nested.b == 20


@dataclass
class DuplicateNamePerson(ImportJsonMixin):
    name: str = "person"
    city: str = "unknown"

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class DuplicateNameRoot(ImportJsonMixin):
    name: str = "root"
    person: Any = field(
        default=SingleObjectDescriptor(DuplicateNamePerson, default=None)
    )

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


def test_flat_import_does_not_reuse_ambiguous_root_key() -> None:
    model = DuplicateNameRoot(name="order-1")

    assert model.name == "order-1"
    assert model.person is None


def test_any_duplicate_field_name_disables_flat_import_for_model() -> None:
    model = DuplicateNameRoot(city="Moscow")

    assert model.person is None


@dataclass
class StructuredPayloadRoot(ImportJsonMixin):
    metadata: Any = field(default_factory=dict)
    nested: Any = field(
        default=SingleObjectDescriptor(MultiFieldNested, default=None)
    )

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


def test_nested_structure_disables_implicit_flat_mapping() -> None:
    model = StructuredPayloadRoot(
        metadata={"source": "api"},
        a="10",
        b="20",
    )

    assert model.metadata == {"source": "api"}
    assert model.nested is None


def test_mapping_object_disables_implicit_flat_mapping() -> None:
    metadata = UserDict({"source": "api"})

    model = StructuredPayloadRoot(
        metadata=metadata,
        a="10",
        b="20",
    )

    assert model.metadata is metadata
    assert model.nested is None


def test_list_of_mapping_objects_disables_implicit_flat_mapping() -> None:
    metadata = [UserDict({"source": "api"})]

    model = StructuredPayloadRoot(
        metadata=metadata,
        a="10",
        b="20",
    )

    assert model.metadata is metadata
    assert model.nested is None


@dataclass
class CalendarDayImport(ImportJsonMixin):
    current_day: Any = field(default=DateTimeDescriptor())
    caption: str = ""

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class CalendarDayRoot(ImportJsonMixin):
    day: Any = field(
        default=SingleObjectDescriptor(CalendarDayImport, default=None)
    )

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


def test_date_leaf_allows_flat_mapping() -> None:
    current_day = date(2026, 9, 1)

    model = CalendarDayRoot(current_day=current_day, caption="Example")

    assert model.day.current_day == current_day
    assert model.day.caption == "Example"


@dataclass
class CalendarImport(ImportJsonMixin):
    days: Any = field(default=ObjectListDescriptor(CalendarDayImport))
    day_map: Any = field(default=MapObjectDescriptor(CalendarDayImport))

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
class DefaultAddress(ImportJsonMixin):
    street: Any = None
    city: Any = None

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class AddressWithDefaultRoot(ImportJsonMixin):
    address: Any = field(
        default=SingleObjectDescriptor(DefaultAddress, default=None)
    )

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class AddressWithFactoryRoot(ImportJsonMixin):
    address: Any = field(
        default=SingleObjectDescriptor(
            DefaultAddress,
            default_factory=lambda: DefaultAddress(street="factory"),
        )
    )

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class AddressWithoutDefaultRoot(ImportJsonMixin):
    address: Any = field(default=SingleObjectDescriptor(DefaultAddress))

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class PlainFactoryModel(ImportJsonMixin):
    name: str = "n"
    tags: Any = field(default_factory=lambda: ["tag"])

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class AllDefaultNested(ImportJsonMixin):
    first: Any = field(default=IntStringDescriptor(default_factory=lambda: 10))
    second: Any = field(default=IntStringDescriptor(default_factory=lambda: 20))

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class AllDefaultNestedRoot(ImportJsonMixin):
    nested: Any = field(
        default=SingleObjectDescriptor(AllDefaultNested, default=None)
    )

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class MixedNested(ImportJsonMixin):
    required_value: Any = field(default=IntStringDescriptor())
    optional_value: Any = field(
        default=IntStringDescriptor(default_factory=lambda: 20)
    )

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class MixedNestedRoot(ImportJsonMixin):
    nested: Any = field(default=SingleObjectDescriptor(MixedNested, default=None))

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class LeftNested(ImportJsonMixin):
    left_value: Any = field(default=IntStringDescriptor())

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class RightNested(ImportJsonMixin):
    right_value: Any = field(default=IntStringDescriptor())

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class SiblingNestedRoot(ImportJsonMixin):
    left: Any = field(default=SingleObjectDescriptor(LeftNested, default=None))
    right: Any = field(default=SingleObjectDescriptor(RightNested, default=None))

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class AliasedNested(ImportJsonMixin):
    amount: Any = field(default=IntStringDescriptor(alias="@amount"))
    currency: str = "USD"

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class AliasedNestedRoot(ImportJsonMixin):
    nested: Any = field(default=SingleObjectDescriptor(AliasedNested, default=None))

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class JsonNestedRoot(ImportJsonMixin):
    nested: Any = field(default=JsonDumpObjectDescriptor(MultiFieldNested))

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class AliasCollisionRoot(ImportJsonMixin):
    root_value: Any = field(default=IntStringDescriptor(alias="@amount"))
    nested: Any = field(default=SingleObjectDescriptor(AliasedNested, default=None))

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class ScalarListPayloadRoot(ImportJsonMixin):
    tags: Any = field(default_factory=list)
    nested: Any = field(
        default=SingleObjectDescriptor(MultiFieldNested, default=None)
    )

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


def test_object_list_and_map_support_hierarchical_import() -> None:
    model = CalendarImport(
        days=[
            {"current_day": "2024-01-01T10:00:00", "caption": "first"},
            {"current_day": "2024-01-02T10:00:00", "caption": "second"},
        ],
        day_map={
            "a": {"current_day": "2024-01-03T10:00:00", "caption": "mapped"}
        },
    )

    assert len(model.days) == 2
    assert model.days[0].caption == "first"
    assert model.days[1].current_day.day == 2
    assert model.day_map["a"].caption == "mapped"


def test_object_list_alias_preserves_nested_validation() -> None:
    with pytest.raises(MissingRequiredFieldsError, match="current_day"):
        AliasObjectListModel(**{"@values": [{"caption": "missing date"}]})


def test_descriptor_default_is_used_without_submodel_data() -> None:
    assert AddressWithDefaultRoot().address is None


def test_unique_flat_data_overrides_descriptor_default() -> None:
    model = AddressWithDefaultRoot(street="Main")

    assert model.address.street == "Main"
    assert model.address.city is None


def test_descriptor_factory_is_used_without_submodel_data() -> None:
    model = AddressWithFactoryRoot()

    assert model.address.street == "factory"
    assert model.address.city is None


def test_unique_flat_data_overrides_descriptor_factory() -> None:
    model = AddressWithFactoryRoot(city="Moscow")

    assert model.address.street is None
    assert model.address.city == "Moscow"


def test_explicit_nested_value_overrides_default_and_flat_values() -> None:
    model = AddressWithDefaultRoot(
        address={"street": "Structured", "city": "X"},
        street="Flat",
        city="Y",
    )

    assert model.address.street == "Structured"
    assert model.address.city == "X"


def test_required_descriptor_maps_complete_unique_flat_data() -> None:
    model = AddressWithoutDefaultRoot(street="Main", city="X")

    assert model.address.street == "Main"
    assert model.address.city == "X"


def test_required_descriptor_without_flat_data_fails() -> None:
    with pytest.raises(MissingRequiredFieldsError, match="address"):
        AddressWithoutDefaultRoot(unrelated="value")


def test_required_flat_submodel_rejects_partial_data() -> None:
    with pytest.raises(MissingRequiredFieldsError, match="nested.b"):
        MultiNestedRoot(a="1")


def test_structured_submodel_rejects_partial_data() -> None:
    with pytest.raises(MissingRequiredFieldsError, match="b"):
        MultiNestedRoot(nested={"a": "1"})


def test_optional_descriptor_rejects_partial_required_flat_data() -> None:
    with pytest.raises(MissingRequiredFieldsError, match="opt_nested.b"):
        OptionalNestedModel(a="1")


def test_all_default_submodel_maps_partial_flat_data() -> None:
    model = AllDefaultNestedRoot(first="7")

    assert model.nested.first == 7
    assert model.nested.second == 20


def test_all_default_submodel_uses_descriptor_default_without_data() -> None:
    assert AllDefaultNestedRoot().nested is None


def test_mixed_submodel_maps_required_value_and_uses_field_default() -> None:
    model = MixedNestedRoot(required_value="7")

    assert model.nested.required_value == 7
    assert model.nested.optional_value == 20


def test_mixed_submodel_rejects_only_optional_flat_data() -> None:
    with pytest.raises(MissingRequiredFieldsError, match="nested.required_value"):
        MixedNestedRoot(optional_value="7")


def test_sibling_submodels_map_their_unique_flat_keys() -> None:
    model = SiblingNestedRoot(left_value="1", right_value="2")

    assert model.left.left_value == 1
    assert model.right.right_value == 2


def test_sibling_without_its_flat_keys_keeps_default() -> None:
    model = SiblingNestedRoot(left_value="1")

    assert model.left.left_value == 1
    assert model.right is None


def test_nested_alias_participates_in_flat_mapping() -> None:
    model = AliasedNestedRoot(**{"@amount": "12"})

    assert model.nested.amount == 12


def test_json_object_descriptor_supports_unique_flat_mapping() -> None:
    model = JsonNestedRoot(a="10", b="20")

    assert model.nested.a == 10
    assert model.nested.b == 20


def test_json_object_descriptor_supports_explicit_json_input() -> None:
    model = JsonNestedRoot(nested='{"a": "10", "b": "20"}')

    assert model.nested.a == 10
    assert model.nested.b == 20


def test_single_object_descriptor_accepts_explicit_model_instance() -> None:
    nested = MultiFieldNested(a="10", b="20")
    model = MultiNestedRoot(nested=nested)

    assert model.nested is nested


def test_ambiguous_alias_does_not_trigger_nested_flat_mapping() -> None:
    model = AliasCollisionRoot(**{"@amount": "12"})

    assert model.root_value == 12
    assert model.nested is None


def test_any_duplicate_alias_disables_flat_import_for_model() -> None:
    model = AliasCollisionRoot(root_value="1", currency="EUR")

    assert model.root_value == 1
    assert model.nested is None


@dataclass
class SummaryDetails(ImportJsonMixin):
    title: str
    note: str = ""

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class HierarchyDetails(ImportJsonMixin):
    ancestor_key: Any = None
    is_group: Any = None

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class MetricDetails(ImportJsonMixin):
    elapsed: int = 0
    total: int = 0

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class ContextSummaryDetails(ImportJsonMixin):
    title: str = "unknown"

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class OptionalContext(ImportJsonMixin):
    summary: Any = field(
        default=SingleObjectDescriptor(
            ContextSummaryDetails,
            default_factory=ContextSummaryDetails,
        )
    )

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class Aggregate(ImportJsonMixin):
    key: str
    metrics: Any = field(default=SingleObjectDescriptor(MetricDetails))
    summary: Any = field(default=SingleObjectDescriptor(SummaryDetails))
    hierarchy: Any = field(default=SingleObjectDescriptor(HierarchyDetails))
    context: Any = field(
        default=SingleObjectDescriptor(
            OptionalContext,
            default_factory=lambda: None,
        )
    )

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class AliasedAggregate(ImportJsonMixin):
    key: str
    metrics: Any = field(default=SingleObjectDescriptor(MetricDetails))
    summary: Any = field(default=SingleObjectDescriptor(SummaryDetails))
    hierarchy: Any = field(default=SingleObjectDescriptor(HierarchyDetails))
    context: Any = field(
        default=SingleObjectDescriptor(
            OptionalContext,
            default_factory=lambda: None,
            alias="@context",
        )
    )

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


def aggregate_payload() -> dict[str, Any]:
    return {
        "key": "example",
        "ancestor_key": None,
        "is_group": None,
        "title": "Example title",
        "note": "",
        "elapsed": 0,
        "total": 0,
    }


@dataclass
class ObjectListPlusFlatRoot(ImportJsonMixin):
    entries: Any = field(default=ObjectListDescriptor(CalendarDayImport))
    details: Any = field(
        default=SingleObjectDescriptor(HierarchyDetails, default=None)
    )

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class ObjectMapPlusFlatRoot(ImportJsonMixin):
    entry_map: Any = field(default=MapObjectDescriptor(CalendarDayImport))
    details: Any = field(
        default=SingleObjectDescriptor(HierarchyDetails, default=None)
    )

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class HybridSideDetails(ImportJsonMixin):
    title: str

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class HybridDeepTop(ImportJsonMixin):
    mid: Any = field(default=SingleObjectDescriptor(MidModel))
    side: Any = field(default=SingleObjectDescriptor(HybridSideDetails))

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class AliasedHybridDeepTop(ImportJsonMixin):
    mid: Any = field(default=SingleObjectDescriptor(MidModel))
    side: Any = field(
        default=SingleObjectDescriptor(HybridSideDetails, alias="@side")
    )

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


def test_explicit_object_dict_with_flat_siblings_maps_remaining_branches() -> None:
    explicit_context = {"summary": {"title": "Packed title"}}

    model = Aggregate(**aggregate_payload(), context=explicit_context)

    assert model.context.summary.title == "Packed title"
    assert model.summary.title == "Example title"
    assert model.summary.note == ""
    assert model.hierarchy.ancestor_key is None
    assert model.metrics.elapsed == 0
    assert model.metrics.total == 0


def test_ready_model_under_explicit_key_with_flat_siblings_maps_remaining_branches() -> None:
    ready_context = OptionalContext(
        summary=ContextSummaryDetails(title="Ready title")
    )

    model = Aggregate(**aggregate_payload(), context=ready_context)

    assert model.context is ready_context
    assert model.summary.title == "Example title"
    assert model.hierarchy.ancestor_key is None
    assert model.metrics.total == 0


def test_explicit_object_list_with_flat_siblings_maps_remaining_branches() -> None:
    model = ObjectListPlusFlatRoot(
        entries=[{"current_day": "2026-01-02T10:00:00", "caption": "first"}],
        ancestor_key="entry-anc",
        is_group=True,
    )

    assert model.entries[0].caption == "first"
    assert model.entries[0].current_day.day == 2
    assert model.details.ancestor_key == "entry-anc"
    assert model.details.is_group is True


def test_explicit_object_map_with_flat_siblings_maps_remaining_branches() -> None:
    model = ObjectMapPlusFlatRoot(
        entry_map={
            "first": {"current_day": "2026-01-03T10:00:00", "caption": "mapped"}
        },
        ancestor_key="map-anc",
        is_group=False,
    )

    assert model.entry_map["first"].caption == "mapped"
    assert model.entry_map["first"].current_day.day == 3
    assert model.details.ancestor_key == "map-anc"
    assert model.details.is_group is False


def test_explicit_optional_branch_is_excluded_from_flat_schema() -> None:
    model = Aggregate(**aggregate_payload(), context=None)

    assert model.summary.title == "Example title"
    assert model.hierarchy.ancestor_key is None
    assert model.metrics.total == 0
    assert model.context is None


def test_explicit_alias_object_dict_with_flat_siblings_maps_remaining_branches() -> None:
    explicit_context = {"summary": {"title": "Packed alias title"}}

    model = AliasedAggregate(
        **aggregate_payload(),
        **{"@context": explicit_context},
    )

    assert model.context.summary.title == "Packed alias title"
    assert model.summary.title == "Example title"
    assert model.hierarchy.is_group is None
    assert model.metrics.total == 0


def test_explicit_optional_alias_is_excluded_from_flat_schema() -> None:
    model = AliasedAggregate(
        **aggregate_payload(),
        **{"@context": None},
    )

    assert model.summary.title == "Example title"
    assert model.hierarchy.ancestor_key is None
    assert model.metrics.elapsed == 0
    assert model.context is None


def test_implicit_conflicting_optional_branch_still_disables_flat_import() -> None:
    with pytest.raises(MissingRequiredFieldsError, match="metrics"):
        Aggregate(**aggregate_payload())


def test_unknown_mapping_beside_explicit_branch_still_blocks_flat_mapping() -> None:
    with pytest.raises(MissingRequiredFieldsError, match="metrics"):
        Aggregate(
            **aggregate_payload(),
            context={"summary": {"title": "Packed title"}},
            extra={"unknown": "value"},
        )


def test_plain_mapping_beside_explicit_branch_still_blocks_flat_mapping() -> None:
    with pytest.raises(MissingRequiredFieldsError, match="metrics"):
        Aggregate(
            **aggregate_payload(),
            context={"summary": {"title": "Packed title"}},
            extra=UserDict({"unknown": "value"}),
        )


def test_stray_mapping_descendant_outside_active_traversal_still_blocks() -> None:
    # "note" belongs to the pruned summary subtree; a Mapping under it is not
    # an excluded explicit object key, so it stays conservative and blocks.
    payload = aggregate_payload()
    payload["note"] = {"stray": "mapping"}

    with pytest.raises(MissingRequiredFieldsError, match="metrics"):
        Aggregate(**payload, summary={"title": "Packed title"}, context=None)


def test_explicit_object_sibling_allows_flat_mapping_through_two_implicit_levels() -> None:
    # The root "side" branch is explicit, so its key must not be forwarded:
    # the residual flat payload reaches Deep through the implicitly selected
    # mid and deep object levels.
    model = HybridDeepTop(val="42", side={"title": "packed"})

    assert model.mid.deep.val == 42
    assert model.side.title == "packed"


def test_explicit_alias_object_sibling_allows_flat_mapping_through_two_implicit_levels() -> None:
    model = AliasedHybridDeepTop(val="42", **{"@side": {"title": "aliased"}})

    assert model.mid.deep.val == 42
    assert model.side.title == "aliased"


def test_list_of_scalars_does_not_disable_flat_mapping() -> None:
    model = ScalarListPayloadRoot(tags=["one", "two"], a="10", b="20")

    assert model.tags == ["one", "two"]
    assert model.nested.a == 10
    assert model.nested.b == 20


def test_list_of_date_leaves_does_not_disable_flat_mapping() -> None:
    days = [date(2026, 9, 1), date(2026, 9, 30)]

    model = ScalarListPayloadRoot(tags=days, a="10", b="20")

    assert model.tags == days
    assert model.nested.a == 10
    assert model.nested.b == 20


def test_json_dump_string_remains_scalar_for_flat_detection() -> None:
    model = StructuredPayloadRoot(
        metadata='{"source": "api"}',
        a="10",
        b="20",
    )

    assert model.metadata == '{"source": "api"}'
    assert model.nested.a == 10
    assert model.nested.b == 20


def test_nested_scalar_list_disables_implicit_flat_mapping() -> None:
    model = ScalarListPayloadRoot(
        tags=[["nested"]],
        a="10",
        b="20",
    )

    assert model.tags == [["nested"]]
    assert model.nested is None


def test_list_of_objects_disables_implicit_flat_mapping() -> None:
    model = StructuredPayloadRoot(
        metadata=[{"source": "api"}],
        a="10",
        b="20",
    )

    assert model.nested is None


def test_ready_submodel_disables_implicit_flat_mapping() -> None:
    ready_model = MultiFieldNested(a="1", b="2")

    model = StructuredPayloadRoot(
        metadata=ready_model,
        a="10",
        b="20",
    )

    assert model.metadata is ready_model
    assert model.nested is None


def test_list_of_ready_submodels_disables_implicit_flat_mapping() -> None:
    ready_model = MultiFieldNested(a="1", b="2")

    model = StructuredPayloadRoot(
        metadata=[ready_model],
        a="10",
        b="20",
    )

    assert model.metadata == [ready_model]
    assert model.nested is None


def test_plain_default_factory_field_is_filled_when_key_is_absent() -> None:
    model = PlainFactoryModel(name="x")

    assert model.name == "x"
    assert model.tags == ["tag"]


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
    assert isinstance(masked, dict)

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
        {"custom": "value", "password": "keep"},
        secret_keys=["custom"],
    )

    assert masked == {"custom": "********", "password": "keep"}
