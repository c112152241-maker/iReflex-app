import math
import time


class FakeSensorService:
    """
    第一版先用假感測器資料。
    之後會改成 SerialSensorService，讀 Arduino / RP2040。
    """

    def __init__(self):
        self.start_time = time.time()
        self.is_opened = False

    def open(self):
        self.start_time = time.time()
        self.is_opened = True

    def read(self):
        """
        回傳格式：
        {
            "fsr_voltage": float,
            "nano_voltage": float
        }
        """
        if not self.is_opened:
            return {
                "fsr_voltage": 0.0,
                "nano_voltage": 0.0,
            }

        elapsed = time.time() - self.start_time

        # 模擬 FSR：每 5 秒產生一次敲擊峰值
        fsr_base = 0.05
        fsr_peak = 1.5 * math.exp(-((elapsed % 5.0 - 1.0) ** 2) / 0.02)
        fsr_voltage = fsr_base + fsr_peak

        # 模擬 Nano：在 FSR 後面約 0.2 秒開始上升
        nano_base = 0.2
        nano_wave = 0.8 * math.exp(-((elapsed % 5.0 - 1.25) ** 2) / 0.08)
        nano_voltage = nano_base + nano_wave

        return {
            "fsr_voltage": float(fsr_voltage),
            "nano_voltage": float(nano_voltage),
        }

    def close(self):
        self.is_opened = False