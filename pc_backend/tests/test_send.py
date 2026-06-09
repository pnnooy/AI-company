"""
test_send.py — 快速测试 PC → MCU 命令发送
=========================================
测试 PC 后端能否正确发送命令帧到开发板。

Usage:
    python test_send.py --port COM6
"""

import sys
import time
sys.path.insert(0, '..')
from comm.uart_link import UartLink
from comm.protocol import Cmd, Expression


def main():
    import argparse
    parser = argparse.ArgumentParser(description="测试 PC → MCU 命令发送")
    parser.add_argument("--port", default="COM6", help="串口号")
    parser.add_argument("--baud", type=int, default=115200, help="波特率")
    args = parser.parse_args()

    print("=" * 50)
    print("PC → MCU 发送测试")
    print("=" * 50)

    link = UartLink(args.port, args.baud)
    if not link.open():
        print("串口打开失败！")
        return

    try:
        # Test 1: 设置 HAPPY 表情
        print("\n[1] 发送 SET_EXPR HAPPY...")
        link.send_command(Cmd.SET_EXPR, bytes([Expression.HAPPY]))
        time.sleep(1)

        # Test 2: 设置红色灯光
        print("[2] 发送 SET_RGB RED...")
        link.send_command(Cmd.SET_RGB, bytes([255, 0, 0]))
        time.sleep(1)

        # Test 3: 设置蓝色灯光
        print("[3] 发送 SET_RGB BLUE...")
        link.send_command(Cmd.SET_RGB, bytes([0, 0, 255]))
        time.sleep(1)

        # Test 4: 各种表情循环
        expressions = [
            (Expression.NORMAL, "NORMAL"),
            (Expression.HAPPY, "HAPPY"),
            (Expression.FOCUS, "FOCUS"),
            (Expression.ANGRY, "ANGRY"),
            (Expression.SLEEP, "SLEEP"),
            (Expression.SURPRISE, "SURPRISE"),
            (Expression.SAD, "SAD"),
            (Expression.LOVE, "LOVE"),
        ]
        for expr, name in expressions:
            print(f"[4] 发送 SET_EXPR {name}...")
            link.send_command(Cmd.SET_EXPR, bytes([int(expr)]))
            time.sleep(1.5)

        # Test 5: 查询状态
        print("[5] 发送 QUERY...")
        link.send_command(Cmd.QUERY)
        time.sleep(0.5)

        # Test 6: 心跳
        print("[6] 发送 HEARTBEAT...")
        link.send_command(Cmd.HEARTBEAT, bytes([0x01]))

        print("\n所有测试发送完成！")

    except KeyboardInterrupt:
        print("\n中断")
    finally:
        link.close()


if __name__ == "__main__":
    main()
