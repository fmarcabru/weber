import asyncio
import time
from bleak import BleakScanner, BleakError
from utils.utils import (
    reset_ble_adapter,
    handle_notification,
    pair_device,
    connect_with_retry,
    print_services,
    ConnectionStatus,
)
from utils.config import Config


async def run_session(status: ConnectionStatus, config: Config):
    while True:
        try:
            print("Scanning for iGrill 2...")
            igrill = await BleakScanner.find_device_by_filter(
                lambda d, _: config.device_name_contains in d.name,
                timeout=config.scan_timeout_sec,
            )

            if not igrill:
                print(
                    "iGrill not found. Retrying in {}s...".format(
                        config.scan_interval_sec
                    )
                )
                status.retry_count += 1
                if status.retry_count >= config.max_retries_before_warning:
                    print(
                        f"[ALERT] Reached max retries ({config.max_retries_before_warning}). Attempting to reset BLE adapter..."
                    )
                    reset_ble_adapter()
                    status.retry_count = 0
                await asyncio.sleep(config.scan_interval_sec)
                continue

            print(f"Found {igrill.name}, attempting to pair...")
            await pair_device(igrill.name)

            print(f"Connecting to {igrill.name}...")
            client = await connect_with_retry(igrill, config)

            try:
                status.connected_once = True
                status.retry_count = 0

                # Print all services and characteristics
                print("\nDiscovering all services and characteristics...")
                await print_services(client)

                while client.is_connected:
                    print("inside while client.is_connected")
                    await client.start_notify(
                        config.temperature_uuid,
                        lambda _, data: handle_notification(data, status, config),
                    )
                    print("Connected and subscribed to temperatures.")
                    await asyncio.sleep(config.scan_interval_sec)

            finally:
                await client.disconnect()

            raise BleakError("Lost connection to iGrill.")
            await asyncio.sleep(config.connection_check_interval)

        except BleakError as e:
            status.retry_count += 1
            print(f"[Error] {e}. Retrying in {config.scan_interval_sec}s...")
            if status.retry_count >= config.max_retries_before_warning:
                print(
                    f"[ALERT] Reached max retries ({config.max_retries_before_warning}). Attempting to reset BLE adapter..."
                )
                reset_ble_adapter()
                status.retry_count = 0
            await asyncio.sleep(config.scan_interval_sec)

        # Disconnect and no data alerts
        now = time.time()

        if now - status.last_temp_time > config.no_probe_data_after_sec:
            if now - status.last_alert_time > config.alert_interval_sec:
                alert_message = "[ALERT] No probe data received recently!"
                print(alert_message)
                status.last_alert_time = now

        if now - status.last_disconnect_time > config.disconnect_alert_after_sec:
            if now - status.last_alert_time > config.alert_interval_sec:
                alert_message = "[ALERT] Disconnected from iGrill for too long!"
                print(alert_message)
                status.last_alert_time = now


if __name__ == "__main__":
    status = ConnectionStatus(
        retry_count=0,
        last_temp_time=0,
        last_disconnect_time=0,
        last_alert_time=0,
        connected_once=False,
    )

    config = Config.load_from_file()

    asyncio.run(run_session(status, config))
