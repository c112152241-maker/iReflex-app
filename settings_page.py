import os
import json
import shutil
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QGroupBox,
    QMessageBox
)

from PyQt6.QtCore import pyqtSignal


SETTINGS_PATH = os.path.join("outputs", "app_settings.json")


class SettingsPage(QWidget):
    back_requested = pyqtSignal()
    theme_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()

        self.current_theme = self.load_theme()

        main_layout = QVBoxLayout()

        title_label = QLabel("系統設定")
        title_label.setStyleSheet("font-size: 22px; font-weight: bold;")

        theme_group = QGroupBox("畫面顏色設定")
        theme_layout = QVBoxLayout()

        theme_label = QLabel("頁面模式：")

        self.theme_combo = QComboBox()
        self.theme_combo.addItem("淺色模式", "light")
        self.theme_combo.addItem("深色模式", "dark")

        index = self.theme_combo.findData(self.current_theme)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)

        self.theme_combo.currentIndexChanged.connect(self.on_theme_changed)

        theme_layout.addWidget(theme_label)
        theme_layout.addWidget(self.theme_combo)
        theme_group.setLayout(theme_layout)

        self.backup_db_button = QPushButton("備份資料庫")
        self.backup_db_button.clicked.connect(self.backup_database)

        self.back_button = QPushButton("返回")
        self.back_button.clicked.connect(self.back_requested.emit)

        main_layout.addWidget(title_label)
        main_layout.addWidget(theme_group)
        main_layout.addStretch()
        main_layout.addWidget(self.backup_db_button)
        main_layout.addWidget(self.back_button)

        self.setLayout(main_layout)

    def on_theme_changed(self):
        theme = self.theme_combo.currentData()
        self.current_theme = theme
        self.save_theme(theme)
        self.theme_changed.emit(theme)

    def load_theme(self):
        try:
            if os.path.exists(SETTINGS_PATH):
                with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("theme", "light")
        except Exception:
            pass

        return "light"

    def save_theme(self, theme):
        os.makedirs("outputs", exist_ok=True)

        data = {
            "theme": theme
        }

        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def backup_database(self):
        """備份 patients.db 到 outputs/backups 資料夾"""

        db_path = "patients.db"

        if not os.path.exists(db_path):
            QMessageBox.warning(
                self,
                "備份失敗",
                "找不到 patients.db，無法備份資料庫。"
            )
            return

        backup_dir = os.path.join("outputs", "backups")
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"patients_backup_{timestamp}.db"
        backup_path = os.path.join(backup_dir, backup_filename)

        try:
            shutil.copy2(db_path, backup_path)

            QMessageBox.information(
                self,
                "備份成功",
                f"資料庫已成功備份到：\n{backup_path}"
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "備份失敗",
                f"備份資料庫時發生錯誤：{e}"
            )