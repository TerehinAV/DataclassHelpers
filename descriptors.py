"""
Field descriptors for dataclass models.

This module contains a set of descriptors that intercept attribute reads
and writes, normalize "raw" values on import (strings to numbers,
dicts to nested objects, etc.), and support default values and
alternative key names (``alias``).
"""

import json
import re
import time
import uuid
from dataclasses import MISSING
from datetime import datetime, date, timezone, timedelta
from typing import Optional, Callable, Union, Dict, Any, List

COMMON_DATE_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S"

DATE_FORMATS = [
    COMMON_DATE_TIME_FORMAT,
    "%Y%m%dT%H%M%S",
    "%Y%m%dT%H%M",
    "%Y.%m.%d %H:%M",
    "%Y%m%dT%H%M%S",
]

VALUE_NOT_SET = object()

# >>> datetime helpers ===
def get_local_tz():
    """
    Determines and returns the local timezone based on the current system
    configuration, accounting for daylight saving time when applicable.

    Returns:
        timezone: A timezone object representing the local timezone,
                  adjusted for daylight saving time if it is currently in
                  effect.
    """
    if time.localtime().tm_isdst and time.daylight:
        return timezone(timedelta(seconds=-time.altzone))
    else:
        return timezone(timedelta(seconds=-time.timezone))


def get_datetime_from_timestamp_local_tz(timestamp: Union[int, float]) -> datetime:
    """
    Converts a UNIX timestamp to a datetime object, applying a timezone if specified.

    This function takes a UNIX timestamp in seconds (as an integer or float)
    and converts it to a timezone-aware datetime object. If no timezone is specified,
    it defaults to the local timezone.

    Parameters:
        timestamp (Union[int, float]): UNIX timestamp representing seconds since
            the epoch (January 1, 1970).
        tzinfo (Optional[timezone]): Timezone to apply. If None, local timezone
            will be applied.

    Returns:
        datetime: A timezone-aware datetime object corresponding to the given
            UNIX timestamp.
    """
    local_tz = get_local_tz()
    result = datetime.fromtimestamp(timestamp)
    return result.astimezone(local_tz)


def get_datetime_local_tz(dt_value: datetime):
    """
    Converts a given datetime object to the local timezone.

    This function adjusts the input datetime object to the local timezone
    if it has a timezone already associated with it. If the input datetime
    does not have any timezone information, it attaches the local timezone
    to it without changing the datetime itself.

    Parameters:
    dt_value (datetime): The datetime object to be converted.

    Returns:
    datetime: A datetime object adjusted to the local timezone.
    """
    local_tz = get_local_tz()

    if dt_value.tzinfo is not None:
        return dt_value.astimezone(local_tz)

    return dt_value.replace(
        tzinfo=local_tz
    )


def parse_date_string(value, default):
    """
    Parses a date string into a datetime object using predefined date formats.

    The method attempts to parse the provided date string using a list of predefined
    date formats. If none of the formats match, a default value is returned. This
    method is used for flexible date string parsing while providing a fallback for
    unparseable strings.

    Args:
        value: The date string to be parsed.
        default: The default value to return if the given string cannot be parsed.

    Returns:
        A datetime object if parsing is successful, otherwise the default value.
    """
    if is_timestamp_candidate(value):
        return parse_timestamp(value, default)
    for date_format in DATE_FORMATS:
        try:
            date_time_value = datetime.strptime(value, date_format)
            return date_time_value
        except ValueError:
            continue
    return default


def is_timestamp_candidate(value: Union[int, float, str]):
    """
    Determines if a value is a valid candidate for a timestamp.

    This function checks whether the given input value can potentially be converted
    to a float, which is commonly required for timestamp-like values. It accepts
    input in the form of integers, floats, or strings, and returns a boolean
    indicating whether the value qualifies.

    Args:
        value (Union[int, float, str]): The input value to be checked for timestamp
        candidacy. This could be an integer, a floating-point number, or a string.

    Returns:
        bool: True if the value can be converted to a float, indicating that it
        could represent a timestamp; False otherwise.
    """
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False


def parse_timestamp(value, default):
    """
    Parses a given timestamp value and converts it into a naive datetime object
    in the local timezone. If the value cannot be parsed into a valid timestamp,
    a default value is returned. The function handles timestamps in both seconds
    and milliseconds format.

    Parameters:
    value : Any
        The input value to be parsed as a timestamp.
    default : Any
        The default value to return if parsing fails.

    Returns:
    datetime | Any
        A naive local-time datetime object if the input value could be parsed as a
        valid timestamp; otherwise, the provided default is returned.

    Raises:
    ValueError
        If the input value cannot be converted to a float and no default is provided.
    TypeError
        If the input type is incompatible with conversion to a float and no default is provided.
    """
    try:
        ts = float(value)
    except (ValueError, TypeError):
        return default

    # Determine the unit — seconds or milliseconds
    # Anything above 10**11 is almost certainly milliseconds (since 10**10 ~ year 2001)
    if ts > 1e11:
        ts /= 1000.0  # convert milliseconds to seconds

    # Return a naive datetime in the local timezone (datetime.fromtimestamp
    # converts from the epoch to local time when no tz argument is given)
    return datetime.fromtimestamp(ts)

# <<< datetime helpers ===


class ObjectFieldDescriptor:
    """Base descriptor class for field descriptors.

    This is an abstract base class for all field descriptors in the module.
    """
    _name = None
    _instance_name = None

    def _get_stored_value(self, instance):
        """Returns the field value from the instance __dict__, or VALUE_NOT_SET if it is not set.

        Args:
            instance: The class instance to look up the value in.

        Returns:
            The value from __dict__ or VALUE_NOT_SET.
        """
        name = getattr(self, "_name", None)
        if name is None:
            return VALUE_NOT_SET
        return instance.__dict__.get(name, VALUE_NOT_SET)

    def _init_default_metadata(self, default=MISSING, default_factory=MISSING):
        """Initializes default value metadata.

        Stores default and default_factory, along with flags indicating
        whether they were explicitly provided.

        Args:
            default: The default value.
            default_factory: A factory used to generate the default value.
        """
        self.default = default
        self.default_factory = default_factory
        self._has_explicit_default = default is not MISSING
        self._has_explicit_default_factory = default_factory is not MISSING

    def _set_value_factory(self, factory: Callable):
        """Sets the default value factory.

        Used when no explicit value is provided.

        Args:
            factory: A factory callable.
        """
        self._value_factory = factory

    def _call_default_factory(self):
        """Calls the default value factory and returns its result.

        Returns:
            The result of calling the factory.
        """
        return self._value_factory()

    def raise_on_value_missed(self):
        """Raises ValueError if the field value is not set.

        Called when there is no default value and no value has been assigned.

        Raises:
            ValueError: If the value is missing.
        """
        raise ValueError(f"Value {self._instance_name}.{self._name} have no default value and must be set")


