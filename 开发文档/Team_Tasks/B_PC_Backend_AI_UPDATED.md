# 角色 B：PC 后端全链路（已更新接口）

> **负责人**: B  
> **工期**: 预计 2-3 天  
> **前置条件**: Python 3.8+, COM6 可用, 项目仓库已 clone  
> **更新日期**: 2026-06-04（根据 A 完成的协议更新）

---

## ⚠️ 重要更新说明

**A 角色已完成固件协议改造（v2.0）**，本文档已根据实际完成的协议规范更新。

**关键变化**:
1. ✅ 帧格式更新：`[A5][5A][LEN][CMD+DATA][CRC-8][EE]`
2. ✅ CRC 改为 CRC-8（多项式 0x07）
3. ✅ NFC 改为喂食模式（不读 UID，上报时长+等级）
4. ✅ 所有事件已改为二进制帧上报
5. ✅ 添加超时机制和错误统计

---

## 一、任务总览

你是整个系统的**大脑中枢**。你的代码连接板子（串口）和前端（Web API），中间跑 AI 决策。

```
STM32 传感器事件
       ↓ 串口字节流（新协议 v2.0）
  [你的代码开始]
       ↓
  uart_link.py    ← 收字节、拼帧、解析（需更新）
       ↓
  protocol.py     ← 协议定义（需完全重写）
       ↓
  main.py         ← 事件总线、主循环
       ↓
  state_machine.py ← 状态转移 + 情绪值
  rules.py         ← 事件→表情/灯光 决策
       ↓
  uart_link.py    ← 发帧、下发指令（需更新）
       ↓
  STM32 执行 (LCD表情 + RGB灯光)
       ↓
  web_api.py      ← 暴露 REST API 给前端 (C 角色)
  [你的代码结束]
       ↓
  Web UI (C 角色的地盘)
```

---

## 二、模块清单与优先级（已更新）

| 优先级 | 模块 | 文件 | 状态 | 工作量 | 说明 |
|--------|------|------|------|--------|------|
| **P0** | **协议定义** | `comm/protocol.py` | ⚠️ **需完全重写** | 2h | 新协议 v2.0 |
| **P0** | **帧解析器** | `comm/uart_link.py` | ⚠️ **需重写** | 2h | 5状态机 + CRC-8 |
| P1 | 主循环/事件总线 | `main.py` | 需补全 | 3h | 事件映射需更新 |
| P1 | 规则引擎接线 | `ai_engine/rules.py` | 已写，连上主循环即可 | 1h | 无需修改 |
| P1 | 状态机接线 | `ai_engine/state_machine.py` | 已写，连上主循环即可 | 0.5h | 无需修改 |
| P2 | Web API 服务 | `web_api.py` (新建) | 未开始 | 2h | 无需修改 |
| P3 | 摄像头接入 | `camera/face_detect.py` | 已写，接入主循环 | 1h | 无需修改 |
| P3 | LLM 客户端 | `ai_engine/llm_client.py` (新建) | 未开始 | 3h | 可选功能 |

---

## 三、P0：协议定义（protocol.py）- 完全重写

### 3.1 新协议完整规范

根据 A 提供的完成文档 `A_NFC_Firmware_Protocol_COMPLETED.md`：

