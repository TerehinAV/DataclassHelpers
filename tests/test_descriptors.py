from datetime import datetime
import uuid

import pytest

from descriptors import (
    AnyToListDescriptor,
    AnyToStringDescriptor,
    BoolToIntDescriptor,
    DateTimeDescriptor,
    DateTimeStringDescriptor,
    DateTimeTimestampDescriptor,
    FloatStringDescriptor,
    IntStringDescriptor,
    IntStringToBoolDescriptor,
    JsonDumpObjectDescriptor,
    ListOfIntDescriptor,
    ListOfStringDescriptor,
    ListOfUuidDescriptor,
    MapObjectDescriptor,
    ObjectListDescriptor,
    SingleObjectDescriptor,
    StrUuidDescriptor,
    StringBoolDescriptor,
    StringWrapperDescriptor,
    StringWrapperObject,
)


class SampleStringWrapper(StringWrapperObject):
    def __init__(self, value=None, label="default"):
        self.value = value
        self.label = label


class ChildObject:
    def __init__(self, name="child"):
        self.name = name

    @classmethod
    def has_required_fields(cls):
        return False


class RequiredChildObject:
    def __init__(self, required):
        self.required = required

    @classmethod
    def has_required_fields(cls):
        return True


class DateTimeHolder:
    value = DateTimeDescriptor(
        default_factory=lambda: datetime(2000, 1, 1, 0, 0, 0), dt_format="%Y-%m-%d"
    )


class StringWrapperHolder:
    value = StringWrapperDescriptor(
        SampleStringWrapper,
        default_factory=lambda: SampleStringWrapper(value="fallback", label="factory"),
    )


class FloatHolder:
    value = FloatStringDescriptor(default=1.25)


class FloatNoDefaultHolder:
    value = FloatStringDescriptor()


class IntHolder:
    value = IntStringDescriptor(default=3)


class IntNoDefaultHolder:
    value = IntStringDescriptor()


class IntToBoolHolder:
    value = IntStringToBoolDescriptor(default=True)


class IntToBoolDefaultHolder:
    value = IntStringToBoolDescriptor()


class SingleObjectDefaultHolder:
    value = SingleObjectDescriptor(ChildObject)


class ObjectListHolder:
    value = ObjectListDescriptor(ChildObject)


class MapObjectHolder:
    value = MapObjectDescriptor(ChildObject)


DEFAULT_UUID = uuid.UUID("12345678-1234-5678-1234-567812345678")


class UuidHolder:
    value = StrUuidDescriptor(default=DEFAULT_UUID)


class UuidNoDefaultHolder:
    value = StrUuidDescriptor()


class UuidRaiseHolder:
    value = StrUuidDescriptor(default=DEFAULT_UUID, raise_on_error=True)


class BoolToIntHolder:
    value = BoolToIntDescriptor(default=0)


class BoolToIntNoDefaultHolder:
    value = BoolToIntDescriptor()


class ListOfIntHolder:
    value = ListOfIntDescriptor(default=["1", 2, "bad"])


class ListOfIntNoDefaultHolder:
    value = ListOfIntDescriptor()


class ListOfUuidHolder:
    value = ListOfUuidDescriptor(
        default=[DEFAULT_UUID, str(DEFAULT_UUID), "not-a-uuid"]
    )


class ListOfUuidRaiseHolder:
    value = ListOfUuidDescriptor(default=[DEFAULT_UUID], raise_on_error=True)


def test_datetime_descriptor_get_without_set_returns_default_datetime_not_wrapper():
    obj = DateTimeHolder()
    value = obj.value
    assert isinstance(value, datetime)
    assert value == datetime(2000, 1, 1, 0, 0, 0)


