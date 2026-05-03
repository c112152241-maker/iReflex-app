import sqlite3

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem,
    QPushButton, QMessageBox, QDialog,
    QFormLayout, QLineEdit, QDateEdit,
    QComboBox, QAbstractItemView
)

from collections import Counter

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib
import matplotlib.font_manager as fm
import os


def setup_matplotlib_chinese_font():
    font_paths = [
        r"C:\Windows\Fonts\msjh.ttc",      # 微軟正黑體
        r"C:\Windows\Fonts\msjhbd.ttc",    # 微軟正黑體粗體
        r"C:\Windows\Fonts\kaiu.ttf",      # 標楷體
        r"C:\Windows\Fonts\mingliu.ttc",   # 細明體
    ]

    for font_path in font_paths:
        if os.path.exists(font_path):
            fm.fontManager.addfont(font_path)
            font_prop = fm.FontProperties(fname=font_path)
            matplotlib.rcParams["font.family"] = font_prop.get_name()
            matplotlib.rcParams["font.sans-serif"] = [font_prop.get_name()]
            matplotlib.rcParams["axes.unicode_minus"] = False
            return

    matplotlib.rcParams["axes.unicode_minus"] = False


setup_matplotlib_chinese_font()

from PyQt6.QtCore import pyqtSignal, QDate

from app.data.measurement_db import (
    fetch_measurements_by_patient,
    delete_measurements_by_patient,
    fetch_patient_by_id,
    delete_measurement_by_id
)

from app.data.report_generator import (
    generate_patient_txt_report,
    generate_patient_pdf_report
)

