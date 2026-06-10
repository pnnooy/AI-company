"""
Desktop Academic Assistant Robot - PC Backend
=============================================
主入口：启动串口通信、AI 引擎、摄像头、Web API 服务。

更新日期: 2026-06-09（摄像头接入 + DeepFace 情绪识别）

Usage:
    python main.py --port COM6 --baud 115200
    python main.py --port COM6 --no-camera --no-ui
"""

import os
# 抑制 TensorFlow oneDNN 日志刷屏
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')
os.environ.setdefault('TF_ENABLE_ONEDNN_OPTS', '0')

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

# LLM 模块（可选）
try:
    from ai_engine.llm_client import LLMClient
    HAS_LLM = True
except ImportError:
    HAS_LLM = False

# 摄像头模块（可选）
try:
    from camera.face_detect import (
        FaceDetector, CameraCapture,
        draw_status_overlay, create_preview_window,
        show_preview, destroy_preview,
    )
    HAS_CAMERA = True
except ImportError:
    HAS_CAMERA = False

logger = logging.getLogger("main")

# 全局引用
_link: Optional[UartLink] = None
_llm_client = None  # 供 _trigger_llm_react 使用
# 全局缓存（供 web_api 摄像头帧端点读取）
cached_frame = None
cached_faces = []
cached_user_emotion = "neutral"
cached_emotion_conf = 0.0
current_expression = "normal"  # 供 web_api 读取
last_rgb = [30, 20, 60]        # 最近一次 RGB 值（默认暗紫色）
camera_jpeg = None             # 最新摄像头帧（JPEG bytes，供 web_api）

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
    # 同步 RGB 全局状态
    global last_rgb
    if cmd == Cmd.SET_RGB and len(data) >= 3:
        last_rgb = list(data[:3])
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
# 事件历史（供 LLM 上下文使用）
# ============================================================================

# 最近事件记录（最多保留 30 条）
_event_history: list = []


def _event_description(event: SensorEvent) -> str:
    """将传感器事件转为 LLM 可读的文字描述"""
    import datetime
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    if event.event_code == EventCode.TOUCH and event.touch:
        t = event.touch
        side_name = "左边" if t.side.name == "LEFT" else "右边"
        type_name = "轻触" if t.type.name == "TAP" else "长按" if t.type.name == "HOLD" else t.type.name
        return f"[{ts}] 你{type_name}了皮皮的{side_name}"
    elif event.event_code == EventCode.NFC and event.nfc:
        n = event.nfc
        level_name = {"TAP": "小零食", "SNACK": "加餐", "MEAL": "正餐", "FEAST": "大餐"}.get(n.level.name, n.level.name)
        return f"[{ts}] 你喂了皮皮{n.duration}秒（{level_name}）"
    elif event.event_code == EventCode.POSE and event.pose:
        p = event.pose
        if p.state.name == "SHAKE":
            return f"[{ts}] 皮皮被摇晃了"
        elif p.state.name == "FALL":
            return f"[{ts}] 皮皮摔倒了"
    elif event.event_code == EventCode.ACK:
        return f"[{ts}] 设备确认"
    return f"[{ts}] 未知事件"


# ============================================================================
# 事件处理
# ============================================================================

