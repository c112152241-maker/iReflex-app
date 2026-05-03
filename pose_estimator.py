import math
import time
import cv2


class PoseEstimator:
    """
    App 統一人體姿態估測介面。

    mode="fake":
        使用假角度，適合 Windows 開發 GUI。

    mode="yolo":
        使用 app/core/yolo_pose_legacy.py 裡的 Yolo 類別，
        適合 Jetson / TensorRT 實機測試。
    """

    def __init__(self, mode="fake", leg_side="right"):
        self.mode = mode
        self.leg_side = leg_side
        self.start_time = time.time()
        self.yolo_model = None

        if self.mode == "yolo":
            self._load_yolo_model()

    def _load_yolo_model(self):
        try:
            from app.core.yolo_pose_legacy import Yolo
            self.yolo_model = Yolo()

            if not hasattr(self.yolo_model, "model"):
                raise RuntimeError(
                    "Yolo 物件沒有成功載入 model。請檢查 engine 路徑是否存在。"
                )

        except Exception as e:
            raise RuntimeError(f"YOLO Pose 模型載入失敗：{e}")

    def estimate(self, frame):
        if self.mode == "fake":
            return self._estimate_fake(frame)

        if self.mode == "yolo":
            return self._estimate_yolo(frame)

        raise ValueError(f"未知 PoseEstimator mode：{self.mode}")

    def _estimate_fake(self, frame):
        elapsed = time.time() - self.start_time

        knee_angle = 140 + 20 * math.sin(elapsed * 2)

        output_frame = frame.copy()
        h, w = output_frame.shape[:2]

        hip = (int(w * 0.45), int(h * 0.35))
        knee = (int(w * 0.50), int(h * 0.55))
        ankle = (int(w * 0.55), int(h * 0.78))

        cv2.circle(output_frame, hip, 8, (0, 255, 0), -1)
        cv2.circle(output_frame, knee, 8, (0, 255, 255), -1)
        cv2.circle(output_frame, ankle, 8, (0, 0, 255), -1)

        cv2.line(output_frame, hip, knee, (255, 255, 0), 3)
        cv2.line(output_frame, knee, ankle, (255, 255, 0), 3)

        cv2.putText(
            output_frame,
            f"Knee Angle: {knee_angle:.1f} deg",
            (30, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (0, 255, 255),
            2,
        )

        result = {
            "knee_angle": float(knee_angle),
            "keypoints": {
                "hip": hip,
                "knee": knee,
                "ankle": ankle,
            },
            "leg_side": "fake",
            "mode": "fake",
        }

        return output_frame, result

    def _is_valid_point(self, pt):
        if pt is None:
            return False
        if len(pt) < 2:
            return False
        return not (pt[0] == 0 and pt[1] == 0)

    def _angle_from_points(self, p1, p2, p3):
        """
        計算三點夾角，p2 是中間點。
        hip-knee-ankle 時，p2 = knee。
        """

        if not (
            self._is_valid_point(p1)
            and self._is_valid_point(p2)
            and self._is_valid_point(p3)
        ):
            return None

        x1, y1 = p1
        x2, y2 = p2
        x3, y3 = p3

        v1 = (x1 - x2, y1 - y2)
        v2 = (x3 - x2, y3 - y2)

        dot = v1[0] * v2[0] + v1[1] * v2[1]
        norm1 = math.sqrt(v1[0] ** 2 + v1[1] ** 2)
        norm2 = math.sqrt(v2[0] ** 2 + v2[1] ** 2)

        if norm1 < 1e-6 or norm2 < 1e-6:
            return None

        cos_theta = dot / (norm1 * norm2)
        cos_theta = max(-1.0, min(1.0, cos_theta))

        return float(math.degrees(math.acos(cos_theta)))

    def _get_leg_angle(self, keypoints, side):
        """
        keypoints 是 yolo_pose_legacy.py 回傳的 18 點格式。

        右腳：
            8  = R-Hip
            9  = R-Knee
            10 = R-Ank

        左腳：
            11 = L-Hip
            12 = L-Knee
            13 = L-Ank
        """

        if keypoints is None:
            return None, None

        if len(keypoints) < 14:
            return None, None

        if side == "right":
            hip = keypoints[8]
            knee = keypoints[9]
            ankle = keypoints[10]
        elif side == "left":
            hip = keypoints[11]
            knee = keypoints[12]
            ankle = keypoints[13]
        else:
            return None, None

        angle = self._angle_from_points(hip, knee, ankle)

        points = {
            "hip": hip,
            "knee": knee,
            "ankle": ankle,
        }

        return angle, points

    def _select_leg_angle(self, keypoints):
        right_angle, right_points = self._get_leg_angle(keypoints, "right")
        left_angle, left_points = self._get_leg_angle(keypoints, "left")

        if self.leg_side == "right":
            return right_angle, right_points, "right"

        if self.leg_side == "left":
            return left_angle, left_points, "left"

        # auto 模式：優先選有效角度。
        # 若兩邊都有，取比較接近正常膝關節範圍 60~180 的值。
        candidates = []

        if right_angle is not None:
            candidates.append(("right", right_angle, right_points))

        if left_angle is not None:
            candidates.append(("left", left_angle, left_points))

        if not candidates:
            return None, None, "none"

        def score(item):
            _, angle, _ = item
            if 60 <= angle <= 180:
                return 0
            return abs(angle - 120)

        selected_side, selected_angle, selected_points = sorted(candidates, key=score)[0]
        return selected_angle, selected_points, selected_side

    def _draw_selected_leg(self, frame, points, angle, side):
        if points is None:
            return frame

        hip = points["hip"]
        knee = points["knee"]
        ankle = points["ankle"]

        if not (
            self._is_valid_point(hip)
            and self._is_valid_point(knee)
            and self._is_valid_point(ankle)
        ):
            return frame

        cv2.circle(frame, hip, 7, (0, 255, 0), -1)
        cv2.circle(frame, knee, 9, (0, 255, 255), -1)
        cv2.circle(frame, ankle, 7, (0, 0, 255), -1)

        cv2.line(frame, hip, knee, (0, 255, 255), 3)
        cv2.line(frame, knee, ankle, (0, 255, 255), 3)

        label = f"{side} knee: {angle:.1f} deg"
        cv2.putText(
            frame,
            label,
            (30, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (0, 255, 255),
            2,
        )

        return frame

    def _estimate_yolo(self, frame):
        if self.yolo_model is None:
            raise RuntimeError("YOLO 模型尚未載入。")

        try:
            output_frame, keypoints = self.yolo_model.inference(frame)

            if hasattr(self.yolo_model, "draw"):
                output_frame = self.yolo_model.draw(output_frame)

            knee_angle, leg_points, selected_side = self._select_leg_angle(keypoints)

            if knee_angle is None:
                cv2.putText(
                    output_frame,
                    "Knee Angle: --",
                    (30, 50),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.0,
                    (0, 0, 255),
                    2,
                )

                result = {
                    "knee_angle": None,
                    "keypoints": keypoints,
                    "leg_points": None,
                    "leg_side": selected_side,
                    "mode": "yolo",
                }

                return output_frame, result

            output_frame = self._draw_selected_leg(
                output_frame,
                leg_points,
                knee_angle,
                selected_side,
            )

            result = {
                "knee_angle": float(knee_angle),
                "keypoints": keypoints,
                "leg_points": leg_points,
                "leg_side": selected_side,
                "mode": "yolo",
            }

            return output_frame, result

        except Exception as e:
            raise RuntimeError(f"YOLO Pose 推論失敗：{e}")