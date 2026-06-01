"""
comm — 串口通信层
===============
负责 PC 与 STM32 之间的 UART 数据收发、帧解析与封包。

模块：
- protocol: 二进制帧协议定义 (帧结构、CRC、命令码)
- uart_link: 基于 pyserial 的异步串口收发
"""
