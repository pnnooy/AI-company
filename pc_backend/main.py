"""
Desktop Academic Assistant Robot - PC Backend
=============================================
主入口：启动串口通信、AI 引擎、摄像头、Web API 服务。

更新日期: 2026-06-04（适配新协议 v2.0）

Usage:
    python main.py --port COM6 --baud 115200
    python main.py --port COM6 --no-camera --no-ui
"""

import argparse
import logging
import queue
import signal
import sys
import time
from typing import Optional

from comm.uart_link import UartLink
from comm.protocol import (
    Frame, Cmd, Expression, SensorEvent,
    EventCode, PoseState,
)
from ai_engine.state_machine import MachineState
from ai_engine.rules import (
    decide, decide_expression_and_rgb, get_nfc_emotion_boost,
)

logger = logging.getLogger("main")

# 全局引用，用于优雅退出
_link: Optional[UartLink] = None


def setup_logging(level: int = logging.INFO):
    """配置日志"""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def parse_args():
    parser = argparse.ArgumentParser(description="桌面学术助手机器人 PC 后端")
    parser.add_argument("--port", default="COM6", help="串口号 (default: COM6)")
    parser.add_argument("--baud", type=int, default=115200, help="波特率 (default: 115200)")
    parser.add_argument("--no-camera", action="store_true", help="禁用摄像头")
    parser.add_argument("--no-ui", action="store_true", help="禁用 Web UI 服务")
    parser.add_argument("--debug", action="store_true", help="启用 DEBUG 日志")
    return parser.parse_args()


# ============================================================================
# 事件处理
# ============================================================================

def handle_sensor_event(event: SensorEvent, fsm: MachineState, link: UartLink):
    """
    处理传感器事件：状态转移 → 规则决策 → 下发命令

    Args:
        event: 解析后的传感器事件
        fsm: 情绪状态机
        link: 串口链路（用于下发命令）
    """
    now_ms = int(time.time() * 1000)

    if event.event_code == EventCode.TOUCH and event.touch:
        touch = event.touch
        logger.info(f"触摸事件: {touch.side.name} {touch.type.name}")

        # 状态转移
        fsm.on_touch_event(now_ms)

        # 规则决策
        result = decide(event, fsm.emotion_value)
        if result:
            expr, rgb, duration = result
            link.send_command(Cmd.SET_EXPR, bytes([int(expr)]))
            link.send_command(Cmd.SET_RGB, bytes(rgb))

    elif event.event_code == EventCode.NFC and event.nfc:
        nfc = event.nfc
        logger.info(f"NFC 喂食: {nfc.duration}秒, 等级={nfc.level.name}")

        # 状态转移
        fsm.on_nfc_event(now_ms)

        # 情绪提升（基于喂食等级）
        boost = get_nfc_emotion_boost(nfc.level)
        fsm.add_emotion(boost, now_ms)

        # 规则决策
        result = decide(event, fsm.emotion_value)
        if result:
            expr, rgb, duration = result
            link.send_command(Cmd.SET_EXPR, bytes([int(expr)]))
            link.send_command(Cmd.SET_RGB, bytes(rgb))

    elif event.event_code == EventCode.POSE and event.pose:
        pose = event.pose
        logger.info(f"姿态事件: {pose.state.name}")

        if pose.state == PoseState.FALL:
            fsm.on_alert_event(now_ms)
        elif pose.state == PoseState.SHAKE:
            fsm.on_shake_event(now_ms)

        # 规则决策
        result = decide(event, fsm.emotion_value)
        if result:
            expr, rgb, duration = result
            link.send_command(Cmd.SET_EXPR, bytes([int(expr)]))
            link.send_command(Cmd.SET_RGB, bytes(rgb))

    elif event.event_code == EventCode.ACK and event.ack:
        logger.debug(f"收到 ACK: cmd=0x{event.ack.ack_cmd:02X}, status={event.ack.status}")


def on_uart_frame(frame: Frame, event_queue: queue.Queue):
    """串口帧回调：Frame → SensorEvent → 入队"""
    event = SensorEvent.from_frame(frame)
    if event:
        event_queue.put(event)
    else:
        # 可能是 PC→MCU 的命令帧被回显，忽略
        logger.debug(f"非事件帧: CMD=0x{frame.cmd:02X}")


# ============================================================================
# 主循环
# ============================================================================

def run_main_loop(link: UartLink, fsm: MachineState, event_queue: queue.Queue):
    """主事件循环"""
    logger.info("主循环已启动，等待事件...")
    logger.info("按 Ctrl+C 退出")

    last_stats_time = time.time()

    try:
        while True:
            # 处理事件队列（非阻塞）
            try:
                while True:
                    event = event_queue.get_nowait()
                    handle_sensor_event(event, fsm, link)
            except queue.Empty:
                pass

            # 状态机 tick（情绪衰减 + 超时转移）
            fsm.tick(int(time.time() * 1000))

            # 定期打印统计（每 10 秒）
            now = time.time()
            if now - last_stats_time > 10:
                stats = link.get_stats()
                logger.debug(
                    f"协议统计: frames={stats['frames_received']}, "
                    f"crc_fail={stats['crc_fail']}, timeout={stats['timeout']}"
                )
                last_stats_time = now

            time.sleep(0.01)  # 10ms 循环

    except KeyboardInterrupt:
        logger.info("收到退出信号")


# ============================================================================
# 入口
# ============================================================================

def main():
    global _link

    args = parse_args()
    setup_logging(logging.DEBUG if args.debug else logging.INFO)

    print("=" * 50)
    print("桌面学术助手机器人 - PC Backend v2.0")
    print("=" * 50)
    logger.info(f"串口: {args.port} @ {args.baud} bps")
    logger.info(f"摄像头: {'禁用' if args.no_camera else '启用'}")
    logger.info(f"Web UI: {'禁用' if args.no_ui else '启用'}")
    print("=" * 50)

    # ── 1. 串口通信 ──
    link = UartLink(args.port, args.baud)
    if not link.open():
        logger.error("串口打开失败，退出")
        return
    _link = link

    # ── 2. 事件队列 + 帧回调 ──
    event_queue = queue.Queue()
    link.on_frame(lambda frame: on_uart_frame(frame, event_queue))
    link.start_receiving()

    # ── 3. AI 引擎 ──
    fsm = MachineState()
    logger.info(f"初始状态: {fsm.state.name}, 情绪值: {fsm.emotion_value:.2f}")

    # ── 4. 摄像头（可选）──
    face_detector = None
    if not args.no_camera:
        try:
            from camera.face_detect import FaceDetector, CameraCapture
            camera = CameraCapture(device_id=0, width=640, height=480)
            if camera.open():
                face_detector = FaceDetector()
                logger.info("摄像头已启用")
            else:
                logger.warning("摄像头打开失败，跳过")
        except ImportError as e:
            logger.warning(f"摄像头模块导入失败: {e}")
        except Exception as e:
            logger.warning(f"摄像头初始化失败: {e}")

    # ── 5. Web API（可选）──
    if not args.no_ui:
        # TODO: 启动 Web API 服务（后台线程）
        logger.info("Web API 服务暂未实现，使用 --no-ui 跳过")

    # ── 6. 主循环 ──
    run_main_loop(link, fsm, event_queue)

    # ── 7. 清理 ──
    link.close()
    logger.info("PC Backend 已退出")


if __name__ == "__main__":
    main()