class FieldDescriptor:
    """Base descriptor class for scalar fields.

    Provides helper methods for storing values in the instance __dict__
    and managing default values and their factories.
    """
    _name = None
    _instance_name = None

    def _get_stored_value(self, instance):
        """Returns the field value from the instance __dict__, or VALUE_NOT_SET if it is not set.

        Args:
            instance: The class instance to look up the value in.

        Returns:
            The value from __dict__ or VALUE_NOT_SET.
        """
        name = getattr(self, "_name", None)
        if name is None:
            return VALUE_NOT_SET
        return instance.__dict__.get(name, VALUE_NOT_SET)

    def _init_default_metadata(self, default=MISSING, default_factory=MISSING):
        """Initializes default value metadata.

        Stores default and default_factory, along with flags indicating
        whether they were explicitly provided.

        Args:
            default: The default value.
            default_factory: A factory used to generate the default value.
        """
        self.default = default
        self.default_factory = default_factory
        self._has_explicit_default = default is not MISSING
        self._has_explicit_default_factory = default_factory is not MISSING

    def _set_value_factory(self, factory: Callable):
        """Sets the default value factory.

        Used when no explicit value is provided.

        Args:
            factory: A factory callable.
        """
        self._value_factory = factory

    def _call_default_factory(self):
        """Calls the default value factory and returns its result.

        Returns:
            The result of calling the factory.
        """
        return self._value_factory()

    def raise_on_value_missed(self):
        """Raises ValueError if the field value is not set.

        Called when there is no default value and no value has been assigned.

        Raises:
            ValueError: If the value is missing.
        """
        raise ValueError(f"Value {self._instance_name}.{self._name} have no default value and must be set")

    def format_value(self, value, stringify=False):
        """Default formatting method for field values during export.

        Can be overridden in subclasses to provide custom formatting.

        Args:
            value: The value to format.
            stringify: Whether to convert to string.

        Returns:
            Formatted value.
        """
        return str(value) if stringify else value


class StringWrapperObject:
    """Base class for string value objects.

    Provides method for manipulating with strings.
    """

    value: Optional[str] = None


class DateTimeDescriptor(FieldDescriptor):
    """
    Datetime descriptor
        it supports:
            - datetime string values, datetime objects
            - several dt formats
    """

    def __init__(
            self,
            default: Any = MISSING,
            default_factory: Any = MISSING,
            dt_format: str = "%Y-%m-%dT%H:%M:%S",
            alias: Optional[str] = None,
    ):
        """
        Initialize the DateTimeDescriptor with a default value or factory.

        Args:
            default: Optional default datetime value
            default_factory: Optional callable that returns a default datetime value
            dt_format: Format string for datetime serialization
            alias: Alternative name for the field in JSON
        """
        self._init_default_metadata(default=default, default_factory=default_factory)
        if callable(default_factory):
            self._set_value_factory(default_factory)
        elif default is None:
            self._set_value_factory(lambda: None)
        elif isinstance(default, datetime):
            self._set_value_factory(lambda: default)
        else:
            self._set_value_factory(self.raise_on_value_missed)
        self.dt_format = dt_format
        self.alias = alias

    def __get__(self, instance, owner):
        """
        Getter for field value - returns plain datetime object
        """
        if instance is None:
            return self
        value = self._get_stored_value(instance)
        if value is not VALUE_NOT_SET:
            return value
        return self._call_default_factory()

    def __set__(self, instance, value):
        self._instance_name = instance.__class__.__name__
        if value is None or value == "":
            value = self._call_default_factory()
        elif isinstance(value, str):
            value = parse_date_string(value, lambda: self._call_default_factory())
        elif isinstance(value, (int, float)):
            value = parse_timestamp(value, lambda: self._call_default_factory())
        elif not isinstance(value, (datetime, date)):
            value = self._call_default_factory()
        instance.__dict__[self._name] = value

    def __set_name__(self, owner, name):
        self._name = name

    def format_value(self, value, stringify=False):
        """
        Format datetime value according to dt_format.
        Override of base class method.

        Args:
            value: datetime value to format
            stringify: whether to convert to string

        Returns:
            Formatted datetime value
        """
        if value is None:
            return None
        if stringify and isinstance(value, (datetime, date)):
            return value.strftime(self.dt_format)
        return value

    @staticmethod
    def _default_time():
        """Default time: now."""
        return datetime.now()


class DateTimeStringDescriptor(FieldDescriptor):
    """
    Descriptor for the string representation of a date-time value.
    The setter accepts:
      - a datetime object,
      - a date-time string (in any format supported by DatetimeHelper),
    Stores the FORMATTED string using the format passed to the constructor (format).
    """
    def __init__(self,
                 dt_format: str,
                 default: Any = MISSING,
                 default_factory: Any = MISSING,
                 alias: Optional[str] = None):
        if not isinstance(dt_format, str) or not dt_format:
            raise ValueError("`format` parameter is required and must be a non-empty string")
        self._format = dt_format
        self._init_default_metadata(default=default, default_factory=default_factory)
        if callable(default_factory):
            self._set_value_factory(default_factory)
        elif default is None:
            self._set_value_factory(lambda: None)
        elif isinstance(default, datetime):
            self._set_value_factory(lambda: default.strftime(self._format))
        else:
            self._set_value_factory(self.raise_on_value_missed)
        self.dt_format = dt_format
        self.alias = alias

    def __set_name__(self, owner, name):
        """ Saving name of attr """
        self._name = name

    def __get__(self, instance, owner):
        """ Value getter """
        if instance is None:
            return self
        value = instance.__dict__.get(self._name)
        if isinstance(value, str):
            return value
        value = self._call_default_factory()
        if isinstance(value, (datetime, date)):
            return value.strftime(self._format)
        if isinstance(value, str):
            return value
        raise ValueError(f"Invalid value for {self._instance_name}.{self._name}: {value}")

    def __set__(self, instance, value):
        """ Value setter """
        self._instance_name = instance.__class__.__name__
        check = False
        if isinstance(value, (datetime, date)):
            # dt = DatetimeHelper.platform_time_to_with_timezone(value)
            result = value.strftime(self._format)
        elif isinstance(value, (int, float)):
            # interpret as a timestamp in seconds
            dt = get_datetime_from_timestamp_local_tz(float(value))
            result = dt.strftime(self._format)
        elif isinstance(value, str):
            # try parsing as a timestamp number
            if value.strip().isdigit() or re.fullmatch(r"[-+]?\d+(?:\.\d+)?", value.strip()):
                dt = get_datetime_from_timestamp_local_tz(float(value))
            else:
                dt = self._parse_date_string(value)
            dt = get_datetime_local_tz(dt)
            result = dt.strftime(self._format)
        else:
            result = self._call_default_factory()
            check = True

        if check:
            self._check_datetime_string_candidate(result)
        instance.__dict__[self._name] = result

    def _parse_date_string(value, default):

        for date_format in DATE_FORMATS:
            try:
                date_time_value = datetime.strptime(value, date_format)
                return date_time_value
            except ValueError as err:
                continue
        return default

    @staticmethod
    def _check_datetime_string_candidate(value: Any):
        """ Check datetime string candidate """
        if not isinstance(value, str):
            raise ValueError(f"Not a datetime string: {value}")
        for date_format in DATE_FORMATS:
            try:
                return datetime.strptime(value, date_format)
            except ValueError:
                continue
        raise ValueError(f"Unsupported datetime string: {value}")


