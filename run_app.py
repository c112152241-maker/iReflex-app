import sys
import sqlite3
from PyQt6.QtWidgets import QApplication
from app.ui.main_window import MainWindow

def create_connection(db_file):
    """建立並返回資料庫連線"""
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        print(f"成功連接資料庫，SQLite 版本：{sqlite3.version}")
    except sqlite3.Error as e:
        print(f"無法連接資料庫，錯誤：{e}")
    return conn

def create_patient_table(conn):
    """創建病人資料表"""
    try:
        sql_create_patients_table = """
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            dob DATE,
            gender TEXT,
            contact_info TEXT,
            medical_history TEXT
        );
        """
        cursor = conn.cursor()
        cursor.execute(sql_create_patients_table)
        conn.commit()
        print("病人資料表已建立")
    except sqlite3.Error as e:
        print(f"創建資料表時發生錯誤：{e}")

def main():
    # 連接並創建資料庫和資料表
    database = "patients.db"
    conn = create_connection(database)
    if conn:
        create_patient_table(conn)
        conn.close()

    # 啟動 PyQt6 應用程式
    qt_app = QApplication(sys.argv)

    # 啟動主視窗
    window = MainWindow()
    window.show()

    sys.exit(qt_app.exec())

if __name__ == "__main__":
    main()