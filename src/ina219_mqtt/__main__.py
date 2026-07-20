"""INA219 UPS Hat → MQTT bridge."""

import argparse
import logging
import os
import signal
import socket
import sys
import time

from .mqtt import MQTTPublisher
from .reader import INA219Reader

logger = logging.getLogger(__name__)


def _env_int(key: str, default: int) -> int:
    return int(os.environ.get(key, default))


def _env_float(key: str, default: float) -> float:
    return float(os.environ.get(key, default))


def main() -> int:
    parser = argparse.ArgumentParser(description="INA219 UPS Hat → MQTT bridge")
    parser.add_argument("-v", "--verbose", action="count", default=0)
    parser.add_argument("--mqtt-broker",        default=os.environ.get("INA219_MQTT_BROKER", "localhost"))
    parser.add_argument("--mqtt-port",          type=int, default=_env_int("INA219_MQTT_PORT", 1883))
    parser.add_argument("--mqtt-username",      default=os.environ.get("INA219_MQTT_USERNAME", ""))
    parser.add_argument("--mqtt-password",      default=os.environ.get("INA219_MQTT_PASSWORD", ""))
    parser.add_argument("--mqtt-client-id",     default=os.environ.get("INA219_MQTT_CLIENT_ID", "ina219-mqtt"))
    parser.add_argument("--mqtt-discovery-prefix", default=os.environ.get("INA219_MQTT_DISCOVERY_PREFIX", "homeassistant"))
    parser.add_argument("--mqtt-state-prefix",  default=os.environ.get("INA219_MQTT_STATE_PREFIX", "ina219ups"))
    parser.add_argument("--device-name",        default=os.environ.get("INA219_DEVICE_NAME", ""))
    parser.add_argument("--i2c-bus",            type=lambda v: int(v, 0), default=_env_int("INA219_I2C_BUS", 1))
    parser.add_argument("--i2c-addr",           type=lambda v: int(v, 0), default=int(os.environ.get("INA219_I2C_ADDR", "0x40"), 0))
    parser.add_argument("--batteries-count",    type=int, default=_env_int("INA219_BATTERIES_COUNT", 3))
    parser.add_argument("--battery-capacity",   type=int, default=_env_int("INA219_BATTERY_CAPACITY", 3000))
    parser.add_argument("--max-soc",            type=int, default=_env_int("INA219_MAX_SOC", 91))
    parser.add_argument("--sma-samples",        type=int, default=_env_int("INA219_SMA_SAMPLES", 5))
    parser.add_argument("--min-online-current", type=float, default=_env_float("INA219_MIN_ONLINE_CURRENT", -100))
    parser.add_argument("--min-charging-current", type=float, default=_env_float("INA219_MIN_CHARGING_CURRENT", 55))
    parser.add_argument("--scan-interval",      type=int, default=_env_int("INA219_SCAN_INTERVAL", 30))
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose >= 2 else logging.INFO if args.verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    hostname = socket.gethostname()
    device_id = (args.device_name or hostname).lower().replace(" ", "_").replace("-", "_")
    device_name = args.device_name or f"{hostname} UPS"

    logger.warning("Starting ina219-mqtt: device=%s bus=%d addr=0x%02x interval=%ds",
                   device_name, args.i2c_bus, args.i2c_addr, args.scan_interval)

    try:
        reader = INA219Reader(
            bus=args.i2c_bus,
            addr=args.i2c_addr,
            batteries_count=args.batteries_count,
            battery_capacity=args.battery_capacity,
            max_soc=args.max_soc,
            sma_samples=args.sma_samples,
            min_online_current=args.min_online_current,
            min_charging_current=args.min_charging_current,
        )
    except Exception as e:
        logger.error("Failed to initialize INA219: %s", e)
        return 1

    publisher = MQTTPublisher(
        broker=args.mqtt_broker,
        port=args.mqtt_port,
        device_id=device_id,
        device_name=device_name,
        discovery_prefix=args.mqtt_discovery_prefix,
        state_prefix=args.mqtt_state_prefix,
        client_id=args.mqtt_client_id,
        username=args.mqtt_username.strip() or None,
        password=args.mqtt_password.strip() or None,
    )

    stop = False

    def _handle_signal(sig, frame):
        nonlocal stop
        logger.warning("Signal %d received, shutting down", sig)
        stop = True

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    try:
        publisher.connect()
        time.sleep(1)  # let the MQTT connection establish
        publisher.publish_discovery()

        while not stop:
            try:
                data = reader.read()
                publisher.publish_state(data)
                logger.info("Published: %s", data)
            except Exception as e:
                logger.error("Read error: %s", e)

            for _ in range(args.scan_interval):
                if stop:
                    break
                time.sleep(1)

    finally:
        publisher.disconnect()
        reader.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
