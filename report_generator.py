import os
from datetime import datetime


def sanitize_filename(text):
    """避免 Windows 檔名出現非法字元"""
    text = str(text)
    invalid_chars = '<>:"/\\|?*'

    for ch in invalid_chars:
        text = text.replace(ch, "_")

    return text.strip().replace(" ", "_")


def fmt_value(value, digits=3):
    if value is None:
        return "--"

    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def generate_patient_txt_report(patient_data, measurement_data):
    """
    產生病人單筆量測 TXT 報告

    patient_data:
        (id, name, dob, gender, contact_info, medical_history)

    measurement_data:
        (id, measure_time, RL, RA, REA, PEAD, TTE, Ext_Vel, Force)
    """

    patient_id, name, dob, gender, contact_info, medical_history = patient_data

    record_id = measurement_data[0]
    measure_time = measurement_data[1]
    RL = measurement_data[2]
    RA = measurement_data[3]
    REA = measurement_data[4]
    PEAD = measurement_data[5]
    TTE = measurement_data[6]
    Ext_Vel = measurement_data[7]
    Force = measurement_data[8]

    quality_status = measurement_data[9] if len(measurement_data) > 9 else ""
    quality_reason = measurement_data[10] if len(measurement_data) > 10 else "" 

    output_dir = os.path.join("outputs", "reports")
    os.makedirs(output_dir, exist_ok=True)

    now_text = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = sanitize_filename(name)

    filename = f"report_patient_{patient_id}_{safe_name}_{now_text}.txt"
    file_path = os.path.join(output_dir, filename)

    report = f"""
iReflex AI 膝反射量測報告
========================================

一、病人基本資料
----------------------------------------
病人 ID：{patient_id}
姓名：{name}
出生日期：{dob}
性別：{gender}
聯絡方式：{contact_info}
病歷：{medical_history}

二、量測紀錄
----------------------------------------
紀錄 ID：{record_id}
量測時間：{measure_time}

三、膝反射量測結果
----------------------------------------
RL 反射潛伏期：{fmt_value(RL)} ms
RA 反射角度：{fmt_value(RA)}
REA 最大伸展角度：{fmt_value(REA)}
PEAD 峰值角度差：{fmt_value(PEAD)}
TTE 達峰時間：{fmt_value(TTE)} ms
Ext_Vel 伸展速度：{fmt_value(Ext_Vel)}
Force 敲擊力道：{Force}
品質狀態：{quality_status}
品質原因：{quality_reason}

四、系統備註
----------------------------------------
本報告由 iReflex App 自動產生。
本系統結果可作為膝反射量測紀錄與後續分析參考。
實際臨床判讀仍需由專業人員綜合評估。

========================================
報告產生時間：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

    with open(file_path, "w", encoding="utf-8-sig") as f:
        f.write(report)

    return file_path

def generate_patient_pdf_report(patient_data, measurement_data):
    """
    產生病人單筆量測 PDF 報告
    """

    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer,
        Table, TableStyle
    )
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    CHINESE_FONT_NAME = "MicrosoftJhengHei"
    CHINESE_FONT_PATHS = [
        r"C:\Windows\Fonts\msjh.ttc",
        r"C:\Windows\Fonts\msjhbd.ttc",
        r"C:\Windows\Fonts\kaiu.ttf",
        r"C:\Windows\Fonts\mingliu.ttc",
    ]

    font_path = None
    for path in CHINESE_FONT_PATHS:
        if os.path.exists(path):
            font_path = path
            break

    if font_path is None:
        raise FileNotFoundError(
            "找不到可用中文字型，請確認 C:\\Windows\\Fonts 是否有 msjh.ttc、kaiu.ttf 或 mingliu.ttc"
        )

    pdfmetrics.registerFont(TTFont(CHINESE_FONT_NAME, font_path))

    patient_id, name, dob, gender, contact_info, medical_history = patient_data

    record_id = measurement_data[0]
    measure_time = measurement_data[1]
    RL = measurement_data[2]
    RA = measurement_data[3]
    REA = measurement_data[4]
    PEAD = measurement_data[5]
    TTE = measurement_data[6]
    Ext_Vel = measurement_data[7]
    Force = measurement_data[8]

    quality_status = measurement_data[9] if len(measurement_data) > 9 else ""
    quality_reason = measurement_data[10] if len(measurement_data) > 10 else ""

    output_dir = os.path.join("outputs", "reports")
    os.makedirs(output_dir, exist_ok=True)

    now_text = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = sanitize_filename(name)

    filename = f"report_patient_{patient_id}_{safe_name}_{now_text}.pdf"
    file_path = os.path.join(output_dir, filename)

    doc = SimpleDocTemplate(
        file_path,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ChineseTitle",
        parent=styles["Title"],
        fontName=CHINESE_FONT_NAME,
        fontSize=20,
        leading=26,
        alignment=1,
        spaceAfter=20,
    )

    heading_style = ParagraphStyle(
        "ChineseHeading",
        parent=styles["Heading2"],
        fontName=CHINESE_FONT_NAME,
        fontSize=14,
        leading=18,
        spaceBefore=12,
        spaceAfter=8,
    )

    normal_style = ParagraphStyle(
        "ChineseNormal",
        parent=styles["Normal"],
        fontName=CHINESE_FONT_NAME,
        fontSize=11,
        leading=16,
    )

    story = []

    story.append(Paragraph("iReflex AI 膝反射量測報告", title_style))
    story.append(Spacer(1, 12))

    story.append(Paragraph("一、病人基本資料", heading_style))

    patient_table_data = [
        ["病人 ID", str(patient_id)],
        ["姓名", str(name)],
        ["出生日期", str(dob)],
        ["性別", str(gender)],
        ["聯絡方式", str(contact_info)],
        ["病歷", str(medical_history)],
    ]

    patient_table = Table(patient_table_data, colWidths=[110, 360])
    patient_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), CHINESE_FONT_NAME),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    story.append(patient_table)
    story.append(Spacer(1, 16))

    story.append(Paragraph("二、量測紀錄", heading_style))

    measurement_info_data = [
        ["紀錄 ID", str(record_id)],
        ["量測時間", str(measure_time)],
    ]

    measurement_info_table = Table(measurement_info_data, colWidths=[110, 360])
    measurement_info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), CHINESE_FONT_NAME),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    story.append(measurement_info_table)
    story.append(Spacer(1, 16))

    story.append(Paragraph("三、膝反射量測結果", heading_style))

    result_table_data = [
        ["項目", "數值", "說明"],
        ["RL", f"{fmt_value(RL)} ms", "反射潛伏期"],
        ["RA", fmt_value(RA), "反射角度"],
        ["REA", fmt_value(REA), "最大伸展角度"],
        ["PEAD", fmt_value(PEAD), "峰值角度差"],
        ["TTE", f"{fmt_value(TTE)} ms", "達峰時間"],
        ["Ext_Vel", fmt_value(Ext_Vel), "伸展速度"],
        ["Force", str(Force), "敲擊力道"],
        ["Quality", str(quality_status), "品質狀態"],
        ["Reason", str(quality_reason), "品質原因"],
    ]

    result_table = Table(result_table_data, colWidths=[90, 150, 230])
    result_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), CHINESE_FONT_NAME),
        ("FONTSIZE", (0, 0), (-1, -1), 10.5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    story.append(result_table)
    story.append(Spacer(1, 16))

    story.append(Paragraph("四、系統備註", heading_style))
    story.append(Paragraph(
        "本報告由 iReflex App 自動產生。本系統結果可作為膝反射量測紀錄與後續分析參考，實際臨床判讀仍需由專業人員綜合評估。",
        normal_style
    ))

    story.append(Spacer(1, 24))

    story.append(Paragraph(
        f"報告產生時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        normal_style
    ))

    doc.build(story)

    return file_path