"""
Dataclass field descriptors
"""
import traceback
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Callable, List, Union, Dict, Any


class FieldDescriptor:
    """
    Base descriptor class for field descriptors.
    This is an abstract base class for all field descriptors in the module.
    """
    pass


class SingleObject:
    """
    Base class for single object descriptors.
    This class serves as a type hint for descriptors that handle single objects.
    """
    pass


COMMON_DATE_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S"

DATE_FORMATS = [
    COMMON_DATE_TIME_FORMAT,
    "%Y%m%dT%H%M%S",
    "%Y%m%dT%H%M",
    "%Y.%m.%d %H:%M",
    "%Y%m%dT%H%M%S"
]
class DateTimeDescriptor:
    """
    Datetime descriptor
        it supports:
            - datetime string values, datetime objects
            - several dt formats
    """
    def __init__(self, default: Optional[datetime] = None, default_factory: Optional[Callable] = None):
        """
        Initialize the DateTimeDescriptor with a default value or factory.

        Args:
            default: Optional default datetime value
            default_factory: Optional callable that returns a default datetime value
        """
        if callable(default_factory):
            self.default_factory = default_factory
        elif isinstance(default, datetime):
            self.default_factory = lambda: default
        else:
            self.default_factory = self._default_time

    def __get__(self, instance, owner):
        """
        Getter for field value
        """
        if instance is None:
            return self
        return instance.__dict__.get(self._name, self.default_factory())

    def __set__(self, instance, value):
        """
        Setter for field value
        """
        if not value:
            value = self.default_factory()
        elif isinstance(value, str):
            value = self._parse_date_string(value, self.default_factory())
        elif not isinstance(value, datetime):
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

    @staticmethod
    def _parse_date_string(value, default):
        """
        Parse a string into a datetime object using various formats.

        Args:
            value: The string to parse
            default: The default value to return if parsing fails

        Returns:
            A datetime object if parsing succeeds, otherwise the default value
        """
        for date_format in DATE_FORMATS:
            try:
                return datetime.strptime(value, date_format)
            except ValueError:
                continue
        return default

    @staticmethod
    def _default_time():
        """ Default time: now. """
        return datetime.now()


class FloatStringDescriptor:
    """
    Float descriptor
        it supports:
            - string values representing floats
            - int and float objects
            - default value or default factory
    """
    def __init__(self, default: Optional[float] = None, default_factory: Optional[Callable[[], float]] = None):
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
            self.default_factory = self._default_float

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
        return instance.__dict__.get(self._name, self.default_factory())

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

    @staticmethod
    def _default_float():
        """ Default float value: 0.0. """
        return 0.0


class IntStringDescriptor:
    """
    Integer descriptor
        it supports:
            - string values representing integers
            - int and float objects
            - default value or default factory
    """
    def __init__(self, default: Optional[int] = None, default_factory: Optional[Callable[[], int]] = None):
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
            self.default_factory = self._default_int

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
        return instance.__dict__.get(self._name, self.default_factory())

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

    @staticmethod
    def _default_int():
        """ Default int value: 0. """
        return 0


@dataclass
class SingleObjectDescriptor(FieldDescriptor):
    def __init__(self, object_class, default: Optional[SingleObject] = None, default_factory: Optional[Callable] = None):
        """
        Initialize the SingleObjectDescriptor with an object class, default value, or factory.

        Args:
            object_class: The class of the object to be created
            default: Optional default object
            default_factory: Optional callable that returns a default object
        """
        self.object_class = object_class
        if callable(default_factory):
            self.default_factory = default_factory
        elif isinstance(default, object_class):
            self.default_factory = lambda: default  # Преобразуем объект в фабрику
        else:
            self.default_factory = self._default_factory

    def __get__(self, instance, owner):
        """
        Getter for field value
        """
        if instance is None:
            return self
        # Возвращаем значение из __dict__ экземпляра, если оно существует
        return instance.__dict__.get(self._name, self.default_factory())

    def __set__(self, instance, value):
        """
        Setter for field value
        """
        if not value:
            value = self.default_factory()
        elif isinstance(value, dict):
            value = self.object_class(**value)
        elif not isinstance(value, self.object_class):
            value = self.default_factory()
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

    def _default_factory(self):
        """ Empty search filter """
        return self.object_class()


@dataclass
class ObjectListDescriptor(FieldDescriptor):
    def __init__(self, object_class, default: Optional[List[SingleObject]] = None, default_factory: Optional[Callable] = None):
        """
        Initialize the ObjectListDescriptor with an object class, default value, or factory.

        Args:
            object_class: The class of the objects in the list
            default: Optional default list of objects
            default_factory: Optional callable that returns a default list of objects
        """
        self.object_class = object_class
        if callable(default_factory):
            self.default_factory = default
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
        return instance.__dict__.get(self._name, self.default_factory())

    def __set__(self, instance, value):
        """
        Setter for field value
        """
        if not value or not isinstance(value, list):
            value = self.default_factory()
        else:
            value = [self.object_class(**object_dto) for object_dto in value]
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


@dataclass
class MapObjectDescriptor:
    def __init__(self, object_class, default: Optional[Dict[str, SingleObject]] = None, default_factory: Optional[Callable] = None):
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
        return instance.__dict__.get(self._name, self.default_factory())

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
                    try:
                        result[key] = self.object_class(**obj_data)
                    except Exception as err:
                        # Fallback to raw dict if instantiation fails
                        print(f"{traceback.format_exc()}")
                        result[key] = obj_data
                else:
                    result[key] = obj_data
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
