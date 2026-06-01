"""
Desktop Academic Assistant Robot - PC Backend
=============================================
主入口：启动串口通信、AI引擎、摄像头、Web API 服务。

Usage:
    python main.py --port COM6 --baud 115200
"""

import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")


def parse_args():
    parser = argparse.ArgumentParser(description="桌面学术助手机器人 PC 后端")
    parser.add_argument("--port", default="COM6", help="串口号 (default: COM6)")
    parser.add_argument("--baud", type=int, default=115200, help="波特率 (default: 115200)")
    parser.add_argument("--no-camera", action="store_true", help="禁用摄像头")
    parser.add_argument("--no-ui", action="store_true", help="禁用 Web UI 服务")
    return parser.parse_args()


def main():
    args = parse_args()
    logger.info("=" * 50)
    logger.info("桌面学术助手机器人 - PC Backend 启动中...")
    logger.info(f"串口: {args.port} @ {args.baud} bps")
    logger.info("=" * 50)

    # TODO: 各模块依次初始化
    # 1. 串口通信 (comm/uart_link.py)
    # 2. AI 引擎 (ai_engine/state_machine.py)
    # 3. 摄像头 (camera/face_detect.py)  -- 可选
    # 4. Web API 服务 (供前端调用)

    logger.info("PC Backend 启动完成，等待事件...")
    # TODO: 主循环 - 事件驱动


if __name__ == "__main__":
    main()
