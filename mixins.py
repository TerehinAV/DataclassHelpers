"""
Import and export mixins for dataclass models.

The module contains ``ImportJsonMixin`` for parsing dicts with arbitrary
keys and ``ExportJsonMixin`` / ``FlatExportJsonMixin`` for recursive
export into a JSON-compatible structure.
"""

from dataclasses import dataclass, fields, MISSING, is_dataclass
from typing import Dict, Any, Optional, List, Set, Tuple

from descriptors import FieldDescriptor, ObjectFieldDescriptor


class MissingRequiredFieldsError(Exception):
    """Raised when required fields are missing in input data."""


@dataclass
class ImportJsonMixin:
    """
    Add support for importing a dict object with any keys,
    even if they are not expected in the current dataclass.
    Only the fields defined in the dataclass will be used.

    A nested-model field is imported from its explicit key or alias first.
    Implicit flat mapping requires both a flat JSON value structure and
    globally unique field names and aliases across the complete model
    hierarchy. Any schema duplicate disables flat mapping for the whole model.
    JSON dump strings remain scalar and are not inspected during shape checks.
    """

    def __init__(self, **kwargs):
        self.validate_required_fields(kwargs)
        for sf_field in fields(self):
            descriptor = self._field_descriptor(sf_field)
            input_key = sf_field.name
            descriptor_alias = getattr(descriptor, "alias", None)
            if descriptor_alias and descriptor_alias in kwargs:
                input_key = descriptor_alias

            has_value = input_key in kwargs
            if isinstance(descriptor, ObjectFieldDescriptor):
                if has_value:
                    setattr(self, sf_field.name, kwargs[input_key])
                    continue

                has_flat_input = self._model_has_unambiguous_flat_input(
                    getattr(descriptor, "object_class", None), kwargs
                )
                if has_flat_input:
                    setattr(self, sf_field.name, kwargs)
                    continue

                if not self._is_descriptor_required(descriptor):
                    descriptor_default = getattr(descriptor, "default", MISSING)
                    descriptor_factory = getattr(
                        descriptor, "default_factory", MISSING
                    )
                    value = descriptor_default
                    if value is MISSING and descriptor_factory is not MISSING:
                        value = descriptor_factory()
                    if value is not MISSING:
                        setattr(self, sf_field.name, value)
                continue

            if has_value:
                setattr(self, sf_field.name, kwargs[input_key])
                continue

            if descriptor is not None:
                continue

            if sf_field.default_factory is not MISSING:
                setattr(self, sf_field.name, sf_field.default_factory())
                continue

            if sf_field.default is not MISSING:
                setattr(self, sf_field.name, sf_field.default)

    @staticmethod
    def _is_descriptor_required(descriptor: Any) -> bool:
        """Return whether a descriptor requires an explicit value.

        A descriptor is required when it has neither a default nor a usable
        default factory. Factories that deliberately raise for missing values
        also make the descriptor required.

        Args:
            descriptor: Descriptor instance to inspect.

        Returns:
            True when the descriptor requires an explicit value.
        """
        descriptor_default = getattr(descriptor, "default", MISSING)
        descriptor_factory = getattr(descriptor, "default_factory", MISSING)
        if descriptor_default is MISSING and descriptor_factory is MISSING:
            return True
        if descriptor_default is MISSING and callable(descriptor_factory):
            if descriptor_factory == getattr(descriptor, "raise_on_value_missed", None):
                return True
            factory_fn = getattr(descriptor_factory, "__func__", None)
            if factory_fn is FieldDescriptor.raise_on_value_missed:
                return True
        return False

    @classmethod
    def _get_missing_fields_recursive(
            cls, descriptor: Any, input_data: Dict[str, Any], prefix: str = ""
    ) -> List[str]:
        """Find missing required fields in a nested object hierarchy.

        Args:
            descriptor: Object descriptor containing the nested model metadata.
            input_data: Flat input data being mapped onto the hierarchy.
            prefix: Field path prefix used in validation errors.

        Returns:
            Paths of all required fields missing from the flat input.
        """
        object_class = getattr(descriptor, "object_class", None)
        if object_class is None or not hasattr(object_class, "__dataclass_fields__"):
            return []

        missing = []
        try:
            nested_fields = fields(object_class)
        except TypeError:
            return []

        for nested_field in nested_fields:
            nested_descriptor = (
                nested_field.default
                if isinstance(
                    nested_field.default, (ObjectFieldDescriptor, FieldDescriptor)
                )
                else None
            )

            nested_alias = (
                getattr(nested_descriptor, "alias", None)
                if nested_descriptor is not None
                else None
            )

            has_value = nested_field.name in input_data or (
                nested_alias in input_data if nested_alias else False
            )

            field_path = f"{prefix}.{nested_field.name}" if prefix else nested_field.name

            # A directly supplied value satisfies this field.
            if has_value:
                continue

            # For a missing value, determine whether the field is required.
            is_required = False
            if nested_descriptor is not None:
                is_required = cls._is_descriptor_required(nested_descriptor)
            else:
                has_default = nested_field.default is not MISSING
                has_factory = nested_field.default_factory is not MISSING
                is_required = not has_default and not has_factory

            if not is_required:
                continue

            # A required nested object may still be populated from flat input.
            if isinstance(nested_descriptor, ObjectFieldDescriptor):
                if cls._model_has_unambiguous_flat_input(
                        getattr(nested_descriptor, "object_class", None), input_data
                ):
                    # Validate the selected nested hierarchy recursively.
                    missing.extend(
                        cls._get_missing_fields_recursive(
                            nested_descriptor, input_data, field_path
                        )
                    )
                else:
                    # No flat data selects this required nested object.
                    missing.append(field_path)
            else:
                # A regular required field is missing.
                missing.append(field_path)

        return missing

    @staticmethod
    def _field_descriptor(field_obj: Any) -> Optional[Any]:
        descriptor = field_obj.default
        if isinstance(descriptor, (ObjectFieldDescriptor, FieldDescriptor)):
            return descriptor
        return None

    @classmethod
    def _accepted_flat_keys(
            cls, model_class: Any, ancestors: Tuple[Any, ...] = ()
    ) -> Set[str]:
        """Collect field names and aliases accepted by a model hierarchy."""
        if model_class in ancestors:
            return set()

        try:
            model_fields = fields(model_class)
        except TypeError:
            return set()

        accepted_keys: Set[str] = set()
        next_ancestors = ancestors + (model_class,)
        for field_obj in model_fields:
            descriptor = cls._field_descriptor(field_obj)
            accepted_keys.add(field_obj.name)
            alias = getattr(descriptor, "alias", None)
            if alias:
                accepted_keys.add(alias)
            if isinstance(descriptor, ObjectFieldDescriptor):
                accepted_keys.update(
                    cls._accepted_flat_keys(
                        getattr(descriptor, "object_class", None), next_ancestors
                    )
                )
        return accepted_keys

    @classmethod
    def _flat_key_owners(cls) -> Dict[str, Set[Tuple[str, ...]]]:
        """Map every accepted key to all field paths that can consume it."""
        owners: Dict[str, Set[Tuple[str, ...]]] = {}

        def collect(
                model_class: Any,
                path: Tuple[str, ...],
                ancestors: Tuple[Any, ...],
        ) -> None:
            if model_class in ancestors:
                return

            try:
                model_fields = fields(model_class)
            except TypeError:
                return

            next_ancestors = ancestors + (model_class,)
            for field_obj in model_fields:
                descriptor = cls._field_descriptor(field_obj)
                field_path = path + (field_obj.name,)
                accepted_keys = {field_obj.name}
                alias = getattr(descriptor, "alias", None)
                if alias:
                    accepted_keys.add(alias)
                for key in accepted_keys:
                    owners.setdefault(key, set()).add(field_path)
                if isinstance(descriptor, ObjectFieldDescriptor):
                    collect(
                        getattr(descriptor, "object_class", None),
                        field_path,
                        next_ancestors,
                    )

        collect(cls, (), ())
        return owners

    @classmethod
    def _flat_schema_is_unambiguous(cls) -> bool:
        """Return whether every accepted flat key has one schema owner.

        Field names and aliases are checked across the complete recursive
        dataclass hierarchy. Any duplicate disables flat import for the whole
        target model, even when the conflicting key is absent from the input.
        """
        return all(
            len(field_paths) == 1
            for field_paths in cls._flat_key_owners().values()
        )

    @staticmethod
    def _input_is_flat(input_data: Dict[str, Any]) -> bool:
        """Return whether JSON-compatible input has a flat value structure.

        JSON scalars and one-dimensional lists of JSON scalars are flat.
        Dictionaries and nested lists indicate hierarchical input. JSON dump
        strings are deliberately treated as ordinary scalar strings.
        """
        scalar_types = (str, int, float, bool, type(None))

        def is_flat_value(value: Any) -> bool:
            if isinstance(value, scalar_types):
                return True
            if isinstance(value, list):
                return all(isinstance(item, scalar_types) for item in value)
            return False

        return all(is_flat_value(value) for value in input_data.values())

    @classmethod
    def _model_has_unambiguous_flat_input(
            cls, model_class: Any, input_data: Dict[str, Any]
    ) -> bool:
        """Return whether flat input unambiguously targets a nested model.

        Input shape is evaluated only from JSON values. Model suitability is
        evaluated independently: every field name and alias in the complete
        target hierarchy must be globally unique, and at least one input key
        must belong to the requested nested model.
        """
        if model_class is None or not cls._input_is_flat(input_data):
            return False
        if not cls._flat_schema_is_unambiguous():
            return False

        accepted_keys = cls._accepted_flat_keys(model_class)
        return any(key in input_data for key in accepted_keys)

    def validate_required_fields(self, input_data: Dict[str, Any]):
        """Validate direct and recursively selected flat input fields.

        Optional nested descriptors are validated when unambiguous flat keys
        select their model. Required nested descriptors may be satisfied by
        the same flat mapping; otherwise their own field name is reported.
        """
        missing_fields = []
        for field_obj in fields(self):
            descriptor = self._field_descriptor(field_obj)
            descriptor_alias = getattr(descriptor, "alias", None)
            has_value = field_obj.name in input_data or (
                descriptor_alias in input_data if descriptor_alias else False
            )
            if has_value:
                continue

            if descriptor is not None:
                is_required = self._is_descriptor_required(descriptor)
            else:
                has_default = field_obj.default is not MISSING
                has_factory = field_obj.default_factory is not MISSING
                is_required = not has_default and not has_factory

            if isinstance(descriptor, ObjectFieldDescriptor):
                has_flat_input = self._model_has_unambiguous_flat_input(
                    getattr(descriptor, "object_class", None), input_data
                )
                if has_flat_input:
                    missing_fields.extend(
                        self._get_missing_fields_recursive(
                            descriptor, input_data, field_obj.name
                        )
                    )
                    continue

            if is_required:
                missing_fields.append(field_obj.name)

        if missing_fields:
            raise MissingRequiredFieldsError(
                f"Model {self.__class__.__name__} missing required fields "
                f"with no default values: {', '.join(missing_fields)}\n"
                f"input_data: {self.mask_secrets(input_data)}"
            )

    @staticmethod
    def mask_secrets(data, secret_keys=None, mask_char='*', mask_length=8):
        """
        Recursively masks the values of secret keys in a dict.

        Args:
            data: A dict, list, or other data structure to process
            secret_keys: A set or list of keys to mask.
                        If None, a default set is used.
            mask_char: The character used for masking (default '*')
            mask_length: The length of the mask (default 8)

        Returns:
            A copy of the input data with secrets masked
        """
        if secret_keys is None:
            secret_keys = {
                'password', 'passwd', 'pwd', 'secret', 'token', 'api_key',
                'apikey', 'access_token', 'refresh_token', 'private_key',
                'auth', 'authorization', 'credentials', 'credential',
                'secret_key', 'session', 'session_id', 'cookie',
                'login', 'username', 'user', 'email'
            }

        # Convert to a set for fast lookup
        if not isinstance(secret_keys, set):
            secret_keys = set(secret_keys)

        # Helper to check whether a key is secret
        def is_secret_key(key):
            if not isinstance(key, str):
                return False
            key_lower = key.lower()
            # Check for an exact match or containment of a secret word
            return key_lower in secret_keys or any(secret in key_lower for secret in secret_keys)

        # Create the mask
        mask = mask_char * mask_length

        # Recursive processing function
        def _mask_recursive(obj):
            if isinstance(obj, dict):
                result = {}
                for key, value in obj.items():
                    if is_secret_key(key):
                        # Mask the value
                        result[key] = mask
                    else:
                        # Process the value recursively
                        result[key] = _mask_recursive(value)
                return result
            elif isinstance(obj, list):
                return [_mask_recursive(item) for item in obj]
            elif isinstance(obj, tuple):
                return tuple(_mask_recursive(item) for item in obj)
            else:
                # Return the value as is (strings, numbers, etc.)
                return obj

        return _mask_recursive(data)

    @classmethod
    def has_required_fields(cls) -> bool:
        """
        Check if the dataclass defines any fields that are required
        (i.e., fields without default values and without default factories).

        Returns:
            True if there is at least one required field; otherwise False.
        """
        try:
            dc_fields = fields(cls)
        except TypeError:
            # Not a dataclass type; by contract, treat as having no required fields
            return False
        for field_obj in dc_fields:
            has_default = field_obj.default is not MISSING
            has_factory = field_obj.default_factory is not MISSING
            if not has_default and not has_factory:
                return True
        return False


