from dataclasses import dataclass, field
from typing import Any

from descriptors import IntStringDescriptor
from mixins import FlatExportJsonMixin


@dataclass
class FlatLeaf:
    amount: Any = field(default=IntStringDescriptor(alias="@amount"))
    title: str = ""


@dataclass
class FlatReport(FlatExportJsonMixin):
    leaf: FlatLeaf = field(default_factory=lambda: FlatLeaf(amount=1, title="one"))
    leaves: list[FlatLeaf] = field(
        default_factory=lambda: [FlatLeaf(amount=2, title="two")]
    )
    leaf_map: dict[str, FlatLeaf] = field(
        default_factory=lambda: {"x": FlatLeaf(amount=3, title="three")}
    )
    tag: Any = field(default=IntStringDescriptor(alias="@tag"))


def test_flat_export_with_prefix_alias_nested_objects_lists_and_maps() -> None:
    report = FlatReport(tag="9")

    result = report.to_json(use_prefix=True, use_alias=True)

    assert result == {
        "leaf.@amount": 1,
        "leaf.title": "one",
        "leaves[0].@amount": 2,
        "leaves[0].title": "two",
        "leaf_map.x.@amount": 3,
        "leaf_map.x.title": "three",
        "@tag": 9,
    }


def test_flat_export_default_no_prefix_current_behavior() -> None:
    report = FlatReport(tag="7")

    error: Any = None
    try:
        report.to_json()
    except AttributeError as exc:
        error = exc
    assert error is not None
