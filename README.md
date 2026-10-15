# cerulean_omniscan450fs

A ROS 2 driver for the [Cerulean Omniscan 450 FS](https://ceruleansonar.com/product/omniscan-450fs-100m-300m/) forward-scan sonar. It connects over Ethernet (TCP), configures the sonar, and publishes each ping as a profile of echo strength against range. It can also publish a first-return range found on that profile.

The sonar has one fixed beam (0.8 deg horizontal, 50 deg vertical). Each ping is one line: it has no bearing, and the sonar does not report a detected range.

## Packages

- `cerulean_omniscan450fs_interfaces`: the `Profile` and `Detection` messages.
- `cerulean_omniscan450fs_driver`: the driver node, the first-return detection, and a fake sonar for testing without hardware.

```
cerulean_omniscan450fs_driver/
  omniscan450fs_node.py       the ROS node
  sonar_io.py                 connection to the sonar, with real read timeouts
  fake_sonar.py               a fake sonar for testing without hardware
  range_detection/
    threshold.py peak.py cfar.py rise.py    one first-return method per file, each with its source
    preprocessing.py          range correction and smoothing
    reference.py              where inside the return the range is placed
    tracker.py                median over pings
    rayscan.py                the result as a one-ray LaserScan
    finder.py                 puts them together
    base.py                   shared types and the method registry
```

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
| `~/scan` | `sensor_msgs/LaserScan` | The first return as a one-ray scan (with `topics.publish_scan`, off by default). One bearing, because the beam is fixed: `ranges[0]` is the range or `inf`, `intensities[0]` the peak power in dB. A fan of rays needs the beam swept, with each ping's bearing taken from outside the sonar (vehicle yaw or a pan mount). |

`header.stamp` is the time the ping was received by the host. The sonar only reports time since its own power-up, which is in `Profile.sonar_time_ms`.

## First-return detection

The sonar returns echo strength only, so the range is found on the profile. Two choices are made separately, both settable at runtime (`ros2 param set`; write a small number as `1.0e-9`, the command line reads `1e-9` as a string).

**`detection.method`, which return is the first return.** Each method is its own class in `range_detection/` with its source in the file header, and its own settings under `detection.<method>.`.

| Method | What it does | Source |
|---|---|---|
| `threshold` | First run of samples above the ping's noise floor (median) plus `min_snr_db`. | Amplitude detection, IHO C-13 ch. 3. The 10 dB default is the value reported for water-column and bottom echoes after loss compensation, de Moustier (OCEANS 2013) as cited by Al-Rawi et al. |
| `peak` | The strongest peak in the gate, accepted if wide enough. Its threshold is the smaller of the average level before and after it. This finds the strongest return, not the nearest. | Ferretti et al., single beam seabed pick |
| `cfar` | Each sample is tested against a threshold from the nearer reference cells so the false-alarm rate stays constant. Textbook 1-D cell-averaging form, not the K-distribution estimator of the paper. | Abu & Diamant, IET Radar Sonar Navig. 2020 |
| `rise` | First place where the smoothed profile rises by `rise_db` between consecutive samples. | Al-Rawi et al., OCEANS 2017 (moving-average method) |

To add a method, write a class in its own file that subclasses `FirstReturnDetector` with a `name`, a `Params` dataclass and a `find()`, decorate it with `@register`, and import it in `range_detection/__init__.py`. The node declares its parameters from the dataclass, so nothing else changes. A test checks that the YAML lists exactly the code's defaults.

**`detection.reference`, where inside that return the range is placed.** `leading_edge` (first arrival), `peak` (maximum amplitude) or `centroid` (centre of mass of the amplitude), the three amplitude detection methods of IHO C-13 ch. 3. The IHO text notes the leading edge degrades as the incidence angle grows and the rise gets less sharp, which is likely for this sonar's 50 deg tall beam at grazing incidence.

**Optional preprocessing**

- `tvg_enabled`: range correction `spreading * log10(R/Rref) + 2*alpha*R` (Ferretti et al. eq. 2). Off by default. Whether the sonar already applies range-dependent gain is not known.
- `smoothing`: `moving_average` (Al-Rawi et al.) or `hann` (Bourguignon et al.). It spreads an edge over its window, so a threshold crossing can move, earlier or later depending on the threshold, by up to about half the window.
- `median_pings`: median of the first-return range over the last N pings, which removes single-ping spikes (Al-Rawi et al. median-filter the along-track first returns). The output lags by about N/2 pings. `Detection.raw_range_m` keeps the unfiltered value.

**Notes**

- The methods are checked against synthetic profiles only, and the defaults need tuning on real data.
- `peak` follows the published threshold, which is the background average, so about half the neighbouring noise samples join the return. `peak.margin_db` stops that.
- `peak.background_samples` is a free setting for the width.
- The CFAR false-alarm rate is exact for exponentially distributed noise power and is tested against that. A real background will differ, so `cfar.pfa` is a design value to tune.

## Notes

- `brping`'s `Omniscan450.wait_message()` spins at full CPU and never times out when the sonar sends nothing over TCP. The driver reads the socket itself with `select()` and uses `brping` only for the message definitions and commands, so a silent sonar triggers a reconnect.
- The driver reconnects after 5 s without data and sends `enable=false` on shutdown.
- Whether the first sample sits at the start or the centre of its range bin is not documented. Check it on hardware.
- To run several sonars together the SDK has `control_set_sync_channel_number(channel, total)`, which the driver does not call yet. What it does on the sonar has not been checked.

## Tests

```bash
cd cerulean_omniscan450fs_driver && python3 -m pytest test
```



