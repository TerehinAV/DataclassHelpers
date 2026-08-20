This repository provides a set of Python mixins and descriptors for creating dataclass-based serializers with robust import/export functionality. It enables seamless conversion between Python dataclasses and JSON-compatible dictionaries while handling complex data types and validation.

Key Features:
- ImportJsonMixin: Validates and imports dictionary data into dataclass instances with support for required field checking
- ExportJsonMixin: Recursively exports dataclass instances to JSON-serializable dictionaries
- FlatExportJsonMixin: Creates flat dictionary representations from nested dataclass structures
- Type Descriptors: Specialized descriptors for datetime, float, integer, and object handling with flexible parsing
- Object Support: Built-in support for single objects, object lists, and object maps with automatic instantiation
- Validation: Comprehensive field validation with customizable error handling

Use Cases:
- API request/response serialization
- Configuration file parsing and generation
- Data validation and transformation pipelines
- Object-relational mapping (ORM) utilities
- Structured data import/export systems

The library emphasizes type safety, flexible default values, and graceful error handling while maintaining clean, declarative dataclass definitions.

## Non-Obvious Import Scenarios

### Nested models: flat input vs. explicit defaults

For a field backed by an object descriptor (`SingleObjectDescriptor`, `JsonDumpObjectDescriptor`, `ObjectListDescriptor`, `MapObjectDescriptor`), the import result depends on the input shape:

| Input state | Result |
|---|---|
| Field key present (by name or alias) | The key's value is passed to the descriptor; a dict is unpacked into the nested model |
| Key absent, descriptor declares `default`/`default_factory` | The declared default wins — the input is **not** fed into the nested model, even when root-level keys coincide with nested model field names |
| Key absent, no default declared | The whole input dict is treated as a flat JSON object and mapped onto the nested model |

The third row is what enables flat imports: `OrderFlat(street="Main", city="Y")` produces `address=Address(street="Main", city="Y")` without nesting.

The second row resolves a conflict that would otherwise fail silently: if the default were ignored, `Order(name="order-1")` would pseudo-fill `person=Person(name="order-1")` from an unrelated same-named root field, and a submodel with required fields would raise an error naming the nested model instead of the root. A runnable demonstration is `examples/flat_import_conflict.py`.

### Required-field validation

A field without a default (including descriptor-backed fields whose factory is `raise_on_value_missed`) raises `MissingRequiredFieldsError` when its key is absent. Two nuances:

- A required object-descriptor field passes validation when its nested model can be built from flat root-level keys (see the row 3 above).
- The error message masks secret-like keys (`password`, `token`, `api_key`, …) before echoing the input data.

### Aliased keys

When a descriptor declares an `alias` and **both** the field name and the alias are present in the input, the alias value wins. Unknown keys that match no field or alias are silently ignored.

### Missing values: `None` and empty string

Most scalar descriptors treat an explicitly passed `None` — and, where a string is expected, `""` — exactly like a missing key: the default value/factory is produced instead. Consequently, passing `None` to a descriptor declared with `default=5` yields `5`, not `None`. To store an actual `None`, declare the default as `None`.

### Datetime and timestamp coercion

Datetime descriptors accept datetime objects, format strings, and raw timestamps. Behavior worth knowing:

- Numeric input above `1e11` is interpreted as **milliseconds** and divided by 1000; anything smaller is treated as seconds.
- String dates are tried against a fixed format list (`%Y-%m-%dT%H:%M:%S`, `%Y%m%dT%H%M%S`, …); unparseable strings fall back to the default.
- Timestamps converted via `datetime.fromtimestamp` produce **naive datetimes in the local timezone**, not UTC-aware ones.

### Collections: silent skipping of invalid items

List descriptors (`ListOfIntDescriptor`, `ListOfUuidDescriptor`, `ListOfStringDescriptor`) skip items that cannot be converted rather than raising. The UUID descriptors accept a `raise_on_error=True` flag to turn skipping into an exception; `StrUuidDescriptor` uses the same flag for invalid UUID strings, falling back to its default when disabled.
