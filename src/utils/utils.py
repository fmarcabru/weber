import subprocess
from dataclasses import dataclass
import time
from .config import Config
import asyncio
from bleak import BleakClient, BleakError


@dataclass
class ConnectionStatus:
    last_temp_time: float
    last_disconnect_time: float
    last_alert_time: float
    connected_once: bool
    retry_count: int = 0


def parse_temperatures(data: bytearray):
    """Parse temperature data from iGrill2 probes.
    Each probe temperature is 3 bytes, little endian.
    first 2 bytes is the temp, the 3rd one not sure.
    Value 0x30f8 indicates no probe connected.
    Temperatures are in Fahrenheit.
    """
    print(f"Raw temperature data: {data.hex()}")

    if str(data.hex()) == "30f800":
        print("probe not connected")
        return None 

    return int.from_bytes(data[:2], byteorder='little')


# Edge Case Handling
def reset_ble_adapter():
    print("[ALERT] Restarting BLE adapter (hci0)...")
    subprocess.run(["sudo", "hciconfig", "hci0", "down"])
    subprocess.run(["sudo", "hciconfig", "hci0", "up"])


async def pair_device(device_name: str):
    """Pair with the iGrill2 device using bluetoothctl."""
    print("inside pair_device")
    print(f"Attempting to pair with {device_name}...")

    # First, remove any existing pairing
    subprocess.run(["bluetoothctl", "remove", device_name])
    await asyncio.sleep(2)

    # Power on and start scanning
    subprocess.run(["bluetoothctl", "power", "on"])
    subprocess.run(["bluetoothctl", "scan", "on"])
    await asyncio.sleep(5)  # Give more time for scanning

    # Find the device address
    result = subprocess.run(["bluetoothctl", "devices"], capture_output=True, text=True)

    # Extract device address
    device_address = None
    for line in result.stdout.split("\n"):
        if device_name in line:
            device_address = line.split()[1]
            break

    if not device_address:
        print(f"Could not find device address for {device_name}")
        return False

    # Pair and trust the device
    subprocess.run(["bluetoothctl", "agent", "on"])
    subprocess.run(["bluetoothctl", "default-agent"])
    subprocess.run(["bluetoothctl", "pair", device_address])
    await asyncio.sleep(2)
    subprocess.run(["bluetoothctl", "trust", device_address])
    await asyncio.sleep(2)
    subprocess.run(["bluetoothctl", "connect", device_address])

    # Give the system time to complete the pairing process
    await asyncio.sleep(5)
    print(f"Successfully paired with {device_name}")
    return True


async def connect_with_retry(
    device, config: Config, max_retries: int = 3
) -> BleakClient:
    """Attempt to connect to the device with retries."""
    print("inside connect_with_retry")
    for attempt in range(max_retries):
        try:
            print(f"Connection attempt {attempt + 1}/{max_retries}...")
            # Create client with specific connection options
            client = BleakClient(
                device,
                timeout=config.connection_timeout_sec,
                disconnected_callback=lambda client: print("Disconnected from device"),
            )

            # Try to connect with a specific connection method
            print("before client.connect")
            await client.connect(
                use_cached=False,  # Don't use cached connections
                timeout=config.connection_timeout_sec,
            )
            print("after client.connect")

            # Verify connection
            if not client.is_connected:
                raise BleakError("Failed to establish connection")

            return client

        except Exception as e:
            print(f"Connection attempt {attempt + 1} failed: {str(e)}")
            if attempt < max_retries - 1:
                print(f"Retrying in {config.scan_interval_sec} seconds...")
                await asyncio.sleep(config.scan_interval_sec)
            else:
                raise


async def print_services(client: BleakClient):
    """Print all available services and characteristics."""
    print("\nAvailable Services and Characteristics:")
    # for service in client.services:
    #     print(f"\nService: {service.uuid}")
    #     for char in service.characteristics:
    #         print(f"  Characteristic: {char.uuid}")
    #         print(f"    Properties: {char.properties}")


def handle_notification(
    pos: int,
    data: bytearray,
    status: ConnectionStatus,
    config: Config,
    characteristic_uuid: str = None,
):
    print(f"\nReceived notification from {pos} characteristic: {characteristic_uuid}")
    temp = parse_temperatures(data)
    now = time.time()

    # Temperature out of range alert
    if temp is not None:  # Only check connected probes
        if temp < config.min_temp_c or temp > config.max_temp_c:
            if now - status.last_alert_time > config.alert_interval_sec:
                alert_message = (
                    f"[ALERT] Probe {pos} temperature out of range: {temp:.1f}°C"
                )
                print(alert_message)
                status.last_alert_time = now

    status.last_temp_time = now

    # Log if enabled
    if config.log_temperature_values:
        temp_str = f"Probe: {temp:.1f}°F" if temp is not None else f"Probe: Not Connected"

        print(f"Temperatures: {temp_str}")
