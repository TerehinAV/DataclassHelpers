"""
Dataclass based serializer
+ export and import mixins
"""

from typing import Dict, Any
from dataclasses import dataclass, fields, MISSING, is_dataclass

from descriptors import FieldDescriptor


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
            # --- НОВАЯ ЛОГИКА ---
            if isinstance(sf_field.default, FieldDescriptor) and name not in kwargs:
                # если поле управляется дескриптором и ключа нет → передаём весь словарь
                setattr(self, name, kwargs)
                continue
            # --------------------
            if new_value is None and sf_field.default_factory is not MISSING:
                setattr(self, sf_field.name, sf_field.default_factory())
                continue
            elif new_value is not None and sf_field.default_factory is not MISSING:
                setattr(self, sf_field.name, new_value)
                continue
            _new_value = new_value
            if not _new_value and sf_field.default is not MISSING and not isinstance(sf_field.default, FieldDescriptor):
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
                f"Missing required fields with no default values: {', '.join(missing_fields)}"
            )


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


class FlatExportJsonMixin:
    """
    Export dataclass to flat dict.
    """
    def to_json(self, stringify: bool = False) -> Dict[str, Any]:
        """
        Convert the dataclass instance to a flat JSON-serializable dictionary.

        Args:
            stringify: If True, convert non-serializable values to strings

        Returns:
            A flat JSON-serializable dictionary representation of the dataclass
        """
        def flatten(obj) -> Dict[str, Any]:
            """
            Recursively flatten a dataclass object into a single-level dictionary.

            Args:
                obj: The object to flatten

            Returns:
                A flat dictionary with all nested dataclass fields at the top level
            """
            out: Dict[str, Any] = {}
            if is_dataclass(obj):
                for f in fields(obj):
                    v = getattr(obj, f.name)
                    if is_dataclass(v):
                        out.update(flatten(v))
                    else:
                        if isinstance(v, bool):
                            out[f.name] = int(v)
                        else:
                            out[f.name] = str(v) if stringify and v is not None else v
            else:
                # не ожидается для верхнего вызова, но оставим на всякий
                out["value"] = int(obj) if isinstance(obj, bool) else (str(obj) if stringify else obj)
            return out
        return flatten(self)