```python
"""
comm/protocol.py
================
新协议 v2.0 定义（与固件完全对齐）

协议规格：
- 帧格式: [A5][5A][LEN][CMD+DATA][CRC-8][EE]
- LEN 范围: [1, 33]
- CRC-8: 多项式 0x07
- 超时: 100ms
"""

from enum import IntEnum
from dataclasses import dataclass
from typing import Optional


# ============ 协议常量 ============

SYNC0 = 0xA5
SYNC1 = 0x5A
END_BYTE = 0xEE
MAX_PAYLOAD = 33  # CMD(1) + DATA(32)
FRAME_TIMEOUT_MS = 100


# ============ 命令码（PC → MCU）============

class Cmd(IntEnum):
    """PC → MCU 命令码"""
    SET_EXPR = 0x01      # payload: [emo_id:1B]
    SET_RGB = 0x02       # payload: [R:1B][G:1B][B:1B]
    QUERY = 0x03         # payload: 无
    HEARTBEAT = 0x04     # payload: [seq:1B]


# ============ 事件码（MCU → PC）============

class EventCode(IntEnum):
    """MCU → PC 事件码"""
    ACK = 0x05           # payload: [ack_cmd:1B][status:1B]
    TOUCH = 0x10         # payload: [side:1B][type:1B]
    NFC = 0x11           # payload: [dur_low:1B][dur_high:1B][level:1B]
    POSE = 0x12          # payload: [state:1B]


# ============ 表情枚举 ============

class Expression(IntEnum):
    """表情 ID（与固件一致）"""
    NORMAL = 0
    HAPPY = 1
    FOCUS = 2
    ANGRY = 3
    SLEEP = 4
    SURPRISE = 5
    SAD = 6
    LOVE = 7


# ============ 触摸事件定义 ============

class TouchSide(IntEnum):
    """触摸传感器位置"""
    LEFT = 0
    RIGHT = 1


class TouchType(IntEnum):
    """触摸类型"""
    TAP = 1    # 轻触 < 1秒
    HOLD = 2   # 长按 > 1秒


# ============ NFC 喂食等级 ============

class NFCLevel(IntEnum):
    """NFC 喂食等级"""
    TAP = 0     # < 3秒
    SNACK = 1   # 3-10秒
    MEAL = 2    # 10-30秒
    FEAST = 3   # > 30秒


# ============ 姿态状态 ============

class PoseState(IntEnum):
    """姿态状态"""
    FALL = 1    # 倾倒
    SHAKE = 2   # 摇晃


# ============ CRC-8 计算 ============

def calc_crc8(data: bytes) -> int:
    """
    CRC-8 校验（多项式 0x07）
    
    Args:
        data: CMD + DATA 拼接的字节串
    
    Returns:
        CRC-8 校验码（0x00-0xFF）
    """
    crc = 0x00
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = (crc << 1) ^ 0x07
            else:
                crc <<= 1
        crc &= 0xFF
    return crc


# ============ 帧数据类 ============

@dataclass
class Frame:
    """协议帧"""
    cmd: int           # 命令码/事件码
    data: bytes = b''  # 数据部分（不含 CMD）
    
    @staticmethod
    def pack(cmd: int, data: bytes = b'') -> bytes:
        """
        打包完整帧
        
        Args:
            cmd: 命令码（0x01-0x04）
            data: 数据部分（最多 32 字节）
        
        Returns:
            完整帧字节串
        
        Raises:
            ValueError: data 超过 32 字节
        """
        if len(data) > 32:
            raise ValueError(f"Data too long: {len(data)} > 32")
        
        payload = bytes([cmd]) + data
        length = len(payload)
        
        if not (1 <= length <= 33):
            raise ValueError(f"Invalid length: {length}")
        
        frame = bytes([
            SYNC0,              # 0xA5
            SYNC1,              # 0x5A
            length,             # LEN
        ]) + payload + bytes([
            calc_crc8(payload), # CRC-8
            END_BYTE,           # 0xEE
        ])
        
        return frame
    
    def pack_bytes(self) -> bytes:
        """打包当前帧"""
        return Frame.pack(self.cmd, self.data)


# ============ 事件解析类 ============

@dataclass
class TouchEvent:
    """触摸事件"""
    side: TouchSide
    type: TouchType
    
    @staticmethod
    def parse(data: bytes) -> Optional['TouchEvent']:
        """解析触摸事件 payload"""
        if len(data) < 2:
            return None
        try:
            return TouchEvent(
                side=TouchSide(data[0]),
                type=TouchType(data[1])
            )
        except ValueError:
            return None


@dataclass
class NFCEvent:
    """NFC 喂食事件"""
    duration: int      # 喂食时长（秒）
    level: NFCLevel    # 喂食等级
    
    @staticmethod
    def parse(data: bytes) -> Optional['NFCEvent']:
        """解析 NFC 事件 payload（小端序）"""
        if len(data) < 3:
            return None
        try:
            duration = data[0] | (data[1] << 8)  # 16-bit 小端序
            level = NFCLevel(data[2])
            return NFCEvent(duration=duration, level=level)
        except ValueError:
            return None


@dataclass
class PoseEvent:
    """姿态事件"""
    state: PoseState
    
    @staticmethod
    def parse(data: bytes) -> Optional['PoseEvent']:
        """解析姿态事件 payload"""
        if len(data) < 1:
            return None
        try:
            return PoseEvent(state=PoseState(data[0]))
        except ValueError:
            return None


@dataclass
class ACKEvent:
    """ACK 响应"""
    ack_cmd: int
    status: int
    
    @staticmethod
    def parse(data: bytes) -> Optional['ACKEvent']:
        """解析 ACK payload"""
        if len(data) < 2:
            return None
        return ACKEvent(ack_cmd=data[0], status=data[1])


# ============ 统一事件类 ============

@dataclass
class SensorEvent:
    """统一的传感器事件"""
    event_code: EventCode
    touch: Optional[TouchEvent] = None
    nfc: Optional[NFCEvent] = None
    pose: Optional[PoseEvent] = None
    ack: Optional[ACKEvent] = None
    
    @staticmethod
    def from_frame(frame: Frame) -> Optional['SensorEvent']:
        """从帧解析传感器事件"""
        try:
            event_code = EventCode(frame.cmd)
        except ValueError:
            return None  # 不是有效的事件码
        
        event = SensorEvent(event_code=event_code)
        
        if event_code == EventCode.TOUCH:
            event.touch = TouchEvent.parse(frame.data)
        elif event_code == EventCode.NFC:
            event.nfc = NFCEvent.parse(frame.data)
        elif event_code == EventCode.POSE:
            event.pose = PoseEvent.parse(frame.data)
        elif event_code == EventCode.ACK:
            event.ack = ACKEvent.parse(frame.data)
        
        return event
```