class DateTimeTimestampDescriptor(FieldDescriptor):
    """
    Descriptor for storing a timestamp as a string.
    The setter accepts:
      - a timestamp (int/float/str),
      - a datetime,
      - a date-time string (in any format supported by DatetimeHelper).
    Output: a timestamp string compatible with datetime.fromtimestamp (seconds since the epoch).
    """
    def __init__(self, default: Optional[str] = None, default_factory: Optional[Callable] = None):
        if callable(default_factory):
            self.default_factory = default_factory
        elif default is not None:
            self.default_factory = lambda: str(default)
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

    def __set__(self, instance, value):
        def to_ts_str(dt: datetime) -> str:
            # Convert to local timezone and get seconds since the epoch
            dt_loc = get_datetime_local_tz(dt)
            try:
                ts = dt_loc.timestamp()
            except Exception:
                ts = datetime.fromtimestamp(0).timestamp()
            # store without redundant zeros: if integral, without .0
            return str(int(ts)) if abs(ts - int(ts)) < 1e-6 else str(ts)

        if value is None or value == "":
            result = self.default_factory()
        elif isinstance(value, (int, float)):
            result = str(int(value)) if isinstance(value, int) or abs(value - int(value)) < 1e-6 else str(value)
        elif isinstance(value, (datetime, date)):
            result = to_ts_str(value)
        elif isinstance(value, str):
            v = value.strip()
            try:
                if v.isdigit() or re.fullmatch(r"[-+]?\d+(?:\.\d+)?", v):
                    # already a timestamp
                    num = float(v)
                    result = str(int(num)) if abs(num - int(num)) < 1e-6 else str(num)
                else:
                    dt = get_datetime_from_timestamp_local_tz(v)
                    result = to_ts_str(dt)
            except Exception:
                result = self.default_factory()
        else:
            result = self.default_factory()
        instance.__dict__[self._name] = result


class StringWrapperDescriptor(FieldDescriptor):
    """Descriptor wrapper for string value in an object of class object_class.

    Inherited from StringValueObject. The setter accepts a string or an object of
    object_class. If a string is passed, an instance of object_class is created and
    assigned to its `value` attribute.
    """

    def __init__(
            self,
            object_class,
            default: Any = MISSING,
            default_factory: Any = MISSING,
            alias: Optional[str] = None,
    ):
        """Initializes StringWrapperDescriptor.

        Args:
            object_class: Class of the object to wrap.
            default: Default value.
            default_factory: Factory for generating default value.
            alias: Field alias.
        """
        self.object_class = object_class
        self._init_default_metadata(default=default, default_factory=default_factory)
        if callable(default_factory):
            self._set_value_factory(default_factory)
        elif default is None:
            self._set_value_factory(lambda: None)
        elif isinstance(default, object_class):
            self._set_value_factory(lambda: default)
        else:
            # by default, create an empty object
            self._set_value_factory(self._default_factory)
        self.alias = alias

    def __set_name__(self, owner, name):
        self._name = name

    def __get__(self, instance, owner):
        """Returns the field value.

        If the value is not explicitly set, returns the result of the default factory.
        When accessed through the class (instance is None), returns the descriptor itself.

        Args:
            instance: The class instance.
            owner: The owner class.

        Returns:
            The field value or the descriptor instance.
        """
        if instance is None:
            return self
        value = self._get_stored_value(instance)
        if value is not VALUE_NOT_SET:
            return value
        return self._call_default_factory()

    def __set__(self, instance, value):
        """Sets the field value.

        Accepts a string, an object_class instance, or a dict of parameters.
        If a string is passed, an object_class instance is created and the
        string is assigned to its `value` attribute.

        Args:
            instance: The class instance.
            value: The new value (string, object, or dict).
        """
        self._instance_name = instance.__class__.__name__
        if value is None:
            obj = self._call_default_factory()
        elif isinstance(value, self.object_class):
            obj = value
        elif isinstance(value, dict):
            # support for ImportJsonMixin, if a dictionary of constructor parameters is received
            obj = self.object_class(**value)
        else:
            # interpret as a string according to requirements
            obj = self.object_class()
            try:
                setattr(obj, "value", None if value is None else str(value))
            except Exception:
                # if object_class doesn't have a value field, leave it as default
                pass
        instance.__dict__[self._name] = obj

    def _default_factory(self):
        return self.object_class()


class FloatStringDescriptor(FieldDescriptor):
    """Float descriptor.

    Supports:
        - string values representing floats
        - int and float objects
        - default value or default factory
    """

    def __init__(
            self,
            default: Any = MISSING,
            default_factory: Any = MISSING,
            alias: Optional[str] = None,
    ):
        """Initialize the FloatStringDescriptor.

        Args:
            default: Optional default float value.
            default_factory: Optional callable that returns a default float value.
            alias: Optional alias for the descriptor.
        """
        self._init_default_metadata(default=default, default_factory=default_factory)
        if callable(default_factory):
            self._set_value_factory(default_factory)
        elif default is None:
            self._set_value_factory(lambda: None)
        elif isinstance(default, (int, float)):
            self._set_value_factory(lambda: float(default))
        else:
            self._set_value_factory(self.raise_on_value_missed)
        self.alias = alias

    def __get__(self, instance, owner):
        """Get the float value from the instance.

        Args:
            instance: The instance containing the attribute.
            owner: The class that owns the attribute.

        Returns:
            The float value or the default value if not set.
        """
        if instance is None:
            return self
        value = self._get_stored_value(instance)
        if value is not VALUE_NOT_SET:
            return value
        return self._call_default_factory()

    def __set__(self, instance, value: Union[str, int, float, None]):
        """Set the float value in the instance.

        Args:
            instance: The instance containing the attribute.
            value: The value to set, can be a string, int, float, or None.
        """
        self._instance_name = instance.__class__.__name__
        if value is None or value == "":
            value = self._call_default_factory()
        elif isinstance(value, str):
            try:
                value = float(value)
            except ValueError:
                value = self._call_default_factory()
        elif isinstance(value, (int, float)):
            value = float(value)
        else:
            value = self._call_default_factory()
        instance.__dict__[self._name] = value

    def __set_name__(self, owner, name):
        """Set the name of the attribute in the owner class.

        Args:
            owner: The class that owns the attribute.
            name: The name of the attribute.
        """
        self._name = name


