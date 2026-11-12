# Bước DL-1 — Kiểm tra mô hình Deep Learning đã huấn luyện

## Mục tiêu

Kiểm tra **các artifacts và chỉ số thực tế đang có trên máy**, không huấn luyện lại, không thay đổi API hoặc kết quả dự đoán. Chưa kết luận mô hình tốt hay kém trước khi xem metrics.

Mô hình từ Giai đoạn 1: MLPClassifier với hai tầng ẩn (64, 32), chia dữ liệu 80/20 theo `stratify`, tiền xử lý trong Pipeline. Các thông tin này lấy từ `backend/training/train_dl.py` đã bàn giao.

## 1. Cài đặt file

Giải nén ZIP vào thư mục **cha** của `diabetes-multiagent`, ví dụ `D:\PTIT\N4-1\PTHTTM`. Chỉ thêm hai file:

- `diabetes-multiagent/backend/scripts/dl_audit_step1.py`
- `diabetes-multiagent/docs/DL_DANH_GIA_BUOC_1.md`

Không cần `pip install`, không sửa `.env` hay `models/`, không thay dữ liệu Neo4j.

## 2. Chạy audit

Tại thư mục gốc `diabetes-multiagent` trong PowerShell:

```powershell
.\.venv\Scripts\python.exe backend/scripts/dl_audit_step1.py
```

Script chỉ đọc:

- `outputs/dl_training_metrics.json`
- `config/model_manifest.json`
- `models/diabetes_mlp_v1.joblib` (**chỉ hash file**, không mở pickle/joblib)
- `data/raw/diabetes_prediction_dataset.csv` (**chỉ hash file**)

Script xuất hai file mới:

- `outputs/dl_audit_step1.md` — kết quả đọc được để đưa vào báo cáo
- `outputs/dl_audit_step1.json` — kết quả dạng máy đọc

Kết quả mong muốn: `DL STEP 1 AUDIT: PASS` hoặc `PASS_WITH_WARNINGS`. Một vài cảnh báo phản ánh giới hạn đánh giá hoặc dữ liệu mất cân bằng; cần xem xét chứ không mặc nhiên coi là lỗi.

## 3. Gửi lại những gì?

Gửi hai file `outputs/dl_training_metrics.json` và `outputs/dl_audit_step1.md` hoặc dán nội dung của chúng. Có thể gửi thêm `config/model_manifest.json` (không chứa mật khẩu).

**Không gửi** `.env`, mật khẩu Neo4j, dữ liệu cá nhân của bệnh nhân hoặc file `.joblib` không rõ nguồn.

## 4. Cách đọc Confusion Matrix

Với ma trận `[[TN, FP], [FN, TP]]`:

- TN: không mắc theo nhãn dữ liệu, dự đoán 0
- FP: nhãn 0, dự đoán 1
- FN: nhãn 1, dự đoán 0
- TP: nhãn 1, dự đoán 1

`Recall = TP/(TP+FN)` đo tỷ lệ phát hiện lớp 1; `Precision = TP/(TP+FP)` đo độ chính xác trong những dự đoán lớp 1. Do nguy cơ mất cân bằng lớp, không chỉ xem Accuracy.

`ROC-AUC` và `Average Precision` phản ánh khả năng xếp hạng; score từ MLP chưa hiệu chuẩn, **không thể coi là xác suất mắc bệnh đã được xác nhận y khoa**.

## 5. Quy tắc chuyển bước

Chỉ sau khi người dùng gửi kết quả DL-1 và xác nhận, mới chuyển sang DL-2: phân tích hiệu năng, chênh lệch lớp, giới hạn dữ liệu và đề xuất chỉnh sửa mô hình (nếu thực sự cần). Không tự động huấn luyện lại.
