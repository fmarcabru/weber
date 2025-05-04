import subprocess
from dataclasses import dataclass
import time
from .config import Config
import asyncio
from bleak import BleakClient, BleakError, BLEDevice, BleakScanner


@dataclass
class ConnectionStatus:
    config: Config
    last_temp_time: float = 0
    last_disconnect_time: float = 0
    last_alert_time: float = 0
    connected_once: bool = False
    device: BLEDevice = None

    @staticmethod
    def _now():
        return time.time()

    def register_disconnection(self):
        self.last_disconnect_time = time.time()

    def can_alert(self)->bool:
        now = self._now()
        time_since_last_alarm = now - self.last_alert_time

        if time_since_last_alarm > self.config.alert_interval_sec:
            return True
        return False

    def register_connection_attempt(self):
        if not self.connected_once:
            return

        now = self._now()
        time_since_disconnect = now - self.last_disconnect_time
        time_since_last_alarm = now - self.last_alert_time

        if time_since_disconnect < self.config.disconnect_alert_after_sec:
            return

        if not self.can_alert():
            return

        alert_message = "[ALERT] Disconnected from iGrill for too long!"
        print(alert_message)
        self.last_alert_time = now

    def validate_temperature(self,probe:int,temp: float):
        now = self._now()
        self.last_temp_time = now

        if self.config.min_temp_c <= temp <= self.config.max_temp_c:
            return
        
        if not self.can_alert():
            return
        
        alert_message = f"[ALERT] Probe {probe} temperature out of range: {temp:.1f}"
        print(alert_message)
        self.last_alert_time = now

def parse_temperatures(data: bytearray):
    """Parse temperature data from iGrill2 probes.
    Each probe temperature is 3 bytes, little endian.
    first 2 bytes is the temp, the 3rd one not sure.
    Value 0x30f8 indicates no probe connected.
    Temperatures are in Fahrenheit.
    """
    print(f"Raw temperature data: {data.hex()}")

    if str(data.hex()) == "30f800":
        print("probe disconnected")
        return None

    return int.from_bytes(data[:2], byteorder="little")


# Edge Case Handling
def reset_ble_adapter():
    print("[ALERT] Restarting BLE adapter (hci0)...")
    subprocess.run(["sudo", "hciconfig", "hci0", "down"])
    subprocess.run(["sudo", "hciconfig", "hci0", "up"])


async def pair_device_bleak(device: BLEDevice, client: BleakClient):
    """Pair with the iGrill2 device using Bleak."""
    print(f"Attempting to pair with {device.address}...")

    print(f"will pair with device: {device.name}")
    
    # Create client
    try:
        # Pair the device first
        print("--> pairing device")
        await client.pair()
        

        print("Successfully paired and connected")
        return True
    except Exception as e:
        print(f"Failed to pair/connect: {str(e)}")
        return False
    finally:
        if client.is_connected:
            await client.disconnect()


# Keep the original pair_device for bluetoothctl
async def pair_device(device_address: str):
    """Pair with the iGrill2 device using bluetoothctl."""
    print(f"Attempting to pair with {device_address}...")

    # First, remove any existing pairing
    print("--> removing existing pairing")
    subprocess.run(["bluetoothctl", "remove", device_address])
    await asyncio.sleep(2)

    # Power on and start scanning
    print("--> power on and start scanning")
    subprocess.run(["bluetoothctl", "power", "on"])
    subprocess.run(["bluetoothctl", "scan", "on"])
    await asyncio.sleep(5)  # Give more time for scanning

    # Pair and trust the device
    print("--> pair and trust the device")
    subprocess.run(["bluetoothctl", "agent", "on"])
    subprocess.run(["bluetoothctl", "default-agent"])
    subprocess.run(["bluetoothctl", "pair", device_address])
    await asyncio.sleep(2)
    subprocess.run(["bluetoothctl", "trust", device_address])
    await asyncio.sleep(2)
    return True


async def connect_with_retry(device: BLEDevice, client: BleakClient, config: Config) -> BleakClient:
    """Attempt to connect to the device with retries."""
    for attempt in range(config.max_retries):
        try:
            print(f"Connection attempt {attempt + 1}/{config.max_retries}...")


            # Try to connect with a specific connection method
            
            await client.connect(use_cached=False,timeout=config.connection_timeout_sec)
            
            # Verify connection
            if not client.is_connected:
                raise BleakError("Failed to establish connection")
            print(f"Connected to {device.name} after {attempt + 1} attempts")
            return client

        except Exception as e:
            print(f"Connection attempt {attempt + 1} failed: {str(e)}")
            if attempt < config.max_retries - 1 :
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


def handle_notification(pos: int,data: bytearray,status: ConnectionStatus):
    # print(f"\nReceived notification from {pos} characteristic: {characteristic_uuid}")
    print(f"Probe {pos}")
    temp = parse_temperatures(data)

    if not temp:
        print(f"Probe {pos} disconnected")
        return

    # Temperature out of range alert
    status.validate_temperature(pos,temp)


    # Log if enabled
    if status.config.log_temperature_values:
        temp_str = (
            f"Probe {pos}: {temp:.1f}°F" if temp is not None else f"Probe {pos}: Not Connected"
        )

        print(temp_str)