class IntStringDescriptor(FieldDescriptor):
    """Integer descriptor.

    Supports:
        - string values representing integers
        - int and float objects
        - default value or default factory
    """

    def __init__(
            self,
            default: Any = MISSING,
            default_factory: Any = MISSING,
            alias: Optional[str] = None,
    ):
        """Initialize the IntStringDescriptor.

        Args:
            default: Optional default integer value.
            default_factory: Optional callable that returns a default integer value.
            alias: Optional alias for the descriptor.
        """
        self._init_default_metadata(default=default, default_factory=default_factory)
        if callable(default_factory):
            self._set_value_factory(default_factory)
        elif default is None:
            self._set_value_factory(lambda: None)
        elif isinstance(default, (int, float)):
            self._set_value_factory(lambda: int(default))
        else:
            self._set_value_factory(self.raise_on_value_missed)
        self.alias = alias

    def __get__(self, instance, owner):
        """Get the integer value from the instance.

        Args:
            instance: The instance containing the attribute.
            owner: The class that owns the attribute.

        Returns:
            The integer value or the default value if not set.
        """
        if instance is None:
            return self
        value = self._get_stored_value(instance)
        if value is not VALUE_NOT_SET:
            return value
        return self._call_default_factory()

    def __set__(self, instance, value: Union[str, int, float, None]):
        """Set the integer value in the instance.

        Args:
            instance: The instance containing the attribute.
            value: The value to set, can be a string, int, float, or None.
        """
        self._instance_name = instance.__class__.__name__
        if value is None or value == "":
            value = self._call_default_factory()
        elif isinstance(value, str):
            try:
                value = int(float(value))  # in case of a string like "12.0"
            except ValueError:
                value = self._call_default_factory()
        elif isinstance(value, (int, float)):
            value = int(value)
        else:
            value = self._call_default_factory()
        instance.__dict__[self._name] = value

    def __set_name__(self, owner, name):
        """Set the name of the attribute in the owner class.

        Args:
            owner: The class that owns the attribute.
            name: The name of the attribute.
        """
        self._name = name


class AnyToStringDescriptor(FieldDescriptor):
    """String descriptor.

    Supports:
        - any values convertible to string
        - None values
        - default value or default factory
    """

    def __init__(
            self,
            default: Any = MISSING,
            default_factory: Any = MISSING,
            alias: Optional[str] = None,
    ):
        """Initialize the AnyToStringDescriptor.

        Args:
            default: Optional default string value.
            default_factory: Optional callable that returns a default string value.
            alias: Optional alias for the descriptor.
        """
        self._init_default_metadata(default=default, default_factory=default_factory)
        if callable(default_factory):
            self._set_value_factory(default_factory)
        elif default is None:
            self._set_value_factory(lambda: None)
        elif isinstance(default, str):
            self._set_value_factory(lambda: default)
        else:
            self._set_value_factory(self.raise_on_value_missed)
        self.alias = alias

    def __get__(self, instance, owner):
        """Get the string value from the instance.

        Args:
            instance: The instance containing the attribute.
            owner: The class that owns the attribute.

        Returns:
            The string value or the default value if not set.
        """
        if instance is None:
            return self
        value = self._get_stored_value(instance)
        if value is not VALUE_NOT_SET:
            return value
        return self._call_default_factory()

    def __set__(self, instance, value: Any):
        """Set the string value in the instance.

        Args:
            instance: The instance containing the attribute.
            value: The value to set, will be converted to string.
        """
        self._instance_name = instance.__class__.__name__
        if value is None:
            value = self._call_default_factory()
        elif not isinstance(value, str):
            value = str(value)
        instance.__dict__[self._name] = value

    def __set_name__(self, owner, name):
        """Set the name of the attribute in the owner class.

        Args:
            owner: The class that owns the attribute.
            name: The name of the attribute.
        """
        self._name = name


class AnyToListDescriptor(FieldDescriptor):
    """List descriptor.

    Supports:
        - list, tuple, set values (converted to list)
        - None values (stored as empty list)
        - default value or default factory

    Raises:
        ValueError: For any other type.
    """

    def __init__(
            self,
            default: Any = MISSING,
            default_factory: Any = MISSING,
            alias: Optional[str] = None,
    ):
        """Initializes the list descriptor.

        Args:
            default: The default value (list, tuple, or set).
            default_factory: A factory used to generate the default value.
            alias: The field alias.
        """
        self._init_default_metadata(default=default, default_factory=default_factory)
        if callable(default_factory):
            self._set_value_factory(default_factory)
        elif default is None:
            self._set_value_factory(lambda: None)
        elif isinstance(default, (list, tuple, set)):
            _default_list = list(default)
            self._set_value_factory(lambda: list(_default_list))
        else:
            self._set_value_factory(list)
        self.alias = alias

    def __get__(self, instance, owner):
        """Returns the field value.

        If the value is not explicitly set, returns the result of the default factory.
        When accessed through the class (instance is None), returns the descriptor itself.

        Args:
            instance: The class instance.
            owner: The owner class.

        Returns:
            The field value or the descriptor instance.
        """
        if instance is None:
            return self
        value = self._get_stored_value(instance)
        if value is not VALUE_NOT_SET:
            return value
        return self._call_default_factory()

    def __set__(self, instance, value: Any):
        """Sets the field value.

        Accepts a list, tuple, or set — converts it to a list.
        None is replaced with the default value. Any other type raises ValueError.

        Args:
            instance: The class instance.
            value: The new value.

        Raises:
            ValueError: If an unsupported type is passed.
        """
        self._instance_name = instance.__class__.__name__
        if value is None:
            result = self._call_default_factory()
        elif isinstance(value, (list, tuple, set)):
            result = list(value)
        else:
            raise ValueError(
                f"{instance.__class__.__name__}.{self._name}: "
                f"expected list, tuple or set, got {type(value).__name__!r}"
            )
        instance.__dict__[self._name] = result

    def __set_name__(self, owner, name):
        """Stores the attribute name used to keep the value in the instance __dict__.

        Args:
            owner: The owner class.
            name: The attribute name.
        """
        self._name = name


