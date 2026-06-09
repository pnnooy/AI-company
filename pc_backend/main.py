"""
Desktop Academic Assistant Robot - PC Backend
=============================================
主入口：启动串口通信、AI 引擎、摄像头、Web API 服务。

更新日期: 2026-06-09（修复审查发现的问题 3/4/5）

Usage:
    python main.py --port COM6 --baud 115200
    python main.py --port COM6 --no-camera --no-ui
"""

import argparse
import logging
import queue
import time
from typing import Optional, Dict, Tuple

from comm.uart_link import UartLink
from comm.protocol import (
    Frame, Cmd, Expression, SensorEvent,
    EventCode, PoseState,
)
from ai_engine.state_machine import MachineState
from ai_engine.rules import (
    decide, decide_by_emotion, get_nfc_emotion_boost,
)

logger = logging.getLogger("main")

# 全局引用
_link: Optional[UartLink] = None

# ============================================================================
# 命令去重（问题5：防止事件洪泛导致重复发送）
# ============================================================================

# 相同命令在此时间内不重复发送
COMMAND_COOLDOWN_MS = 300
_command_history: Dict[Tuple[int, bytes], float] = {}

# POSE 事件去抖：同一类型（SHAKE/FALL）在此时间内只处理一次
POSE_DEBOUNCE_MS = 200
_last_pose_time: Dict[int, float] = {}  # key=pose_state, value=last_time


def _send_throttled(link: UartLink, cmd: int, data: bytes,
                    cooldown_ms: int = COMMAND_COOLDOWN_MS) -> bool:
    """
    发送命令，相同命令在 cooldown 内不重复发送。

    Returns:
        True 如果实际发送了，False 如果在冷却中
    """
    key = (cmd, data)
    now = time.time()
    if key in _command_history:
        if now - _command_history[key] < cooldown_ms / 1000.0:
            return False
    _command_history[key] = now
    return link.send_command(cmd, data)


def _pose_debounced(pose_state: int) -> bool:
    """POSE 事件去抖：返回 True 表示应该处理，False 表示跳过"""
    now = time.time()
    last = _last_pose_time.get(pose_state, 0)
    if now - last < POSE_DEBOUNCE_MS / 1000.0:
        return False
    _last_pose_time[pose_state] = now
    return True


# ============================================================================
# 事件处理
# ============================================================================

def handle_sensor_event(event: SensorEvent, fsm: MachineState, link: UartLink):
    """
    处理传感器事件：状态转移 → 规则决策 → 下发命令（带去重）

    Args:
        event: 解析后的传感器事件
        fsm: 情绪状态机
        link: 串口链路
    """
    now_ms = int(time.time() * 1000)

    if event.event_code == EventCode.TOUCH and event.touch:
        touch = event.touch
        logger.info(f"触摸事件: {touch.side.name} {touch.type.name}")

        fsm.on_touch_event(now_ms)

        result = decide(event, fsm.emotion_value)
        if result:
            expr, rgb, _ = result
            _send_throttled(link, Cmd.SET_EXPR, bytes([int(expr)]))
            _send_throttled(link, Cmd.SET_RGB, bytes(rgb))

    elif event.event_code == EventCode.NFC and event.nfc:
        nfc = event.nfc
        boost = get_nfc_emotion_boost(nfc.level)
        logger.info(f"NFC 喂食: {nfc.duration}秒, 等级={nfc.level.name}")

        # 问题4修复：emotion_boost 传入状态机，不需单独调 add_emotion
        fsm.on_nfc_event(now_ms, boost)

        result = decide(event, fsm.emotion_value)
        if result:
            expr, rgb, _ = result
            _send_throttled(link, Cmd.SET_EXPR, bytes([int(expr)]))
            _send_throttled(link, Cmd.SET_RGB, bytes(rgb))

    elif event.event_code == EventCode.POSE and event.pose:
        pose = event.pose

        # POSE 事件去抖：同一类型 200ms 内不重复处理
        if not _pose_debounced(pose.state.value):
            logger.debug(f"姿态事件去抖跳过: {pose.state.name}")
            return

        logger.info(f"姿态事件: {pose.state.name}")

        if pose.state == PoseState.FALL:
            fsm.on_alert_event(now_ms)
        elif pose.state == PoseState.SHAKE:
            fsm.on_shake_event(now_ms)

        result = decide(event, fsm.emotion_value)
        if result:
            expr, rgb, _ = result
            _send_throttled(link, Cmd.SET_EXPR, bytes([int(expr)]))
            _send_throttled(link, Cmd.SET_RGB, bytes(rgb))

    elif event.event_code == EventCode.ACK and event.ack:
        logger.debug(f"ACK: cmd=0x{event.ack.ack_cmd:02X}, status={event.ack.status}")


