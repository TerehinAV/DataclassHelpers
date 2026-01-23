"""
Alias usage example
"""
from dataclasses import dataclass, field

from descriptors import IntStringDescriptor
from mixins import ImportJsonMixin, ExportJsonMixin


@dataclass
class Model(ImportJsonMixin, ExportJsonMixin):
    """ Some model """
    foo: str = field(default=IntStringDescriptor())
    a_foo: str = field(default=IntStringDescriptor(default_factory=lambda: None, alias="@foo"))

    def __init__(self, **kwargs):
        ImportJsonMixin.__init__(self, **kwargs)


if __name__ == "__main__":
    data = {
        "foo": "101",
    }

    model = Model(**data)
    print(f"input: {data}")
    print(model)

    data_with_alias = {
        "foo": "103",
        "@foo": "102",
    }

    model_with_alias = Model(**data_with_alias)
    print(f"input: {data_with_alias}")
    print(model_with_alias)
    print(model_with_alias.to_json())
    print(model_with_alias.to_json(use_alias=True))
