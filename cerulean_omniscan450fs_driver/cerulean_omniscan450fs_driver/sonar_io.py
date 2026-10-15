"""Connection to an Omniscan 450 FS, with real read timeouts.

brping's Omniscan450.wait_message() cannot be used for this: its TCP read loop spins at
full CPU when the sonar sends nothing and never returns, so the timeout never fires and a
silent or dropped sonar would hang the driver. Here the socket is read with select(),
and bytes are fed to brping's parser. brping is still used for the message definitions
and for writing commands.

No ROS imports, so it can be tested against the fake sonar.
"""

import collections
import select
import struct
import time
from dataclasses import dataclass
from typing import Tuple

from brping import Omniscan450, definitions, pingmessage

READ_SIZE = 4096


@dataclass
class ProfileData:
    ping_number: int
    start_mm: int
    length_mm: int
    timestamp_ms: int
    acoustic_frequency_hz: int
    gain_index: int
    num_results: int
    sos_dmps: int
    channel_number: int
    pulse_duration_sec: float
    analog_gain: float
    max_pwr_db: float
    min_pwr_db: float
    transducer_heading_deg: float
    vehicle_heading_deg: float
    power_db: Tuple[float, ...]


class SonarLink:
    def __init__(self, host, port, connect_timeout=5.0):
        self.host = host
        self.port = port
        self._dev = Omniscan450()
        try:
            self._dev.connect_tcp(host, port, connect_timeout)
        except Exception:
            # brping creates the socket before connecting and leaves it open on failure
            if self._dev.iodev is not None:
                self._dev.iodev.close()
            raise
        self._sock = self._dev.iodev
        self._parser = pingmessage.PingParser()
        self._queue = collections.deque()

    # -- reading ------------------------------------------------------------------------
    def read_message(self, timeout):
        """Next complete message from the sonar, or None after `timeout` seconds of silence.

        Raises ConnectionError if the sonar closes the connection.
        """
        deadline = time.monotonic() + timeout
        while True:
            if self._queue:
                return self._queue.popleft()
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                return None
            readable, _, _ = select.select([self._sock], [], [], remaining)
            if not readable:
                return None
            data = self._sock.recv(READ_SIZE)
            if not data:
                raise ConnectionError('connection closed by the sonar')
            for byte in data:
                if self._parser.parse_byte(byte) == pingmessage.PingParser.NEW_MESSAGE:
                    # Several messages can arrive in one read, keep them in order.
                    self._queue.append(self._parser.rx_msg)

    # -- requests and commands ----------------------------------------------------------
    def request(self, message_id, timeout=2.0):
        """Ask the sonar for a message and wait for the reply, None on timeout."""
        m = pingmessage.PingMessage(definitions.COMMON_GENERAL_REQUEST)
        m.requested_id = message_id
        m.pack_msg_data()
        self._dev.write(m.msg_data)
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                return None
            msg = self.read_message(remaining)
            if msg is not None and msg.message_id == message_id:
                return msg

    def device_information(self, timeout=2.0):
        return self.request(definitions.COMMON_DEVICE_INFORMATION, timeout)

    def set_speed_of_sound(self, mm_per_s):
        self._dev.control_set_speed_of_sound(int(mm_per_s))

    def configure(self, start_mm, length_mm, msec_per_ping, pulse_len_percent,
                  filter_duration_percent, gain_index, num_results, enable=True):
        self._dev.control_os_ping_params(
            start_mm=int(start_mm), length_mm=int(length_mm), msec_per_ping=int(msec_per_ping),
            pulse_len_percent=pulse_len_percent, filter_duration_percent=filter_duration_percent,
            gain_index=int(gain_index), num_results=int(num_results), enable=enable)

    @staticmethod
    def msec_per_ping(rate_hz):
        return Omniscan450.calc_msec_per_ping(rate_hz) if rate_hz > 0.0 else 0

    # -- profiles -----------------------------------------------------------------------
    def read_profile(self, timeout):
        """Next profile, skipping any other messages. None after `timeout` seconds."""
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                return None
            msg = self.read_message(remaining)
            if msg is not None and msg.message_id == definitions.OMNISCAN450_OS_MONO_PROFILE:
                return self._profile(msg)

    @staticmethod
    def _profile(msg):
        raw = struct.unpack('<' + 'H' * int(msg.num_results), bytes(msg.pwr_results))
        span = msg.max_pwr_db - msg.min_pwr_db
        power_db = tuple(msg.min_pwr_db + (r / 65535.0) * span for r in raw)
        return ProfileData(
            ping_number=msg.ping_number, start_mm=msg.start_mm, length_mm=msg.length_mm,
            timestamp_ms=msg.timestamp_ms, acoustic_frequency_hz=msg.ping_hz,
            gain_index=msg.gain_index, num_results=msg.num_results, sos_dmps=msg.sos_dmps,
            channel_number=msg.channel_number, pulse_duration_sec=msg.pulse_duration_sec,
            analog_gain=msg.analog_gain, max_pwr_db=msg.max_pwr_db, min_pwr_db=msg.min_pwr_db,
            transducer_heading_deg=msg.transducer_heading_deg,
            vehicle_heading_deg=msg.vehicle_heading_deg, power_db=power_db)

    # -- closing ------------------------------------------------------------------------
    def close(self, stop_pinging=None):
        """Close the connection, first telling the sonar to stop pinging if given its settings."""
        if stop_pinging is not None:
            try:
                self.configure(enable=False, **stop_pinging)
            except Exception:
                pass
        try:
            self._sock.close()
        except Exception:
            pass
