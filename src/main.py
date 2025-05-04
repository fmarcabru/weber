import asyncio
import time
from bleak import BleakScanner
from bleak.exc import BleakError
from src.utils import (
    pair_device,
    connect_with_retry,
    handle_notification,
    reset_ble_adapter,
    print_services,
    ConnectionStatus,
)
from src.utils import Config


async def connect_and_monitor(status: ConnectionStatus, config: Config):
    print("Scanning for iGrill 2...")
    igrill = await BleakScanner.find_device_by_filter(
        lambda d, _: config.device_name_contains in d.name,
        timeout=config.scan_timeout_sec,
    )

    if not igrill:
        print("iGrill not found. Retrying in {}s...".format(config.scan_interval_sec))
        status.retry_count += 1
        if status.retry_count >= config.max_retries_before_warning:
            print(
                f"[ALERT] Reached max retries ({config.max_retries_before_warning}). Attempting to reset BLE adapter..."
            )
            reset_ble_adapter()
            status.retry_count = 0
        await asyncio.sleep(config.scan_interval_sec)
        return

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

        # Subscribe to all probe notifications
        for position, probe_uuid in enumerate(config.probe_uuids):
            print(f"\nSubscribing to probe {position + 1} characteristic: {probe_uuid}")
            await client.start_notify(
                probe_uuid,
                lambda _, data, pos=position + 1, uuid=probe_uuid: handle_notification(
                    pos, data, status, config, uuid
                ),
            )

        while client.is_connected:
            await asyncio.sleep(config.scan_interval_sec)

    finally:
        await client.disconnect()

    raise BleakError("Lost connection to iGrill.")


async def run_session(status: ConnectionStatus, config: Config):
    while True:
        try:
            await connect_and_monitor(status, config)
        except Exception as e:
            print(f"Error in main loop: {e}")
            await asyncio.sleep(5)  # Wait before retrying

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
