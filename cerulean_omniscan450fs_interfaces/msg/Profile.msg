# One ping from a Cerulean Omniscan 450 FS: echo strength along a single fixed beam.
#
# header.stamp is the host time when the ping was received (the sonar only reports
# time since its own power-up, see sonar_time_ms). header.frame_id is the sonar frame.
#
# Sample i of power_db lies at range  start_m + i * length_m / num_samples  (nearest first).
std_msgs/Header header

uint32 ping_number          # counts from 0 at sonar power-up
uint32 sonar_time_ms        # ms since sonar power-up at the time of the ping
uint32 acoustic_frequency_hz  # frequency of the acoustic signal (reported as "ping_hz" by the SDK)

float32 start_m             # start of the scanned window, from the transducer [m]
float32 length_m            # length of the scanned window [m]
float32 sound_speed_mps     # speed of sound used by the sonar [m/s]
uint8 gain_index            # 0-7
float32 analog_gain
float32 pulse_duration_s
uint8 channel_number

float32 min_power_db        # scale used for power_db
float32 max_power_db

# Reported by the sonar, meaning not documented for the FS unit. Passed through as is.
float32 transducer_heading_deg
float32 vehicle_heading_deg

float32[] power_db          # echo strength [dB], nearest sample first