---

### 3.2 帧解析器（状态机）

在 `comm/uart_link.py` 中实现：

```python
"""
comm/uart_link.py
=================
串口链路层 + 帧解析器
"""

import serial
import threading
import time
import logging
from typing import Optional, Callable
from .protocol import Frame, calc_crc8, SYNC0, SYNC1, END_BYTE, FRAME_TIMEOUT_MS

logger = logging.getLogger(__name__)


class FrameParser:
    """
    帧解析器（5 状态机）
    WAIT_SYNC0 → WAIT_SYNC1 → GET_LEN → GET_BODY → GET_END
    """
    
    def __init__(self):
        self.state = 'WAIT_SYNC0'
        self.buffer = bytearray()
        self.length = 0
        self.last_byte_time = 0
        
        # 错误统计
        self.stats = {
            'invalid_len': 0,
            'crc_fail': 0,
            'end_byte_err': 0,
            'timeout': 0,
        }
    
    def reset(self):
        """重置状态机"""
        self.state = 'WAIT_SYNC0'
        self.buffer.clear()
        self.length = 0
    
    def feed(self, byte: int) -> Optional[Frame]:
        """
        喂入一个字节，返回解析出的帧（如果有）
        
        Returns:
            Frame 对象或 None
        """
        now_ms = int(time.time() * 1000)
        
        # 超时检测（除了 WAIT_SYNC0）
        if self.state != 'WAIT_SYNC0':
            if now_ms - self.last_byte_time > FRAME_TIMEOUT_MS:
                self.stats['timeout'] += 1
                self.reset()
        
        self.last_byte_time = now_ms
        
        if self.state == 'WAIT_SYNC0':
            if byte == SYNC0:
                self.state = 'WAIT_SYNC1'
        
        elif self.state == 'WAIT_SYNC1':
            if byte == SYNC1:
                self.state = 'GET_LEN'
                self.buffer.clear()
            elif byte == SYNC0:
                # 连续 A5，保持在 WAIT_SYNC1
                pass
            else:
                self.state = 'WAIT_SYNC0'
        
        elif self.state == 'GET_LEN':
            if 1 <= byte <= 33:
                self.length = byte
                self.state = 'GET_BODY'
            else:
                self.stats['invalid_len'] += 1
                self.reset()
        
        elif self.state == 'GET_BODY':
            self.buffer.append(byte)
            if len(self.buffer) >= self.length:
                self.state = 'GET_END'
        
        elif self.state == 'GET_END':
            self.reset()
            if byte == END_BYTE:
                # 校验 CRC
                data_len = self.length - 1  # 去掉 CRC
                payload = self.buffer[:data_len]
                crc_received = self.buffer[data_len]
                crc_expected = calc_crc8(payload)
                
                if crc_received == crc_expected:
                    cmd = payload[0]
                    data = bytes(payload[1:]) if len(payload) > 1 else b''
                    return Frame(cmd=cmd, data=data)
                else:
                    self.stats['crc_fail'] += 1
            else:
                self.stats['end_byte_err'] += 1
        
        return None


class UartLink:
    """串口链路"""
    
    def __init__(self, port: str, baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.serial: Optional[serial.Serial] = None
        self.parser = FrameParser()
        self.running = False
        self.rx_thread: Optional[threading.Thread] = None
        self.frame_callback: Optional[Callable[[Frame], None]] = None
    
    def open(self) -> bool:
        """打开串口"""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=8,
                parity='N',
                stopbits=1,
                timeout=0.1
            )
            logger.info(f"串口已打开: {self.port} @ {self.baudrate}")
            return True
        except Exception as e:
            logger.error(f"串口打开失败: {e}")
            return False
    
    def close(self):
        """关闭串口"""
        self.running = False
        if self.rx_thread and self.rx_thread.is_alive():
            self.rx_thread.join(timeout=1.0)
        if self.serial and self.serial.is_open:
            self.serial.close()
            logger.info("串口已关闭")
    
    def on_frame(self, callback: Callable[[Frame], None]):
        """注册帧回调"""
        self.frame_callback = callback
    
    def send_command(self, cmd: int, data: bytes = b'') -> bool:
        """
        发送命令帧
        
        Args:
            cmd: 命令码（Cmd 枚举）
            data: 数据部分
        
        Returns:
            是否发送成功
        """
        if not self.serial or not self.serial.is_open:
            logger.error("串口未打开")
            return False
        
        try:
            frame_bytes = Frame.pack(cmd, data)
            self.serial.write(frame_bytes)
            logger.debug(f"发送: {frame_bytes.hex()}")
            return True
        except Exception as e:
            logger.error(f"发送失败: {e}")
            return False
    
    def start_receiving(self):
        """启动接收线程"""
        if self.running:
            logger.warning("接收线程已在运行")
            return
        
        self.running = True
        self.rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
        self.rx_thread.start()
        logger.info("接收线程已启动")
    
    def _rx_loop(self):
        """接收循环（后台线程）"""
        while self.running:
            try:
                if self.serial and self.serial.in_waiting > 0:
                    byte = self.serial.read(1)[0]
                    frame = self.parser.feed(byte)
                    
                    if frame and self.frame_callback:
                        self.frame_callback(frame)
                else:
                    time.sleep(0.001)  # 1ms
            except Exception as e:
                logger.error(f"接收异常: {e}")
                time.sleep(0.1)
    
    def get_stats(self) -> dict:
        """获取错误统计"""
        return self.parser.stats.copy()
```