class MeasurementChartDialog(QDialog):
    def __init__(self, patient_id, patient_name, parent=None):
        super().__init__(parent)

        self.patient_id = patient_id
        self.patient_name = patient_name

        self.setWindowTitle(f"量測趨勢圖 - {patient_name}")
        self.resize(1100, 800)

        main_layout = QVBoxLayout()

        self.figure = Figure(figsize=(10, 8))
        self.canvas = FigureCanvas(self.figure)

        self.close_button = QPushButton("關閉")
        self.close_button.clicked.connect(self.accept)

        main_layout.addWidget(self.canvas)
        main_layout.addWidget(self.close_button)

        self.setLayout(main_layout)

        self.plot_charts()

    def to_float_list(self, rows, index):
        values = []

        for row in rows:
            try:
                values.append(float(row[index]))
            except (TypeError, ValueError):
                values.append(None)

        return values

    def plot_line(self, ax, x_values, y_values, title, ylabel):
        valid_x = []
        valid_y = []

        for x, y in zip(x_values, y_values):
            if y is not None:
                valid_x.append(x)
                valid_y.append(y)

        if len(valid_y) == 0:
            ax.text(
                0.5,
                0.5,
                "無可用資料",
                ha="center",
                va="center",
                transform=ax.transAxes
            )
        else:
            ax.plot(valid_x, valid_y, marker="o")

        ax.set_title(title)
        ax.set_xlabel("量測序號")
        ax.set_ylabel(ylabel)
        ax.grid(True)

    def plot_charts(self):
        rows = fetch_measurements_by_patient(self.patient_id)

        self.figure.clear()

        if len(rows) == 0:
            ax = self.figure.add_subplot(111)
            ax.text(
                0.5,
                0.5,
                "目前沒有量測紀錄",
                ha="center",
                va="center",
                transform=ax.transAxes
            )
            self.canvas.draw()
            return

        # fetch_measurements_by_patient 回傳欄位：
        # 0 id
        # 1 measure_time
        # 2 RL
        # 3 RA
        # 4 REA
        # 5 PEAD
        # 6 TTE
        # 7 Ext_Vel
        # 8 Force
        # 9 quality_status
        # 10 quality_reason

        # 因為資料庫是 ORDER BY measure_time DESC，所以這裡反轉成時間由舊到新
        rows = list(reversed(rows))

        x_values = list(range(1, len(rows) + 1))

        rl_values = self.to_float_list(rows, 2)
        ra_values = self.to_float_list(rows, 3)
        rea_values = self.to_float_list(rows, 4)
        tte_values = self.to_float_list(rows, 6)

        ax1 = self.figure.add_subplot(221)
        self.plot_line(
            ax1,
            x_values,
            rl_values,
            "RL 反射潛伏期趨勢",
            "RL(ms)"
        )

        ax2 = self.figure.add_subplot(222)

        valid_ra_x = []
        valid_ra_y = []
        valid_rea_x = []
        valid_rea_y = []

        for x, y in zip(x_values, ra_values):
            if y is not None:
                valid_ra_x.append(x)
                valid_ra_y.append(y)

        for x, y in zip(x_values, rea_values):
            if y is not None:
                valid_rea_x.append(x)
                valid_rea_y.append(y)

        if len(valid_ra_y) == 0 and len(valid_rea_y) == 0:
            ax2.text(
                0.5,
                0.5,
                "無可用角度資料",
                ha="center",
                va="center",
                transform=ax2.transAxes
            )
        else:
            ax2.plot(valid_ra_x, valid_ra_y, marker="o", label="RA")
            ax2.plot(valid_rea_x, valid_rea_y, marker="o", label="REA")
            ax2.legend()

        ax2.set_title("RA / REA 角度趨勢")
        ax2.set_xlabel("量測序號")
        ax2.set_ylabel("角度")
        ax2.grid(True)

        ax3 = self.figure.add_subplot(223)
        self.plot_line(
            ax3,
            x_values,
            tte_values,
            "TTE 達峰時間趨勢",
            "TTE(ms)"
        )

        ax4 = self.figure.add_subplot(224)

        quality_list = []
        for row in rows:
            quality = str(row[9]) if len(row) > 9 and row[9] is not None else "未標記"
            if quality.strip() == "":
                quality = "未標記"
            quality_list.append(quality)

        quality_counter = Counter(quality_list)

        labels = list(quality_counter.keys())
        counts = list(quality_counter.values())

        ax4.bar(labels, counts)
        ax4.set_title("量測品質狀態統計")
        ax4.set_xlabel("品質狀態")
        ax4.set_ylabel("筆數")
        ax4.tick_params(axis="x", rotation=20)

        self.figure.suptitle(f"{self.patient_name} 量測紀錄統計圖", fontsize=14)
        self.figure.tight_layout()

        self.canvas.draw()

