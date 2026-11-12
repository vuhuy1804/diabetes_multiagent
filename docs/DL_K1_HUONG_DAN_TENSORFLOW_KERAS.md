# DL-K1 — Huấn luyện Deep Learning bằng TensorFlow/Keras độc lập

**Project:** Hệ Multi-Agent hỗ trợ ra quyết định về bệnh tiểu đường  
**Phạm vi:** Bước DL-K1. **Không tích hợp Keras vào Flask ở bước này.**

## 1. Mục tiêu

- Dùng **TensorFlow 2.21 / tf.keras** để huấn luyện một mạng Dense với hai tầng ẩn **64 và 32 neuron**.
- Dùng cùng bộ CSV và **cùng cách chia outer train/test (random_state=42, stratify, 80/20)** như model scikit-learn MLP cũ.
- Có tập **validation riêng** nằm bên trong 80% train để dùng EarlyStopping. Bộ tiền xử lý chỉ `fit` trên phần train con; không fit trên validation hoặc test.
- Giữ nguyên dữ liệu đầu vào 8 trường và nhãn `diabetes` 0/1; giữ nguyên ngưỡng dự đoán kỹ thuật 0.5 để so sánh.
- Tạo metrics + confusion matrix + history thật; báo cáo so sánh trên tập test riêng.
- **Không sửa** `backend/services/dl_service.py`, `backend/agents/dl_prediction_agent.py`, `config/model_manifest.json`, `models/diabetes_mlp_v1.joblib` hoặc các API hiện tại.

> Mô hình chỉ nhằm trình diễn học thuật. `diabetes` là nhãn của dataset, không phải chẩn đoán; đầu ra sigmoid không phải xác suất lâm sàng đã hiệu chỉnh.

## 2. Các file được thêm

```text
diabetes-multiagent/
├── .gitignore                           # thay phiên bản cũ, không commit model/dataset
├── requirements-keras.txt               # thư viện CHỈ cho môi trường riêng
├── backend/
│   ├── training/
│   │   ├── keras_dlk1.py                # huấn luyện thật + đánh giá + báo cáo
│   │   └── keras_smoke_dlk1.py          # smoke test trên dữ liệu tổng hợp, KHÔNG dùng báo cáo
│   └── tests/
│       └── test_keras_dlk1.py           # 8 test không cần TensorFlow
└── docs/
    └── DL_K1_HUONG_DAN_TENSORFLOW_KERAS.md
```

**Kết quả chỉ xuất hiện sau khi bạn train thành công:**

```text
models/keras_dlk1/diabetes_keras_v1.keras
models/keras_dlk1/preprocessor.joblib
outputs/keras_dlk1/metrics.json
outputs/keras_dlk1/experiment_manifest.json
outputs/keras_dlk1/training_history.csv
outputs/keras_dlk1/comparison_report.md
outputs/keras_dlk1/comparison_metrics.png
outputs/keras_dlk1/keras_confusion_matrix.png
outputs/keras_dlk1/keras_training_loss.png
```

Toàn bộ nằm trong `models/keras_dlk1/` hoặc `outputs/keras_dlk1/`, **không đổi model Flask đang dùng**.

## 3. Cài đặt Windows 11 trong VS Code

### Bước A — cập nhật file

1. Sao lưu project/commit code đang chạy tốt.
2. Giải nén ZIP vào **`D:\PTIT\N4-1\PTHTTM`** (thư mục cha chứa `diabetes-multiagent`).
3. Kiểm tra các file trên đã xuất hiện bên trong project; không giải nén lồng thêm `diabetes-multiagent/diabetes-multiagent`.

### Bước B — kiểm tra Python

Tại thư mục gốc project:

```powershell
py -3.13 --version
```

Nếu máy không có 3.13, dùng `py -3.11 --version` hoặc `py -3.12 --version` rồi thay lệnh dưới đây tương ứng. TensorFlow 2.21 cung cấp gói Windows CPU cho Python 3.10–3.13, 64-bit.

### Bước C — tạo môi trường **riêng**

```powershell
py -3.13 -m venv .venv-keras
.\.venv-keras\Scripts\python.exe -m pip install --upgrade pip
.\.venv-keras\Scripts\python.exe -m pip install -r requirements-keras.txt
```

Môi trường này tách hoàn toàn `.venv` của Flask. Nếu gặp lỗi thiếu Microsoft Visual C++ runtime, kiểm tra hướng dẫn cài đặt chính thức của TensorFlow.

### Bước D — xác minh TensorFlow/Keras

```powershell
.\.venv-keras\Scripts\python.exe -c "import tensorflow as tf; print('TensorFlow', tf.__version__); print('Keras', tf.keras.__version__)"
```

Không cần GPU; TensorFlow native Windows mới chạy CPU. Không cần cài CUDA.

## 4. Chạy kiểm thử trước khi huấn luyện thật

**Kiểm thử mã nguồn, không cần TensorFlow:**

```powershell
.\.venv-keras\Scripts\python.exe -m unittest discover -s backend/tests -p test_keras_dlk1.py -v
```

Kỳ vọng `Ran 8 tests ... OK`.

**Smoke TensorFlow trên dữ liệu tổng hợp:**

