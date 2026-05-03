import sqlite3
from datetime import datetime

DB_PATH = "patients.db"

def add_column_if_not_exists(cursor, table_name, column_name, column_def):
    """如果欄位不存在，就新增欄位"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]

    if column_name not in columns:
        cursor.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}"
        )

def init_measurement_table():
    """建立量測紀錄資料表"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS measurement_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                measure_time TEXT NOT NULL,
                RL REAL,
                RA REAL,
                REA REAL,
                PEAD REAL,
                TTE REAL,
                Ext_Vel REAL,
                Force TEXT,
                csv_path TEXT DEFAULT '',
                quality_status TEXT DEFAULT '',
                quality_reason TEXT DEFAULT '',
                FOREIGN KEY(patient_id) REFERENCES patients(id)
            )
        """)

        # 如果舊資料庫已經存在，但沒有這兩個欄位，就補上
        add_column_if_not_exists(
            cursor,
            "measurement_records",
            "quality_status",
            "TEXT DEFAULT ''"
        )

        add_column_if_not_exists(
            cursor,
            "measurement_records",
            "quality_reason",
            "TEXT DEFAULT ''"
        )

        conn.commit()

def fetch_all_patients():
    """讀取所有病人，給選擇病人視窗使用"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, name, dob, gender, contact_info, medical_history
            FROM patients
            ORDER BY id ASC
        """)

        return cursor.fetchall()

def insert_measurement_record(patient_id, record, csv_path=""):
    """新增一筆量測紀錄"""
    measure_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO measurement_records (
                patient_id,
                measure_time,
                RL,
                RA,
                REA,
                PEAD,
                TTE,
                Ext_Vel,
                Force,
                csv_path,
                quality_status,
                quality_reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            patient_id,
            measure_time,
            record.get("RL"),
            record.get("RA"),
            record.get("REA"),
            record.get("PEAD"),
            record.get("TTE"),
            record.get("Ext_Vel"),
            record.get("Force", ""),
            csv_path,
            record.get("Quality", ""),
            record.get("Quality_Reason", ""),
        ))

        conn.commit()

def fetch_measurements_by_patient(patient_id):
    """讀取某位病人的所有量測紀錄"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                id,
                measure_time,
                RL,
                RA,
                REA,
                PEAD,
                TTE,
                Ext_Vel,
                Force,
                quality_status,
                quality_reason
            FROM measurement_records
            WHERE patient_id = ?
            ORDER BY measure_time DESC
        """, (patient_id,))

        return cursor.fetchall()

def delete_measurements_by_patient(patient_id):
    """刪除某位病人的所有量測紀錄"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM measurement_records WHERE patient_id = ?",
            (patient_id,)
        )

        conn.commit()

def fetch_patient_by_id(patient_id):
    """依照病人 ID 讀取病人基本資料"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, name, dob, gender, contact_info, medical_history
            FROM patients
            WHERE id = ?
        """, (patient_id,))

        return cursor.fetchone()
    
def delete_measurement_by_id(record_id):
    """刪除單筆量測紀錄"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM measurement_records WHERE id = ?",
            (record_id,)
        )

        conn.commit()
