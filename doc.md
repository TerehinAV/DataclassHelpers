# `ImportJsonMixin` Documentation

`ImportJsonMixin` initializes dataclass models from JSON-compatible keyword arguments. It supports field aliases, ignores unknown keys, validates required values, and can populate nested dataclasses from either explicit hierarchical values or an unambiguous flat payload.

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

When no explicit nested value is present, the mixin examines the complete payload without consulting descriptor implementations.

Flat JSON values are:

- `null` / `None`;
- booleans;
- numbers;
- strings;
- one-dimensional lists containing only these scalar values.

A dictionary or nested list makes the payload hierarchical and disables all implicit flat mapping. JSON dump strings are not parsed during this check and remain ordinary scalar strings.

The flat-input contract contains only JSON-compatible values. Model instances may be accepted by an object descriptor through an explicit field key, but they are not part of flat JSON input.

### 3. Global schema-uniqueness check

The mixin recursively collects every dataclass field name and descriptor alias from the root model and all nested models. Flat mapping is allowed only when every accepted key has exactly one owner in the complete hierarchy.

Any duplicate field name or alias disables flat mapping for the entire model, even when the conflicting key is absent from the current payload. Explicit hierarchical input continues to work for such schemas.

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
# order.person is None: "name" has multiple owners in the hierarchy.
```

### 4. Nested-model selection

After the payload and schema pass their checks, at least one input key must belong to the candidate nested model. The complete flat payload is then passed through the object descriptor so deeper nested models can resolve their own fields recursively.

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
