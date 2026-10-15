"""SonarLink against the fake sonar: connect, configure, read profiles, silence, disconnect."""

import socket
import threading
import time

import pytest

pytest.importorskip('brping')

from cerulean_omniscan450fs_driver.fake_sonar import FakeOmniscan450FS   # noqa: E402
from cerulean_omniscan450fs_driver.range_detector import detect_first_return   # noqa: E402
from cerulean_omniscan450fs_driver.sonar_io import SonarLink   # noqa: E402

SETTINGS = dict(start_mm=0, length_mm=30000, msec_per_ping=0, pulse_len_percent=0.002,
                filter_duration_percent=0.0015, gain_index=-1, num_results=600)


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


@pytest.fixture
def fake():
    port = free_port()
    sonar = FakeOmniscan450FS(targets=[(12.0, 0.5, -40.0)])
    stop = threading.Event()
    t = threading.Thread(target=sonar.serve, args=('127.0.0.1', port, stop), daemon=True)
    t.start()
    time.sleep(0.3)
    yield sonar, port
    stop.set()
    t.join(timeout=2.0)


def test_connect_configure_read_and_detect(fake):
    _, port = fake
    link = SonarLink('127.0.0.1', port, 2.0)
    try:
        info = link.device_information()
        assert info is not None and info.firmware_version_major == 1

        link.set_speed_of_sound(1482000)
        link.configure(**SETTINGS, enable=True)
        p = link.read_profile(timeout=3.0)
        assert p is not None
        assert p.num_results == 600 and len(p.power_db) == 600 and p.length_mm == 30000
        assert p.sos_dmps == 14820 and p.acoustic_frequency_hz == 450000

        det = detect_first_return(p.power_db, p.start_mm / 1000.0, p.length_mm / 1000.0)
        assert det.detected and det.range_m == pytest.approx(12.0, abs=0.1)
    finally:
        link.close()


def test_ping_numbers_increase_and_all_profiles_arrive_in_order(fake):
    _, port = fake
    link = SonarLink('127.0.0.1', port, 2.0)
    try:
        link.configure(**{**SETTINGS, 'msec_per_ping': 20}, enable=True)
        numbers = [link.read_profile(timeout=2.0).ping_number for _ in range(10)]
        assert numbers == sorted(numbers) and len(set(numbers)) == 10
    finally:
        link.close()


def test_silent_sonar_times_out_instead_of_hanging(fake):
    """brping's own wait_message spins forever here, this must return."""
    _, port = fake
    link = SonarLink('127.0.0.1', port, 2.0)
    try:
        assert link.device_information() is not None
        # pinging was never enabled, so the sonar sends nothing
        t0 = time.monotonic()
        assert link.read_profile(timeout=0.5) is None
        assert 0.4 < time.monotonic() - t0 < 1.5
    finally:
        link.close()


def test_stop_pinging_on_close(fake):
    sonar, port = fake
    link = SonarLink('127.0.0.1', port, 2.0)
    link.configure(**SETTINGS, enable=True)
    assert link.read_profile(timeout=3.0) is not None
    assert sonar.params['enable']
    link.close(stop_pinging=SETTINGS)
    deadline = time.monotonic() + 2.0
    while sonar.params['enable'] and time.monotonic() < deadline:
        time.sleep(0.02)
    assert not sonar.params['enable']


def test_closed_connection_raises(fake):
    _, port = fake
    stop_server = socket.socket()
    # A server that accepts then closes, to simulate the sonar dropping the link.
    stop_server.bind(('127.0.0.1', 0))
    stop_server.listen(1)
    p = stop_server.getsockname()[1]

    def accept_and_close():
        c, _ = stop_server.accept()
        c.close()

    threading.Thread(target=accept_and_close, daemon=True).start()
    link = SonarLink('127.0.0.1', p, 2.0)
    try:
        with pytest.raises(ConnectionError):
            link.read_message(timeout=2.0)
    finally:
        link.close()
        stop_server.close()


def test_connection_refused_raises():
    with pytest.raises(Exception):
        SonarLink('127.0.0.1', free_port(), 1.0)