def handle_sensor_event(event: SensorEvent, fsm: MachineState, link: UartLink) -> str:
    """
    处理传感器事件：状态转移 → 规则决策 → 下发命令（带去重）

    Returns:
        设置的表情名称（"normal", "happy" 等）
    """
    now_ms = int(time.time() * 1000)
    expression = None  # 最终设置的表情

    if event.event_code == EventCode.TOUCH and event.touch:
        touch = event.touch
        logger.info(f"触摸事件: {touch.side.name} {touch.type.name}")

        fsm.on_touch_event(now_ms)
        _event_history.append(_event_description(event))

        result = decide(event, fsm.emotion_value)
        if result:
            expr, rgb, _ = result
            expression = expr.name.lower()
            _send_throttled(link, Cmd.SET_EXPR, bytes([int(expr)]))
            _send_throttled(link, Cmd.SET_RGB, bytes(rgb))

    elif event.event_code == EventCode.NFC and event.nfc:
        nfc = event.nfc
        boost = get_nfc_emotion_boost(nfc.level)
        logger.info(f"NFC 喂食: {nfc.duration}秒, 等级={nfc.level.name}")

        # 问题4修复：emotion_boost 传入状态机，不需单独调 add_emotion
        fsm.on_nfc_event(now_ms, boost)
        _event_history.append(_event_description(event))

        # SNACK+ 等级触发 LLM 即时反应
        if nfc.level.value >= 1:  # SNACK 或更高
            _trigger_llm_react(f"你刚刚喂了皮皮 {nfc.duration} 秒（{nfc.level.name}）！")

        result = decide(event, fsm.emotion_value)
        if result:
            expr, rgb, _ = result
            expression = expr.name.lower()
            _send_throttled(link, Cmd.SET_EXPR, bytes([int(expr)]))
            _send_throttled(link, Cmd.SET_RGB, bytes(rgb))

    elif event.event_code == EventCode.POSE and event.pose:
        pose = event.pose

        # POSE 事件去抖：同一类型 200ms 内不重复处理
        if not _pose_debounced(pose.state.value):
            logger.debug(f"姿态事件去抖跳过: {pose.state.name}")
            return

        logger.info(f"姿态事件: {pose.state.name}")
        _event_history.append(_event_description(event))

        if pose.state == PoseState.FALL:
            fsm.on_alert_event(now_ms)
            _trigger_llm_react("皮皮刚刚摔倒了！")
        elif pose.state == PoseState.SHAKE:
            fsm.on_shake_event(now_ms)

        result = decide(event, fsm.emotion_value)
        if result:
            expr, rgb, _ = result
            expression = expr.name.lower()
            _send_throttled(link, Cmd.SET_EXPR, bytes([int(expr)]))
            _send_throttled(link, Cmd.SET_RGB, bytes(rgb))

    elif event.event_code == EventCode.ACK and event.ack:
        logger.debug(f"ACK: cmd=0x{event.ack.ack_cmd:02X}, status={event.ack.status}")

    return expression if expression else "normal"


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

# 人脸检测参数
FACE_DETECT_INTERVAL_MS = 1000   # 每 1 秒检测一次
PREVIEW_REFRESH_MS = 33          # 预览窗口每 33ms 刷新（30fps）
FACE_ABSENT_TIMEOUT_MS = 45000   # 45 秒无人脸 → 判定离开（避免短暂误检）
FACE_PRESENT_COUNT = 3           # 连续 3 次检测到 → 判定在场


