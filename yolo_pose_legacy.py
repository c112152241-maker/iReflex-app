# -*- coding: utf-8 -*-
import os
import sys
import time
import math
import cv2
import numpy as np
import torch
from ultralytics import YOLO

# 保持你原本的路徑設定，避免 import 錯誤
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'yolov7_pose')))
sys.path.append('/yolov7_pose/')

class Yolo(object):
    def __init__(self):
        # 1) TensorRT 引擎路徑
        self.model_path = '/home/nvidia/yolo/yolov7_pose/weights/yolo26x-pose.engine'
        self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

        if not os.path.exists(self.model_path):
            print(f"錯誤：找不到引擎檔 {self.model_path}")
            return

        print(f"正在載入 TensorRT 引擎: {self.model_path}")
        self.model = YOLO(self.model_path, task='pose')

        # -----------------------------------------------------------
        # ✅ 設定輸出編碼：YOLOv7 OpenPose-like 18 點格式
        # -----------------------------------------------------------
        # 0:Nose, 1:Neck, 2:R-Sho, 3:R-Elb, 4:R-Wr, 5:L-Sho, 6:L-Elb, 7:L-Wr
        # 8:R-Hip, 9:R-Knee, 10:R-Ank, 11:L-Hip, 12:L-Knee, 13:L-Ank, 14:R-Eye, 15:L-Eye, 16:R-Ear, 17:L-Ear
        self.re_kpts = [0, 17, 6, 8, 10, 5, 7, 9, 12, 14, 16, 11, 13, 15, 2, 1, 4, 3]

        # 畫線連接 (對應上述 0~17 的索引)
        self.lines = [
            (0, 1), (1, 2), (2, 3), (3, 4),      # 右手
            (1, 5), (5, 6), (6, 7),              # 左手
            (1, 8), (8, 9), (9, 10),             # 右腳
            (1, 11), (11, 12), (12, 13),         # 左腳
            (0, 14), (0, 15), (14, 16), (15, 17) # 頭部
        ]

        # 顏色與粗細設定
        self.line_color = (157, 157, 79)
        self.point_color = (102, 102, 51)
        self.line_thickness = 3
        self.point_radius = 2
        self.point_thickness = 3

        # 信心門檻值
        self.conf_thres = 0.4

        # 儲存當前幀的主使用者 18 點座標
        self.keypoints = None

        # 預熱 GPU
        print("正在預熱 GPU...")
        dummy = np.zeros((640, 640, 3), dtype=np.uint8)
        _ = self.model(dummy, imgsz=640, verbose=False)

    # -------------------------
    # ✅ 工具函式
    # -------------------------
    def _is_valid(self, pt):
        return pt[0] != 0 and pt[1] != 0

    def get_length(self, p1, p2):
        if p1 == (0, 0) or p2 == (0, 0):
            return None
        return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)

    def get_angle(self, p1, p2, p3):
        """ 計算三點夾角 (p2 為頂點) - 解決 main.py 報錯的關鍵 """
        a = self.get_length(p1, p2)
        b = self.get_length(p2, p3)
        c = self.get_length(p1, p3)
        if a is None or b is None or c is None: return None
        if a < 1e-6 or b < 1e-6: return None
        try:
            cos_angle = (a*a + b*b - c*c) / (2*a*b)
            cos_angle = max(-1.0, min(1.0, cos_angle))
            return math.degrees(math.acos(cos_angle))
        except Exception:
            return None

    def add_neck_like_v7(self, keypoints17_xy):
        """ 計算 Neck 座標 (左右肩中點) """
        # COCO 原生索引: 6=L-Sho, 5=R-Sho, 2=L-Eye, 1=R-Eye, 0=Nose
        l_shoulder, r_shoulder = keypoints17_xy[6], keypoints17_xy[5]
        l_eye, r_eye, nose = keypoints17_xy[2], keypoints17_xy[1], keypoints17_xy[0]

        if self._is_valid(l_shoulder) and self._is_valid(r_shoulder):
            neck = (int((l_shoulder[0] + r_shoulder[0]) / 2),
                    int((l_shoulder[1] + r_shoulder[1]) / 2))
        elif self._is_valid(l_shoulder) and self._is_valid(r_eye) and self._is_valid(nose):
            neck = (nose[0], l_shoulder[1])
        elif self._is_valid(r_shoulder) and self._is_valid(l_eye) and self._is_valid(nose):
            neck = (nose[0], r_shoulder[1])
        elif self._is_valid(l_shoulder):
            neck = l_shoulder
        elif self._is_valid(r_shoulder):
            neck = r_shoulder
        else:
            neck = (0, 0)
        return neck

    def coco17_to_v7_18(self, kpts17x3, img_w, img_h):
        """ 轉換：COCO(17) -> Neck -> OpenPose(18) """
        xy17 = []
        for i in range(17):
            x, y, conf = float(kpts17x3[i][0]), float(kpts17x3[i][1]), float(kpts17x3[i][2])
            x_i, y_i = int(x), int(y)
            if conf > self.conf_thres and (0 < x_i < img_w) and (0 < y_i < img_h):
                xy17.append((x_i, y_i))
            else:
                xy17.append((0, 0))

        neck = self.add_neck_like_v7(xy17)
        xy18 = xy17 + [neck] # index 17 is neck

        # 重排順序
        reordered18 = [xy18[idx] for idx in self.re_kpts]
        
        # 回傳: (用於畫圖的18點, 用於計算的原始順序含neck)
        return reordered18, xy18

    # -------------------------
    # ✅ 判定主使用者邏輯 (Double Check: 姿態水平 + 骨架最大)
    # -------------------------
    def pick_main_person_hybrid(self, all_persons_kpts17x3, img_w, img_h):
        """
        🔥 雙重確認策略 (修改版)：
        1. 第一層：找出大腿趨近水平的人 (Y軸差異 < y_diff_threshold)。
        2. 第二層：在這些人之中，挑選「骨架最大 (面積最大)」的人。
        """
        y_diff_threshold = 50  # 容許的 Y 軸誤差像素，可依據你的攝影機距離微調
        
        best_person = None
        max_skeleton_area = -1  # 用來記錄目前找到的「最大骨架面積」
        
        # 保底機制：如果沒人小於閾值，至少抓一個大腿最平的
        fallback_person = None
        min_y_diff_overall = float('inf')

        for person_kpts17x3 in all_persons_kpts17x3:
            valid_y_diffs = []
            valid_kpts_x = []
            valid_kpts_y = []
            
            # --- 新增：收集所有有效關鍵點，用來計算骨架大小 ---
            for kpt in person_kpts17x3:
                if kpt[2] > self.conf_thres:
                    valid_kpts_x.append(kpt[0])
                    valid_kpts_y.append(kpt[1])

            # 如果這個人連一個有效點都沒有，直接跳過
            if not valid_kpts_x or not valid_kpts_y:
                continue
                
            # 計算骨架覆蓋的面積 (寬 x 高)
            skeleton_width = max(valid_kpts_x) - min(valid_kpts_x)
            skeleton_height = max(valid_kpts_y) - min(valid_kpts_y)
            skeleton_area = skeleton_width * skeleton_height

            # --- 原有邏輯：計算大腿 Y 軸差異 ---
            l_hip, l_knee = person_kpts17x3[11], person_kpts17x3[13]
            r_hip, r_knee = person_kpts17x3[12], person_kpts17x3[14]

            if l_hip[2] > self.conf_thres and l_knee[2] > self.conf_thres:
                valid_y_diffs.append(abs(l_hip[1] - l_knee[1]))
            if r_hip[2] > self.conf_thres and r_knee[2] > self.conf_thres:
                valid_y_diffs.append(abs(r_hip[1] - r_knee[1]))

            # 如果沒有算到 Y 軸差異，跳過
            if not valid_y_diffs:
                continue

            # 第一關指標：計算 Y 軸差異平均 (代表大腿平不平)
            avg_y_diff = sum(valid_y_diffs) / len(valid_y_diffs)

            # --- 雙重判斷邏輯開始 ---
            # 紀錄保底 (永遠記下大腿最平的人，以防萬一大家大腿都不平)
            if avg_y_diff < min_y_diff_overall:
                min_y_diff_overall = avg_y_diff
                fallback_person = person_kpts17x3

            # 第一層過濾：大腿必須夠平 (Y軸差異小於閾值)
            if avg_y_diff < y_diff_threshold:
                # 第二層過濾：比較「骨架面積」，挑選最大的人
                if skeleton_area > max_skeleton_area:
                    max_skeleton_area = skeleton_area
                    best_person = person_kpts17x3

        # 決策：如果有找到符合雙重條件的人就用他，否則啟動保底機制
        final_target = best_person if best_person is not None else fallback_person
        
        if final_target is not None:
            reordered18, _ = self.coco17_to_v7_18(final_target, img_w, img_h)
            return reordered18
            
        return None

    # -------------------------
    # ✅ 推論與繪圖
    # -------------------------
    def inference(self, frame):
        """
        回傳:
        - img: 原始 frame
        - kpts: 18 點列表 (如果沒抓到人則為 None)
        """
        img_h, img_w = frame.shape[:2]

        # 推論
        results = self.model(frame, imgsz=640, verbose=False, stream=True)

        self.keypoints = None
        for result in results:
            if result.keypoints is None: continue
            kpts = result.keypoints.data  # (n, 17, 3)
            if kpts is None or kpts.shape[0] == 0: continue

            all_persons = kpts.cpu().numpy()

            # 🔥 選擇主使用者的判定方式 🔥
            # 使用雙重確認：大腿水平 + 距離中心最近
            self.keypoints = self.pick_main_person_hybrid(all_persons, img_w, img_h)

            break

        return frame, self.keypoints

    def draw(self, frame):
        """ 外部呼叫用 """
        return self.draw_like_v7(frame)

    def draw_like_v7(self, frame):
        """ 畫出 OpenPose 18 點骨架 """
        if self.keypoints is None:
            return frame

        # 畫線
        for a, b in self.lines:
            # 確保索引不會超出範圍 (預防萬一)
            if a < len(self.keypoints) and b < len(self.keypoints):
                pt1 = self.keypoints[a]
                pt2 = self.keypoints[b]
                if pt1 != (0, 0) and pt2 != (0, 0):
                    cv2.line(frame, pt1, pt2, color=self.line_color, thickness=self.line_thickness)

        # 畫點
        for kpt in self.keypoints:
            if kpt != (0, 0):
                cv2.circle(frame, center=kpt, radius=self.point_radius,
                           color=self.point_color, thickness=self.point_thickness)

        return frame

    def run(self):
        """ 測試用：開啟 Webcam 即時推論 """
        cap = cv2.VideoCapture(0)
        # 設定相機參數
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)

        prev_time = 0
        print("\n=== 開始推論 (已修正版) 按 'q' 離開 ===")

        while True:
            ret, frame = cap.read()
            if not ret: break

            curr_time = time.time()

            # 呼叫整合好的 inference
            frame, kpts = self.inference(frame)
            
            # 畫圖
            self.draw(frame)

            # 計算 FPS
            fps = 1 / (curr_time - prev_time) if (curr_time - prev_time) > 0 else 0
            prev_time = curr_time

            cv2.putText(frame, f"FPS: {int(fps)}", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
            status = "Detected" if kpts else "No Person"
            cv2.putText(frame, f"Status: {status}", (20, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

            cv2.imshow('YOLO11 Pose (V7 Style)', frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    app = Yolo()
    if hasattr(app, 'model'):
        app.run()