class IntStringToBoolDescriptor(FieldDescriptor):
    """Bool descriptor based on int/string values.

    Supports:
        - bool values
        - int values (0 -> False, non-zero -> True)
        - string values ("0" -> False, anything else -> True)
        - default value or default factory
    """

    def __init__(
            self,
            default: Any = MISSING,
            default_factory: Any = MISSING,
            alias: Optional[str] = None,
    ):
        """Initializes the descriptor.

        Args:
            default: The default value (bool, int, or None).
            default_factory: A factory used to generate the default value.
            alias: The field alias.
        """
        self._init_default_metadata(default=default, default_factory=default_factory)
        if callable(default_factory):
            self._set_value_factory(default_factory)
        elif default is None:
            self._set_value_factory(lambda: None)
        elif isinstance(default, bool):
            self._set_value_factory(lambda: default)
        else:
            self._set_value_factory(self._default_bool)
        self.alias = alias

    def __get__(self, instance, owner):
        """Returns the field value.

        If the value is not explicitly set, returns the result of the default factory.
        When accessed through the class (instance is None), returns the descriptor itself.

        Args:
            instance: The class instance.
            owner: The owner class.

        Returns:
            The field value (bool) or the descriptor itself.
        """
        if instance is None:
            return self
        value = self._get_stored_value(instance)
        if value is not VALUE_NOT_SET:
            return value
        return self._call_default_factory()

    def __set__(self, instance, value: Union[str, int, bool, None]):
        """Sets the boolean field value.

        Accepts bool, int (0/non-zero), or a string ("0"/"false"/"no" → False, otherwise → True).
        None and the empty string are replaced with the default value.

        Args:
            instance: The class instance.
            value: The new value.
        """
        self._instance_name = instance.__class__.__name__
        if value is None or value == "":
            value = self._call_default_factory()
        elif isinstance(value, bool):
            pass  # already good
        elif isinstance(value, int):
            value = bool(value)
        elif isinstance(value, str):
            try:
                value = bool(int(value))
            except ValueError:
                # fallback: "true"/"false" style strings
                lowered = value.strip().lower()
                if lowered in ("true", "yes", "y", "on"):
                    value = True
                elif lowered in ("false", "no", "n", "off"):
                    value = False
                else:
                    value = self._call_default_factory()
        else:
            value = self._call_default_factory()
        instance.__dict__[self._name] = value

    def __set_name__(self, owner, name):
        """Stores the attribute name.

        Args:
            owner: The owner class.
            name: The attribute name.
        """
        self._name = name

    @staticmethod
    def _default_bool():
        """Default bool value: False.

        Returns:
            bool: False.
        """
        return False


class SingleObjectDescriptor(ObjectFieldDescriptor):
    """Descriptor for a field storing a single object of a given class.

    Accepts an object_class instance or a dict of constructor parameters.
    """

    def __init__(
            self,
            object_class,
            default: Any = MISSING,
            default_factory: Any = MISSING,
            alias: Optional[str] = None
    ):
        """Initialize the SingleObjectDescriptor.

        Args:
            object_class: The class of the object to be created.
            default: Optional default object.
            default_factory: Optional callable that returns a default object.
            alias: Optional alias for the descriptor.
        """
        self.object_class = object_class
        self._init_default_metadata(default=default, default_factory=default_factory)
        if callable(default_factory):
            self._set_value_factory(default_factory)
        elif default is None:
            self._set_value_factory(lambda: None)
        elif isinstance(default, object_class):
            self._set_value_factory(lambda: default)  # wrap the object in a factory
        elif self.has_required_fields():
            self._set_value_factory(self._raise_no_default)
        else:
            self._set_value_factory(self._default_factory)
        self.alias = alias

    def __get__(self, instance, owner):
        """Returns the object from the instance __dict__.

        If the value has not been set yet, initializes it via the default factory.

        Args:
            instance: The class instance.
            owner: The owner class.

        Returns:
            An object of the given class, or the descriptor itself.
        """
        if instance is None:
            return self
        # Return the value from the instance __dict__ if it exists
        if self._name not in instance.__dict__:
            instance.__dict__[self._name] = self._call_default_factory()
        return instance.__dict__[self._name]

    def __set__(self, instance, value):
        """Sets the field value.

        Accepts an object_class instance or a dict of parameters.
        None is replaced with the default value. Any other type raises ValueError.

        Args:
            instance: The class instance.
            value: The new value (object or dict).

        Raises:
            ValueError: If an unsupported type is passed.
        """
        self._instance_name = instance.__class__.__name__
        if value is None:
            value = self._call_default_factory()
        elif isinstance(value, dict):
            value = self.object_class(**value)
        elif not isinstance(value, self.object_class):
            raise ValueError(
                f"Value must be a dict or a {self.object_class.__name__} instance, not {type(value)}: {value}"
            )
        # Store the value in the instance __dict__
        instance.__dict__[self._name] = value

    def __set_name__(self, owner, name):
        """Set the name of the attribute in the owner class.

        Args:
            owner: The class that owns the attribute.
            name: The name of the attribute.
        """
        # Remember the attribute name to store the value in __dict__
        self._name = name

    def _raise_no_default(self):
        """Raises ValueError when no default value is available.

        Raises:
            ValueError: Always.
        """
        raise ValueError(f"No default value or factory for {self._name}")

    def has_required_fields(self):
        """Checks for the presence of required fields.

        Returns:
            bool: True if object_class has required fields without default values.
        """
        has_required_fields: Callable = getattr(
            self.object_class, "has_required_fields"
        )
        return has_required_fields and has_required_fields()

    def _default_factory(self):
        """Default factory.

        Returns:
            The result of calling the object_class constructor.
        """
        return self.object_class()


class JsonDumpObjectDescriptor(ObjectFieldDescriptor):
    """Descriptor for a field accepting a JSON string, a dict, or an object_class instance.

    The JSON string is deserialized into a dict and passed to the object_class constructor.
    """

    def __init__(
            self,
            object_class,
            default: Any = MISSING,
            default_factory: Any = MISSING,
            alias: Optional[str] = None
    ):
        """Initializes the descriptor.

        Args:
            object_class: The object class.
            default: The default value.
            default_factory: A factory used to generate the default value.
            alias: The field alias.
        """
        self.object_class = object_class
        if callable(default_factory):
            self._set_value_factory(default_factory)
        elif default is None:
            self._set_value_factory(lambda: None)
        elif isinstance(default, object_class):
            self._set_value_factory(lambda: default)
        else:
            self._set_value_factory(self.raise_on_value_missed)
        self.alias = alias

    def __get__(self, instance, owner):
        """Returns the object from the instance __dict__.

        If the value is not set, returns the result of the default factory.

        Args:
            instance: The class instance.
            owner: The owner class.

        Returns:
            An object of the given class, or the descriptor itself.
        """
        if instance is None:
            return self
        value = instance.__dict__.get(self._name)
        if value is not None:
            return value
        return self._call_default_factory()

    def __set__(self, instance, value):
        """Sets the field value.

        Accepts a JSON string, a dict, or an object_class instance.
        An empty/None value is replaced with the default value.

        Args:
            instance: The class instance.
            value: The new value.

        Raises:
            ValueError: If an unsupported type is passed or the string is not a JSON dict.
        """
        # Accept instance of object_class, dict, or JSON string
        self._instance_name = instance.__class__.__name__
        if not value:
            value = self._call_default_factory()
        elif isinstance(value, str):
            loaded = json.loads(value)
            if isinstance(loaded, dict):
                value = self.object_class(**loaded)
            else:
                raise ValueError(f"{loaded} is not a dict")
        elif isinstance(value, dict):
            value = self.object_class(**value)
        else:
            raise ValueError(f"{value} ({type(value)}) is not an object that "
                             f"can be used to initialize {self.object_class}")
        instance.__dict__[self._name] = value

    def __set_name__(self, owner, name):
        """Stores the attribute name.

        Args:
            owner: The owner class.
            name: The attribute name.
        """
        self._name = name

    def _default_factory(self):
        """Default factory.

        Returns:
            An object_class instance.
        """
        return self.object_class()


