from pydantic import BaseModel, Field
import json
from pathlib import Path
from typing import List


class Config(BaseModel):
    # waiting period between bluetooth scans
    scan_interval_sec: int = Field(..., ge=1)  # Ensure positive interval
    # waiting period for bluetooth scan to complete
    scan_timeout_sec: int = Field(..., ge=1)  # Ensure positive timeout
    # waiting period between connection checks after a disconnect
    connection_check_interval: int = Field(..., ge=1)
    # connection timeout in seconds
    connection_timeout_sec: int = Field(30, ge=1)  # Default 30 seconds
    # waiting period after disconnect before alerting
    disconnect_alert_after_sec: int = Field(..., ge=1)
    # waiting period after no probe data before alerting
    no_probe_data_after_sec: int = Field(..., ge=1)
    # bluetooth device name contains
    device_name_contains: str = "iGrill"
    reset_ble_adapter_after_fail: bool = True
    # max retries before reset ble adapter
    max_retries_before_warning: int = Field(..., ge=1)
    # List of UUIDs for each probe
    probe_uuids: List[str]
    service_uuid: str
    # normal operating temperature range
    min_temp_c: float = Field(..., ge=-100, le=100)  # Reasonable min/max temp range
    max_temp_c: float = Field(..., ge=-100, le=200)
    # waiting period between alerts
    alert_interval_sec: int = Field(..., ge=1)
    # switch to print temperatures
    log_temperature_values: bool = True

    @classmethod
    def load_from_file(
        cls, config_path: str | Path = Path("src/config/conf.json")
    ) -> "Config":
        """Load configuration from a JSON file.

        Args:
            config_path: Path to the JSON configuration file

        Returns:
            Config: A Config instance with values from the file

        Raises:
            FileNotFoundError: If the config file doesn't exist
            json.JSONDecodeError: If the JSON file is invalid
            ValueError: If the config values don't match the schema
        """
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, "r") as f:
            config_data = json.load(f)

        return cls(**config_data)
