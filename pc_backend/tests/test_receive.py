"""
test_receive.py — 快速测试 MCU → PC 事件接收
===========================================
测试 PC 后端能否正确接收并解析开发板上报的事件。

Usage:
    python test_receive.py --port COM6
"""

import sys
import time
sys.path.insert(0, '..')
from comm.uart_link import UartLink
from comm.protocol import Frame, SensorEvent, EventCode


def main():
    import argparse
    parser = argparse.ArgumentParser(description="测试 MCU → PC 事件接收")
    parser.add_argument("--port", default="COM6", help="串口号")
    parser.add_argument("--baud", type=int, default=115200, help="波特率")
    args = parser.parse_args()

    print("=" * 50)
    print("MCU → PC 接收测试")
    print("=" * 50)
    print("提示: 触摸开发板或刷 NFC 卡来产生事件")
    print("按 Ctrl+C 退出")
    print("=" * 50)

    link = UartLink(args.port, args.baud)

    def on_frame(frame: Frame):
        """帧回调：解析并打印事件"""
        print(f"\n收到帧: CMD=0x{frame.cmd:02X}, DATA={frame.data.hex()}")

        event = SensorEvent.from_frame(frame)
        if event is None:
            print(f"  → 非事件帧 (可能是命令回显)")
            return

        if event.event_code == EventCode.TOUCH and event.touch:
            print(f"  → 触摸事件: {event.touch.side.name} {event.touch.type.name}")

        elif event.event_code == EventCode.NFC and event.nfc:
            print(f"  → NFC 喂食: {event.nfc.duration}秒, 等级={event.nfc.level.name}")

        elif event.event_code == EventCode.POSE and event.pose:
            print(f"  → 姿态事件: {event.pose.state.name}")

        elif event.event_code == EventCode.ACK and event.ack:
            print(f"  → ACK: cmd=0x{event.ack.ack_cmd:02X}, status={event.ack.status}")

    if not link.open():
        print("串口打开失败！")
        return

    link.on_frame(on_frame)
    link.start_receiving()

    # 每 5 秒打印统计
    try:
        last_stats = time.time()
        while True:
            time.sleep(0.1)
            now = time.time()
            if now - last_stats > 5:
                stats = link.get_stats()
                print(f"\n[统计] frames={stats['frames_received']}, "
                      f"crc_fail={stats['crc_fail']}, timeout={stats['timeout']}, "
                      f"inv_len={stats['invalid_len']}, end_err={stats['end_byte_err']}")
                last_stats = now
    except KeyboardInterrupt:
        print("\n退出")
    finally:
        link.close()


if __name__ == "__main__":
    main()
