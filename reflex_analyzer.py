from typing import List, Optional
import numpy as np


class ReflexAnalyzer:
    def __init__(
        self,
        fsr_threshold: float = 0.8,
        nano_rise_len: int = 5,
        valid_latency_ms: float = 500,
    ):
        self.fsr_threshold = fsr_threshold
        self.nano_rise_len = nano_rise_len
        self.valid_latency_ms = valid_latency_ms

    def find_t0(
        self,
        sensor_time: List[float],
        fsr_voltage: List[float],
    ) -> Optional[float]:
        if len(sensor_time) == 0 or len(fsr_voltage) == 0:
            return None

        row_count = min(len(sensor_time), len(fsr_voltage))

        for i in range(row_count):
            if fsr_voltage[i] >= self.fsr_threshold:
                return sensor_time[i]

        return None

    def find_t1(
        self,
        t0: Optional[float],
        sensor_time: List[float],
        nano_voltage: List[float],
    ) -> Optional[float]:
        if t0 is None:
            return None

        if len(sensor_time) == 0 or len(nano_voltage) == 0:
            return None

        row_count = min(len(sensor_time), len(nano_voltage))

        start_idx = None
        for i in range(row_count):
            if sensor_time[i] >= t0:
                start_idx = i
                break

        if start_idx is None:
            return None

        rise_count = 0

        for i in range(start_idx + 1, row_count):
            if nano_voltage[i] > nano_voltage[i - 1]:
                rise_count += 1

                if rise_count >= self.nano_rise_len:
                    first_rise_idx = i - self.nano_rise_len + 1
                    return sensor_time[first_rise_idx]
            else:
                rise_count = 0

        return None

    def compute_latency(
        self,
        t0: Optional[float],
        t1: Optional[float],
    ) -> Optional[float]:
        if t0 is None or t1 is None:
            return None

        latency = t1 - t0

        if latency <= 0:
            return None

        if latency > self.valid_latency_ms:
            return None

        return latency

    def analyze_event(
        self,
        sensor_time: List[float],
        fsr_voltage: List[float],
        nano_voltage: List[float],
    ) -> dict:
        """
        回傳格式一定是 dict，不可以回傳 None。
        """
        t0 = self.find_t0(sensor_time, fsr_voltage)
        t1 = self.find_t1(t0, sensor_time, nano_voltage)
        latency = self.compute_latency(t0, t1)

        return {
            "t0_ms": t0,
            "t1_ms": t1,
            "latency_ms": latency,
            "is_valid": latency is not None,
        }

    def analyze_angle_response(
        self,
        t0: float,
        t1: float,
        yolo_time: List[float],
        yolo_angle: List[float],
        before_window_ms: float = 300,
        after_window_ms: float = 1500,
    ) -> dict:
        if t0 is None or t1 is None:
            raise ValueError("t0 或 t1 不存在，無法分析角度反應。")

        if len(yolo_time) == 0 or len(yolo_angle) == 0:
            raise ValueError("沒有角度時間序列資料。")

        if len(yolo_time) != len(yolo_angle):
            raise ValueError(
                f"yolo_time 與 yolo_angle 長度不一致："
                f"time={len(yolo_time)}, angle={len(yolo_angle)}"
            )

        times = np.array(yolo_time, dtype=float)
        angles = np.array(yolo_angle, dtype=float)

        # RA：t0 前 before_window_ms 內的平均角度
        before_mask = (times >= t0 - before_window_ms) & (times <= t0)

        if before_mask.sum() == 0:
            before_mask = times <= t0

        if before_mask.sum() == 0:
            raise ValueError("t0 前沒有足夠角度資料，無法計算 RA。")

        resting_angle = float(np.mean(angles[before_mask]))

        # REA：t1 後 after_window_ms 內最大角度
        after_mask = (times >= t1) & (times <= t1 + after_window_ms)

        if after_mask.sum() == 0:
            raise ValueError("t1 後沒有足夠角度資料，無法計算 REA。")

        after_times = times[after_mask]
        after_angles = angles[after_mask]

        peak_idx = int(np.argmax(after_angles))
        reflex_extension_angle = float(after_angles[peak_idx])
        peak_time = float(after_times[peak_idx])

        pead = reflex_extension_angle - resting_angle
        tte = peak_time - t1

        if tte <= 0:
            ext_vel = 0.0
        else:
            ext_vel = pead / (tte / 1000.0)

        return {
            "RA": resting_angle,
            "REA": reflex_extension_angle,
            "PEAD": pead,
            "TTE": tte,
            "Ext_Vel": ext_vel,
            "peak_time_ms": peak_time,
        }