class ObjectListDescriptor(ObjectFieldDescriptor):
    """Descriptor for a field storing a list of objects of a given class.

    Accepts a list of object_class instances or dicts of constructor parameters.
    """

    def __init__(
            self,
            object_class,
            default: Any = MISSING,
            default_factory: Any = MISSING,
            alias: Optional[str] = None,
    ):
        """Initializes the descriptor.

        Args:
            object_class: The class of objects in the list.
            default: The default list of objects.
            default_factory: A factory returning the default list of objects.
            alias: The field alias.
        """
        self.object_class = object_class
        self._init_default_metadata(default=default, default_factory=default_factory)
        if callable(default_factory):
            self._set_value_factory(default_factory)
        elif default is None:
            self._set_value_factory(lambda: None)
        elif isinstance(default, list):
            self._set_value_factory(lambda: default)
        else:
            self._set_value_factory(self._default_factory)
        self.alias = alias

    def __get__(self, instance, owner):
        """Returns the list of objects from the instance __dict__.

        If the value is not set, returns the result of the default factory.

        Args:
            instance: The class instance.
            owner: The owner class.

        Returns:
            The list of objects, or the descriptor itself.
        """
        if instance is None:
            return self
        # return instance.__dict__.get(self._name)
        value = self._get_stored_value(instance)
        if value is not VALUE_NOT_SET:
            return value
        return self._call_default_factory()

    def __set__(self, instance, value):
        """Sets the list of objects.

        Accepts a list of object_class instances or dicts of parameters.
        None or a non-list is replaced with the default value. Dicts are
        automatically converted to object_class instances.

        Args:
            instance: The class instance.
            value: The new value.
        """
        self._instance_name = instance.__class__.__name__
        if value is None or not isinstance(value, list):
            value = self._call_default_factory()
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
        """Stores the attribute name.

        Args:
            owner: The owner class.
            name: The attribute name.
        """
        self._name = name

    @staticmethod
    def _default_factory():
        """Creates and returns an empty list.

        Returns:
            list: An empty list.
        """
        return []


class MapObjectDescriptor(ObjectFieldDescriptor):
    """Descriptor for a field storing a dict of {str: object_class}.

    Accepts a dict of object_class instances or dicts of constructor parameters.
    """

    def __init__(
            self,
            object_class,
            default: Any = MISSING,
            default_factory: Any = MISSING,
            alias: Optional[str] = None,
    ):
        """Initializes the descriptor.

        Args:
            object_class: The class of objects in the dict.
            default: The default dict of objects.
            default_factory: A factory returning the default dict.
            alias: The field alias.
        """
        self.object_class = object_class
        self._init_default_metadata(default=default, default_factory=default_factory)
        if callable(default_factory):
            self._set_value_factory(default_factory)
        elif default is None:
            self._set_value_factory(lambda: None)
        elif isinstance(default, dict):
            self._set_value_factory(lambda: default)
        else:
            self._set_value_factory(self._default_factory)
        self.alias = alias

    def __get__(self, instance, owner):
        """Returns the dict of objects from the instance __dict__.

        If the value is not set, returns the result of the default factory.

        Args:
            instance: The class instance.
            owner: The owner class.

        Returns:
            The dict of objects, or the descriptor itself.
        """
        if instance is None:
            return self
        value = self._get_stored_value(instance)
        if value is not VALUE_NOT_SET:
            return value
        return self._call_default_factory()

    def __set__(self, instance, value: Optional[Dict[str, Any]]):
        """Sets the dict of objects.

        Accepts a dict where values are object_class instances or dicts of parameters.
        A non-dict is replaced with the default value.

        Args:
            instance: The class instance.
            value: The new value.
        """
        self._instance_name = instance.__class__.__name__
        if not isinstance(value, dict):
            value = self._call_default_factory()
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
        """Stores the attribute name.

        Args:
            owner: The owner class.
            name: The attribute name.
        """
        self._name = name

    @staticmethod
    def _default_factory():
        """Creates and returns an empty dict.

        Returns:
            dict: An empty dict.
        """
        return {}


class StrUuidDescriptor(FieldDescriptor):
    """Descriptor for a UUID field.

    Supports:
        - uuid.UUID objects
        - string values (parsed into UUID)
        - a default value or factory

    On a parsing error, it may either raise an exception (if raise_on_error=True)
    or fall back to the default value.
    """

    def __init__(
            self,
            default: Any = MISSING,
            default_factory: Any = MISSING,
            alias: Optional[str] = None,
            raise_on_error: bool = False,
    ):
        """Initializes the UUID descriptor.

        Args:
            default (Any): The default value (a string or uuid.UUID).
            default_factory (Any): A factory for the default value.
            alias (Optional[str]): An alternative field name for serialization.
            raise_on_error (bool): If True, raises an exception on an invalid UUID.

        Raises:
            ValueError: On an invalid UUID format in `default` (if raise_on_error=True).
            TypeError: On a wrong UUID type in `default` (if raise_on_error=True).
        """
        self._raise_on_error = raise_on_error
        self._init_default_metadata(default=default, default_factory=default_factory)
        if callable(default_factory):
            self._set_value_factory(default_factory)
        elif default is None:
            self._set_value_factory(lambda: None)
        elif isinstance(default, uuid.UUID):
            self._set_value_factory(lambda: default)
        elif isinstance(default, str):
            try:
                parsed = uuid.UUID(default)
                self._set_value_factory(lambda: parsed)
            except (ValueError, TypeError) as err:
                if self._raise_on_error:
                    raise err
                self._set_value_factory(self.raise_on_value_missed)
        elif isinstance(default, uuid.UUID):
            self._set_value_factory(lambda: default)
        else:
            self._set_value_factory(self.raise_on_value_missed)
        self.alias = alias

    def __get__(self, instance, owner):
        """Returns the UUID value of the field.

        If the value is not set, returns the result of the default factory.

        Args:
            instance: The class instance through which access is performed.
            owner: The owner class.

        Returns:
            uuid.UUID: The field's UUID value or the factory result.
        """
        if instance is None:
            return self
        value = self._get_stored_value(instance)
        if value is not VALUE_NOT_SET:
            return value
        return self._call_default_factory()

    def __set__(self, instance, value: Union[str, uuid.UUID, None]):
        """Sets the UUID value of the field.

        Accepts a uuid.UUID or a string (parsed into a UUID). None and the
        empty string are replaced with the default value. On a parsing error,
        the behavior depends on raise_on_error.

        Args:
            instance: The class instance in which the value is set.
            value (Union[str, uuid.UUID, None]): The value to set.

        Raises:
            Exception: If an unsupported type or an invalid UUID is passed (when raise_on_error=True).
        """
        self._instance_name = instance.__class__.__name__
        if value is None or value == "":
            value = self._call_default_factory()
        elif isinstance(value, uuid.UUID):
            pass
        elif isinstance(value, str):
            try:
                value = uuid.UUID(value)
            except ValueError as err:
                if self._raise_on_error:
                    raise Exception(f"{value} is not valid UUID").with_traceback(
                        err.__traceback__
                    )
                value = self._call_default_factory()
            except TypeError as err:
                if self._raise_on_error:
                    raise Exception(
                        f"{type(value)} is not valid type for UUID "
                    ).with_traceback(err.__traceback__)
                value = self._call_default_factory()
            except Exception as err:
                if self._raise_on_error:
                    raise Exception(
                        f"Unexpected exception with value: {str(value)} {err}"
                    ).with_traceback(err.__traceback__)
                value = self._call_default_factory()
        elif isinstance(
                value, type(self)
        ):  # no default value provided — a descriptor instance is passed instead
            # No value passed and no default available
            if self._raise_on_error and self.default_factory is MISSING:
                raise Exception(f"Unsupported type: {str(value)}")
            value = self._call_default_factory()
        else:
            raise Exception(f"Unsupported type {value}: {type(value)}")
        instance.__dict__[self._name] = value

    def __set_name__(self, owner, name):
        """Stores the attribute name used to store the value.

        Args:
            owner: The owner class.
            name (str): The attribute name.
        """
        self._name = name