def test_string_wrapper_descriptor_supports_string_dict_object_and_default():
    obj = StringWrapperHolder()

    assert isinstance(obj.value, SampleStringWrapper)
    assert obj.value.value == "fallback"

    obj.value = "hello"
    assert isinstance(obj.value, SampleStringWrapper)
    assert obj.value.value == "hello"

    direct = SampleStringWrapper(value="direct", label="x")
    obj.value = direct
    assert obj.value is direct

    obj.value = {"value": "from-dict", "label": "mapped"}
    assert isinstance(obj.value, SampleStringWrapper)
    assert obj.value.value == "from-dict"
    assert obj.value.label == "mapped"

    obj.value = False
    assert isinstance(obj.value, SampleStringWrapper)
    assert obj.value.value == "False"


def test_float_string_descriptor_coercion_and_default_fallback():
    obj = FloatHolder()
    assert obj.value == 1.25

    obj.value = "2.5"
    assert obj.value == 2.5

    obj.value = 7
    assert obj.value == 7.0

    obj.value = "bad"
    assert obj.value == 1.25


def test_float_string_descriptor_without_default_raises_on_get_and_invalid_set():
    obj = FloatNoDefaultHolder()
    with pytest.raises(ValueError):
        _ = obj.value

    with pytest.raises(ValueError):
        obj.value = "bad"


def test_int_string_descriptor_coercion_and_default_fallback():
    obj = IntHolder()
    assert obj.value == 3

    obj.value = "12.0"
    assert obj.value == 12

    obj.value = 9.9
    assert obj.value == 9

    obj.value = "bad"
    assert obj.value == 3


def test_int_string_descriptor_without_default_raises_on_get_and_invalid_set():
    obj = IntNoDefaultHolder()
    with pytest.raises(ValueError):
        _ = obj.value

    with pytest.raises(ValueError):
        obj.value = "bad"


def test_int_string_to_bool_descriptor_handles_numbers_and_text_values():
    obj = IntToBoolDefaultHolder()
    assert obj.value is False

    obj.value = 0
    assert obj.value is False

    obj.value = 2
    assert obj.value is True

    obj.value = "0"
    assert obj.value is False

    obj.value = "yes"
    assert obj.value is True

    obj.value = "off"
    assert obj.value is False


def test_int_string_to_bool_descriptor_invalid_string_uses_default_factory_value():
    obj = IntToBoolHolder()
    obj.value = "not-bool"
    assert obj.value is True


def test_single_object_descriptor_raises_for_invalid_type_and_uses_default_for_falsey():
    obj = SingleObjectDefaultHolder()
    obj.value = None
    assert isinstance(obj.value, ChildObject)
    assert obj.value.name == "child"

    with pytest.raises(
        ValueError, match="Value must be a dict or a ChildObject instance"
    ):
        obj.value = "wrong"


def test_object_list_descriptor_converts_dicts_keeps_objects_skips_invalids():
    obj = ObjectListHolder()
    assert obj.value == []

    existing = ChildObject(name="existing")
    obj.value = [{"name": "first"}, existing, "skip-me"]

    assert len(obj.value) == 2
    assert isinstance(obj.value[0], ChildObject)
    assert obj.value[0].name == "first"
    assert obj.value[1] is existing


def test_map_object_descriptor_converts_values_and_ignores_invalid_entries():
    obj = MapObjectHolder()
    assert obj.value == {}

    existing = ChildObject(name="ready")
    obj.value = {
        "a": {"name": "mapped"},
        "b": existing,
        "c": "skip-me",
    }

    assert set(obj.value.keys()) == {"a", "b"}
    assert isinstance(obj.value["a"], ChildObject)
    assert obj.value["a"].name == "mapped"
    assert obj.value["b"] is existing

    obj.value = "not-a-dict"
    assert obj.value == {}


def test_str_uuid_descriptor_parses_valid_string_and_uses_default_on_invalid():
    obj = UuidHolder()
    assert obj.value == DEFAULT_UUID

    another_uuid = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    obj.value = another_uuid
    assert obj.value == uuid.UUID(another_uuid)

    obj.value = "invalid-uuid"
    assert obj.value == DEFAULT_UUID


