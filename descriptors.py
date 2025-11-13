"""
Dataclass field descriptors
"""

import uuid
from typing import Optional, Callable, Union, Dict, Any, List


class ObjectFieldDescriptor:
    """
    Base descriptor class for field descriptors.
    This is an abstract base class for all field descriptors in the module.
    """
    pass


class FieldDescriptor:
    """"""
    def raise_on_value_missed(self):
        """ """
        raise ValueError("Value have no default value and must be set")


class StringWrapperObject:
    """
    Base class for string value objects, like parent. Provides method for manipulating with strings
    """
    value: Optional[str] = None


class StringWrapperDescriptor(FieldDescriptor):
    """
    Descriptor wrapper for string value in an object of class object_class,
    inherited from StringValueObject. The setter accepts a string or an object of
    object_class. If a string is passed, an instance of object_class is created and
    assigned to its `value` attribute.
    """
    def __init__(self, object_class, default: Optional[StringWrapperObject] = None, default_factory: Optional[Callable] = None, optional=True):
        self.object_class = object_class
        if callable(default_factory):
            self.default_factory = default_factory
        elif isinstance(default, object_class):
            self.default_factory = lambda: default
        else:
            # by default, create an empty object
            self.default_factory = self._default_factory

    def __set_name__(self, owner, name):
        self._name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        value = instance.__dict__.get(self._name)
        if value is not None:
            return value
        return self.default_factory()

    def __set__(self, instance, value):
        if value is None or value is False:
            obj = self.default_factory()
        elif isinstance(value, self.object_class):
            obj = value
        elif isinstance(value, dict):
            # support for ImportJsonMixin, if a dictionary of constructor parameters is received
            obj = self.object_class(**value)
        else:
            # interpret as a string according to requirements
            obj = self.object_class()
            try:
                setattr(obj, 'value', None if value is None else str(value))
            except Exception:
                # if object_class doesn't have a value field, leave it as default
                pass
        instance.__dict__[self._name] = obj

    def _default_factory(self):
        return self.object_class()


class FloatStringDescriptor(FieldDescriptor):
    """
    Float descriptor
        it supports:
            - string values representing floats
            - int and float objects
            - default value or default factory
    """
    def __init__(self, default: Optional[float] = None, default_factory: Optional[Callable] = None):
        """
        Initialize the FloatStringDescriptor with a default value or factory.

        Args:
            default: Optional default float value
            default_factory: Optional callable that returns a default float value
        """
        if callable(default_factory):
            self.default_factory = default_factory
        elif isinstance(default, (int, float)):
            self.default_factory = lambda: float(default)
        else:
            self.default_factory = self.raise_on_value_missed

    def __get__(self, instance, owner):
        """
        Get the float value from the instance.

        Args:
            instance: The instance containing the attribute
            owner: The class that owns the attribute

        Returns:
            The float value or the default value if not set
        """
        if instance is None:
            return self
        value = instance.__dict__.get(self._name)
        if value is not None:
            return value
        return self.default_factory()

    def __set__(self, instance, value: Union[str, int, float, None]):
        """
        Set the float value in the instance.

        Args:
            instance: The instance containing the attribute
            value: The value to set, can be a string, int, float, or None
        """
        if value is None or value == '':
            value = self.default_factory()
        elif isinstance(value, str):
            try:
                value = float(value)
            except ValueError:
                value = self.default_factory()
        elif isinstance(value, (int, float)):
            value = float(value)
        else:
            value = self.default_factory()
        instance.__dict__[self._name] = value

    def __set_name__(self, owner, name):
        """
        Set the name of the attribute in the owner class.

        Args:
            owner: The class that owns the attribute
            name: The name of the attribute
        """
        self._name = name