class StringBoolDescriptor(FieldDescriptor):
    """Descriptor for a boolean field.

    Accepts bool, int, or a string (including "true"/"false", "1"/"0").
    Stores the value as a bool.
    """
    def __init__(self,
                 default: Any = MISSING,
                 default_factory: Any = MISSING,
                 alias: Optional[str] = None):
        """Initializes the boolean field descriptor.

        Args:
            default (Any): The default value.
            default_factory (Any): A factory for the default value.
            alias (Optional[str]): An alternative field name for serialization.
        """
        self._init_default_metadata(default=default, default_factory=default_factory)
        if callable(default_factory):
            self._set_value_factory(default_factory)
        elif default is None:
            self._set_value_factory(lambda: None)
        elif isinstance(default, (bool, int)):
            self._set_value_factory(lambda: int(bool(default)))
        else:
            self._set_value_factory(self.raise_on_value_missed)
        self.alias = alias

    def __set_name__(self, owner, name):
        """Stores the attribute name used to store the value.

        Args:
            owner: The owner class.
            name (str): The attribute name.
        """
        self._name = name

    def __get__(self, instance, owner):
        """Returns the boolean value of the field.

        If the value is not set, returns the result of the default factory.

        Args:
            instance: The class instance.
            owner: The owner class.

        Returns:
            bool: The boolean value of the field.
        """
        if instance is None:
            return self
        value = instance.__dict__.get(self._name)
        if value is not None:
            return value
        return self._call_default_factory()

    def __set__(self, instance, value: Union[bool, int, None]):
        """Sets the boolean value of the field.

        Accepts a bool, a string ("1"/"0", "true"/"false"), or None.
        None is replaced with the default value. Stores the value as a bool.

        Args:
            instance: The class instance.
            value (Union[bool, int, str, None]): The value to set.
        """
        self._instance_name = instance.__class__.__name__
        # Allow ImportJsonMixin to pass whole kwargs
        if value is None:
            result = self._call_default_factory()
        elif isinstance(value, bool):
            result = value
        elif isinstance(value, str):
            try:
                if value.isdigit():     # "1", "0"
                    result = bool(int(value))
                else:
                    value = json.loads(value)  # true/false
                    result = bool(value)
            except ValueError:
                result = bool(value)    # any
        else:
            # Only bool/int are allowed per requirements
            result = self._call_default_factory()
        instance.__dict__[self._name] = result


class BoolToIntDescriptor(FieldDescriptor):
    """Descriptor for a boolean field that coerces the value to int (0 or 1).

    Accepts bool or int; any non-zero int becomes 1, zero becomes 0.
    """

    def __init__(
            self,
            default: Any = MISSING,
            default_factory: Any = MISSING,
            alias: Optional[str] = None,
    ):
        """Initializes the descriptor.

        Args:
            default (Any): The default value (bool or int, coerced to int).
            default_factory (Any): A factory for the default value.
            alias (Optional[str]): An alternative field name for serialization.
        """
        self._init_default_metadata(default=default, default_factory=default_factory)
        if callable(default_factory):
            self._set_value_factory(default_factory)
        elif default is None:
            self._set_value_factory(lambda: None)
        elif isinstance(default, (bool, int)):
            self._set_value_factory(lambda: int(bool(default)))
        else:
            self._set_value_factory(self.raise_on_value_missed)
        self.alias = alias

    def __set_name__(self, owner, name):
        """Stores the attribute name used to store the value.

        Args:
            owner: The owner class.
            name (str): The attribute name.
        """
        self._name = name

    def __get__(self, instance, owner):
        """Returns the field value as an int (0 or 1).

        If the value is not set, returns the result of the default factory.

        Args:
            instance: The class instance.
            owner: The owner class.

        Returns:
            int: The field value (0 or 1).
        """
        if instance is None:
            return self
        value = self._get_stored_value(instance)
        if value is not VALUE_NOT_SET:
            return value
        return self._call_default_factory()

    def __set__(self, instance, value: Union[bool, int, None]):
        """Sets the field value as an int.

        Accepts bool or int; any non-zero int becomes 1.
        None is replaced with the default value.

        Args:
            instance: The class instance.
            value (Union[bool, int, None]): The value to set.
        """
        self._instance_name = instance.__class__.__name__
        # Allow ImportJsonMixin to pass whole kwargs
        if value is None:
            result = self._call_default_factory()
        elif isinstance(value, bool):
            result = int(value)
        elif isinstance(value, int):
            result = 1 if value != 0 else 0
        else:
            # Only bool/int are allowed per requirements
            result = self._call_default_factory()
        instance.__dict__[self._name] = result


