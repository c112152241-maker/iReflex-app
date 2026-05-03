from PyQt6.QtWidgets import (
    QWidget, QLineEdit, QFormLayout, QPushButton,
    QHBoxLayout, QVBoxLayout, QDateEdit,
    QComboBox, QMessageBox
)
from PyQt6.QtCore import QDate, pyqtSignal
import sqlite3


class PatientForm(QWidget):
    back_requested = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.form_layout = QFormLayout()

        self.name_input = QLineEdit()

        self.dob_input = QDateEdit()
        self.dob_input.setCalendarPopup(True)
        self.dob_input.setDisplayFormat("yyyy-MM-dd")
        self.dob_input.setDate(QDate.currentDate().addYears(-20))
        self.dob_input.setMaximumDate(QDate.currentDate())

        self.gender_input = QComboBox()
        self.gender_input.addItems(["男", "女"])

        self.contact_input = QLineEdit()
        self.medical_history_input = QLineEdit()

        self.submit_button = QPushButton("提交")
        self.submit_button.clicked.connect(self.submit_patient_data)

        self.return_button = QPushButton("返回")
        self.return_button.clicked.connect(self.return_to_previous)

        self.form_layout.addRow("姓名:", self.name_input)
        self.form_layout.addRow("出生日期:", self.dob_input)
        self.form_layout.addRow("性別:", self.gender_input)
        self.form_layout.addRow("聯絡方式:", self.contact_input)
        self.form_layout.addRow("病歷:", self.medical_history_input)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.return_button)
        button_layout.addWidget(self.submit_button)

        main_layout = QVBoxLayout()
        main_layout.addLayout(self.form_layout)
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

    def submit_patient_data(self):
        name = self.name_input.text().strip()
        dob = self.dob_input.date().toString("yyyy-MM-dd")
        gender = self.gender_input.currentText()
        contact_info = self.contact_input.text().strip()
        medical_history = self.medical_history_input.text().strip()

        if not name or not contact_info or not medical_history:
            QMessageBox.warning(self, "錯誤", "姓名、聯絡方式、病歷必須填寫！")
            return

        try:
            with sqlite3.connect("patients.db") as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO patients 
                    (name, dob, gender, contact_info, medical_history)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (name, dob, gender, contact_info, medical_history)
                )
                conn.commit()

            QMessageBox.information(self, "成功", "病人資料已成功新增！")

            self.clear_form()
            self.back_requested.emit()

        except sqlite3.Error as e:
            QMessageBox.critical(self, "資料庫錯誤", f"資料儲存失敗：{e}")

    def return_to_previous(self):
        self.back_requested.emit()

    def clear_form(self):
        self.name_input.clear()
        self.dob_input.setDate(QDate.currentDate().addYears(-20))
        self.gender_input.setCurrentIndex(0)
        self.contact_input.clear()
        self.medical_history_input.clear()