---

## 四、P1：主循环更新

### 4.1 事件映射更新

原有的事件映射需要更新为新协议：

```python
"""
main.py
=======
主循环（事件总线）
"""

import logging
import queue
import time
from comm.uart_link import UartLink
from comm.protocol import (
    Frame, Cmd, Expression, SensorEvent, 
    EventCode, TouchEvent, NFCEvent, PoseEvent
)
from ai_engine.state_machine import MachineState
from ai_engine.rules import decide_expression_and_rgb

logger = logging.getLogger(__name__)


def handle_sensor_event(event: SensorEvent, fsm: MachineState, link: UartLink):
    """
    处理传感器事件
    
    Args:
        event: 传感器事件
        fsm: 状态机
        link: 串口链路
    """
    now_ms = int(time.time() * 1000)
    
    # 根据事件类型处理
    if event.event_code == EventCode.TOUCH and event.touch:
        touch = event.touch
        logger.info(f"触摸事件: {touch.side.name} {touch.type.name}")
        
        # 更新状态机
        fsm.on_touch_event(now_ms)
        
        # 决策表情和灯光
        expr, rgb = decide_expression_and_rgb(fsm.emotion_value, "touch")
        link.send_command(Cmd.SET_EXPR, bytes([int(expr)]))
        link.send_command(Cmd.SET_RGB, bytes(rgb))
    
    elif event.event_code == EventCode.NFC and event.nfc:
        nfc = event.nfc
        logger.info(f"NFC 喂食: {nfc.duration}秒, 等级={nfc.level.name}")
        
        # 根据喂食等级更新情绪值
        emotion_boost = {
            0: 0.1,   # TAP
            1: 0.3,   # SNACK
            2: 0.5,   # MEAL
            3: 0.8,   # FEAST
        }.get(nfc.level, 0.1)
        
        fsm.add_emotion(emotion_boost, now_ms)
        
        # 决策（已在固件端切换表情，这里可选择性补发）
        # expr, rgb = decide_expression_and_rgb(fsm.emotion_value, "nfc")
        # link.send_command(Cmd.SET_EXPR, bytes([int(expr)]))
    
    elif event.event_code == EventCode.POSE and event.pose:
        pose = event.pose
        logger.info(f"姿态事件: {pose.state.name}")
        
        if pose.state.value == 1:  # FALL
            fsm.on_alert_event(now_ms)
        elif pose.state.value == 2:  # SHAKE
            fsm.on_touch_event(now_ms)
    
    elif event.event_code == EventCode.ACK and event.ack:
        logger.debug(f"收到 ACK: cmd=0x{event.ack.ack_cmd:02X}, status={event.ack.status}")


def on_uart_frame(frame: Frame, event_queue: queue.Queue):
    """串口帧回调"""
    event = SensorEvent.from_frame(frame)
    if event:
        event_queue.put(event)
    else:
        logger.warning(f"无法解析帧: CMD=0x{frame.cmd:02X}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="桌面学术助手 PC 后端")
    parser.add_argument("--port", default="COM6", help="串口号")
    parser.add_argument("--baud", type=int, default=115200, help="波特率")
    args = parser.parse_args()
    
    logger.info("=" * 50)
    logger.info("PC Backend 启动中...")
    logger.info(f"串口: {args.port} @ {args.baud}")
    logger.info("=" * 50)
    
    # 1. 串口
    link = UartLink(args.port, args.baud)
    if not link.open():
        logger.error("串口打开失败")
        return
    
    # 2. 事件队列
    event_queue = queue.Queue()
    link.on_frame(lambda frame: on_uart_frame(frame, event_queue))
    link.start_receiving()
    
    # 3. 状态机
    fsm = MachineState()
    
    # 4. 主循环
    logger.info("主循环已启动，等待事件...")
    
    try:
        while True:
            # 处理事件队列
            try:
                while True:
                    event = event_queue.get_nowait()
                    handle_sensor_event(event, fsm, link)
            except queue.Empty:
                pass
            
            # FSM tick（情绪衰减）
            fsm.tick(int(time.time() * 1000))
            
            time.sleep(0.01)  # 10ms
    
    except KeyboardInterrupt:
        logger.info("收到退出信号")
    finally:
        link.close()
        logger.info("PC Backend 已退出")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    main()
```

