"""
face_detect.py — 人脸检测
========================
检测摄像头画面中是否有人脸，用于判断用户是否在场。

MVP 使用 OpenCV Haar Cascade，后续可升级为 MediaPipe 或深度学习方案。
"""

import logging
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger("face_detect")


class FaceDetector:
    """人脸检测器"""

    def __init__(self, cascade_path: Optional[str] = None):
        """
        Args:
            cascade_path: Haar Cascade XML 路径。
                         为 None 时使用 OpenCV 内置的正面人脸检测器。
        """
        if cascade_path is None:
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self._cascade = cv2.CascadeClassifier(cascade_path)
        if self._cascade.empty():
            raise RuntimeError(f"无法加载 Haar Cascade: {cascade_path}")
        logger.info("人脸检测器初始化完成")

    def detect(self, frame: np.ndarray) -> Tuple[bool, int]:
        """
        检测画面中的人脸。

        Args:
            frame: BGR 格式的图像帧 (H x W x 3)

        Returns:
            (has_face, face_count): 是否有人脸 + 人脸数量
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self._cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(60, 60),
        )
        count = len(faces)
        has_face = count > 0
        if has_face:
            logger.debug(f"检测到 {count} 张人脸")
        return has_face, count

    def detect_with_boxes(self, frame: np.ndarray) -> Tuple[bool, list]:
        """
        检测人脸并返回边界框（用于前端显示）。

        Returns:
            (has_face, [(x, y, w, h), ...])
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self._cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60),
        )
        return len(faces) > 0, faces.tolist() if len(faces) > 0 else []


class CameraCapture:
    """摄像头采集封装"""

    def __init__(self, device_id: int = 0, width: int = 640, height: int = 480):
        self.device_id = device_id
        self.width = width
        self.height = height
        self._cap: Optional[cv2.VideoCapture] = None

    def open(self) -> bool:
        """打开摄像头"""
        self._cap = cv2.VideoCapture(self.device_id)
        if not self._cap.isOpened():
            logger.error(f"无法打开摄像头 (device_id={self.device_id})")
            return False
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        logger.info(f"摄像头已打开: {self.width}x{self.height}")
        return True

    def read(self) -> Optional[np.ndarray]:
        """读取一帧"""
        if self._cap is None or not self._cap.isOpened():
            return None
        ret, frame = self._cap.read()
        return frame if ret else None

    def close(self):
        """关闭摄像头"""
        if self._cap:
            self._cap.release()
            logger.info("摄像头已关闭")


# ============================================================================
# 实时预览窗口
# ============================================================================