def test_str_uuid_descriptor_raise_on_error_and_unsupported_type():
    obj = UuidRaiseHolder()
    with pytest.raises(Exception, match="is not valid UUID"):
        obj.value = "invalid-uuid"

    obj_no_raise = UuidHolder()
    with pytest.raises(Exception, match="Unsupported type"):
        obj_no_raise.value = 123


def test_str_uuid_descriptor_without_default_raises_when_missing_or_falsey_set():
    obj = UuidNoDefaultHolder()
    with pytest.raises(ValueError):
        _ = obj.value

    with pytest.raises(ValueError):
        obj.value = None


def test_bool_to_int_descriptor_coercion_and_default_behavior():
    obj = BoolToIntHolder()
    assert obj.value == 0

    obj.value = True
    assert obj.value == 1

    obj.value = False
    assert obj.value == 0

    obj.value = 15
    assert obj.value == 1

    obj.value = 0
    assert obj.value == 0

    obj.value = "bad"
    assert obj.value == 0


def test_bool_to_int_descriptor_without_default_raises_on_get_and_invalid_set():
    obj = BoolToIntNoDefaultHolder()
    with pytest.raises(ValueError):
        _ = obj.value

    with pytest.raises(ValueError):
        obj.value = "bad"


def test_list_of_int_descriptor_coercion_and_default_fallback():
    obj = ListOfIntHolder()
    assert obj.value == [1, 2]

    obj.value = ["10", 3.7, "bad", -2]
    assert obj.value == [10, 3, -2]

    obj.value = "not-a-list"
    assert obj.value == [1, 2]


def test_list_of_int_descriptor_without_default_raises_on_get_and_non_list_set():
    obj = ListOfIntNoDefaultHolder()
    with pytest.raises(ValueError):
        _ = obj.value

    with pytest.raises(ValueError):
        obj.value = None


def test_list_of_uuid_descriptor_coercion_and_invalid_skip():
    obj = ListOfUuidHolder()
    assert obj.value == [DEFAULT_UUID, DEFAULT_UUID]

    valid_2 = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    obj.value = [str(valid_2), DEFAULT_UUID, "bad"]
    assert obj.value == [valid_2, DEFAULT_UUID]


def test_list_of_uuid_descriptor_raise_on_error_for_invalid_item():
    obj = ListOfUuidRaiseHolder()
    with pytest.raises(Exception, match="Invalid UUID value"):
        obj.value = ["bad"]


class DateTimeStringHolder:
    value = DateTimeStringDescriptor(dt_format="%Y-%m-%d", default=datetime(2024, 1, 2))


class DateTimeTimestampHolder:
    value = DateTimeTimestampDescriptor(default="0")


class DateTimeTimestampsHolder:
    value = DateTimeDescriptor(
        default_factory=lambda: datetime(2000, 1, 1), dt_format="%Y-%m-%d"
    )


class JsonDumpHolder:
    value = JsonDumpObjectDescriptor(
        ChildObject, default=ChildObject(name="fallback")
    )


class StringBoolHolder:
    value = StringBoolDescriptor(default=False)


class ListOfStringHolder:
    value = ListOfStringDescriptor(default=["a", 1, ["skip"]])


class AnyToStringHolder:
    value = AnyToStringDescriptor(default="fallback")


class AnyToListHolder:
    value = AnyToListDescriptor(default=[1, 2])


def test_date_time_string_descriptor_formats_datetime_and_timestamps():
    obj = DateTimeStringHolder()
    assert obj.value == "2024-01-02"

    obj.value = datetime(2024, 2, 3, 4, 5)
    assert obj.value == "2024-02-03"

    expected = datetime.fromtimestamp(1704160800).strftime("%Y-%m-%d")
    obj.value = 1704160800
    assert obj.value == expected

    obj.value = str(1704160800)
    assert obj.value == expected


