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

## `ImportJsonMixin` Input Resolution

`ImportJsonMixin` accepts keyword arguments, ignores unknown keys, resolves aliases, and validates required fields. Nested object fields can be populated explicitly, inferred from a flat payload, or mixed: an explicitly supplied object branch is exempt from flat-shape detection, so a hierarchical dict, ready model, object list, or object map can coexist with flat sibling values consumed by the remaining active branches.

### Resolution order

Nested fields are resolved in this order:

1. **Explicit field name or alias.** Its value is passed directly to the descriptor. This always takes precedence over flat fields, and the value is exempt from shape detection because that branch has already selected hierarchical import.
2. **Payload shape.** When no explicit nested value exists, every payload value outside the explicit object branches must be structurally flat before implicit mapping is considered.
3. **Schema uniqueness.** Every field name and alias in branches still eligible for implicit flat mapping must have exactly one owner. Descendants of explicitly supplied object fields are excluded.
4. **Nested-model evidence.** At least one flat key must belong to the candidate nested model.
5. **Validation or default.** Selected nested models are validated recursively; otherwise descriptor defaults apply.

| Condition | Result |
|---|---|
| Object field name or alias is present | Import that explicit nested value; its key is exempt from shape detection |
| Any payload value outside an explicit object branch is a mapping, nested list, ready submodel, or list containing mappings or ready submodels | Disable all implicit flat mapping |
| Payload values are leaves not mapped by object descriptors, or one-dimensional lists of such leaves | Payload shape is flat |
| A field name or alias is duplicated across active flat-mapping branches | Disable flat mapping for the remaining implicit branches |
| The flat payload contains keys owned by an unambiguous nested model | Map the remaining flat payload, without the current level's explicit object keys, onto that nested model |
| No flat key selects an optional nested model | Use its `default` or `default_factory` |
| Selected flat data omits a required nested field | Raise `MissingRequiredFieldsError` |

Leaf values are not limited to JSON primitives: scalar descriptors may consume Python objects such as `date` or `datetime`, and one-dimensional lists of such leaves remain flat. A ready instance of any model class mapped by an object descriptor is hierarchical instead. Such instances remain importable through an explicit object field key, where they are skipped by shape detection. JSON dump strings remain ordinary scalar strings and are not parsed during shape detection.

### Global schema ambiguity

Field names and aliases are collected recursively from the root model and nested dataclass branches that still require implicit resolution. When an object field is explicitly present by name or alias, its descendants are removed from the flat ownership graph because that branch has already selected hierarchical import. Duplicates remaining in the active graph disable flat mapping even if the conflicting key is absent from the payload.

This conservative rule prevents a root field from pseudo-filling a nested model and prevents the same flat key from selecting multiple sibling branches. The exemption is scoped to active schema branches only: a mapping under any other key — including a stray key owned by a pruned subtree — still marks the payload hierarchical and blocks implicit flat mapping.

### Defaults and required fields

A descriptor default is used only when no explicit value or unambiguous flat data selects that field. Once flat data selects a nested model, its required fields are validated recursively. Partial data raises `MissingRequiredFieldsError`; optional nested fields continue to use their own defaults.

Validation errors include masked input data. Secret-like keys such as `password`, `token`, and `api_key` are replaced before the payload is added to the exception message.

### Aliases and unknown keys

When both a field name and its alias are present, the alias value wins. Aliases also participate in the active-schema uniqueness check. Keys matching neither a field name nor an alias are ignored.

### Missing values: `None` and empty string

Most scalar descriptors treat an explicitly passed `None` — and, where a string is expected, `""` — exactly like a missing key: the default value/factory is produced instead. Consequently, passing `None` to a descriptor declared with `default=5` yields `5`, not `None`. To store an actual `None`, declare the default as `None`.

### Datetime and timestamp coercion

Datetime descriptors accept datetime objects, format strings, and raw timestamps. Behavior worth knowing:

- Numeric input above `1e11` is interpreted as **milliseconds** and divided by 1000; anything smaller is treated as seconds.
- String dates are tried against a fixed format list (`%Y-%m-%dT%H:%M:%S`, `%Y%m%dT%H%M%S`, …); unparseable strings fall back to the default.
- Timestamps converted via `datetime.fromtimestamp` produce **naive datetimes in the local timezone**, not UTC-aware ones.

### Collections: silent skipping of invalid items

List descriptors (`ListOfIntDescriptor`, `ListOfUuidDescriptor`, `ListOfStringDescriptor`) skip items that cannot be converted rather than raising. The UUID descriptors accept a `raise_on_error=True` flag to turn skipping into an exception; `StrUuidDescriptor` uses the same flag for invalid UUID strings, falling back to its default when disabled.

## Running Tests

Install the dev dependencies and run the suite:

```bash
pip install pytest pytest-cov
```

Run all tests:

```bash
just test        # or: pytest
```

Run tests with line coverage for `descriptors.py` and `mixins.py`:

```bash
just coverage    # or: pytest --cov=descriptors --cov=mixins --cov-report=term-missing
```
