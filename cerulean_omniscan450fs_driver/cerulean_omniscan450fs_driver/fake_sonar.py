"""Fake Omniscan 450 FS: a TCP server that speaks the Ping protocol.

Lets the driver be exercised without hardware. It answers device-information and
protocol-version requests, accepts os_ping_params, and streams os_mono_profile
messages with synthetic noise and optional targets.

  ros2 run cerulean_omniscan450fs_driver fake_sonar --port 51200 --target 12:0.5:-40
"""

import argparse
import socket
import threading
import time

import numpy as np

from brping import definitions, pingmessage

MIN_DB, MAX_DB = -100.0, 0.0
DEFAULT_PING_PERIOD_S = 0.05


def parse_target(text):
    range_m, width_m, level_db = (float(v) for v in text.split(':'))
    return range_m, width_m, level_db


class FakeOmniscan450FS:
    def __init__(self, targets=(), noise_db=-80.0, jitter_db=1.0, seed=0):
        self.targets = list(targets)
        self.noise_db = noise_db
        self.jitter_db = jitter_db
        self.rng = np.random.default_rng(seed)
        self.params = dict(start_mm=0, length_mm=5000, msec_per_ping=0, num_results=600,
                           gain_index=0, enable=False)
        self.ping_number = 0
        self.t0 = time.time()
        self._lock = threading.Lock()

    # -- protocol helpers ---------------------------------------------------------------
    @staticmethod
    def _pack(msg_id, **fields):
        m = pingmessage.PingMessage(msg_id)
        for k, v in fields.items():
            setattr(m, k, v)
        m.pack_msg_data()
        return bytes(m.msg_data)

    def device_information(self):
        return self._pack(definitions.COMMON_DEVICE_INFORMATION, device_type=0, device_revision=1,
                          firmware_version_major=1, firmware_version_minor=0,
                          firmware_version_patch=0, reserved=0)

    def protocol_version(self):
        return self._pack(definitions.COMMON_PROTOCOL_VERSION, version_major=1, version_minor=0,
                          version_patch=0, reserved=0)

    def profile(self):
        with self._lock:
            p = dict(self.params)
        n = int(p['num_results'])
        start_m, length_m = p['start_mm'] / 1000.0, p['length_mm'] / 1000.0
        res = length_m / n
        power = self.noise_db + self.rng.normal(0.0, self.jitter_db, n)
        for range_m, width_m, level_db in self.targets:
            i0 = int(round((range_m - start_m) / res))
            i1 = i0 + max(1, int(round(width_m / res)))
            if 0 <= i0 < n:
                power[i0:min(i1, n)] = level_db
        raw = np.clip((power - MIN_DB) / (MAX_DB - MIN_DB) * 65535.0, 0, 65535).astype('<u2')
        self.ping_number += 1
        return self._pack(
            definitions.OMNISCAN450_OS_MONO_PROFILE,
            ping_number=self.ping_number, start_mm=p['start_mm'], length_mm=p['length_mm'],
            timestamp_ms=int((time.time() - self.t0) * 1000), ping_hz=450000,
            gain_index=max(0, p['gain_index']), num_results=n, sos_dmps=14820, channel_number=0,
            reserved=0, pulse_duration_sec=0.0001, analog_gain=1.0,
            max_pwr_db=MAX_DB, min_pwr_db=MIN_DB, transducer_heading_deg=0.0,
            vehicle_heading_deg=0.0, pwr_results=raw.tobytes())

    def handle(self, msg):
        """Return reply bytes for a message from the client, or None."""
        if msg.message_id == definitions.COMMON_GENERAL_REQUEST:
            if msg.requested_id == definitions.COMMON_DEVICE_INFORMATION:
                return self.device_information()
            if msg.requested_id == definitions.COMMON_PROTOCOL_VERSION:
                return self.protocol_version()
        elif msg.message_id == definitions.OMNISCAN450_OS_PING_PARAMS:
            with self._lock:
                self.params.update(start_mm=msg.start_mm, length_mm=msg.length_mm,
                                   msec_per_ping=msg.msec_per_ping, num_results=msg.num_results,
                                   gain_index=msg.gain_index, enable=bool(msg.enable))
        return None

    # -- server -------------------------------------------------------------------------
    def serve_client(self, conn, stop):
        conn.setblocking(False)
        parser = pingmessage.PingParser()
        next_ping = time.time()
        while not stop.is_set():
            try:
                data = conn.recv(4096)
                if not data:
                    return
                for b in data:
                    if parser.parse_byte(b) == pingmessage.PingParser.NEW_MESSAGE:
                        reply = self.handle(parser.rx_msg)
                        if reply:
                            conn.sendall(reply)
            except BlockingIOError:
                pass
            except OSError:
                return
            with self._lock:
                enabled = self.params['enable']
                period = self.params['msec_per_ping'] / 1000.0 or DEFAULT_PING_PERIOD_S
            now = time.time()
            if enabled and now >= next_ping:
                try:
                    conn.sendall(self.profile())
                except OSError:
                    return
                next_ping = now + period
            time.sleep(0.002)

    def serve(self, host, port, stop=None):
        stop = stop or threading.Event()
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((host, port))
        srv.listen(1)
        srv.settimeout(0.5)
        try:
            while not stop.is_set():
                try:
                    conn, _ = srv.accept()
                except socket.timeout:
                    continue
                with self._lock:
                    self.params['enable'] = False
                self.serve_client(conn, stop)
                conn.close()
        finally:
            srv.close()


def main(args=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=51200)
    ap.add_argument('--target', action='append', default=[], type=parse_target,
                    metavar='RANGE_M:WIDTH_M:LEVEL_DB')
    ap.add_argument('--noise-db', type=float, default=-80.0)
    a = ap.parse_args(args)
    sonar = FakeOmniscan450FS(a.target, a.noise_db)
    print(f'fake Omniscan 450 FS on {a.host}:{a.port}, targets={a.target}', flush=True)
    try:
        sonar.serve(a.host, a.port)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
