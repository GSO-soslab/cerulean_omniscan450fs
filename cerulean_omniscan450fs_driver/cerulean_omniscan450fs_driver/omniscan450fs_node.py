"""ROS 2 driver for the Cerulean Omniscan 450 FS forward-scan sonar.

Each ping is one line of echo strength against range (no bearing, no detected range).
The node publishes that profile, and optionally a first-return range found on it.

Topics (relative to the node, so two units do not collide):
  ~/profile    cerulean_omniscan450fs_interfaces/Profile
  ~/range      sensor_msgs/Range        (publish_range) range to the first return, inf if none
  ~/detection  cerulean_omniscan450fs_interfaces/Detection   (publish_range) with confidence
"""

import math
import threading
import time

import rclpy
from rcl_interfaces.msg import SetParametersResult
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import Range

from cerulean_omniscan450fs_interfaces.msg import Detection as DetectionMsg
from cerulean_omniscan450fs_interfaces.msg import Profile
from cerulean_omniscan450fs_driver.range_detection import (
    FinderConfig, RangeFinder, RangeTracker, default_flat)
from cerulean_omniscan450fs_driver.sonar_io import SonarLink

# Parameters that change what the sonar is told to do, as opposed to how we process pings.
SONAR_PARAMS = (
    'configuration.start_m', 'configuration.length_m', 'configuration.num_samples',
    'configuration.ping_rate_hz', 'configuration.gain_index',
    'configuration.pulse_len_percent', 'configuration.filter_duration_percent',
    'configuration.sound_speed_mps',
)

# Reconnect when this many consecutive reads return nothing (reads time out after 0.5 s).
MAX_SILENT_READS = 10


