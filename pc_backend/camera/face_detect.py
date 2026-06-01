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
