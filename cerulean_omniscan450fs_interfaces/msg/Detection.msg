# First-return detection on one Profile. See cerulean_omniscan450fs_driver range_detector.
# Powers are after the detector's preprocessing (range correction, smoothing) if enabled.
std_msgs/Header header      # same stamp and frame as the Profile it came from

uint32 ping_number
bool detected               # false when no return passed the detector
float32 range_m             # range to the first return, NaN if not detected. After the median over
                            # pings when detection.median_pings > 1
float32 raw_range_m         # the same for this ping alone
float32 peak_power_db       # strongest sample of the first return
float32 threshold_db        # threshold that was applied to this ping
float32 snr_db              # peak_power_db minus the ping's noise floor
float32 width_m             # extent of the first return above threshold
