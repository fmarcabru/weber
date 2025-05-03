import pytest
from src.utils.utils import parse_temperatures

def test_parse_temperatures_normal():
    # Test normal temperature values
    # 25.0°C = (77°F * 10) = 770 in little endian
    # 30.0°C = (86°F * 10) = 860 in little endian
    data = bytearray([0x0A, 0x03, 0x5C, 0x03, 0xFF, 0xFF, 0xFF, 0xFF])
    temps = parse_temperatures(data)
    assert len(temps) == 4
    assert abs(temps[0] - 25.0) < 0.1
    assert abs(temps[1] - 30.0) < 0.1
    assert temps[2] is None
    assert temps[3] is None

def test_parse_temperatures_all_disconnected():
    # Test all probes disconnected (0xFFFF)
    data = bytearray([0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
    temps = parse_temperatures(data)
    assert len(temps) == 4
    assert temps[0] is None
    assert temps[1] is None
    assert temps[2] is None
    assert temps[3] is None

def test_parse_temperatures_alternate_disconnect():
    # Test alternate disconnect value (0xF830)
    data = bytearray([0x30, 0xF8, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
    temps = parse_temperatures(data)
    assert len(temps) == 4
    assert temps[0] is None
    assert temps[1] is None
    assert temps[2] is None
    assert temps[3] is None

def test_parse_temperatures_short_data():
    # Test with less than 4 probe values
    data = bytearray([0x0A, 0x03, 0x5C, 0x03])
    temps = parse_temperatures(data)
    assert len(temps) == 4
    assert abs(temps[0] - 25.0) < 0.1
    assert abs(temps[1] - 30.0) < 0.1
    assert temps[2] is None
    assert temps[3] is None 