def on_uart_frame(frame: Frame, event_queue: queue.Queue):
    """串口帧回调：Frame → SensorEvent → 入队"""
    event = SensorEvent.from_frame(frame)
    if event:
        event_queue.put(event)
    else:
        logger.debug(f"非事件帧: CMD=0x{frame.cmd:02X}")


# ============================================================================
# 主循环
# ============================================================================

# 空闲时情绪驱动表情更新的间隔（问题3）
IDLE_EMOTION_UPDATE_MS = 5000   # 每 5 秒检查一次
IDLE_EMOTION_CHANGE_THRESHOLD = 0.05  # 情绪变化超过此值才更新


def run_main_loop(link: UartLink, fsm: MachineState, event_queue: queue.Queue):
    """主事件循环"""
    logger.info("主循环已启动，等待事件...")
    logger.info("按 Ctrl+C 退出")

    last_stats_time = time.time()
    last_emotion_update = time.time()
    last_emotion_value = fsm.emotion_value
    had_events = False  # 上一轮是否有事件

    try:
        while True:
            now = time.time()
            now_ms = int(now * 1000)

            # 处理事件队列（非阻塞）
            try:
                while True:
                    event = event_queue.get_nowait()
                    handle_sensor_event(event, fsm, link)
                    had_events = True
            except queue.Empty:
                pass

            # 状态机 tick（情绪衰减 + 超时转移）
            fsm.tick(now_ms)

            # 问题3修复：无事件时，情绪值驱动表情更新
            if (not had_events
                    and now - last_emotion_update > IDLE_EMOTION_UPDATE_MS / 1000.0
                    and abs(fsm.emotion_value - last_emotion_value) > IDLE_EMOTION_CHANGE_THRESHOLD):
                expr, rgb = decide_by_emotion(fsm.emotion_value)
                logger.debug(f"空闲情绪更新: {fsm.emotion_value:.2f} → {expr.name}")
                _send_throttled(link, Cmd.SET_EXPR, bytes([int(expr)]))
                _send_throttled(link, Cmd.SET_RGB, bytes(rgb))
                last_emotion_update = now
                last_emotion_value = fsm.emotion_value

            had_events = False

            # 定期打印统计（每 30 秒）
            if now - last_stats_time > 30:
                stats = link.get_stats()
                logger.info(
                    f"统计: frames={stats['frames_received']}, "
                    f"crc_fail={stats['crc_fail']}, timeout={stats['timeout']}, "
                    f"state={fsm.state.name}, emotion={fsm.emotion_value:.2f}"
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
        try:
            from web_api import WebAPI
            api = WebAPI(link, fsm)
            api.start(host="0.0.0.0", port=5000)
        except Exception as e:
            logger.warning(f"Web API 启动失败: {e}")

    # ── 6. 主循环 ──
    run_main_loop(link, fsm, event_queue)

    # ── 7. 清理 ──
    link.close()
    logger.info("PC Backend 已退出")


def parse_args():
    parser = argparse.ArgumentParser(description="桌面学术助手机器人 PC 后端")
    parser.add_argument("--port", default="COM6", help="串口号 (default: COM6)")
    parser.add_argument("--baud", type=int, default=115200, help="波特率 (default: 115200)")
    parser.add_argument("--no-camera", action="store_true", help="禁用摄像头")
    parser.add_argument("--no-ui", action="store_true", help="禁用 Web UI 服务")
    parser.add_argument("--debug", action="store_true", help="启用 DEBUG 日志")
    return parser.parse_args()


def setup_logging(level: int = logging.INFO):
    """配置日志（强制实时刷新，避免缓冲延迟）"""
    import sys
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    ))
    handler.setLevel(level)
    # 每次写日志立即刷新
    handler.stream.reconfigure(line_buffering=True) if hasattr(handler.stream, 'reconfigure') else None

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)

    # Flask 日志也走同一个 handler
    logging.getLogger("werkzeug").handlers = [handler]


if __name__ == "__main__":
    main()
