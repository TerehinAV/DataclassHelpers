"""
Dataclass based serializer
+ export and import mixins
"""

from dataclasses import MISSING, dataclass, fields, is_dataclass
from typing import Any, Dict

from descriptors import FieldDescriptor, ObjectFieldDescriptor


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
            descriptor = (
                sf_field.default
                if isinstance(
                    sf_field.default, (ObjectFieldDescriptor, FieldDescriptor)
                )
                else None
            )
            input_key = name
            descriptor_alias = (
                getattr(descriptor, "alias", None) if descriptor is not None else None
            )
            if descriptor_alias and descriptor_alias in kwargs:
                input_key = descriptor_alias

            has_value = input_key in kwargs
            if isinstance(sf_field.default, ObjectFieldDescriptor):
                if not has_value:
                    # if this field is under descriptor it has not an input value
                    # -> send full kwargs dict into descriptor setter
                    setattr(self, name, kwargs)
                else:
                    setattr(self, name, kwargs[input_key])
                continue

            if has_value:
                setattr(self, name, kwargs[input_key])
                continue

            if descriptor is not None:
                continue

            if sf_field.default_factory is not MISSING:
                setattr(self, name, sf_field.default_factory())
                continue

            if sf_field.default is not MISSING:
                setattr(self, name, sf_field.default)

    @staticmethod
    def _is_descriptor_required(descriptor: Any) -> bool:
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
    def _object_descriptor_can_be_built_from_flat_input(
        cls, descriptor: Any, input_data: Dict[str, Any]
    ) -> bool:
        object_class = getattr(descriptor, "object_class", None)
        if object_class is None or not hasattr(object_class, "__dataclass_fields__"):
            return False

        try:
            nested_fields = fields(object_class)
        except TypeError:
            return False

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
            nested_has_value = nested_field.name in input_data or (
                nested_alias in input_data if nested_alias else False
            )

            if nested_descriptor is not None and isinstance(
                nested_descriptor, ObjectFieldDescriptor
            ):
                if nested_has_value:
                    return True
                if cls._object_descriptor_can_be_built_from_flat_input(
                    nested_descriptor, input_data
                ):
                    return True
                continue

            if nested_has_value:
                return True

        return False

    def validate_required_fields(self, input_data: Dict[str, Any]):
        """
        Validates that all required fields are present in the input data.
        Raises an exception if any required field is missing.
        """
        missing_fields = []
        for field_obj in fields(self):
            descriptor = (
                field_obj.default
                if isinstance(
                    field_obj.default, (ObjectFieldDescriptor, FieldDescriptor)
                )
                else None
            )

            if descriptor is not None:
                is_required = self._is_descriptor_required(descriptor)
                if is_required:
                    descriptor_alias = getattr(descriptor, "alias", None)
                    has_value = field_obj.name in input_data or (
                        descriptor_alias in input_data if descriptor_alias else False
                    )
                    if (
                        not has_value
                        and isinstance(descriptor, ObjectFieldDescriptor)
                        and self._object_descriptor_can_be_built_from_flat_input(
                            descriptor, input_data
                        )
                    ):
                        has_value = True
                    if not has_value:
                        missing_fields.append(field_obj.name)
                continue

            has_default = field_obj.default is not MISSING
            has_factory = field_obj.default_factory is not MISSING
            if not has_default and not has_factory and field_obj.name not in input_data:
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
                for field in fields(obj):
                    field_value = getattr(obj, field.name)

                    # Определяем ключ для экспорта
                    export_key = field.name
                    if use_alias:
                        # Получаем дескриптор через класс
                        descriptor = getattr(type(obj), field.name, None)
                        if (
                            descriptor is not None
                            and hasattr(descriptor, "alias")
                            and descriptor.alias
                        ):
                            export_key = descriptor.alias

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

                    # Определяем имя поля для экспорта
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