class MeasurementHistoryDialog(QDialog):
    def __init__(self, patient_id, patient_name, parent=None):
        super().__init__(parent)

        self.patient_id = patient_id
        self.patient_name = patient_name

        self.setWindowTitle(f"量測紀錄 - {patient_name}")
        self.resize(1000, 500)

        layout = QVBoxLayout()

        self.table = QTableWidget()

        self.table.setColumnCount(11)
        self.table.setHorizontalHeaderLabels([
            "紀錄ID",
            "量測時間",
            "RL(ms)",
            "RA",
            "REA",
            "PEAD",
            "TTE(ms)",
            "Ext_Vel",
            "Force",
            "品質狀態",
            "品質原因"
        ])

        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        self.report_button = QPushButton("產生 TXT 報告")
        self.pdf_report_button = QPushButton("產生 PDF 報告")
        self.chart_button = QPushButton("查看趨勢圖")
        self.delete_button = QPushButton("刪除選取紀錄")
        self.close_button = QPushButton("關閉")

        self.report_button.clicked.connect(self.generate_selected_report)
        self.pdf_report_button.clicked.connect(self.generate_selected_pdf_report)
        self.chart_button.clicked.connect(self.show_chart_dialog)
        self.delete_button.clicked.connect(self.delete_selected_record)
        self.close_button.clicked.connect(self.accept)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.close_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addWidget(self.report_button)
        button_layout.addWidget(self.pdf_report_button)
        button_layout.addWidget(self.chart_button)

        layout.addWidget(self.table)
        layout.addLayout(button_layout)

        self.setLayout(layout)

        self.load_records(self.patient_id)

    def load_records(self, patient_id):
        rows = fetch_measurements_by_patient(patient_id)

        self.table.setRowCount(len(rows))

        for row_num, row_data in enumerate(rows):
            for col_num, data in enumerate(row_data):
                self.table.setItem(
                    row_num,
                    col_num,
                    QTableWidgetItem(str(data))
                )

        self.table.resizeColumnsToContents()

    def get_selected_measurement_data(self):
        row = self.table.currentRow()

        if row < 0:
            QMessageBox.warning(
                self,
                "未選取量測紀錄",
                "請先選取一筆量測紀錄。"
            )
            return None

        measurement_data = []

        for col in range(11):
            item = self.table.item(row, col)
            measurement_data.append(item.text() if item is not None else "")

        measurement_data[0] = int(measurement_data[0])

        return measurement_data

    def generate_selected_report(self):
        measurement_data = self.get_selected_measurement_data()

        if measurement_data is None:
            return

        patient_data = fetch_patient_by_id(self.patient_id)

        if patient_data is None:
            QMessageBox.warning(
                self,
                "找不到病人資料",
                "無法產生報告，因為找不到此病人的基本資料。"
            )
            return

        try:
            file_path = generate_patient_txt_report(
                patient_data=patient_data,
                measurement_data=measurement_data
            )

            QMessageBox.information(
                self,
                "報告產生成功",
                f"已產生報告：\n{file_path}"
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "報告產生失敗",
                f"產生報告時發生錯誤：{e}"
            )

    def generate_selected_pdf_report(self):
        measurement_data = self.get_selected_measurement_data()

        if measurement_data is None:
            return

        patient_data = fetch_patient_by_id(self.patient_id)

        if patient_data is None:
            QMessageBox.warning(
                self,
                "找不到病人資料",
                "無法產生 PDF 報告，因為找不到此病人的基本資料。"
            )
            return

        try:
            file_path = generate_patient_pdf_report(
                patient_data=patient_data,
                measurement_data=measurement_data
            )

            QMessageBox.information(
                self,
                "PDF 報告產生成功",
                f"已產生 PDF 報告：\n{file_path}"
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "PDF 報告產生失敗",
                f"產生 PDF 報告時發生錯誤：{e}"
            )

    def show_chart_dialog(self):
        dialog = MeasurementChartDialog(
            patient_id=self.patient_id,
            patient_name=self.patient_name,
            parent=self
        )

        dialog.exec()

    def delete_selected_record(self):
        measurement_data = self.get_selected_measurement_data()

        if measurement_data is None:
            return

        record_id = measurement_data[0]
        measure_time = measurement_data[1]

        reply = QMessageBox.question(
            self,
            "確認刪除",
            f"確定要刪除這筆量測紀錄嗎？\n\n"
            f"紀錄 ID：{record_id}\n"
            f"量測時間：{measure_time}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            delete_measurement_by_id(record_id)

            QMessageBox.information(
                self,
                "刪除成功",
                "量測紀錄已刪除。"
            )

            self.load_records(self.patient_id)

        except Exception as e:
            QMessageBox.critical(
                self,
                "刪除失敗",
                f"刪除量測紀錄時發生錯誤：{e}"
            )

class PatientEditDialog(QDialog):
    def __init__(self, patient_data, parent=None):
        super().__init__(parent)

        self.setWindowTitle("編輯病人資料")
        self.patient_id = patient_data[0]

        _, name, dob, gender, contact_info, medical_history = patient_data

        layout = QFormLayout()

        self.name_input = QLineEdit(str(name))

        self.dob_input = QDateEdit()
        self.dob_input.setCalendarPopup(True)
        self.dob_input.setDisplayFormat("yyyy-MM-dd")

        date = QDate.fromString(str(dob), "yyyy-MM-dd")
        if not date.isValid():
            date = QDate.currentDate().addYears(-20)

        self.dob_input.setDate(date)
        self.dob_input.setMaximumDate(QDate.currentDate())

        self.gender_input = QComboBox()
        self.gender_input.addItems(["男", "女"])

        gender_index = self.gender_input.findText(str(gender))
        if gender_index >= 0:
            self.gender_input.setCurrentIndex(gender_index)

        self.contact_input = QLineEdit(str(contact_info))
        self.medical_history_input = QLineEdit(str(medical_history))

        self.save_button = QPushButton("儲存修改")
        self.cancel_button = QPushButton("取消")

        self.save_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.save_button)

        layout.addRow("姓名:", self.name_input)
        layout.addRow("出生日期:", self.dob_input)
        layout.addRow("性別:", self.gender_input)
        layout.addRow("聯絡方式:", self.contact_input)
        layout.addRow("病歷:", self.medical_history_input)
        layout.addRow(button_layout)

        self.setLayout(layout)

    def get_data(self):
        return {
            "id": self.patient_id,
            "name": self.name_input.text().strip(),
            "dob": self.dob_input.date().toString("yyyy-MM-dd"),
            "gender": self.gender_input.currentText(),
            "contact_info": self.contact_input.text().strip(),
            "medical_history": self.medical_history_input.text().strip(),
        }