```powershell
.\.venv-keras\Scripts\python.exe backend/training/keras_smoke_dlk1.py
```

Kỳ vọng có dòng `DL-K1 SMOKE PASS — synthetic dataset ONLY`. Smoke tạo riêng `models/keras_dlk1_smoke/` và `outputs/keras_dlk1_smoke/`. **Các chỉ số smoke là giả lập, không được dùng trong báo cáo.**

## 5. Huấn luyện thật với dataset cũ

Đảm bảo file sau vẫn tồn tại:

```text
data/raw/diabetes_prediction_dataset.csv
```

Chạy:

```powershell
.\.venv-keras\Scripts\python.exe backend/training/keras_dlk1.py
```

Mặc định `epochs=80`, `batch_size=256`, Adam 0.001, EarlyStopping trên `val_loss` với `patience=8`. Có thể đổi số epoch tối đa (nhưng không dùng kết quả test để tinh chỉnh):

```powershell
.\.venv-keras\Scripts\python.exe backend/training/keras_dlk1.py --epochs 60
```

Nếu muốn **chạy lại** cùng thư mục thí nghiệm, phải chủ động thêm `--overwrite` (chỉ ghi đè output Keras, không đụng model đang chạy):

```powershell
.\.venv-keras\Scripts\python.exe backend/training/keras_dlk1.py --overwrite
```

Đầu ra cuối của bước này sẽ in `DL-K1 TRAIN COMPLETE — EXPERIMENT ONLY, NOT IN FLASK` và đường dẫn tới 9 artifact/báo cáo.

**Giữ nguyên tập test**: Dataset được kiểm tra SHA256 với manifest cũ. Nếu CSV khác bản từng dùng để train scikit-learn thì chương trình sẽ dừng, vì so sánh không còn công bằng.

## 6. Đọc kết quả và so sánh

```powershell
Get-Content .\outputs\keras_dlk1\metrics.json -Raw -Encoding UTF8
Get-Content .\outputs\keras_dlk1\comparison_report.md -Raw -Encoding UTF8
```

Có ba biểu đồ PNG: chỉ số Keras vs sklearn, Confusion Matrix, lịch sử loss train/validation. Đường ROC/PR không được dựng từ số liệu tổng hợp; phải có score từng mẫu mới tạo chính xác, nên ở DL-K1 chỉ biểu diễn các giá trị chỉ số.

**Baseline scikit-learn đã báo cáo trước đó:** Accuracy 0.97088, Precision lớp 1 0.98382, Recall lớp 1 0.68101, F1 0.80488, ROC-AUC 0.97420, Average Precision 0.87324. Code đọc **thực tế** từ `outputs/dl_training_metrics.json`; không điền cứng các số này vào báo cáo tạo tự động.

Nếu Keras có recall tốt hơn nhưng precision thấp hơn, hãy ghi nhận sự đánh đổi. Không được thử nhiều ngưỡng trên tập test rồi chọn ngưỡng cho kết quả cao nhất để trình bày.

## 7. Xác nhận không ảnh hưởng Backend hiện tại

Dùng lại môi trường `.venv` cũ:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
```

Mã test DL-K1 **không import TensorFlow khi chạy test**, nên vẫn chạy được cùng bộ kiểm thử Backend cũ. Trong bản project P1 trước đó, tổng dự kiến 264 test; sau khi thêm 8 test mới sẽ là khoảng 272 (nếu bạn không tự thêm test).

Có thể giữ Flask/Frontend đang chạy và gọi `/api/health`, `/api/predict`. Ở DL-K1 chúng **vẫn phải trả model scikit-learn cũ**, chưa trả `diabetes_keras_v1`. Nếu thấy Keras trong `/api/predict` ở giai đoạn này, tức là đã thay nhầm manifest/service.

## 8. Tiêu chí PASS và kết quả cần gửi

- [ ] `.gitignore` đã chặn mật khẩu, dataset, model và SQLite; `git status` an toàn.
- [ ] TensorFlow/Keras import thành công trong `.venv-keras`.
- [ ] 8/8 unit tests DL-K1 PASS.
- [ ] Smoke TensorFlow in `DL-K1 SMOKE PASS`.
- [ ] Dataset thật train được, tạo đủ artifact `.keras`, preprocessor, metrics, manifest, báo cáo và ba biểu đồ.
- [ ] `comparison_report.md` ghi rõ hai mô hình và ma trận nhầm lẫn của Keras.
- [ ] Các test Backend cũ PASS; `/api/predict` vẫn dùng model sklearn.

**Gửi về:** (1) phần cuối log train; (2) `outputs/keras_dlk1/metrics.json`; (3) `outputs/keras_dlk1/comparison_report.md`; (4) kết quả 8 tests, smoke và Backend regression. Không gửi dataset gốc hoặc `.env`.

**Dừng ở DL-K1.** Chỉ khi bạn xác nhận PASS mới chuyển DL-K2: cập nhật DL Prediction Service dùng Keras với hợp đồng đầu ra cũ.

## Nguồn kỹ thuật

- TensorFlow official Windows/Python support: https://www.tensorflow.org/install/pip
- Keras Sequential model: https://keras.io/guides/sequential_model/
- scikit-learn train_test_split: https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.train_test_split.html
