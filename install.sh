#!/bin/bash

# ina219-mqtt Installer/Updater

set -e

SERVICE_NAME="ina219-mqtt"
INSTALL_DIR="/opt/ina219-mqtt"
CONFIG_FILE="/etc/default/ina219-mqtt"
SERVICE_FILE="/etc/systemd/system/ina219-mqtt.service"

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root"
  exit 1
fi

export PATH="/root/.local/bin:$PATH"

if ! command -v uv &> /dev/null; then
    echo "uv not found. Installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

UV_BIN=$(command -v uv || echo "/root/.local/bin/uv")

if [ "$1" == "--update" ]; then
    echo "Updating ina219-mqtt from git..."
    if [ -d ".git" ]; then
        [ -n "$SUDO_USER" ] && sudo -u "$SUDO_USER" git pull origin master || git pull origin master
    else
        echo "Error: Not a git repository."
        exit 1
    fi
fi

echo "Installing ina219-mqtt..."

if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    echo "Stopping existing service..."
    systemctl stop "$SERVICE_NAME"
fi

mkdir -p "$INSTALL_DIR"
rsync -av --exclude='.venv' --exclude='.git' --exclude='__pycache__' . "$INSTALL_DIR"
chown -R root:root "$INSTALL_DIR"

echo "Setting up virtual environment..."
cd "$INSTALL_DIR"
"$UV_BIN" sync

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Creating config: $CONFIG_FILE"
    cat <<EOF > "$CONFIG_FILE"
# ina219-mqtt configuration

# MQTT broker (required)
INA219_MQTT_BROKER="ranchhouse.local"
INA219_MQTT_PORT=1883
INA219_MQTT_USERNAME=""
INA219_MQTT_PASSWORD=""
INA219_MQTT_CLIENT_ID="ina219-mqtt"
INA219_MQTT_DISCOVERY_PREFIX="homeassistant"
INA219_MQTT_STATE_PREFIX="ina219ups"

# INA219 hardware
INA219_I2C_BUS=10
INA219_I2C_ADDR=0x43

# Battery parameters
INA219_BATTERIES_COUNT=3
INA219_BATTERY_CAPACITY=3000
INA219_MAX_SOC=91
INA219_SMA_SAMPLES=5
INA219_MIN_ONLINE_CURRENT=-100
INA219_MIN_CHARGING_CURRENT=55

# Poll interval in seconds
INA219_SCAN_INTERVAL=30

# Device name shown in HA (defaults to hostname)
# INA219_DEVICE_NAME="Barn UPS"
EOF
else
    echo "Config already exists: $CONFIG_FILE (skipping)"
fi

echo "Writing systemd service..."
cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=INA219 UPS Hat MQTT Bridge
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$CONFIG_FILE
ExecStart=$INSTALL_DIR/.venv/bin/python -m ina219_mqtt \
    --mqtt-broker "\${INA219_MQTT_BROKER}" \
    --mqtt-port "\${INA219_MQTT_PORT}" \
    --mqtt-username "\${INA219_MQTT_USERNAME}" \
    --mqtt-password "\${INA219_MQTT_PASSWORD}" \
    --mqtt-client-id "\${INA219_MQTT_CLIENT_ID}" \
    --mqtt-discovery-prefix "\${INA219_MQTT_DISCOVERY_PREFIX}" \
    --mqtt-state-prefix "\${INA219_MQTT_STATE_PREFIX}" \
    --i2c-bus "\${INA219_I2C_BUS}" \
    --i2c-addr "\${INA219_I2C_ADDR}" \
    --batteries-count "\${INA219_BATTERIES_COUNT}" \
    --battery-capacity "\${INA219_BATTERY_CAPACITY}" \
    --max-soc "\${INA219_MAX_SOC}" \
    --sma-samples "\${INA219_SMA_SAMPLES}" \
    --min-online-current "\${INA219_MIN_ONLINE_CURRENT}" \
    --min-charging-current "\${INA219_MIN_CHARGING_CURRENT}" \
    --scan-interval "\${INA219_SCAN_INTERVAL}" \
    \${INA219_DEVICE_NAME:+--device-name "\${INA219_DEVICE_NAME}"}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl start "$SERVICE_NAME"

echo ""
echo "Done. Service status:"
systemctl status "$SERVICE_NAME" --no-pager
echo ""
echo "Edit config: $CONFIG_FILE"
echo "Tail logs:   journalctl -u $SERVICE_NAME -f"
