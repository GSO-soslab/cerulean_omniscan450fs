# cerulean_omniscan450fs

A ROS 2 driver for the [Cerulean Omniscan 450 FS](https://ceruleansonar.com/product/omniscan-450fs-100m-300m/) forward-scan sonar. It connects over Ethernet (TCP), configures the sonar, and publishes each ping as a profile of echo strength against range. It can also publish a first-return range found on that profile.

The sonar has one fixed beam (0.8 deg horizontal, 50 deg vertical). Each ping is one line: it has no bearing, and the sonar does not report a detected range.

## Packages

- `cerulean_omniscan450fs_interfaces`: the `Profile` and `Detection` messages.
- `cerulean_omniscan450fs_driver`: the driver node, the first-return detector, and a fake sonar for testing without hardware.

## Dependencies

- [`brping`](https://github.com/bluerobotics/ping-python), the Blue Robotics ping protocol library (rosdep key `python3-bluerobotics-ping-pip`)

```bash
pip install --user bluerobotics-ping --upgrade
```

## Building

```bash
colcon build --packages-select cerulean_omniscan450fs_interfaces cerulean_omniscan450fs_driver
```

## Running

```bash
ros2 launch cerulean_omniscan450fs_driver omniscan450fs_driver.launch.py
```

Set `interface.ip_address` in `config/omniscan450fs_driver.yaml` to the address configured on the sonar. Parameters can be changed while the node runs, for example `ros2 param set /omniscan450fs_driver configuration.length_m 20.0`.

### Without hardware

```bash
ros2 run cerulean_omniscan450fs_driver fake_sonar --port 51200 --target 12:0.5:-40
ros2 run cerulean_omniscan450fs_driver omniscan450fs_driver --ros-args -p interface.ip_address:=127.0.0.1
```

`--target RANGE_M:WIDTH_M:LEVEL_DB` can be repeated.

## Published Topics

Topics are relative to the node, so several sonars can run side by side under different node names.

| Topic | Message Type | Description |
|---|---|---|
| `~/profile` | `cerulean_omniscan450fs_interfaces/Profile` | One ping: echo strength in dB from the nearest sample to the farthest, with the ping metadata. Sample `i` lies at `start_m + i * length_m / num_samples` |
| `~/range` | `sensor_msgs/Range` | Range to the first return, `inf` if there is none (with `topics.publish_range`) |
| `~/detection` | `cerulean_omniscan450fs_interfaces/Detection` | The first-return result with peak power, threshold, SNR and width |

`header.stamp` is the time the ping was received by the host. The sonar only reports time since its own power-up, which is in `Profile.sonar_time_ms`.

## First-return detection

The sonar returns echo strength only, so the range is found on the profile:

1. The noise floor is the median power inside the range gate.
2. The threshold is the larger of `noise floor + min_snr_db` and `min_power_db`.
3. The first return is the first run of `min_width_samples` consecutive samples above the threshold inside `[min_range_m, max_range_m]`. Its range is the leading edge of the run.

This is a first version. It does not compensate for range-dependent loss, use an adaptive (CFAR) threshold, or track returns across pings. Tune it on real profiles before relying on it. For a forward-looking mount, a seabed return is not a single range, because the beam is 50 deg tall.

## Notes

- `brping`'s `Omniscan450.wait_message()` spins at full CPU and never times out when the sonar sends nothing over TCP. The driver reads the socket itself with `select()` and uses `brping` only for the message definitions and commands, so a silent sonar triggers a reconnect.
- The driver reconnects after 5 s without data and sends `enable=false` on shutdown.
- Whether the first sample sits at the start or the centre of its range bin is not documented. Check it on hardware.

## Tests

```bash
cd cerulean_omniscan450fs_driver && python3 -m pytest test
```

## Acknowledgement

Based on the protocol use in [cerulean-omniscan450-frontscan-ros2-driver](https://github.com/Aatmaj9/cerulean-omniscan450-frontscan-ros2-driver) (MIT, Aatmaj Bhayani) and the [Blue Robotics ping-python](https://github.com/bluerobotics/ping-python) library. The package layout follows [cerulean_surveyor_mbes](https://github.com/GSO-soslab/cerulean_surveyor_mbes).
