#!/usr/bin/env python3
"""Forward a serial MAVLink byte stream through MQTT.

Run with role=boat on the Orange Pi (Pixhawk UART), and role=desktop on the
computer (the modem-facing end of a virtual COM pair). The MQTT payload is
base64-wrapped so the original MAVLink byte stream is preserved exactly.
"""
import argparse
import base64
import json
import logging
import os
import signal
import ssl
import threading
import time
import uuid

import paho.mqtt.client as mqtt
import serial


LOG = logging.getLogger("mqtt-mavlink-tunnel")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", choices=("boat", "desktop"), required=True)
    parser.add_argument("--boat-id", default=os.getenv("USV_BOAT_ID", "boat_1"))
    parser.add_argument("--serial", default=os.getenv("USV_SERIAL", "/dev/ttyS1"))
    parser.add_argument("--baud", type=int, default=int(os.getenv("USV_BAUD", "57600")))
    parser.add_argument("--host", default=os.getenv("MQTT_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "8883")))
    parser.add_argument("--username", default=os.getenv("MQTT_USERNAME", ""))
    parser.add_argument("--password", default=os.getenv("MQTT_PASSWORD", ""))
    parser.add_argument("--ca-cert", default=os.getenv("MQTT_CA_CERT", ""))
    parser.add_argument("--insecure", action="store_true", help="Disable TLS certificate verification; test only")
    return parser.parse_args()


def make_client(client_id):
    try:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    except (AttributeError, TypeError):  # paho-mqtt 1.x compatibility
        return mqtt.Client(client_id=client_id)


def main():
    args = parse_args()
    if args.insecure and args.port == 8883:
        LOG.warning("TLS certificate verification is disabled; do not use this setting in production")

    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper(),
                        format="%(asctime)s %(levelname)s %(message)s")
    root = f"usv/{args.boat_id}/mavlink"
    if args.role == "boat":
        tx_topic, rx_topic = f"{root}/up", f"{root}/down"
    else:
        tx_topic, rx_topic = f"{root}/down", f"{root}/up"

    uart = serial.Serial(args.serial, args.baud, timeout=0.05, write_timeout=2)
    uart_lock = threading.Lock()
    client = make_client(f"usv-{args.role}-{args.boat_id}-{uuid.uuid4().hex[:8]}")
    session_id = uuid.uuid4().hex
    sequence = 0
    seen = {}
    running = threading.Event()
    running.set()

    if args.username:
        client.username_pw_set(args.username, args.password)
    if args.port == 8883:
        client.tls_set(ca_certs=args.ca_cert or None, cert_reqs=ssl.CERT_NONE if args.insecure else ssl.CERT_REQUIRED)
        client.tls_insecure_set(args.insecure)

    def on_connect(mqtt_client, userdata, flags, reason_code, properties=None):
        if int(reason_code) != 0:
            LOG.error("MQTT connection rejected: %s", reason_code)
            return
        mqtt_client.subscribe(rx_topic, qos=1)
        LOG.info("MQTT connected: host=%s port=%d subscribe=%s publish=%s",
                 args.host, args.port, rx_topic, tx_topic)

    def on_message(_client, _userdata, message):
        try:
            envelope = json.loads(message.payload.decode("utf-8"))
            sid, seq = envelope["sid"], int(envelope["seq"])
            if seq <= seen.get(sid, -1):
                return
            payload = base64.b64decode(envelope["data"], validate=True)
            with uart_lock:
                uart.write(payload)
            seen[sid] = seq
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            LOG.warning("Discarding malformed tunnel message: %s", exc)
        except serial.SerialException as exc:
            LOG.error("Serial write failed: %s", exc)

    client.on_connect = on_connect
    client.on_message = on_message
    client.connect_async(args.host, args.port, keepalive=45)
    client.loop_start()
    signal.signal(signal.SIGINT, lambda *_: running.clear())
    signal.signal(signal.SIGTERM, lambda *_: running.clear())
    LOG.info("Serial open: %s @ %d baud; role=%s", args.serial, args.baud, args.role)

    try:
        while running.is_set():
            payload = uart.read(512)
            if not payload or not client.is_connected():
                continue
            sequence += 1
            envelope = json.dumps({
                "sid": session_id,
                "seq": sequence,
                "data": base64.b64encode(payload).decode("ascii"),
            }, separators=(",", ":"))
            qos = 0 if args.role == "boat" else 1
            info = client.publish(tx_topic, envelope, qos=qos)
            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                LOG.debug("MQTT publish queued/failed: rc=%s", info.rc)
    finally:
        running.clear()
        client.disconnect()
        client.loop_stop()
        uart.close()
        LOG.info("Tunnel stopped")


if __name__ == "__main__":
    main()