def run_main_loop(link: UartLink, fsm: MachineState, event_queue: queue.Queue,
                 camera=None, face_detector=None, preview_window=None,
                 emotion_recognizer=None, llm_client=None):
    """主事件循环"""
    logger.info("主循环已启动，等待事件...")
    logger.info("按 Ctrl+C 退出")

    last_stats_time = time.time()
    last_emotion_update = time.time()
    last_face_detect_time = 0.0
    last_preview_time = 0.0
    last_emotion_value = fsm.emotion_value
    had_events = False

    # 人脸在场跟踪
    face_present_count = 0           # 连续检测到人脸的次数
    user_present = False             # 当前用户是否在场
    last_face_seen_time = 0.0        # 最后一次看到人脸的时间
    # 使用模块级全局缓存
    global cached_frame, cached_faces, cached_user_emotion, cached_emotion_conf, current_expression, camera_jpeg

    # LLM 相关
    current_expression = "normal"
    last_llm_reflect_time = 0.0
    last_llm_result_check = 0.0

    try:
        while True:
            now = time.time()
            now_ms = int(now * 1000)

            # 处理事件队列（非阻塞）
            try:
                while True:
                    event = event_queue.get_nowait()
                    expr = handle_sensor_event(event, fsm, link)
                    if expr != "normal" or not had_events:
                        current_expression = expr
                    had_events = True
            except queue.Empty:
                pass

            # ── 摄像头预览刷新（高频：每 80ms ≈ 12fps）──
            if (camera and preview_window
                    and now - last_preview_time > PREVIEW_REFRESH_MS / 1000.0):
                last_preview_time = now
                frame = camera.read()
                if frame is not None:
                    cached_frame = frame
                    # 编码 JPEG 供 web_api
                    try:
                        import cv2
                        _, jpg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
                        camera_jpeg = jpg.tobytes()
                    except:
                        pass
                    # 用缓存的人脸数据画叠加层
                    face_count = len(cached_faces)
                    annotated = draw_status_overlay(
                        frame, cached_faces, user_present, face_count,
                        fsm.state.name, fsm.emotion_value,
                        cached_user_emotion, cached_emotion_conf,
                    )
                    if not show_preview(preview_window, annotated):
                        logger.info("预览窗口已关闭，按 Ctrl+C 退出")

            # ── 人脸检测 + 情绪识别（低频：每 2 秒）──
            if (camera and face_detector
                    and now - last_face_detect_time > FACE_DETECT_INTERVAL_MS / 1000.0):
                last_face_detect_time = now
                frame = cached_frame if cached_frame is not None else camera.read()
                if frame is not None:
                    has_face, cached_faces = face_detector.detect_with_boxes(frame)
                    face_count = len(cached_faces)

                    if has_face:
                        face_present_count += 1
                        last_face_seen_time = now
                        if not user_present and face_present_count >= FACE_PRESENT_COUNT:
                            user_present = True
                            logger.info("用户出现在摄像头前")
                            _on_user_arrive(fsm, link, now_ms)

                        # 用户情绪识别
                        if emotion_recognizer and face_count > 0:
                            rois = [frame[y:y+h, x:x+w] for (x, y, w, h) in cached_faces]
                            results = emotion_recognizer.predict_all(rois)
                            if results:
                                cached_user_emotion, cached_emotion_conf = results[0]
                                # 用户情绪影响机器人
                                _on_user_emotion(fsm, link, now_ms,
                                                 cached_user_emotion, cached_emotion_conf)
                    else:
                        face_present_count = 0
                        if user_present and now - last_face_seen_time > FACE_ABSENT_TIMEOUT_MS / 1000.0:
                            user_present = False
                            logger.info("用户离开")
                            _on_user_leave(fsm, link, now_ms)

            # 状态机 tick（情绪衰减 + 超时转移）
            fsm.tick(now_ms)

            # ── LLM 反思（每 15s，低优先级）──
            if (llm_client and llm_client.available
                    and now - last_llm_reflect_time > 15):
                last_llm_reflect_time = now
                # 裁剪事件历史
                events_for_llm = _event_history[-15:] if _event_history else []
                llm_client.reflect(
                    state=fsm.state.name,
                    emotion=fsm.emotion_value,
                    expression=current_expression,
                    user_present=user_present,
                    events=events_for_llm,
                )

            # ── 处理 LLM 结果 ──
            if llm_client:
                result = llm_client.get_result()
                if result:
                    delta = result.get("emotion_delta", 0.0)
                    suggested_expr = result.get("expression", "normal")
                    if abs(delta) > 0:
                        fsm.add_emotion(delta, now_ms)

                    # 如果 LLM 建议切换表情且最近没有传感器事件
                    if not had_events and suggested_expr != current_expression:
                        try:
                            from comm.protocol import Expression
                            expr_enum = Expression[suggested_expr.upper()]
                            logger.debug(f"LLM 建议切换: {current_expression} → {suggested_expr}")
                            _send_throttled(link, Cmd.SET_EXPR, bytes([int(expr_enum)]))
                            current_expression = suggested_expr
                        except KeyError:
                            pass

                    # 打印内心独白
                    thought = result.get("thought", "") or result.get("reply", "")
                    if thought:
                        logger.info(f"皮皮: {thought}")

            # 空闲时情绪值驱动表情更新
            if (not had_events
                    and now - last_emotion_update > IDLE_EMOTION_UPDATE_MS / 1000.0
                    and abs(fsm.emotion_value - last_emotion_value) > IDLE_EMOTION_CHANGE_THRESHOLD):
                expr, rgb = decide_by_emotion(fsm.emotion_value)
                logger.debug(f"空闲情绪更新: {fsm.emotion_value:.2f} → {expr.name}")
                _send_throttled(link, Cmd.SET_EXPR, bytes([int(expr)]))
                _send_throttled(link, Cmd.SET_RGB, bytes(rgb))
                current_expression = expr.name.lower()
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


