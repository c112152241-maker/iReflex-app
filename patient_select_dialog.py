from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem,
    QPushButton, QMessageBox, QAbstractItemView
)

from app.data.measurement_db import fetch_all_patients


class PatientSelectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("選擇目前病人")
        self.resize(800, 400)

        self.selected_patient_id = None
        self.selected_patient_name = None

        main_layout = QVBoxLayout()

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "ID", "姓名", "出生日期", "性別", "聯絡方式", "病歷"
        ])

        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        self.select_button = QPushButton("選擇")
        self.cancel_button = QPushButton("取消")

        self.select_button.clicked.connect(self.on_select)
        self.cancel_button.clicked.connect(self.reject)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.select_button)

        main_layout.addWidget(self.table)
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

        self.load_patients()

    def load_patients(self):
        rows = fetch_all_patients()

        self.table.setRowCount(len(rows))

        for row_num, row_data in enumerate(rows):
            for col_num, data in enumerate(row_data):
                self.table.setItem(
                    row_num,
                    col_num,
                    QTableWidgetItem(str(data))
                )

        self.table.resizeColumnsToContents()

    def on_select(self):
        row = self.table.currentRow()

        if row < 0:
            QMessageBox.warning(self, "未選取病人", "請先選擇一位病人。")
            return

        id_item = self.table.item(row, 0)
        name_item = self.table.item(row, 1)

        if id_item is None or name_item is None:
            QMessageBox.warning(self, "資料錯誤", "選取的病人資料不完整。")
            return

        self.selected_patient_id = int(id_item.text())
        self.selected_patient_name = name_item.text()

        self.accept()

    def get_selected_patient(self):
        return self.selected_patient_id, self.selected_patient_name