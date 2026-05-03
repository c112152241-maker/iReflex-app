import os
import time
import sqlite3
import cv2
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QGroupBox, QMessageBox,
    QStackedWidget
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap
from app.ui.patient_form import PatientForm
from app.ui.patient_list import PatientListWidget
from app.core.camera_service import CameraService
from app.core.pose_estimator import PoseEstimator
from app.core.sensor_service import FakeSensorService
from app.core.reflex_analyzer import ReflexAnalyzer
from app.config import load_config
import csv
from datetime import datetime
from app.ui.settings_page import SettingsPage
from app.ui.patient_select_dialog import PatientSelectDialog
from app.data.measurement_db import init_measurement_table, insert_measurement_record


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # 初始化配置
        self.config = load_config()
        self.setWindowTitle("iReflex App - AI 膝反射量測與分析系統")
        self.resize(1280, 720)

        # 初始化病人資料顯示和新增表單
        self.patient_list_widget = PatientListWidget()  # 顯示病人資料
        self.patient_form = PatientForm()  # 用於新增病人資料
        self.settings_page = SettingsPage()
        init_measurement_table()

        self.current_patient_id = None
        self.current_patient_name = None
        self.saved_result_count = 0

        # 初始化感測器與相機
        self.camera = None
        pose_mode = self.config.pose.get("mode", "fake")
        leg_side = self.config.pose.get("leg_side", "right")
        self.pose_estimator = PoseEstimator(mode=pose_mode, leg_side=leg_side)
        self.sensor_service = FakeSensorService()
        reflex_cfg = self.config.reflex
        self.reflex_analyzer = ReflexAnalyzer(
            fsr_threshold=reflex_cfg.get("fsr_threshold", 0.8),
            nano_rise_len=reflex_cfg.get("nano_rise_len", 5),
            valid_latency_ms=reflex_cfg.get("valid_latency_ms", 500),
        )

        # 初始化變數
        self.current_knee_angle = None
        self.current_fsr_voltage = 0.0
        self.current_nano_voltage = 0.0
        self.event_detected = False
        self.current_t0 = None
        self.current_t1 = None
        self.current_latency = None
        self.result_records = []
        self.is_measuring = False
        self.measure_start_time = None
        self.yolo_time = []
        self.yolo_angle = []
        self.sensor_time = []
        self.fsr_voltage = []
        self.nano_voltage = []

        # 設定計時器
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)

        # 控制介面設置
        self.video_label = QLabel("Camera Preview")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setMinimumSize(800, 480)
        self.video_label.setStyleSheet("background-color: #111; color: white; font-size: 24px;")

        self.status_label = QLabel()
        self.update_status_text(camera_running=False)

        # 控制按鈕
        self.start_btn = QPushButton("開始量測")
        self.stop_btn = QPushButton("停止量測")
        self.save_btn = QPushButton("儲存本次")
        self.discard_btn = QPushButton("捨棄本次")
        self.export_btn = QPushButton("匯出 CSV")
        self.switch_leg_btn = QPushButton("切換偵測腳")
        self.switch_leg_btn.setStyleSheet("font-size: 16px")
        self.switch_leg_btn.clicked.connect(self.on_switch_leg)

        self.result_table = QTableWidget(0, 9)
        self.result_table.setHorizontalHeaderLabels([
            "RL(ms)", "RA", "REA", "PEAD", "TTE(ms)",
            "Ext_Vel", "Force", "品質狀態", "品質原因"
        ])

        # 顯示病人資料和新增病人資料按鈕
        self.view_patients_button = QPushButton("查看病人資料")
        self.view_patients_button.clicked.connect(self.show_patient_list)

        self.add_patient_button = QPushButton("新增病人資料")
        self.add_patient_button.clicked.connect(self.show_patient_form)

        self.current_patient_label = QLabel("目前病人：未選擇")
        self.select_patient_button = QPushButton("選擇病人")
        self.clear_patient_button = QPushButton("清除選擇")

        self.settings_button = QPushButton("設定")

        self._build_layout()
        self._connect_signals()
        self.apply_theme(self.settings_page.current_theme)


    def _build_layout(self):
        right_panel = QGroupBox("系統狀態 / 即時數據")
        right_layout = QVBoxLayout()
        right_layout.addWidget(self.status_label)
        right_panel.setLayout(right_layout)

        top_layout = QHBoxLayout()
        top_layout.addWidget(self.video_label, stretch=3)
        top_layout.addWidget(right_panel, stretch=1)

        control_layout = QHBoxLayout()
        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addWidget(self.save_btn)
        control_layout.addWidget(self.discard_btn)
        control_layout.addWidget(self.export_btn)
        control_layout.addWidget(self.switch_leg_btn)
        control_layout.addWidget(self.view_patients_button)  # 顯示病人資料按鈕
        control_layout.addWidget(self.add_patient_button)  # 新增病人資料按鈕
        control_layout.addWidget(self.settings_button)

        patient_layout = QHBoxLayout()
        patient_layout.addWidget(self.current_patient_label, stretch=3)
        patient_layout.addWidget(self.select_patient_button)
        patient_layout.addWidget(self.clear_patient_button)

        main_layout = QVBoxLayout()
        main_layout.addLayout(patient_layout)
        main_layout.addLayout(top_layout)
        main_layout.addLayout(control_layout)
        main_layout.addWidget(self.result_table)

        self.main_page = QWidget()
        self.main_page.setLayout(main_layout)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.main_page)
        self.stack.addWidget(self.patient_form)
        self.stack.addWidget(self.patient_list_widget)
        self.stack.addWidget(self.settings_page)

        self.setCentralWidget(self.stack)
        self.stack.setCurrentWidget(self.main_page)

    def _connect_signals(self):
        self.start_btn.clicked.connect(self.on_start)
        self.stop_btn.clicked.connect(self.on_stop)
        self.save_btn.clicked.connect(self.on_save)
        self.discard_btn.clicked.connect(self.on_discard)
        self.export_btn.clicked.connect(self.on_export)

        self.select_patient_button.clicked.connect(self.select_patient)
        self.clear_patient_button.clicked.connect(self.clear_selected_patient)

        self.settings_button.clicked.connect(self.show_settings_page)

        self.patient_form.back_requested.connect(self.show_main_page)
        self.patient_list_widget.back_requested.connect(self.show_main_page)
        self.settings_page.back_requested.connect(self.show_main_page)

        self.settings_page.theme_changed.connect(self.apply_theme)

    def on_switch_leg(self):
        if self.pose_estimator.leg_side == "right":
            self.pose_estimator.leg_side = "left"
            self.switch_leg_btn.setText("切換偵測右腳")
        else:
            self.pose_estimator.leg_side = "right"
            self.switch_leg_btn.setText("切換偵測左腳")
        self.update_status_text(camera_running=True)

    def update_status_text(self, camera_running=False):
        pose_mode = self.config.pose.get("mode", "fake")
        sensor_mode = self.config.sensor.get("mode", "fake")
        camera_text = "已啟動" if camera_running else "未啟動"
        leg_side_text = f"偵測腳: {self.pose_estimator.leg_side}"

        self.status_label.setText(
            f"Camera: {camera_text}\n"
            f"Pose: {pose_mode}\n"
            f"Sensor: {sensor_mode}\n"
            f"{leg_side_text}\n\n"
            f"FSR: {self.fmt_voltage(self.current_fsr_voltage)} V\n"
            f"Nano: {self.fmt_voltage(self.current_nano_voltage)} V\n"
            f"Knee Angle: {self.fmt_float(self.current_knee_angle, 1)} deg\n\n"
            f"{self.get_event_text()}"
        )

    def fmt_float(self, value, digits=1, empty="--"):
        if value is None:
            return empty
        try:
            return f"{float(value):.{digits}f}"
        except (TypeError, ValueError):
            return empty

    def fmt_voltage(self, value, empty="--"):
        if value is None:
            return empty
        try:
            return f"{float(value):.2f}"
        except (TypeError, ValueError):
            return empty

    def get_event_text(self):
        if self.event_detected:
            return (
                f"t0: {self.fmt_float(self.current_t0, 1)} ms\n"
                f"t1: {self.fmt_float(self.current_t1, 1)} ms\n"
                f"RL: {self.fmt_float(self.current_latency, 1)} ms"
            )
        return "t0: -- ms\nt1: -- ms\nRL: -- ms"

    def show_main_page(self):
        """返回主畫面"""
        self.stack.setCurrentWidget(self.main_page)

    def show_patient_list(self):
        """顯示病人資料列表"""
        self.patient_list_widget.load_patients()
        self.stack.setCurrentWidget(self.patient_list_widget)

    def show_patient_form(self):
        """顯示病人新增表單"""
        self.stack.setCurrentWidget(self.patient_form)
    
    def select_patient(self):
        """選擇目前量測病人"""
        dialog = PatientSelectDialog(self)

        if dialog.exec() == dialog.DialogCode.Accepted:
            patient_id, patient_name = dialog.get_selected_patient()

            self.current_patient_id = patient_id
            self.current_patient_name = patient_name

            self.current_patient_label.setText(
                f"目前病人：{patient_name}，ID：{patient_id}"
            )

            self.statusBar().showMessage(
                f"已選擇目前病人：{patient_name}"
            )


    def clear_selected_patient(self):
        """清除目前選擇病人"""
        self.current_patient_id = None
        self.current_patient_name = None

        self.current_patient_label.setText("目前病人：未選擇")
        self.statusBar().showMessage("已清除目前病人")

    def show_settings_page(self):
        """顯示設定頁"""
        self.stack.setCurrentWidget(self.settings_page)

    def apply_theme(self, theme):
        """套用淺色 / 深色模式"""

        if theme == "dark":
            self.setStyleSheet("""
                QMainWindow, QWidget {
                    background-color: #1e1e1e;
                    color: #f0f0f0;
                    font-size: 14px;
                }

                QGroupBox {
                    border: 1px solid #555;
                    border-radius: 6px;
                    margin-top: 8px;
                    padding: 8px;
                    color: #f0f0f0;
                }

                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 4px;
                }

                QPushButton {
                    background-color: #333333;
                    color: #ffffff;
                    border: 1px solid #666666;
                    border-radius: 5px;
                    padding: 6px;
                }

                QPushButton:hover {
                    background-color: #444444;
                }

                QPushButton:pressed {
                    background-color: #555555;
                }

                QLineEdit, QComboBox, QDateEdit {
                    background-color: #2b2b2b;
                    color: #ffffff;
                    border: 1px solid #666666;
                    border-radius: 4px;
                    padding: 4px;
                }

                QTableWidget {
                    background-color: #252525;
                    color: #ffffff;
                    gridline-color: #555555;
                    selection-background-color: #3a6ea5;
                    selection-color: #ffffff;
                }

                QHeaderView::section {
                    background-color: #333333;
                    color: #ffffff;
                    border: 1px solid #555555;
                    padding: 4px;
                }

                QStatusBar {
                    background-color: #1e1e1e;
                    color: #ffffff;
                }
            """)
        else:
            self.setStyleSheet("""
                QMainWindow, QWidget {
                    background-color: #f5f5f5;
                    color: #000000;
                    font-size: 14px;
                }

                QPushButton {
                    background-color: #ffffff;
                    color: #000000;
                    border: 1px solid #cccccc;
                    border-radius: 5px;
                    padding: 6px;
                }

                QPushButton:hover {
                    background-color: #eeeeee;
                }

                QLineEdit, QComboBox, QDateEdit {
                    background-color: #ffffff;
                    color: #000000;
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                    padding: 4px;
                }

                QTableWidget {
                    background-color: #ffffff;
                    color: #000000;
                    gridline-color: #dddddd;
                    selection-background-color: #cce5ff;
                    selection-color: #000000;
                }

                QHeaderView::section {
                    background-color: #f0f0f0;
                    color: #000000;
                    border: 1px solid #dddddd;
                    padding: 4px;
                }
            """)

        # 相機預覽區固定維持黑底，避免被主題蓋掉
        self.video_label.setStyleSheet(
        "background-color: #111; color: white; font-size: 24px;"
    )

    def on_start(self):
        try:
            camera_cfg = self.config.camera
            self.camera = CameraService(
                camera_index=camera_cfg.get("index", 0),
                width=camera_cfg.get("width", 640),
                height=camera_cfg.get("height", 480),
                fps=camera_cfg.get("fps", 30),
            )
            self.camera.open()
            self.sensor_service.open()

            self.is_measuring = True
            self.measure_start_time = time.perf_counter()

            self.yolo_time.clear()
            self.yolo_angle.clear()
            self.sensor_time.clear()
            self.fsr_voltage.clear()
            self.nano_voltage.clear()

            self.event_detected = False
            self.current_t0 = None
            self.current_t1 = None
            self.current_latency = None

            self.saved_result_count = len(self.result_records)

            self.timer.start(30)
            self.update_status_text(camera_running=True)

            self.statusBar().showMessage("相機已啟動")

        except Exception as e:
            QMessageBox.critical(self, "相機錯誤", str(e))
            self.statusBar().showMessage("相機啟動失敗")

    def on_stop(self):
        self.timer.stop()
        self.is_measuring = False
        self.sensor_service.close()

        if self.camera is not None:
            self.camera.release()
            self.camera = None

        self.video_label.setText("Camera Preview")
        self.update_status_text(camera_running=False)

        self.statusBar().showMessage(
            f"相機已停止，共記錄 {len(self.yolo_angle)} 筆角度資料"
        )

    def update_frame(self):
        if self.camera is None:
            return

        ret, frame = self.camera.read()
        if not ret or frame is None:
            self.statusBar().showMessage("讀取相機畫面失敗")
            return

        try:
            output_frame, pose_result = self.pose_estimator.estimate(frame)
        except Exception as e:
            QMessageBox.critical(self, "Pose 錯誤", str(e))
            self.on_stop()
            return

        self.current_knee_angle = pose_result.get("knee_angle")

        sensor_data = self.sensor_service.read()
        self.current_fsr_voltage = sensor_data.get("fsr_voltage", 0.0)
        self.current_nano_voltage = sensor_data.get("nano_voltage", 0.0)

        if self.is_measuring and self.measure_start_time is not None:
            now_ms = (time.perf_counter() - self.measure_start_time) * 1000.0

            if self.current_knee_angle is not None:
                self.yolo_time.append(now_ms)
                self.yolo_angle.append(self.current_knee_angle)

            self.sensor_time.append(now_ms)
            self.fsr_voltage.append(self.current_fsr_voltage)
            self.nano_voltage.append(self.current_nano_voltage)

            if not self.event_detected and len(self.sensor_time) >= 10:
                event = self.reflex_analyzer.analyze_event(
                    self.sensor_time,
                    self.fsr_voltage,
                    self.nano_voltage,
                )

                if event is not None and event.get("is_valid", False):
                    self.event_detected = True
                    self.current_t0 = event.get("t0_ms")
                    self.current_t1 = event.get("t1_ms")
                    self.current_latency = event.get("latency_ms")

                    self.statusBar().showMessage(
                        f"偵測到反射事件："
                        f"t0={self.fmt_float(self.current_t0, 1)} ms, "
                        f"t1={self.fmt_float(self.current_t1, 1)} ms, "
                        f"RL={self.fmt_float(self.current_latency, 1)} ms"
                    )

                    self.add_result_to_table()

        self.update_status_text(camera_running=True)

        frame_rgb = cv2.cvtColor(output_frame, cv2.COLOR_BGR2RGB)
        h, w, ch = frame_rgb.shape
        bytes_per_line = ch * w

        q_img = QImage(
            frame_rgb.data,
            w,
            h,
            bytes_per_line,
            QImage.Format.Format_RGB888,
        )

        pixmap = QPixmap.fromImage(q_img)
        pixmap = pixmap.scaled(
            self.video_label.width(),
            self.video_label.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
        )

        self.video_label.setPixmap(pixmap)
    def classify_force(self):
        """
        根據 FSR 電壓判斷敲擊力道。
        目前用簡單門檻分類：
        < 1.4 V：偏弱
        1.4 ~ 1.8 V：適中
        >= 1.8 V：偏強
        """

        if len(self.fsr_voltage) > 0:
            force_value = max(self.fsr_voltage)
        else:
            force_value = self.current_fsr_voltage

        try:
            force_value = float(force_value)
        except (TypeError, ValueError):
            return "未知"

        if force_value < 1.4:
            return "偏弱"
        elif force_value < 1.8:
            return "適中"
        else:
            return "偏強"

    def add_result_to_table(self):
        if self.current_latency is None:
            return

        force_level = self.classify_force()

        try:
            angle_metrics = self.reflex_analyzer.analyze_angle_response(
                t0=self.current_t0,
                t1=self.current_t1,
                yolo_time=self.yolo_time,
                yolo_angle=self.yolo_angle,
                before_window_ms=300,
                after_window_ms=1500,
            )

            ra = angle_metrics.get("RA")
            rea = angle_metrics.get("REA")
            pead = angle_metrics.get("PEAD")
            tte = angle_metrics.get("TTE")
            ext_vel = angle_metrics.get("Ext_Vel")

        except Exception as e:
            self.statusBar().showMessage(f"角度指標計算失敗：{e}")

            ra = self.current_knee_angle if self.current_knee_angle is not None else 0.0
            rea = self.current_knee_angle if self.current_knee_angle is not None else 0.0
            pead = 0.0
            tte = 0.0
            ext_vel = 0.0

        record = {
            "RL": self.current_latency,
            "RA": ra,
            "REA": rea,
            "PEAD": pead,
            "TTE": tte,
            "Ext_Vel": ext_vel,
            "Force": force_level,
        }

        quality_status, quality_reason = self.evaluate_measurement_quality(record)

        record["Quality"] = quality_status
        record["Quality_Reason"] = quality_reason

        self.result_records.append(record)

        row = self.result_table.rowCount()
        self.result_table.insertRow(row)

        values = [
            self.fmt_float(record.get("RL"), 1),
            self.fmt_float(record.get("RA"), 1),
            self.fmt_float(record.get("REA"), 1),
            self.fmt_float(record.get("PEAD"), 1),
            self.fmt_float(record.get("TTE"), 1),
            self.fmt_float(record.get("Ext_Vel"), 1),
            record.get("Force", "未知"),
            record.get("Quality", ""),
            record.get("Quality_Reason", ""),
        ]

        for col, value in enumerate(values):
            self.result_table.setItem(row, col, QTableWidgetItem(value))
    
    def evaluate_measurement_quality(self, record):
        """
        判斷本次量測品質。
        目前使用保守規則：
        1. Force 偏弱 → 建議重測
        2. RL 無效或超過 500 ms → 建議重測
        3. RA / REA 缺失或為 0 → 建議重測
        4. PEAD 過小 → 建議重測
        """

        reasons = []

        rl = record.get("RL")
        ra = record.get("RA")
        rea = record.get("REA")
        pead = record.get("PEAD")
        force = record.get("Force")

        try:
            rl_value = float(rl)
            if rl_value <= 0 or rl_value > 500:
                reasons.append("反射潛伏期異常")
        except (TypeError, ValueError):
            reasons.append("反射潛伏期無效")

        try:
            ra_value = float(ra)
            rea_value = float(rea)

            if ra_value <= 0 or rea_value <= 0:
                reasons.append("角度資料異常")

        except (TypeError, ValueError):
            reasons.append("角度資料無效")

        try:
            pead_value = float(pead)

            if pead_value < 3:
                reasons.append("角度變化過小")

        except (TypeError, ValueError):
            reasons.append("峰值角度差無效")

        if force == "偏弱":
            reasons.append("敲擊力道偏弱")

        if len(reasons) == 0:
            return "有效", "資料品質正常"

        return "建議重測", "、".join(reasons)

    def on_save(self):
        if self.current_patient_id is None:
            QMessageBox.warning(
                self,
                "尚未選擇病人",
                "請先點選「選擇病人」，再儲存本次量測結果。"
            )
            return

        if len(self.result_records) == 0:
            QMessageBox.warning(
                self,
                "無資料",
                "目前沒有反射結果可以儲存。"
            )
            return

        unsaved_records = self.result_records[self.saved_result_count:]

        if len(unsaved_records) == 0:
            QMessageBox.information(
                self,
                "無新資料",
                "目前沒有新的量測結果需要儲存。"
            )
            return

        try:
            for record in unsaved_records:
                insert_measurement_record(
                    patient_id=self.current_patient_id,
                    record=record,
                    csv_path=""
                )

            self.saved_result_count = len(self.result_records)

            QMessageBox.information(
                self,
                "儲存成功",
                f"已將 {len(unsaved_records)} 筆量測結果儲存至病人："
                f"{self.current_patient_name}"
            )

            self.statusBar().showMessage(
                f"已儲存 {len(unsaved_records)} 筆量測結果至資料庫"
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "儲存失敗",
                f"量測結果寫入資料庫失敗：{e}"
            )

    def on_discard(self):
        row_count = self.result_table.rowCount()

        if row_count == 0:
            self.statusBar().showMessage("目前沒有紀錄可以捨棄")
            return

        if len(self.result_records) <= self.saved_result_count:
            QMessageBox.warning(
                self,
                "無法捨棄",
                "最新資料已經儲存到資料庫，不建議直接從暫存表格刪除。"
            )
            return

        self.result_table.removeRow(row_count - 1)

        if len(self.result_records) > 0:
            self.result_records.pop()

        self.statusBar().showMessage("已捨棄最新一筆尚未儲存的紀錄")

    def on_export(self):
        if len(self.yolo_time) == 0 or len(self.yolo_angle) == 0:
            QMessageBox.warning(self, "匯出失敗", "目前沒有角度資料可以匯出。")
            return

        if len(self.yolo_time) != len(self.yolo_angle):
            QMessageBox.critical(
                self,
                "資料錯誤",
                f"時間資料與角度資料長度不一致："
                f"time={len(self.yolo_time)}, angle={len(self.yolo_angle)}"
            )
            return

        output_dir = os.path.join("outputs", "csv")
        os.makedirs(output_dir, exist_ok=True)

        filename = datetime.now().strftime("angle_timeseries_%Y%m%d_%H%M%S.csv")
        file_path = os.path.join(output_dir, filename)

        with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)

            writer.writerow(["event_summary"])
            writer.writerow(["t0_ms", self.current_t0 if self.current_t0 is not None else ""])
            writer.writerow(["t1_ms", self.current_t1 if self.current_t1 is not None else ""])
            writer.writerow(["latency_ms", self.current_latency if self.current_latency is not None else ""])
            writer.writerow([])

            writer.writerow(["result_records"])
            writer.writerow([
                "RL(ms)", "RA", "REA", "PEAD", "TTE(ms)",
                "Ext_Vel", "Force", "Quality", "Quality_Reason"
            ])

            for record in self.result_records:
                writer.writerow([
                    self.fmt_float(record.get("RL"), 3),
                    self.fmt_float(record.get("RA"), 3),
                    self.fmt_float(record.get("REA"), 3),
                    self.fmt_float(record.get("PEAD"), 3),
                    self.fmt_float(record.get("TTE"), 3),
                    self.fmt_float(record.get("Ext_Vel"), 3),
                    record.get("Force", "未知"),
                    record.get("Quality", ""),
                    record.get("Quality_Reason", ""),
                ])

            writer.writerow([])
            writer.writerow(["time_ms", "knee_angle", "fsr_voltage", "nano_voltage"])

            row_count = min(
                len(self.yolo_time),
                len(self.yolo_angle),
                len(self.fsr_voltage),
                len(self.nano_voltage),
            )

            for i in range(row_count):
                writer.writerow([
                    self.fmt_float(self.yolo_time[i], 3),
                    self.fmt_float(self.yolo_angle[i], 3),
                    self.fmt_float(self.fsr_voltage[i], 3),
                    self.fmt_float(self.nano_voltage[i], 3),
                ])

        QMessageBox