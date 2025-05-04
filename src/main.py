import asyncio
from bleak import BleakScanner, BleakClient
from bleak.exc import BleakError
from src.utils import (
    pair_device,
    connect_with_retry,
    handle_notification,
    ConnectionStatus,
    pair_device_bleak,
)



async def connect_and_monitor(status: ConnectionStatus):
    print(f"Scanning for {status.config.scan_timeout_sec} seconds for {status.config.device_name_contains}...")
    igrill = await BleakScanner.find_device_by_filter(
        lambda device, _: status.config.device_name_contains in device.name,
        timeout=status.config.scan_timeout_sec,
    )
    client = BleakClient(
                igrill,
                timeout=status.config.connection_timeout_sec,
                disconnected_callback=lambda client: print("Disconnected from device"),
            )

    if not igrill:
        return

    print(f"--> Found {igrill.name} at {igrill.address} first time")
    await pair_device_bleak(igrill, client)

    print(f"Connecting to {igrill.name}...")
    await connect_with_retry(igrill, client,status.config)

    try:
        status.connected_once = True
        status.retry_count = 0

        # # Print all services and characteristics
        # print("\nDiscovering all services and characteristics...")
        # await print_services(client)

        # Subscribe to all probe notifications
        for position, probe_uuid in enumerate(status.config.probe_uuids):
            print(f"\nSubscribing to probe {position + 1}")
            await client.start_notify(
                probe_uuid,
                lambda _, 
                data, 
                pos=position + 1, 
                uuid=probe_uuid: handle_notification(pos, data, status),
            )

        while client.is_connected:
            await asyncio.sleep(status.config.scan_interval_sec)

    finally:
        print("Disconnecting from iGrill...")
        await client.disconnect()

    raise BleakError("Lost connection to iGrill.")


async def run_session(status: ConnectionStatus):
    while True:
        try:
            # loop until connected to iGrill, then stay there
            await connect_and_monitor(status)

        except Exception as e:
            print(f"Error in main loop: {str(e)}")
            status.register_disconnection()

        print(f"iGrill not found. Retrying in {status.config.scan_interval_sec}s...")
        await asyncio.sleep(status.config.scan_interval_sec)

        status.register_connection_attempt()