---

## 五、测试与联调

### 5.1 快速测试发送

```python
# test_send.py
from comm.uart_link import UartLink
from comm.protocol import Cmd, Expression
import time

link = UartLink("COM6", 115200)
if link.open():
    # 设置 HAPPY 表情
    link.send_command(Cmd.SET_EXPR, bytes([Expression.HAPPY]))
    time.sleep(1)
    
    # 设置红色灯光
    link.send_command(Cmd.SET_RGB, bytes([255, 0, 0]))
    time.sleep(1)
    
    link.close()
```

---

### 5.2 快速测试接收

```python
# test_receive.py
from comm.uart_link import UartLink
from comm.protocol import Frame, SensorEvent
import time

link = UartLink("COM6", 115200)

def on_frame(frame: Frame):
    print(f"收到帧: CMD=0x{frame.cmd:02X}, DATA={frame.data.hex()}")
    
    event = SensorEvent.from_frame(frame)
    if event:
        if event.touch:
            print(f"  → 触摸: {event.touch.side.name} {event.touch.type.name}")
        elif event.nfc:
            print(f"  → NFC: {event.nfc.duration}秒, {event.nfc.level.name}")
        elif event.pose:
            print(f"  → 姿态: {event.pose.state.name}")

if link.open():
    link.on_frame(on_frame)
    link.start_receiving()
    print("等待事件...（按 Ctrl+C 退出）")
    
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        link.close()
```

---

## 六、接口规范汇总

### 与 A (固件)

| 项目 | 值 |
|------|-----|
| 帧格式 | `[A5][5A][LEN][CMD+DATA][CRC-8][EE]` |
| CRC-8 | 多项式 0x07 |
| LEN 范围 | [1, 33] |
| 超时 | 100ms |
| PC→MCU 命令 | 0x01~0x04 |
| MCU→PC 事件 | 0x05, 0x10~0x12 |

### 与 C (Web UI)

（无变化，参考原文档）

---

## 七、完成标准

- [ ] `protocol.py` 重写完成，与固件完全对齐
- [ ] `uart_link.py` 帧解析器实现（5 状态机 + 超时 + CRC-8）
- [ ] 测试发送：PC 发送 SET_EXPR → 板子切换表情
- [ ] 测试接收：触摸板子 → PC 收到 TOUCH 事件并正确解析
- [ ] NFC 事件解析：喂食 5 秒 → PC 收到 duration=5, level=SNACK
- [ ] 错误统计功能：`link.get_stats()` 返回正确计数
- [ ] 与 A 完成联调（往返测试）
- [ ] 代码提交到 GitHub

---

## 八、参考文档

| 文档 | 路径 | 说明 |
|------|------|------|
| A 完成文档 | `Team_Tasks/A_NFC_Firmware_Protocol_COMPLETED.md` | **必读**，完整协议规范 |
| 测试指南 | `开发文档/Complete_Test_Guide.md` | 25 项测试清单 |
| AI 审查记录 | `开发文档/Protocol_AI_Review.md` | 协议设计细节 |

---

**更新人**: Claude Opus 4.7  
**更新日期**: 2026-06-04  
**下一步**: 按照本文档重写 `protocol.py` 和 `uart_link.py`
