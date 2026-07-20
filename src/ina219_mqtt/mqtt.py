"""MQTT publisher with Home Assistant autodiscovery."""

import json
import logging
from typing import Optional

from paho.mqtt import client as mqtt_client

logger = logging.getLogger(__name__)

_SENSORS = [
    {"key": "voltage",            "name": "Voltage",             "device_class": "voltage",  "unit": "V",   "state_class": "measurement", "icon": None},
    {"key": "current",            "name": "Current",             "device_class": "current",  "unit": "A",   "state_class": "measurement", "icon": None},
    {"key": "power",              "name": "Power",               "device_class": "power",    "unit": "W",   "state_class": "measurement", "icon": None},
    {"key": "soc",                "name": "Battery",             "device_class": "battery",  "unit": "%",   "state_class": "measurement", "icon": None},
    {"key": "remaining_capacity", "name": "Remaining Capacity",  "device_class": "energy_storage", "unit": "Wh", "state_class": "measurement", "icon": "mdi:battery-charging"},
    {"key": "remaining_time",     "name": "Remaining Time",      "device_class": "duration", "unit": "h",   "state_class": "measurement", "icon": "mdi:timer"},
]

_BINARY_SENSORS = [
    {"key": "online",   "name": "Online",   "device_class": "power",   "icon": None},
    {"key": "charging", "name": "Charging", "device_class": "battery_charging", "icon": None},
]


class MQTTPublisher:
    def __init__(
        self,
        broker: str,
        port: int,
        device_id: str,
        device_name: str,
        discovery_prefix: str = "homeassistant",
        state_prefix: str = "ina219ups",
        client_id: str = "ina219-mqtt",
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        self._broker = broker
        self._port = port
        self._device_id = device_id
        self._device_name = device_name
        self._discovery_prefix = discovery_prefix
        self._state_prefix = state_prefix
        self._availability_topic = f"{state_prefix}/{device_id}/status"
        self._state_topic = f"{state_prefix}/{device_id}/state"

        self._client = mqtt_client.Client(
            mqtt_client.CallbackAPIVersion.VERSION2, client_id
        )
        if username:
            self._client.username_pw_set(username, password)
        self._client.will_set(self._availability_topic, payload="offline", retain=True)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect

    def connect(self) -> None:
        self._client.connect(self._broker, self._port)
        self._client.loop_start()

    def disconnect(self) -> None:
        self._client.publish(self._availability_topic, "offline", retain=True)
        self._client.loop_stop()
        self._client.disconnect()

    def publish_discovery(self) -> None:
        device = {
            "identifiers": [f"ina219ups_{self._device_id}"],
            "name": self._device_name,
            "manufacturer": "Waveshare",
            "model": "INA219 UPS Hat",
        }

        for s in _SENSORS:
            unique_id = f"ina219ups_{self._device_id}_{s['key']}"
            payload: dict = {
                "name": s["name"],
                "unique_id": unique_id,
                "state_topic": self._state_topic,
                "value_template": f"{{{{ value_json.{s['key']} }}}}",
                "device": device,
                "availability_topic": self._availability_topic,
                "payload_available": "online",
                "payload_not_available": "offline",
                "device_class": s["device_class"],
                "unit_of_measurement": s["unit"],
                "state_class": s["state_class"],
            }
            if s["icon"]:
                payload["icon"] = s["icon"]
            topic = f"{self._discovery_prefix}/sensor/{unique_id}/config"
            self._client.publish(topic, json.dumps(payload), retain=True)
            logger.debug("Published discovery for %s", s["key"])

        for b in _BINARY_SENSORS:
            unique_id = f"ina219ups_{self._device_id}_{b['key']}"
            payload = {
                "name": b["name"],
                "unique_id": unique_id,
                "state_topic": self._state_topic,
                "value_template": f"{{{{ 'ON' if value_json.{b['key']} else 'OFF' }}}}",
                "device": device,
                "availability_topic": self._availability_topic,
                "payload_available": "online",
                "payload_not_available": "offline",
                "device_class": b["device_class"],
            }
            if b["icon"]:
                payload["icon"] = b["icon"]
            topic = f"{self._discovery_prefix}/binary_sensor/{unique_id}/config"
            self._client.publish(topic, json.dumps(payload), retain=True)
            logger.debug("Published discovery for %s", b["key"])

        self._client.publish(self._availability_topic, "online", retain=True)
        logger.info("Discovery published for device '%s'", self._device_name)

    def publish_state(self, data: dict) -> None:
        payload = json.dumps(data)
        result = self._client.publish(self._state_topic, payload)
        if result.rc != 0:
            logger.warning("Failed to publish state, rc=%d", result.rc)
        else:
            logger.debug("Published state: %s", payload)

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code == 0:
            logger.info("Connected to MQTT broker at %s:%d", self._broker, self._port)
        else:
            logger.error("MQTT connect failed, reason_code=%s", reason_code)

    def _on_disconnect(self, client, userdata, flags, reason_code, properties) -> None:
        logger.info("Disconnected from MQTT broker")