class ListOfIntDescriptor(FieldDescriptor):
    """Descriptor for a field storing a list of integers (int).

    Accepts a list of any values coercible to int; non-coercible items are skipped.
    Priority: explicit value > factory > default.
    """

    def __init__(
            self,
            default: Any = MISSING,
            default_factory: Any = MISSING,
            alias: Optional[str] = None,
    ):
        """Initializes the list-of-int descriptor.

        Args:
            default (Any): The default list of ints.
            default_factory (Any): A factory for the default value.
            alias (Optional[str]): An alternative field name for serialization.
        """
        self._init_default_metadata(default=default, default_factory=default_factory)
        if callable(default_factory):
            self._set_value_factory(default_factory)
        elif default is None:
            self._set_value_factory(lambda: None)
        elif isinstance(default, list):
            # copy to avoid shared list
            self._set_value_factory(
                lambda: [int(x) for x in default if self._can_int(x)]
            )
        else:
            self._set_value_factory(self.raise_on_value_missed)
        self.alias = alias

    @staticmethod
    def _can_int(x: Any) -> bool:
        """Checks whether the value x can be coerced to int.

        Args:
            x (Any): The value to check.

        Returns:
            bool: True if x can be coerced to int, False otherwise.
        """
        try:
            int(str(x))
            return True
        except Exception:
            return False

    def __set_name__(self, owner, name):
        """Stores the attribute name used to store the value.

        Args:
            owner: The owner class.
            name (str): The attribute name.
        """
        self._name = name

    def __get__(self, instance, owner):
        """Returns the list of ints.

        If the value is not set, returns the result of the default factory.

        Args:
            instance: The class instance.
            owner: The owner class.

        Returns:
            List[int]: The list of integers.
        """
        if instance is None:
            return self
        value = self._get_stored_value(instance)
        if value is not VALUE_NOT_SET:
            return value
        return self._call_default_factory()

    def __set__(self, instance, value: Union[List[Any], None]):
        """Sets the list of ints.

        Non-coercible items are skipped. A non-list is replaced with the default value.

        Args:
            instance: The class instance.
            value (Union[List[Any], None]): The value to set.
        """
        self._instance_name = instance.__class__.__name__
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
            result: List[int] = self._call_default_factory()
        instance.__dict__[self._name] = result


class ListOfUuidDescriptor(FieldDescriptor):
    """Descriptor for a field storing a list of UUIDs (uuid.UUID).

    Accepts a list of uuid.UUID objects or strings (parsed into UUIDs).
    Invalid items are skipped, or raise an exception when raise_on_error=True.
    """

    def __init__(
            self,
            default: Any = MISSING,
            default_factory: Any = MISSING,
            alias: Optional[str] = None,
            raise_on_error=False,
    ):
        """Initializes the list-of-UUID descriptor.

        Args:
            default (Any): The default list of UUIDs or strings.
            default_factory (Any): A factory for the default value.
            alias (Optional[str]): An alternative field name for serialization.
            raise_on_error (bool): If True, raises an exception on an invalid UUID.
        """
        self._raise_on_error = raise_on_error
        self._init_default_metadata(default=default, default_factory=default_factory)
        if callable(default_factory):
            self._set_value_factory(default_factory)
        elif default is None:
            self._set_value_factory(lambda: None)
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

            self._set_value_factory(_df)
        else:
            self._set_value_factory(self.raise_on_value_missed)
        self.alias = alias

    def __set_name__(self, owner, name):
        """Stores the attribute name used to store the value.

        Args:
            owner: The owner class.
            name (str): The attribute name.
        """
        self._name = name

    def __get__(self, instance, owner):
        """Returns the list of UUIDs.

        If the value is not set, returns the result of the default factory.

        Args:
            instance: The class instance.
            owner: The owner class.

        Returns:
            List[uuid.UUID]: The list of UUID objects.
        """
        if instance is None:
            return self
        value = self._get_stored_value(instance)
        if value is not VALUE_NOT_SET:
            return value
        return self._call_default_factory()

    def __set__(self, instance, value: Union[List[Union[str, uuid.UUID, Any]], None]):
        """Sets the list of UUIDs.

        Accepts a list of uuid.UUID objects or strings (parsed into UUIDs).
        Invalid items are skipped, or raise an exception when raise_on_error=True.
        None and non-list values are replaced with the default value.

        Args:
            instance: The class instance.
            value (Union[List[Any], None]): The value to set.

        Raises:
            Exception: On an invalid UUID when raise_on_error=True.
        """
        self._instance_name = instance.__class__.__name__
        if value is None:
            result: List[uuid.UUID] = self._call_default_factory()
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
                            raise Exception(
                                f"Invalid UUID value: {item}"
                            ).with_traceback(err.__traceback__)
                        # skip invalid
        else:
            # Only list is accepted
            result = self._call_default_factory()
        instance.__dict__[self._name] = result


class ListOfStringDescriptor(FieldDescriptor):
    """Descriptor for a field storing a list of strings.

    Accepts a list of strings or builtin non-iterable types (int, float, bool, complex),
    coercing them to str. Iterable and non-builtin types are skipped.
    """
    def __init__(self,
                 default: Any = MISSING,
                 default_factory: Any = MISSING,
                 alias: Optional[str] = None):
        """Initializes the list-of-strings descriptor.

        Args:
            default (Any): The default list of values.
            default_factory (Any): A factory for the default value.
            alias (Optional[str]): An alternative field name for serialization.
        """
        if callable(default_factory):
            self._set_value_factory(default_factory)
        elif default is None:
            self._set_value_factory(lambda: None)
        elif isinstance(default, list):
            self._set_value_factory(lambda: [str(x) for x in default
                                             if self._is_builtin_non_iterable(x) or isinstance(x, str)])
        else:
            self._set_value_factory(self.raise_on_value_missed)
        self.alias = alias

    def __set_name__(self, owner, name):
        """Stores the attribute name used to store the value.

        Args:
            owner: The owner class.
            name (str): The attribute name.
        """
        self._name = name

    def __get__(self, instance, owner):
        """Returns the list of strings.

        If the value is not set, returns the result of the default factory.

        Args:
            instance: The class instance.
            owner: The owner class.

        Returns:
            List[str]: The list of strings.
        """
        if instance is None:
            return self
        value = instance.__dict__.get(self._name)
        if value is not None:
            return value
        return self._call_default_factory()

    @staticmethod
    def _is_builtin_non_iterable(x: Any) -> bool:
        """Checks whether x is a builtin non-iterable type.

        Such types include int, float, bool, and complex. Strings, collections,
        and other iterable types return False.

        Args:
            x (Any): The value to check.

        Returns:
            bool: True if x is a builtin non-iterable type, False otherwise.
        """
        # Consider common builtin, non-iterable types: int, float, bool, complex, bytes? (bytes is iterable)
        # We'll treat numbers and bool as non-iterable; exclude collections and str/bytes/bytearray.
        non_iterable_types = (int, float, bool, complex)
        if isinstance(x, non_iterable_types):
            return True
        # Exclude iterables
        try:
            iter(x)
            return False
        except Exception:
            # Not iterable; if it's not a builtin simple object, we still exclude by default
            # Accept simple builtins like None as well
            return type(x).__module__ == 'builtins'

    def __set__(self, instance, value: Union[List[Any], None]):
        """Sets the list of strings.

        Strings are stored as is; builtin non-iterable types are coerced to str.
        Iterable and non-builtin types are skipped. A non-list is replaced
        with the default value.

        Args:
            instance: The class instance.
            value (Union[List[Any], None]): The value to set.
        """
        self._instance_name = instance.__class__.__name__
        if isinstance(value, list):
            result = []
            for item in value:
                if isinstance(item, str):
                    result.append(item)
                elif self._is_builtin_non_iterable(item):
                    result.append(str(item))
                else:
                    # skip items that are iterable or not builtin
                    pass
        else:
            # Only list is accepted
            result: List[str] = self._call_default_factory()
        instance.__dict__[self._name] = result