def test_date_time_string_descriptor_parses_known_formats_and_falls_back():
    obj = DateTimeStringHolder()
    obj.value = "2024-01-02T10:00:00"
    assert obj.value == "2024-01-02"

    obj.value = "not-a-date"
    assert obj.value == "2024-01-02"


def test_date_time_timestamp_descriptor_converts_inputs_to_ts_strings():
    obj = DateTimeTimestampHolder()
    assert obj.value == "0"

    obj.value = 1704160800
    assert obj.value == "1704160800"

    obj.value = 1704160800.5
    assert obj.value == "1704160800.5"

    obj.value = "1704160800"
    assert obj.value == "1704160800"

    expected = str(int(datetime(2024, 1, 2, 3, 20).astimezone().timestamp()))
    obj.value = datetime(2024, 1, 2, 3, 20)
    assert obj.value == expected

    obj.value = "2024-01-02T03:20:00"
    assert obj.value == "0"


def test_datetime_descriptor_accepts_timestamps_seconds_and_milliseconds():
    obj = DateTimeTimestampsHolder()
    obj.value = 1704160800
    assert obj.value == datetime.fromtimestamp(1704160800)

    obj.value = 1704160800000
    assert obj.value == datetime.fromtimestamp(1704160800)

    obj.value = "1704160800"
    assert obj.value == datetime.fromtimestamp(1704160800)


def test_datetime_descriptor_unparseable_string_falls_back_to_default():
    obj = DateTimeTimestampsHolder()
    obj.value = "not-a-date"
    assert obj.value == datetime(2000, 1, 1)


def test_json_dump_descriptor_accepts_json_string_dict_and_instance():
    obj = JsonDumpHolder()
    assert obj.value.name == "fallback"

    obj.value = '{"name": "from-json"}'
    assert isinstance(obj.value, ChildObject)
    assert obj.value.name == "from-json"

    obj.value = {"name": "from-dict"}
    assert obj.value.name == "from-dict"

    obj.value = None
    assert obj.value.name == "fallback"


def test_json_dump_descriptor_rejects_non_dict_json_and_types():
    obj = JsonDumpHolder()
    with pytest.raises(ValueError, match="is not a dict"):
        obj.value = "[1, 2]"

    with pytest.raises(ValueError, match="is not an object"):
        obj.value = 123


def test_string_bool_descriptor_parses_bool_strings_and_json_values():
    obj = StringBoolHolder()
    assert not obj.value

    obj.value = True
    assert obj.value is True

    obj.value = "1"
    assert obj.value is True

    obj.value = "0"
    assert not obj.value

    obj.value = "true"
    assert obj.value is True

    obj.value = "false"
    assert not obj.value

    obj.value = "not-json"
    assert obj.value is True

    obj.value = None
    assert not obj.value


def test_list_of_string_descriptor_keeps_strings_and_coerces_builtin_scalars():
    obj = ListOfStringHolder()
    assert obj.value == ["a", "1"]

    obj.value = ["x", 2, 3.5, True, [1], {"k": 1}, None]
    assert obj.value == ["x", "2", "3.5", "True", "None"]

    obj.value = "not-a-list"
    assert obj.value == ["a", "1"]


def test_any_to_string_descriptor_converts_values_to_str():
    obj = AnyToStringHolder()
    assert obj.value == "fallback"

    obj.value = 42
    assert obj.value == "42"

    obj.value = None
    assert obj.value == "fallback"


def test_any_to_list_descriptor_converts_collections_and_validates():
    obj = AnyToListHolder()
    assert obj.value == [1, 2]

    obj.value = (3, 4)
    assert obj.value == [3, 4]

    obj.value = {5}
    assert obj.value == [5]

    obj.value = None
    assert obj.value == [1, 2]

    with pytest.raises(ValueError, match="expected list, tuple or set"):
        obj.value = "nope"
