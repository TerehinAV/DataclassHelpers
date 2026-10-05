# `ImportJsonMixin` Documentation

`ImportJsonMixin` initializes dataclass models from keyword arguments. It supports field aliases, ignores unknown keys, validates required values, and can populate nested dataclasses from explicit hierarchical values, an unambiguous flat payload, or a hybrid of both: explicit object branches are exempt from flat-shape detection, so hierarchical values and flat sibling values can coexist in one payload.

## Model Definition

Dataclass subclasses must delegate initialization to the mixin:

```python
@dataclass
class User(ImportJsonMixin):
    name: str
    user_id: Any = field(default=IntStringDescriptor(alias="ID"))

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)
```

Only declared fields and aliases are imported. Other keys are ignored. When both a field name and its alias are present, the alias value wins.

## Nested Input Resolution

For each field backed by an `ObjectFieldDescriptor`, input is resolved in the following order.

### 1. Explicit nested value

If the payload contains the field name or its alias, that value is assigned directly through the descriptor. Explicit input always takes precedence over matching flat keys.

```python
profile = Profile(
    address={"city": "Moscow", "street": "Arbat"},
    city="Ignored flat value",
)
```

### 2. Payload-shape check

For each branch without an explicit nested value, the mixin examines the complete payload without consulting concrete descriptor implementations.

Flat values are arbitrary leaves that are not instances of model classes mapped by object descriptors. This includes JSON primitives as well as domain scalar values accepted by ordinary fields or scalar descriptors, such as `date` and `datetime`. One-dimensional lists containing only such leaves are also flat.

A mapping, nested list, ready mapped-model instance, or list containing mappings or ready mapped-model instances makes the payload hierarchical and disables all implicit flat mapping. Model classes are discovered through the common `ObjectFieldDescriptor` contract rather than concrete descriptor implementations.

The shape rules apply only to keys outside explicitly supplied object branches. A value under an object field name or alias present in the payload has already selected hierarchical import, so it is never inspected — an explicit dict, ready mapped model, object list, or object map can coexist with flat sibling values that the remaining active branches consume implicitly. The exemption holds only within active schema branches: a mapping under any other key, including a stray key owned by a pruned subtree, still marks the payload hierarchical.

Ready models may still be supplied through an explicit object field or alias, where they are skipped by shape detection. JSON dump strings are not parsed during shape detection and remain ordinary scalar strings.

```python
profile = Profile(
    address={"city": "Moscow", "street": "Arbat"},
    user_name="bob",
)
# address is imported hierarchically while user_name stays a flat leaf.
```

### 3. Global schema-uniqueness check

The mixin recursively collects every dataclass field name and descriptor alias from the root model and nested branches that remain eligible for implicit flat mapping. When an object field is explicitly supplied by field name or alias, its descendants are excluded from the ownership graph because that branch has already selected hierarchical import. Ownership collection and shape exclusion share this single pruned traversal: the present field name or alias of an explicit object branch is recorded as an excluded key at the same moment its subtree is pruned.

Flat mapping is allowed only when every accepted key in the remaining active graph has exactly one owner. Any duplicate field name or alias in that graph disables implicit flat mapping, even when the conflicting key is absent from the current payload. Explicit hierarchical input continues to work for ambiguous branches.

```python
@dataclass
class Person(ImportJsonMixin):
    name: str = "unknown"

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class Order(ImportJsonMixin):
    name: str = "order"
    person: Any = field(default=SingleObjectDescriptor(Person, default=None))

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


order = Order(name="order-1")
# order.person is None: "name" has multiple owners in active branches.

# Supplying person explicitly removes Person descendants from flat ownership.
explicit_order = Order(name="order-1", person=None)
```

### 4. Nested-model selection

After the payload and schema pass their checks, at least one input key must belong to the candidate nested model. The remaining flat payload — without the current level's explicitly supplied object keys — is then passed through the object descriptor so deeper nested models can resolve their own fields recursively.

```python
@dataclass
class Address(ImportJsonMixin):
    city: str
    street: str

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class Profile(ImportJsonMixin):
    user_name: str
    address: Any = field(default=SingleObjectDescriptor(Address))

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


profile = Profile(user_name="bob", city="Moscow", street="Arbat")
# profile.address.city == "Moscow"
```

## Defaults and Partial Flat Data

An object descriptor's `default` or `default_factory` is used when its explicit key is absent and no unambiguous flat key selects its model.

Once flat data selects a nested model, all required fields in that hierarchy are validated recursively. Missing required fields raise `MissingRequiredFieldsError`; defaults declared by optional nested fields still apply.

```python
@dataclass
class Coordinates(ImportJsonMixin):
    latitude: Any = field(default=FloatStringDescriptor())
    longitude: Any = field(default=FloatStringDescriptor(default=0.0))

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


@dataclass
class Location(ImportJsonMixin):
    coordinates: Any = field(
        default=SingleObjectDescriptor(Coordinates, default=None)
    )

    def __init__(self, **kwargs: Any) -> None:
        ImportJsonMixin.__init__(self, **kwargs)


# latitude selects Coordinates; longitude uses its field default.
location = Location(latitude="55.75")
# location.coordinates.longitude == 0.0
```

## Required-Field Errors and Secret Masking

A field is required when it has no usable `default` or `default_factory`. Required object fields may be satisfied by unambiguous flat data. Otherwise `MissingRequiredFieldsError` is raised.

Validation errors include the input payload for diagnostics. Values under secret-like keys such as `password`, `token`, and `api_key` are masked before the payload is added to the exception message.
