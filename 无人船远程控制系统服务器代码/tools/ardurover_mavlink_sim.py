#!/usr/bin/env python3
"""A small pymavlink ArduRover autopilot simulator for serial-link testing."""
import argparse
import logging
import time

from pymavlink import mavutil


LOG = logging.getLogger("ardurover-sim")
SUPPORTED_MODES = {0: "MANUAL", 10: "AUTO", 11: "RTL"}


def send_ack(connection, command, result, target_system=0, target_component=0):
    connection.mav.command_ack_send(command, result, 0, 0, target_system, target_component)


def send_mission_ack(connection, target_system, target_component, result):
    connection.mav.mission_ack_send(target_system, target_component, result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", required=True, help="COM port or serial device at the far end of the tunnel")
    parser.add_argument("--baud", type=int, default=57600)
    parser.add_argument("--system", type=int, default=1)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    link = mavutil.mavlink_connection(args.device, baud=args.baud, source_system=args.system,
                                     source_component=mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1,
                                     dialect="ardupilotmega")
    mode = 0
    armed = False
    mission = []
    expected_count = None
    next_heartbeat = 0.0
    LOG.info("ArduRover simulator ready on %s @ %d baud; MANUAL/AUTO/RTL supported", args.device, args.baud)

    while True:
        now = time.monotonic()
        if now >= next_heartbeat:
            base_mode = mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED
            if armed:
                base_mode |= mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED
            link.mav.heartbeat_send(
                mavutil.mavlink.MAV_TYPE_GROUND_ROVER,
                mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA,
                base_mode, mode, mavutil.mavlink.MAV_STATE_ACTIVE if armed else mavutil.mavlink.MAV_STATE_STANDBY,
            )
            next_heartbeat = now + 1.0

        msg = link.recv_match(blocking=True, timeout=0.1)
        if msg is None:
            continue
        kind = msg.get_type()
        LOG.info("RX %s", msg)

        if kind == "SET_MODE":
            requested = int(msg.custom_mode)
            if requested in SUPPORTED_MODES:
                mode = requested
                LOG.info("Mode changed to %s (%d)", SUPPORTED_MODES[mode], mode)

        elif kind == "COMMAND_LONG" and msg.command == mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM:
            requested_arm = msg.param1 >= 0.5
            armed = requested_arm
            result = mavutil.mavlink.MAV_RESULT_ACCEPTED
            send_ack(link, msg.command, result, msg.get_srcSystem(), msg.get_srcComponent())
            LOG.info("Vehicle %s", "armed" if armed else "disarmed")

        elif kind == "MISSION_CLEAR_ALL":
            mission.clear()
            expected_count = None
            send_mission_ack(link, msg.get_srcSystem(), msg.get_srcComponent(),
                             mavutil.mavlink.MAV_MISSION_ACCEPTED)

        elif kind == "MISSION_COUNT":
            expected_count = int(msg.count)
            mission = [None] * expected_count
            if expected_count == 0:
                send_mission_ack(link, msg.get_srcSystem(), msg.get_srcComponent(),
                                 mavutil.mavlink.MAV_MISSION_ACCEPTED)
                expected_count = None
            else:
                link.mav.mission_request_int_send(msg.get_srcSystem(), msg.get_srcComponent(), 0,
                                                  getattr(msg, "mission_type", 0))

        elif kind in ("MISSION_ITEM_INT", "MISSION_ITEM") and expected_count is not None:
            seq = int(msg.seq)
            if 0 <= seq < expected_count:
                mission[seq] = msg
            next_seq = next((i for i, item in enumerate(mission) if item is None), None)
            if next_seq is None:
                send_mission_ack(link, msg.get_srcSystem(), msg.get_srcComponent(),
                                 mavutil.mavlink.MAV_MISSION_ACCEPTED)
                LOG.info("Mission accepted: %d item(s)", len(mission))
                expected_count = None
            else:
                link.mav.mission_request_int_send(msg.get_srcSystem(), msg.get_srcComponent(), next_seq,
                                                  getattr(msg, "mission_type", 0))

        elif kind == "MISSION_REQUEST_LIST":
            link.mav.mission_count_send(msg.get_srcSystem(), msg.get_srcComponent(), len(mission))


if __name__ == "__main__":
    main()
