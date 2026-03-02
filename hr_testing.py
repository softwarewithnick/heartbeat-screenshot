import asyncio
import os
import time
from datetime import datetime

import mss
from bleak import BleakScanner, BleakClient

DEVICE_NAME = "KYTO 2809_520D"
HR_MEASUREMENT_UUID = "00002a37-0000-1000-8000-00805f9b34fb"
HR_SPIKE_THRESHOLD = 100
SCREENSHOT_INTERVAL = 5  # seconds between screenshots while HR > threshold
MONITOR_NUMBER = 2  # 2560x1440 center monitor
SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")

last_screenshot_time = 0.0


def take_screenshot():
    global last_screenshot_time
    now = time.time()
    if now - last_screenshot_time < SCREENSHOT_INTERVAL:
        return
    last_screenshot_time = now

    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(SCREENSHOT_DIR, f"hr_spike_{timestamp}.png")

    with mss.mss() as sct:
        img = sct.grab(sct.monitors[MONITOR_NUMBER])
        mss.tools.to_png(img.rgb, img.size, output=filepath)

    print(f"  -> Screenshot saved: {filepath}")


def parse_heart_rate(data: bytearray) -> int:
    flags = data[0]
    hr_format_16bit = flags & 0x01
    if hr_format_16bit:
        return int.from_bytes(data[1:3], byteorder="little")
    return data[1]


def on_hr_notification(sender, data: bytearray):
    hr = parse_heart_rate(data)
    print(f"Heart Rate: {hr} bpm")

    if hr > HR_SPIKE_THRESHOLD:
        print(f"  ** HR spike detected ({hr} > {HR_SPIKE_THRESHOLD})!")
        take_screenshot()


async def main():
    print(f"Scanning for {DEVICE_NAME}...")
    device = await BleakScanner.find_device_by_name(DEVICE_NAME, timeout=10.0)

    if device is None:
        print(f"Could not find device '{DEVICE_NAME}'. Make sure it is on and in range.")
        return

    print(f"Found {device.name} ({device.address}). Connecting...")

    async with BleakClient(device) as client:
        print("Connected! Reading heart rate... (Ctrl+C to stop)")
        print(f"Screenshots will be taken every {SCREENSHOT_INTERVAL}s while HR > {HR_SPIKE_THRESHOLD} bpm\n")
        await client.start_notify(HR_MEASUREMENT_UUID, on_hr_notification)

        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

        await client.stop_notify(HR_MEASUREMENT_UUID)
        print("\nDisconnected.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
