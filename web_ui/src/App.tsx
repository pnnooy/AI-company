import React from 'react';

/**
 * 桌面学术助手机器人 - 主面板
 *
 * TODO: 各面板组件
 * - StatusPanel: 设备状态概览
 * - ExpressionPanel: 表情预览 + 手动切换
 * - SensorPanel: 传感器实时数据
 * - CameraPanel: 摄像头画面 + 人脸检测框
 * - ChatPanel: AI 对话 (V3)
 * - DebugPanel: 原始串口数据
 */
function App() {
  return (
    <div style={{ padding: 24, fontFamily: 'system-ui, sans-serif' }}>
      <h1>🤖 桌面学术助手机器人</h1>
      <p>控制面板开发中...</p>
      <p>确保 PC Backend 已启动 (python pc_backend/main.py)</p>
    </div>
  );
}

export default App;