def draw_status_overlay(frame: np.ndarray, faces: list, user_present: bool,
                        face_count: int, state: str, emotion: float,
                        user_emotion: str = "neutral",
                        emotion_conf: float = 0.0) -> np.ndarray:
    """
    在摄像帧上绘制人脸框 + 状态信息。

    Args:
        frame: BGR 摄像头帧
        faces: [(x, y, w, h), ...] 人脸边界框列表
        user_present: 用户是否在场
        face_count: 检测到的人脸数
        state: 当前 FSM 状态名称
        emotion: 当前情绪值 [0, 1]

    Returns:
        带标注的帧（直接修改原帧）
    """
    h, w = frame.shape[:2]

    # ── 半透明底部状态栏 ──
    overlay = frame.copy()
    bar_h = 80
    cv2.rectangle(overlay, (0, h - bar_h), (w, h), (0, 0, 0), -1)
    frame = cv2.addWeighted(frame, 0.4, overlay, 0.6, 0)

    # ── 人脸框 + 情绪标签 ──
    for i, (x, y, fw, fh) in enumerate(faces):
        color = (0, 255, 0) if user_present else (0, 0, 255)
        cv2.rectangle(frame, (x, y), (x + fw, y + fh), color, 2)
        label = f"{user_emotion}" if i == 0 else "Face"
        if i == 0 and emotion_conf > 0.5:
            label += f" ({emotion_conf:.0%})"
        cv2.putText(frame, label, (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

    # ── 状态文字 ──
    y0 = h - bar_h + 20

    # 在场状态
    if user_present:
        cv2.putText(frame, "USER: ONLINE", (10, y0),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    else:
        cv2.putText(frame, "USER: OFFLINE", (10, y0),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    # FSM 状态 + 情绪值 + 用户情绪
    ue_str = f"  |  User: {user_emotion}" if user_present else ""
    cv2.putText(frame,
                f"State: {state}  |  Faces: {face_count}  |  Robot: {emotion:.2f}{ue_str}",
                (10, y0 + 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    # 情绪条
    bar_x, bar_y, bar_w, bar_h2 = 10, y0 + 45, 200, 8
    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h2), (80, 80, 80), -1)
    fill_w = int(bar_w * emotion)
    # 情绪颜色：红(低) → 绿(高)
    r = int(255 * (1 - emotion))
    g = int(255 * emotion)
    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + fill_w, bar_y + bar_h2), (0, g, r), -1)

    return frame


def create_preview_window(name: str = "Desktop Assistant - Camera"):
    """创建预览窗口"""
    cv2.namedWindow(name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(name, 640, 520)
    return name


def show_preview(window_name: str, frame: np.ndarray) -> bool:
    """
    显示预览帧，返回是否应继续（用户没关窗口）。

    Returns:
        True 继续，False 用户关闭了窗口
    """
    cv2.imshow(window_name, frame)
    key = cv2.waitKey(1) & 0xFF
    # 按下 q 或关闭窗口 → 退出预览
    if key == ord('q'):
        return False
    # 检查窗口是否被关闭
    try:
        prop = cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE)
        if prop < 0:
            return False
    except:
        pass
    return True


def destroy_preview(window_name: str):
    """关闭预览窗口"""
    cv2.destroyWindow(window_name)


# ============================================================================
# 用户情绪识别（基于 OpenCV DNN + ONNX 模型）
# ============================================================================

# Microsoft FER+ 情绪模型（8 类）
# 模型下载: python -c "from camera.face_detect import download_emotion_model; download_emotion_model()"
_EMOTION_MODEL_URL = (
    "https://github.com/onnx/models/raw/main/validated/"
    "vision/body_analysis/emotion_ferplus/model/emotion-ferplus-8.onnx"
)
_EMOTION_MODEL_PATH = None  # 运行时自动探测
_EMOTION_LABELS = ["neutral", "happy", "surprise", "sad", "angry", "disgust", "fear", "contempt"]

# 情绪 → 机器人表情映射
EMOTION_TO_EXPRESSION = {
    "happy":    1,   # HAPPY
    "surprise": 5,   # SURPRISE
    "sad":      6,   # SAD
    "angry":    3,   # ANGRY
    "fear":     5,   # SURPRISE (fear ≈ surprise)
    "disgust":  3,   # ANGRY
    "contempt": 3,   # ANGRY
    "neutral":  0,   # NORMAL
}


def _get_model_path() -> Optional[str]:
    """探测本地模型文件"""
    import os
    global _EMOTION_MODEL_PATH
    if _EMOTION_MODEL_PATH and os.path.exists(_EMOTION_MODEL_PATH):
        return _EMOTION_MODEL_PATH

    # 搜索可能的路径
    candidates = [
        os.path.join(os.path.dirname(__file__), "emotion-ferplus-8.onnx"),
        os.path.join(os.getcwd(), "camera", "emotion-ferplus-8.onnx"),
        os.path.join(os.getcwd(), "emotion-ferplus-8.onnx"),
    ]
    for p in candidates:
        if os.path.exists(p):
            _EMOTION_MODEL_PATH = p
            return p
    return None


def download_emotion_model(save_dir: Optional[str] = None):
    """下载情绪识别模型文件"""
    import os
    if save_dir is None:
        save_dir = os.path.dirname(__file__)
    save_path = os.path.join(save_dir, "emotion-ferplus-8.onnx")

    if os.path.exists(save_path):
        print(f"模型已存在: {save_path}")
        return save_path

    print(f"正在下载情绪识别模型...")
    print(f"URL: {_EMOTION_MODEL_URL}")
    try:
        import urllib.request
        urllib.request.urlretrieve(_EMOTION_MODEL_URL, save_path)
        print(f"下载完成: {save_path}")
        return save_path
    except Exception as e:
        print(f"下载失败: {e}")
        print(f"请手动下载模型文件放到: {save_path}")
        return None


class EmotionRecognizer:
    """
    用户面部情绪识别器。

    优先使用 DeepFace（TensorFlow 后端），回退到 ONNX 模型。
    """

    def __init__(self):
        self._backend = None  # 'deepface' | 'onnx' | None
        self._net = None
        self._deepface_ready = False

        # 尝试 deepface
        try:
            from deepface import DeepFace
            self._DeepFace = DeepFace
            # 预热：第一次调用比较慢
            logger.info("情绪识别: DeepFace 后端已就绪")
            self._backend = 'deepface'
            self._deepface_ready = True
            return
        except ImportError:
            logger.debug("DeepFace 未安装，尝试 ONNX...")
        except Exception as e:
            logger.debug(f"DeepFace 初始化失败: {e}，尝试 ONNX...")

        # 回退 ONNX
        model_path = _get_model_path()
        if model_path:
            try:
                self._net = cv2.dnn.readNetFromONNX(model_path)
                self._backend = 'onnx'
                logger.info(f"情绪识别: ONNX 后端 ({model_path})")
                return
            except Exception as e:
                logger.warning(f"ONNX 模型加载失败: {e}")

        logger.info("情绪识别: 不可用")

    @property
    def available(self) -> bool:
        return self._backend is not None

    @staticmethod
    def crop_tight(face_roi: np.ndarray, shrink: float = 0.15) -> np.ndarray:
        """紧缩人脸区域"""
        h, w = face_roi.shape[:2]
        dh = int(h * shrink)
        dw = int(w * shrink)
        return face_roi[max(0, dh):h - dh, max(0, dw):w - dw]

    def predict(self, face_roi: np.ndarray) -> Tuple[str, float]:
        """
        识别单个人脸的情绪。

        Returns:
            (emotion_label, confidence)
        """
        if self._backend == 'deepface':
            return self._predict_deepface(face_roi)
        elif self._backend == 'onnx':
            return self._predict_onnx(face_roi)
        return "neutral", 0.0

    def predict_all(self, face_rois: list) -> list:
        """批量识别"""
        return [self.predict(roi) for roi in face_rois]

    # ── DeepFace 后端 ─────────────────────────

    def _predict_deepface(self, face_roi: np.ndarray) -> Tuple[str, float]:
        try:
            # DeepFace 需要至少 80x80 的输入
            h, w = face_roi.shape[:2]
            if h < 80 or w < 80:
                face_roi = cv2.resize(face_roi, (80, 80))

            result = self._DeepFace.analyze(
                face_roi,
                actions=['emotion'],
                enforce_detection=False,
                detector_backend='skip',  # 我们已裁好人脸，跳过内部检测
                silent=True,
            )
            if result and len(result) > 0:
                emotions = result[0].get('emotion', {})
                dominant = result[0].get('dominant_emotion', 'neutral')
                confidence = emotions.get(dominant, 0.0) / 100.0
                return dominant, confidence
        except Exception as e:
            logger.debug(f"DeepFace 推理失败: {e}")
        return "neutral", 0.0

    # ── ONNX 后端（回退）───────────────────────

    def _predict_onnx(self, face_roi: np.ndarray) -> Tuple[str, float]:
        if self._net is None:
            return "neutral", 0.0
        try:
            tight = self.crop_tight(face_roi) if face_roi.shape[0] > 30 else face_roi
            gray = cv2.cvtColor(tight, cv2.COLOR_BGR2GRAY)
            resized = cv2.resize(gray, (64, 64)).astype(np.float32)
            normalized = (resized / 127.5) - 1.0
            blob = normalized.reshape(1, 1, 64, 64)

            self._net.setInput(blob)
            logits = self._net.forward()[0]
            exp_logits = np.exp(logits - logits.max())
            probs = exp_logits / exp_logits.sum()

            best_idx = int(probs.argmax())
            confidence = float(probs[best_idx])
            label = _EMOTION_LABELS[best_idx] if best_idx < len(_EMOTION_LABELS) else "neutral"
            if confidence < 0.30:
                label = "neutral"
            return label, confidence
        except Exception as e:
            logger.debug(f"ONNX 推理失败: {e}")
            return "neutral", 0.0
