# DL-K3 — CHECKLIST NGHIỆM THU

**Nguyên tắc:** DL-K3 chỉ cập nhật tài liệu, `.env.example`, `requirements.txt` (thêm matplotlib phục vụ huấn luyện/biểu đồ) và những hình minh họa; không sửa logic Backend/Frontend hay model. **Chưa chuyển bước nếu người thực hiện chưa xác nhận.**

## 1. Kiểm tra file sau khi giải nén

- [ ] `README.md` hiện mô tả TensorFlow/Keras, Neo4j, Flask, React và DL-K2 rollback.
- [ ] `.env.example` chứa `DL_MODEL_BACKEND=keras`; **`.env` hiện tại không bị ghi đè**.
- [ ] `requirements.txt` có TensorFlow 2.21 và matplotlib.
- [ ] `docs/DL_K3_DANH_GIA_DEEP_LEARNING.md` + `docs/reports/DL_K3_DANH_GIA_KERAS.docx` mở bình thường.
- [ ] Trong `docs/reports/figures/` có **4 file PNG**.

## 2. Kiểm tra mô hình và tích hợp

```powershell
python -m pip check
python -m unittest discover -s backend/tests -v
python backend/scripts/dl_k2_check.py --backend keras
python backend/scripts/dl_k2_check.py --backend sklearn
python backend/scripts/build_kg_seed.py --check
```

- [ ] Các unit tests Backend **không có FAIL/ERROR**.
- [ ] Cả hai CLI kết thúc `DL-K2 CHECK PASS`.
- [ ] `GET /api/health` hiển thị Deep Learning và Neo4j sẵn sàng.
- [ ] `POST /api/predict` → `payload.model_version = diabetes_keras_v1`.
- [ ] `POST /api/assess` → workflow hoàn tất, audit thành công và Keras model version đúng.

## 3. Kiểm thử Frontend

```powershell
cd frontend
npm ci
npm test
npm run build
npm run smoke:api
```

- [ ] Các lệnh chạy thành công.
- [ ] Giao diện hỏi đáp và phân tích dữ liệu giả lập hoạt động.

## 4. Kiểm tra GitHub

```powershell
git status --short
git diff --cached --name-only
git ls-files .env
```

- [ ] `.env` không xuất hiện trong `git ls-files`.
- [ ] Dataset tải về, `.keras`, `.joblib`, `outputs/`, SQLite, `.venv` không nằm trong commit.
- [ ] README, `.env.example`, requirements, biểu đồ PNG và báo cáo Word/Markdown được commit.

## 5. Kết luận và bước tiếp theo

- [ ] Đã mở và đọc ít nhất 4 hình, Word và Markdown.
- [ ] Không có lỗi sau thay đổi tài liệu/config.
- [ ] Người thực hiện **chủ động xác nhận** DL-K3 PASS trong cuộc trò chuyện.

**Giới hạn nghiệm thu:** các metric sử dụng kết quả huấn luyện đã cung cấp, không chạy huấn luyện lại trong DL-K3. Không dựng loss/ROC/PR curves khi thiếu lịch sử epoch/prediction scores. Bản báo cáo không có chức năng chẩn đoán.