class IntStringDescriptor(FieldDescriptor):
    """
    Integer descriptor
        it supports:
            - string values representing integers
            - int and float objects
            - default value or default factory
    """
    def __init__(self, default: Optional[int] = None, default_factory: Optional[Callable] = None):
        """
        Initialize the IntStringDescriptor with a default value or factory.

        Args:
            default: Optional default integer value
            default_factory: Optional callable that returns a default integer value
        """
        if callable(default_factory):
            self.default_factory = default_factory
        elif isinstance(default, (int, float)):
            self.default_factory = lambda: int(default)
        else:
            self.default_factory = self.raise_on_value_missed

    def __get__(self, instance, owner):
        """
        Get the integer value from the instance.

        Args:
            instance: The instance containing the attribute
            owner: The class that owns the attribute

        Returns:
            The integer value or the default value if not set
        """
        if instance is None:
            return self
        value = instance.__dict__.get(self._name)
        if value is not None:
            return value
        return self.default_factory()

    def __set__(self, instance, value: Union[str, int, float, None]):
        """
        Set the integer value in the instance.

        Args:
            instance: The instance containing the attribute
            value: The value to set, can be a string, int, float, or None
        """
        if value is None or value == '':
            value = self.default_factory()
        elif isinstance(value, str):
            try:
                value = int(float(value))  # на случай строки вроде "12.0"
            except ValueError:
                value = self.default_factory()
        elif isinstance(value, (int, float)):
            value = int(value)
        else:
            value = self.default_factory()
        instance.__dict__[self._name] = value

    def __set_name__(self, owner, name):
        """
        Set the name of the attribute in the owner class.

        Args:
            owner: The class that owns the attribute
            name: The name of the attribute
        """
        self._name = name


class SingleObjectDescriptor(ObjectFieldDescriptor):
    def __init__(self,
                 object_class,
                 default: Optional[ObjectFieldDescriptor] = None,
                 default_factory: Optional[Callable] = None,
                 optional=True):
        """
        Initialize the SingleObjectDescriptor with an object class, default value, or factory.

        Args:
            object_class: The class of the object to be created
            default: Optional default object
            default_factory: Optional callable that returns a default object
        """
        self._optional = optional
        self.object_class = object_class
        if callable(default_factory):
            self.default_factory = default_factory
        elif isinstance(default, object_class):
            self.default_factory = lambda: default  # Преобразуем объект в фабрику
        elif self._optional:
            self.default_factory = lambda: None
        elif self.has_required_fields():
            self.default_factory = self._raise_no_default
        else:
            self.default_factory = self._default_factory


    def __get__(self, instance, owner):
        """
        Getter for field value
        """
        if instance is None:
            return self
        # Возвращаем значение из __dict__ экземпляра, если оно существует
        if self._name not in instance.__dict__:
            instance.__dict__[self._name] = self.default_factory()
        return instance.__dict__[self._name]

    def __set__(self, instance, value):
        """
        Setter for field value
        """
        if not value:
            value = self.default_factory()
        elif isinstance(value, dict):
            value = self.object_class(**value)
        elif not isinstance(value, self.object_class):
            # value = self.default_factory()
            raise ValueError(f"Value must be a dict or a {self.object_class.__name__} instance, not {type(value)}: {value}")
        # Сохраняем значение в __dict__ экземпляра
        instance.__dict__[self._name] = value

    def __set_name__(self, owner, name):
        """
        Set the name of the attribute in the owner class.

        Args:
            owner: The class that owns the attribute
            name: The name of the attribute
        """
        # Запоминаем имя атрибута, чтобы хранить значение в __dict__
        self._name = name

    def _raise_no_default(self):
        raise ValueError(f"No default value or factory for {self._name}")

    def has_required_fields(self):
        has_required_fields: Callable = getattr(self.object_class, "has_required_fields")
        return has_required_fields and has_required_fields()

    def _default_factory(self):
        """ Empty search filter """
        return self.object_class()

class ObjectListDescriptor(ObjectFieldDescriptor):
    def __init__(self,
                 object_class,
                 default: Optional[List[ObjectFieldDescriptor]] = None,
                 default_factory: Optional[Callable] = None):
        """
        Initialize the ObjectListDescriptor with an object class, default value, or factory.

        Args:
            object_class: The class of the objects in the list
            default: Optional default list of objects
            default_factory: Optional callable that returns a default list of objects
        """
        self.object_class = object_class
        if callable(default_factory):
            self.default_factory = default_factory
        elif isinstance(default, list):
            self.default_factory = lambda: default
        else:
            self.default_factory = self._default_factory

    def __get__(self, instance, owner):
        """
        Getter for field value
        """
        if instance is None:
            return self
        # return instance.__dict__.get(self._name)
        value = instance.__dict__.get(self._name)
        if value is not None:
            return value
        return self.default_factory()

    def __set__(self, instance, value):
        """
        Setter for field value
        """
        if value is None or not isinstance(value, list):
            value = self.default_factory()
        else:
            new_value = []
            for object_dto in value:
                if isinstance(object_dto, dict):
                    new_value.append(self.object_class(**object_dto))
                elif isinstance(object_dto, self.object_class):
                    new_value.append(object_dto)
            value = new_value
        instance.__dict__[self._name] = value

    def __set_name__(self, owner, name):
        """
        Set the name of the attribute in the owner class.

        Args:
            owner: The class that owns the attribute
            name: The name of the attribute
        """
        self._name = name

    @staticmethod
    def _default_factory():
        """ Empty search filter """
        return []