class Omniscan450FSDriver(Node):
    def __init__(self):
        super().__init__('omniscan450fs_driver')

        self._names = []

        def d(name, default):
            self._names.append(name)
            self.declare_parameter(name, default)

        d('interface.ip_address', '192.168.194.90')
        d('interface.port', 51200)
        d('interface.connect_timeout_s', 5.0)
        d('interface.reconnect_interval_s', 2.0)

        d('configuration.frame_id', 'omniscan450fs_link')
        d('configuration.start_m', 0.0)
        d('configuration.length_m', 5.0)
        d('configuration.num_samples', 600)
        d('configuration.ping_rate_hz', 0.0)            # 0 = as fast as the sonar allows
        d('configuration.gain_index', -1)               # -1 = automatic
        d('configuration.pulse_len_percent', 0.002)
        d('configuration.filter_duration_percent', 0.0015)
        d('configuration.sound_speed_mps', 1482.0)

        d('topics.publish_profile', True)
        d('topics.publish_range', True)

        # First-return detection, see the range_detection package. Every setting of every
        # method is declared from its defaults, so a new method needs nothing added here.
        for key, value in default_flat().items():
            d(f'detection.{key}', value)
        d('detection.median_pings', 1)                  # median of the last N pings, 1 = off
        d('detection.field_of_view_rad', math.radians(0.8))

        self._lock = threading.Lock()
        self._cfg = self._read_params()
        self._reconfigure = threading.Event()
        self._finder = RangeFinder(self._finder_config(self._cfg))
        self._tracker = RangeTracker(self._cfg['detection.median_pings'])

        self._pub_profile = self.create_publisher(Profile, '~/profile', 10)
        self._pub_range = self.create_publisher(Range, '~/range', 10)
        self._pub_detection = self.create_publisher(DetectionMsg, '~/detection', 10)

        self.add_on_set_parameters_callback(self._on_parameters)

        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name='omniscan450fs_reader', daemon=True)
        self._thread.start()

    # -- parameters ---------------------------------------------------------------------
    def _read_params(self):
        return {n: self.get_parameter(n).value for n in self._names}

    def _on_parameters(self, params):
        with self._lock:
            candidate = dict(self._cfg)
        changed = set()
        for p in params:
            if p.name in candidate and candidate[p.name] != p.value:
                candidate[p.name] = p.value
                changed.add(p.name)

        error = self._validate(candidate)
        if error:
            return SetParametersResult(successful=False, reason=error)

        with self._lock:
            self._cfg = candidate
            if any(name.startswith('detection.') for name in changed):
                self._finder = RangeFinder(self._finder_config(candidate))
                # ranges from another method or window are not comparable
                self._tracker = RangeTracker(candidate['detection.median_pings'])
        if changed.intersection(SONAR_PARAMS):
            self._reconfigure.set()
        return SetParametersResult(successful=True)

    @staticmethod
    def _validate(c):
        if c['configuration.length_m'] <= 0.0:
            return 'configuration.length_m must be > 0'
        if c['configuration.start_m'] < 0.0:
            return 'configuration.start_m must be >= 0'
        if c['configuration.num_samples'] < 1:
            return 'configuration.num_samples must be >= 1'
        if c['configuration.ping_rate_hz'] < 0.0:
            return 'configuration.ping_rate_hz must be >= 0'
        if not -1 <= c['configuration.gain_index'] <= 7:
            return 'configuration.gain_index must be -1 (auto) or 0 to 7'
        if c['configuration.sound_speed_mps'] <= 0.0:
            return 'configuration.sound_speed_mps must be > 0'
        if c['detection.median_pings'] < 1:
            return 'detection.median_pings must be >= 1'
        try:
            Omniscan450FSDriver._finder_config(c)
        except ValueError as e:
            return f'detection: {e}'
        return ''

    @staticmethod
    def _finder_config(c):
        flat = {k[len('detection.'):]: v for k, v in c.items() if k.startswith('detection.')}
        flat.pop('median_pings')
        flat.pop('field_of_view_rad')
        return FinderConfig.from_flat(flat)

    def _snapshot(self):
        with self._lock:
            return dict(self._cfg)

    # -- sonar connection ---------------------------------------------------------------
    def _log_throttled(self, level, msg, key, period_s=10.0):
        if self._stop.is_set() or not rclpy.ok():
            return
        now = time.monotonic()
        last = getattr(self, '_last_log', {})
        if now - last.get(key, -1e9) >= period_s:
            last[key] = now
            self._last_log = last
            # rclpy needs a fixed severity per call site, so one call per level
            logger = self.get_logger()
            if level == 'error':
                logger.error(msg)
            elif level == 'warn':
                logger.warn(msg)
            else:
                logger.info(msg)

    def _ping_settings(self):
        c = self._snapshot()
        return dict(
            start_mm=round(c['configuration.start_m'] * 1000),
            length_mm=round(c['configuration.length_m'] * 1000),
            msec_per_ping=SonarLink.msec_per_ping(c['configuration.ping_rate_hz']),
            pulse_len_percent=c['configuration.pulse_len_percent'],
            filter_duration_percent=c['configuration.filter_duration_percent'],
            gain_index=int(c['configuration.gain_index']),
            num_results=int(c['configuration.num_samples']))

    def _send_ping_config(self, link):
        c = self._snapshot()
        link.set_speed_of_sound(round(c['configuration.sound_speed_mps'] * 1000))   # mm/s
        link.configure(**self._ping_settings(), enable=True)

    def _connect(self):
        c = self._snapshot()
        link = SonarLink(c['interface.ip_address'], int(c['interface.port']),
                         float(c['interface.connect_timeout_s']))
        try:
            info = link.device_information()
            if info is None:
                raise ConnectionError('sonar did not answer the device information request')
            self._send_ping_config(link)
        except Exception:
            link.close()
            raise
        if not self._stop.is_set() and rclpy.ok():
            self.get_logger().info(
                f"Connected to {c['interface.ip_address']}:{c['interface.port']}, firmware "
                f'{info.firmware_version_major}.{info.firmware_version_minor}'
                f'.{info.firmware_version_patch}')
        return link

    def _run(self):
        while not self._stop.is_set():
            try:
                link = self._connect()
            except Exception as e:
                self._log_throttled('error', f'Cannot connect to sonar: {e}', 'connect')
                self._stop.wait(self._snapshot()['interface.reconnect_interval_s'])
                continue

            silent = 0
            try:
                while not self._stop.is_set():
                    if self._reconfigure.is_set():
                        self._reconfigure.clear()
                        self._send_ping_config(link)
                    profile = link.read_profile(timeout=0.5)
                    if profile is None:
                        silent += 1
                        if silent >= MAX_SILENT_READS:
                            self._log_throttled('warn', 'No data from sonar, reconnecting',
                                                'silent')
                            break
                        continue
                    silent = 0
                    self._publish(profile)
            except Exception as e:
                self._log_throttled('error', f'Lost connection to sonar: {e}', 'lost')
            finally:
                # stop pinging on shutdown, a plain reconnect just drops the link
                link.close(stop_pinging=self._ping_settings() if self._stop.is_set() else None)

    # -- publishing ---------------------------------------------------------------------
    def _publish(self, msg):
        stamp = self.get_clock().now().to_msg()
        c = self._snapshot()
        frame = c['configuration.frame_id']
        power_db = list(msg.power_db)
        start_m, length_m = msg.start_mm / 1000.0, msg.length_mm / 1000.0

        if c['topics.publish_profile']:
            p = Profile()
            p.header.stamp = stamp
            p.header.frame_id = frame
            p.ping_number = int(msg.ping_number)
            p.sonar_time_ms = int(msg.timestamp_ms)
            p.acoustic_frequency_hz = int(msg.acoustic_frequency_hz)
            p.start_m = start_m
            p.length_m = length_m
            p.sound_speed_mps = msg.sos_dmps / 10.0
            p.gain_index = int(msg.gain_index)
            p.analog_gain = float(msg.analog_gain)
            p.pulse_duration_s = float(msg.pulse_duration_sec)
            p.channel_number = int(msg.channel_number)
            p.min_power_db = float(msg.min_pwr_db)
            p.max_power_db = float(msg.max_pwr_db)
            p.transducer_heading_deg = float(msg.transducer_heading_deg)
            p.vehicle_heading_deg = float(msg.vehicle_heading_deg)
            p.power_db = power_db
            self._pub_profile.publish(p)

        if c['topics.publish_range']:
            with self._lock:
                finder = self._finder
            det = self._track(finder.detect(power_db, start_m, length_m))

            dm = DetectionMsg()
            dm.header.stamp = stamp
            dm.header.frame_id = frame
            dm.ping_number = int(msg.ping_number)
            dm.detected = det.detected
            dm.range_m = det.range_m
            dm.raw_range_m = det.raw_range_m
            dm.peak_power_db = det.peak_power_db
            dm.threshold_db = det.threshold_db
            dm.snr_db = det.snr_db
            dm.width_m = det.width_m
            self._pub_detection.publish(dm)

            r = Range()
            r.header.stamp = stamp
            r.header.frame_id = frame
            r.radiation_type = Range.ULTRASOUND
            r.field_of_view = float(c['detection.field_of_view_rad'])
            common = finder.config.common
            r.min_range = float(common.min_range_m)
            r.max_range = float(common.max_range_m if common.max_range_m > 0.0
                                else start_m + length_m)
            r.range = det.range_m if det.detected else math.inf
            self._pub_range.publish(r)

    def _track(self, detection):
        with self._lock:
            return self._tracker.update(detection)

    # -- shutdown -----------------------------------------------------------------------
    def shutdown(self):
        self._stop.set()
        self._thread.join(timeout=3.0)


def main(args=None):
    rclpy.init(args=args)
    node = Omniscan450FSDriver()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.shutdown()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
