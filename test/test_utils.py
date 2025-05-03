import pytest
from src.utils import parse_temperatures

def test_parse_temperatures_normal():
    # Test normal temperature values
    # 25.0°C = (77°F * 10) = 770 in little endian
    # 30.0°C = (86°F * 10) = 860 in little endian
    data = bytearray([0x44, 0x00, 0x00])
    print(f"len data is {len(data)}")
    print(data.hex())
    assert parse_temperatures(data) == 68


def test_parse_temperatures_all_disconnected():
    # Test all probes disconnected (0xFFFF)
    data = bytearray([0x30,0xf8,0x00])
    assert parse_temperatures(data) is None