class MapObjectDescriptor(ObjectFieldDescriptor):
    def __init__(self,
                 object_class,
                 default: Optional[Dict[str, ObjectFieldDescriptor]] = None,
                 default_factory: Optional[Callable] = None):
        """
        Initialize the MapObjectDescriptor with an object class, default value, or factory.

        Args:
            object_class: The class of the objects in the map
            default: Optional default dictionary of objects
            default_factory: Optional callable that returns a default dictionary of objects
        """
        self.object_class = object_class
        if callable(default_factory):
            self.default_factory = default_factory
        elif isinstance(default, dict):
            self.default_factory = lambda: default
        else:
            self.default_factory = self._default_factory

    def __get__(self, instance, owner):
        """
        Getter for field value
        """
        if instance is None:
            return self
        value = instance.__dict__.get(self._name)
        if value is not None:
            return value
        return self.default_factory()

    def __set__(self, instance, value: Optional[Dict[str, Any]]):
        """
        Setter for field value
        """
        if not isinstance(value, dict):
            value = self.default_factory()
        else:
            result = {}
            for key, obj_data in value.items():
                if isinstance(obj_data, self.object_class):
                    result[key] = obj_data
                elif isinstance(obj_data, dict):
                    result[key] = self.object_class(**obj_data)
                # else:
                #     result[key] = obj_data
            value = result
        instance.__dict__[self._name] = value

    def __set_name__(self, owner, name):
        """
        Set the name of the attribute in the owner class.

        Args:
            owner: The class that owns the attribute
            name: The name of the attribute
        """
        self._name = name

    @staticmethod
    def _default_factory():
        """

        """
        return {}


class StrUuidDescriptor(FieldDescriptor):
    """
    UUID descriptor
        it supports:
            - uuid.UUID objects
            - string values (parsed into UUID)
            - default value or default factory
    """
    def __init__(self, default: Optional[uuid.UUID] = None,
                 default_factory: Optional[Union[Callable[[], uuid.UUID], Callable[[], None]]] = None,
                 raise_on_error: bool = False):
        self._raise_on_error = raise_on_error
        if callable(default_factory):
            self.default_factory = default_factory
        elif isinstance(default, uuid.UUID):
            self.default_factory = lambda: default
        elif isinstance(default, str):
            try:
                parsed = uuid.UUID(default)
                self.default_factory = lambda: parsed
            except (ValueError, TypeError) as err:
                if self._raise_on_error:
                    raise err
        elif isinstance(default, uuid.UUID):
            self.default_factory = lambda: default
        else:
            self.default_factory = self.raise_on_value_missed

    def __get__(self, instance, owner):
        if instance is None:
            return self
        value = instance.__dict__.get(self._name)
        if value is not None:
            return value
        return self.default_factory()

    def __set__(self, instance, value: Union[str, uuid.UUID, None]):
        if not value:
            value = self.default_factory()
        elif isinstance(value, uuid.UUID):
            pass
        elif isinstance(value, str):
            try:
                value = uuid.UUID(value)
            except ValueError as err:
                if self._raise_on_error:
                    raise Exception(f"{value} is not valid UUID").with_traceback(err.__traceback__)
                value = self.default_factory()
            except TypeError as err:
                if self._raise_on_error:
                    raise Exception(f"{type(value)} is not valid type for UUID ").with_traceback(err.__traceback__)
                value = self.default_factory()
            except Exception as err:
                if self._raise_on_error:
                    raise Exception(f"Unexpected exception with value: {str(value)} {err}").with_traceback(err.__traceback__)
                value = self.default_factory()
        elif isinstance(value, type(self)): # не задано значение по-умолчанию - передается экземпляр дескриптора
            # Не передано значение и нет дефолтного
            if self._raise_on_error and self.default_factory is None:
                raise Exception(f"Unsupported type: {str(value)}")
            value = self.default_factory()
        else:
            raise Exception(f"Unsupported type {value}: {type(value)}")
        instance.__dict__[self._name] = value

    def __set_name__(self, owner, name):
        self._name = name