def _on_user_arrive(fsm: MachineState, link: UartLink, now_ms: int):
    """用户出现时的反应"""
    if fsm.state == fsm.state.SLEEP:
        fsm.state = fsm.state.IDLE
        logger.info("用户出现，从 SLEEP 唤醒")
    fsm.add_emotion(0.1, now_ms)
    expr, rgb = decide_by_emotion(fsm.emotion_value)
    _send_throttled(link, Cmd.SET_EXPR, bytes([int(expr)]))
    _send_throttled(link, Cmd.SET_RGB, bytes(rgb))
    # LLM 即时反应
    _trigger_llm_react("你刚刚出现在皮皮面前了！")


def _on_user_leave(fsm: MachineState, link: UartLink, now_ms: int):
    """用户离开时的反应"""
    fsm.last_event_time = now_ms  # 加速进入休眠
    _trigger_llm_react("你刚刚离开了...")


def _trigger_llm_react(trigger: str):
    """触发 LLM 即时反应（通过全局 llm_client）"""
    global _llm_client
    if _llm_client and _llm_client.available:
        _llm_client.react(
            trigger=trigger,
            state="", emotion=0.5, expression="normal",
            user_present=True, events=_event_history[-8:],
        )


# 上次检测到的用户情绪（用于触发 LLM 反应）
_last_user_emotion = "neutral"


def _on_user_emotion(fsm: MachineState, link: UartLink, now_ms: int,
                     user_emotion: str, confidence: float):
    """根据用户表情调情绪 + 触发 LLM 语言回复"""
    global _last_user_emotion
    if confidence < 0.5:
        return

    boosts = {
        "happy":     0.03, "surprise":  0.02,
        "sad":       -0.02, "angry":     -0.03,
        "fear":      -0.02, "neutral":    0.0,
    }
    delta = boosts.get(user_emotion, 0.0)
    if abs(delta) > 0:
        fsm.add_emotion(delta, now_ms)
        logger.debug(f"用户情绪: {user_emotion} ({confidence:.0%}) → 机器人 {'+' if delta > 0 else ''}{delta:+.2f}")

    # 用户表情变了 → 皮皮马上回应
    if user_emotion != _last_user_emotion and user_emotion != "neutral":
        _last_user_emotion = user_emotion
        emotion_cn = {"happy": "开心", "surprise": "惊讶", "sad": "难过",
                      "angry": "生气", "fear": "害怕"}.get(user_emotion, user_emotion)
        _trigger_llm_react(f"你看起来有点{emotion_cn}，皮皮注意到了你的表情！")


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
    camera = None
    face_detector = None
    emotion_recognizer = None
    preview_window = None
    if not args.no_camera and HAS_CAMERA:
        try:
            from camera.face_detect import EmotionRecognizer
            camera = CameraCapture(device_id=0, width=640, height=480)
            if camera.open():
                face_detector = FaceDetector()
                emotion_recognizer = EmotionRecognizer()
                preview_window = create_preview_window()
                logger.info("摄像头已启用（预览窗口已打开）")
                if emotion_recognizer.available:
                    logger.info("用户情绪识别已启用")
            else:
                logger.warning("摄像头打开失败，跳过")
        except Exception as e:
            logger.warning(f"摄像头初始化失败: {e}")
    elif not args.no_camera and not HAS_CAMERA:
        logger.warning("opencv-python 未安装，摄像头不可用")

    # ── 5. LLM 客户端（可选）──
    llm_client = None
    if HAS_LLM:
        try:
            llm_client = LLMClient()
            global _llm_client
            _llm_client = llm_client
            if llm_client.available:
                llm_client.start()
                logger.info("LLM 客户端已启用（每 20s 反思 + 事件即时反应）")
            else:
                logger.info("LLM 未配置（设置 DEEPSEEK_API_KEY 环境变量启用）")
        except Exception as e:
            logger.warning(f"LLM 客户端初始化失败: {e}")

    # ── 6. Web API（可选）──
    if not args.no_ui:
        try:
            from web_api import WebAPI
            api = WebAPI(link, fsm, llm_client)
            api.start(host="0.0.0.0", port=5000)
        except Exception as e:
            logger.warning(f"Web API 启动失败: {e}")

    # ── 7. 主循环 ──
    run_main_loop(link, fsm, event_queue, camera, face_detector, preview_window,
                  emotion_recognizer, llm_client)

    # ── 8. 清理 ──
    if llm_client:
        llm_client.stop()
    try:
        if preview_window:
            destroy_preview(preview_window)
    except NameError:
        pass
    try:
        if camera:
            camera.close()
    except NameError:
        pass
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