@dataclass
class ExportJsonMixin:
    """
    Add support of recursive exporting
    """

    def to_json(self, stringify=False, use_alias=False):
        """
        Convert the dataclass instance to a JSON-serializable dictionary.

        Args:
            stringify: If True, convert non-serializable values to strings
            use_alias: If True, use alias from descriptor if available

        Returns:
            A JSON-serializable representation of the dataclass
        """

        def recursive_to_json(obj):
            """
            Recursively convert an object to a JSON-serializable representation.

            Args:
                obj: The object to convert
                field_descriptor: Optional descriptor for formatting

            Returns:
                A JSON-serializable representation of the object
            """
            obj_type = type(obj)
            instance_type = type(self)
            if (
                    hasattr(obj, "to_json")
                    and not obj_type == instance_type
                    and callable(obj.to_json)
            ):
                # Use custom to_json method
                # NOTE: to use specified export implement "to_json/0" instance method
                return obj.to_json(stringify=stringify)
            elif is_dataclass(obj):
                result = {}
                for field_obj in fields(obj):
                    field_value = getattr(obj, field_obj.name)

                    # Get the descriptor through the class
                    descriptor = getattr(type(obj), field_obj.name, None)

                    # Determine the export key
                    export_key = field_obj.name
                    if use_alias and isinstance(descriptor, FieldDescriptor):
                        if hasattr(descriptor, "alias") and descriptor.alias:
                            export_key = descriptor.alias

                    # Use the descriptor's format_value if available
                    if isinstance(descriptor, FieldDescriptor) and hasattr(descriptor, 'format_value'):
                        formatted_value = descriptor.format_value(field_value, stringify=stringify)
                        result[export_key] = recursive_to_json(formatted_value)
                    else:
                        result[export_key] = recursive_to_json(field_value)
                return result
            elif isinstance(obj, list):
                return [recursive_to_json(item) for item in obj]
            elif isinstance(obj, dict):
                return {key: recursive_to_json(value) for key, value in obj.items()}
            else:
                return str(obj) if stringify is True else obj

        return recursive_to_json(self)