class BoolToIntDescriptor(FieldDescriptor):
    """Descriptor that coerces various truthy/falsey inputs to integer 1/0."""
    def __init__(self, default: Optional[Union[bool, int]] = None, default_factory: Optional[Callable] = None):
        if callable(default_factory):
            self.default_factory = default_factory
        elif isinstance(default, (bool, int)):
            self.default_factory = lambda: int(bool(default))
        else:
            self.default_factory = self.raise_on_value_missed

    def __set_name__(self, owner, name):
        self._name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        value = instance.__dict__.get(self._name)
        if value is not None:
            return value
        return self.default_factory()

    def __set__(self, instance, value: Union[bool, int, None]):
        # Allow ImportJsonMixin to pass whole kwargs
        if value is None:
            result = self.default_factory()
        elif isinstance(value, bool):
            result = int(value)
        elif isinstance(value, int):
            result = 1 if value != 0 else 0
        else:
            # Only bool/int are allowed per requirements
            result = self.default_factory()
        instance.__dict__[self._name] = result


class ListOfIntDescriptor(FieldDescriptor):
    """Descriptor that ensures a list of ints.
    Priority: value > factory > default
    """
    def __init__(self, default: Optional[List[int]] = None, default_factory: Optional[Callable] = None):
        if callable(default_factory):
            self.default_factory = default_factory
        elif isinstance(default, list):
            # copy to avoid shared list
            self.default_factory = lambda: [int(x) for x in default if self._can_int(x)]
        else:
            self.default_factory = self.raise_on_value_missed

    @staticmethod
    def _can_int(x: Any) -> bool:
        try:
            int(str(x))
            return True
        except Exception:
            return False

    def __set_name__(self, owner, name):
        self._name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        value = instance.__dict__.get(self._name)
        if value is not None:
            return value
        return self.default_factory()

    def __set__(self, instance, value: Union[List[Any], None]):
        if isinstance(value, list):
            result = []
            for item in value:
                try:
                    result.append(int(item))
                except Exception:
                    # skip non-convertible items
                    pass
        else:
            # Only list is accepted per requirements
            result: List[int] = self.default_factory()
        instance.__dict__[self._name] = result


class ListOfUuidDescriptor(FieldDescriptor):
    """Descriptor that ensures a list of UUIDs (uuid.UUID). Accepts strings too."""
    def __init__(self,
                 default: Optional[List[uuid.UUID]] = None,
                 default_factory: Optional[Callable] = None,
                 raise_on_error=False):
        self._raise_on_error = raise_on_error
        if callable(default_factory):
            self.default_factory = default_factory
        elif isinstance(default, list):
            # copy with validation
            def _df():
                res = []
                for x in default:
                    if isinstance(x, uuid.UUID):
                        res.append(x)
                    elif isinstance(x, str):
                        try:
                            res.append(uuid.UUID(x))
                        except (ValueError, TypeError) as err:
                            if self._raise_on_error:
                                raise err
                return res
            self.default_factory = _df
        else:
            self.default_factory = self.raise_on_value_missed

    def __set_name__(self, owner, name):
        self._name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        value = instance.__dict__.get(self._name)
        if value is not None:
            return value
        return self.default_factory()

    def __set__(self, instance, value: Union[List[Union[str, uuid.UUID, Any]], None]):
        if value is None:
            result: List[uuid.UUID] = self.default_factory()
        elif isinstance(value, list):
            result = []
            for item in value:
                if isinstance(item, uuid.UUID):
                    result.append(item)
                else:
                    try:
                        result.append(uuid.UUID(str(item)))
                    except Exception as err:
                        if self._raise_on_error:
                            raise Exception(f"Invalid UUID value: {item}").with_traceback(err.__traceback__)
                        # skip invalid
        else:
            # Only list is accepted
            result = self.default_factory()
        instance.__dict__[self._name] = result
