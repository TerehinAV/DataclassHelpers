"""
Dataclass based serializer
+ export and import mixins
"""

from typing import Dict, Any
from dataclasses import dataclass, fields, MISSING, is_dataclass

from descriptors import ObjectFieldDescriptor


class MissingRequiredFieldsError(Exception):
    """Raised when required fields are missing in input data."""


@dataclass
class ImportJsonMixin:
    """
    Add support for importing a dict object with any keys,
    even if they are not expected in the current dataclass.
    Only the fields defined in the dataclass will be used.
    """

    def __init__(self, **kwargs):
        self.validate_required_fields(kwargs)
        sf_fields = {sf_field.name: sf_field for sf_field in fields(self)}
        for name, sf_field in sf_fields.items():
            new_value = kwargs.get(name)
            is_model = isinstance(sf_field.default, ObjectFieldDescriptor)
            has_value = name in kwargs
            if is_model:
                if not has_value:
                    # поле управляется дескриптором и ключ присутствует → передаём только его значение
                    setattr(self, name, kwargs)
                else:
                    setattr(self, name, new_value)
                # если ключ отсутствует, оставляем значение по умолчанию дескриптора
                continue
            if new_value is None and sf_field.default_factory is not MISSING:
                setattr(self, sf_field.name, sf_field.default_factory())
                continue
            elif new_value is not None and sf_field.default_factory is not MISSING:
                setattr(self, sf_field.name, new_value)
                continue
            _new_value = new_value
            if _new_value is None and sf_field.default is not MISSING and not isinstance(sf_field.default, ObjectFieldDescriptor):
                _new_value = sf_field.default
            setattr(self, name, _new_value)

    def validate_required_fields(self, input_data: Dict[str, Any]):
        """
        Validates that all required fields are present in the input data.
        Raises an exception if any required field is missing.
        """
        missing_fields = []
        for field_obj in fields(self):
            has_default = field_obj.default is not MISSING
            has_factory = field_obj.default_factory is not MISSING
            if not has_default and not has_factory:
                if field_obj.name not in input_data or input_data[field_obj.name] is None:
                    missing_fields.append(field_obj.name)
        if missing_fields:
            raise MissingRequiredFieldsError(
                f"missing required fields with no default values: {', '.join(missing_fields)}\ninput_data: {input_data}"
            )

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
    def to_json(self, stringify=False):
        """
        Convert the dataclass instance to a JSON-serializable dictionary.

        Args:
            stringify: If True, convert non-serializable values to strings

        Returns:
            A JSON-serializable representation of the dataclass
        """
        def recursive_to_json(obj):
            """
            Recursively convert an object to a JSON-serializable representation.

            Args:
                obj: The object to convert

            Returns:
                A JSON-serializable representation of the object
            """
            obj_type = type(obj)
            instance_type = type(self)
            if hasattr(obj, 'to_json') and not obj_type == instance_type and callable(obj.to_json):
                # Use custom to_json method
                # NOTE: to use specified export implement "to_json/0" instance method
                return obj.to_json()
            elif is_dataclass(obj):
                return {field.name: recursive_to_json(getattr(obj, field.name)) for field in fields(obj)}
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

    def to_json(self, stringify=False, use_prefix=False):
        """
        Convert the dataclass instance to a flat JSON-serializable dictionary.

        Args:
            use_prefix: bool, if True, add prefixes to nested keys
            stringify: If True, convert non-serializable values to strings

        Returns:
            A flat JSON-serializable representation of the dataclass
        """

        def recursive_to_json(obj, prefix=""):
            """
            Recursively flatten an object into a dict with dot-separated keys.

            Args:
                obj: The object to convert
                prefix: The current key prefix for nested fields

            Returns:
                A flat dictionary of key-value pairs
            """
            flat_dict = {}

            if hasattr(obj, "to_json") and callable(obj.to_json) and not isinstance(obj, type(self)):
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
                    if use_prefix:
                        new_prefix = f"{prefix}{field.name}" if not prefix else f"{prefix}.{field.name}"
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