@dataclass
class FlatExportJsonMixin:
    """
    Add support of recursive exporting with flattening
    """

    def to_json(self, stringify=False, use_prefix=False, use_alias=False):
        """
        Convert the dataclass instance to a flat JSON-serializable dictionary.

        Args:
            use_prefix: bool, if True, add prefixes to nested keys
            stringify: If True, convert non-serializable values to strings
            use_alias: If True, use alias from descriptor if available

        Returns:
            A flat JSON-serializable representation of the dataclass
        """

        def recursive_to_json(obj, prefix: Optional[str]=""):
            """
            Recursively flatten an object into a dict with dot-separated keys.

            Args:
                obj: The object to convert
                prefix: The current key prefix for nested fields

            Returns:
                A flat dictionary of key-value pairs
            """
            flat_dict = {}

            if (
                    hasattr(obj, "to_json")
                    and callable(obj.to_json)
                    and not isinstance(obj, type(self))
            ):
                # if another dataclass has its own exporter
                nested = obj.to_json(stringify=stringify)
                # if nested export is also flat — merge directly
                if isinstance(nested, dict):
                    for k, v in nested.items():
                        if use_prefix:
                            key = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
                        else:
                            key = k
                        flat_dict[key] = v
                else:
                    flat_dict[prefix.rstrip(".")] = nested

            elif is_dataclass(obj):
                for field in fields(obj):
                    value = getattr(obj, field.name)

                    # Determine the field name for export
                    field_name = field.name
                    if use_alias:
                        descriptor = getattr(type(obj), field.name, None)
                        if (
                                descriptor is not None
                                and hasattr(descriptor, "alias")
                                and descriptor.alias
                        ):
                            field_name = descriptor.alias

                    if use_prefix:
                        new_prefix = (
                            f"{prefix}{field_name}"
                            if not prefix
                            else f"{prefix}.{field_name}"
                        )
                    else:
                        new_prefix = None
                    flat_dict.update(recursive_to_json(value, new_prefix))

            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    if use_prefix:
                        new_prefix = f"{prefix}[{i}]"
                    else:
                        new_prefix = None
                    flat_dict.update(recursive_to_json(item, new_prefix))

            elif isinstance(obj, dict):
                for k, v in obj.items():
                    if use_prefix:
                        new_prefix = f"{prefix}.{k}" if prefix else str(k)
                    else:
                        new_prefix = None
                    flat_dict.update(recursive_to_json(v, new_prefix))

            else:
                key = prefix.rstrip(".")
                flat_dict[key] = str(obj) if stringify else obj

            return flat_dict

        return recursive_to_json(self)