class PatientListWidget(QWidget):
    back_requested = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.layout = QVBoxLayout()

        # 搜尋區
        search_layout = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("輸入 ID、姓名、生日、性別、聯絡方式或病歷關鍵字")

        self.search_button = QPushButton("搜尋")
        self.show_all_button = QPushButton("顯示全部")

        self.search_button.clicked.connect(self.search_patients)
        self.show_all_button.clicked.connect(self.reset_search)

        # 按 Enter 也可以搜尋
        self.search_input.returnPressed.connect(self.search_patients)

        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_button)
        search_layout.addWidget(self.show_all_button)

        self.layout.addLayout(search_layout)

        button_layout = QHBoxLayout()

        self.return_button = QPushButton("返回")
        self.refresh_button = QPushButton("重新整理")
        self.edit_button = QPushButton("編輯選取資料")
        self.delete_button = QPushButton("刪除選取資料")
        self.records_button = QPushButton("查看量測紀錄")

        self.return_button.clicked.connect(self.back_requested.emit)
        self.refresh_button.clicked.connect(self.load_patients)
        self.edit_button.clicked.connect(self.edit_selected_patient)
        self.delete_button.clicked.connect(self.delete_selected_patient)
        self.records_button.clicked.connect(self.view_selected_patient_records)

        button_layout.addWidget(self.return_button)
        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.edit_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addWidget(self.records_button)

        self.table = QTableWidget(self)
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "ID", "姓名", "出生日期", "性別", "聯絡方式", "病歷"
        ])

        # 讓使用者只能選整列，不直接在表格上亂改
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        self.layout.addLayout(button_layout)
        self.layout.addWidget(self.table)

        self.setLayout(self.layout)

        self.load_patients()

    def load_patients(self):
        self.table.setRowCount(0)

        try:
            conn = sqlite3.connect("patients.db")
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, name, dob, gender, contact_info, medical_history
                FROM patients
                ORDER BY id ASC
            """)

            rows = cursor.fetchall()
            conn.close()

            self.populate_table(rows)

        except sqlite3.Error as e:
            QMessageBox.critical(
                self,
                "資料庫錯誤",
                f"讀取病人資料失敗：{e}"
            )

    def populate_table(self, rows):
        """把查詢結果顯示到表格"""
        self.table.setRowCount(0)
        self.table.setRowCount(len(rows))

        for row_num, row_data in enumerate(rows):
            for col_num, data in enumerate(row_data):
                self.table.setItem(
                    row_num,
                    col_num,
                    QTableWidgetItem(str(data))
                )

        self.table.resizeColumnsToContents()

    def search_patients(self):
        keyword = self.search_input.text().strip()

        if keyword == "":
            self.load_patients()
            return

        like_keyword = f"%{keyword}%"

        try:
            conn = sqlite3.connect("patients.db")
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, name, dob, gender, contact_info, medical_history
                FROM patients
                WHERE CAST(id AS TEXT) LIKE ?
                   OR name LIKE ?
                   OR dob LIKE ?
                   OR gender LIKE ?
                   OR contact_info LIKE ?
                   OR medical_history LIKE ?
                ORDER BY id ASC
            """, (
                like_keyword,
                like_keyword,
                like_keyword,
                like_keyword,
                like_keyword,
                like_keyword,
            ))

            rows = cursor.fetchall()
            conn.close()

            self.populate_table(rows)

            if len(rows) == 0:
                QMessageBox.information(
                    self,
                    "搜尋結果",
                    "找不到符合條件的病人資料。"
                )

        except sqlite3.Error as e:
            QMessageBox.critical(
                self,
                "資料庫錯誤",
                f"搜尋病人資料失敗：{e}"
            )
    
    def reset_search(self):
        """清除搜尋並顯示全部病人"""
        self.search_input.clear()
        self.load_patients()
    

    def get_selected_patient_data(self):
        row = self.table.currentRow()

        if row < 0:
            QMessageBox.warning(self, "未選取資料", "請先選取一筆病人資料。")
            return None

        patient_data = []

        for col in range(6):
            item = self.table.item(row, col)
            patient_data.append(item.text() if item is not None else "")

        patient_data[0] = int(patient_data[0])

        return patient_data

    def edit_selected_patient(self):
        patient_data = self.get_selected_patient_data()

        if patient_data is None:
            return

        dialog = PatientEditDialog(patient_data, self)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()

            if not data["name"] or not data["contact_info"] or not data["medical_history"]:
                QMessageBox.warning(
                    self,
                    "資料不完整",
                    "姓名、聯絡方式、病歷必須填寫。"
                )
                return

            try:
                conn = sqlite3.connect("patients.db")
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE patients
                    SET name = ?,
                        dob = ?,
                        gender = ?,
                        contact_info = ?,
                        medical_history = ?
                    WHERE id = ?
                """, (
                    data["name"],
                    data["dob"],
                    data["gender"],
                    data["contact_info"],
                    data["medical_history"],
                    data["id"],
                ))

                conn.commit()
                conn.close()

                QMessageBox.information(self, "修改成功", "病人資料已更新。")

                self.load_patients()

            except sqlite3.Error as e:
                QMessageBox.critical(
                    self,
                    "資料庫錯誤",
                    f"更新病人資料失敗：{e}"
                )

    def delete_selected_patient(self):
        patient_data = self.get_selected_patient_data()

        if patient_data is None:
            return

        patient_id = patient_data[0]
        patient_name = patient_data[1]

        reply = QMessageBox.question(
            self,
            "確認刪除",
            f"確定要刪除病人資料嗎？\n\nID：{patient_id}\n姓名：{patient_name}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            conn = sqlite3.connect("patients.db")
            cursor = conn.cursor()

            delete_measurements_by_patient(patient_id)

            cursor.execute(
                "DELETE FROM patients WHERE id = ?",
                (patient_id,)
            )

            conn.commit()
            conn.close()

            QMessageBox.information(self, "刪除成功", "病人資料已刪除。")

            self.load_patients()

        except sqlite3.Error as e:
            QMessageBox.critical(
                self,
                "資料庫錯誤",
                f"刪除病人資料失敗：{e}"
            )
    
    def view_selected_patient_records(self):
        patient_data = self.get_selected_patient_data()

        if patient_data is None:
            return

        patient_id = patient_data[0]
        patient_name = patient_data[1]

        dialog = MeasurementHistoryDialog(
            patient_id=patient_id,
            patient_name=patient_name,
            parent=self
        )

        dialog.exec()