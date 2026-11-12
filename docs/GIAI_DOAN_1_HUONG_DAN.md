# GIAI ĐOẠN 1 — Xây dựng và tích hợp Deep Learning Prediction Agent

**Project:** Hệ đa Agent hỗ trợ ra quyết định về bệnh tiểu đường  
**Môn:** Phát triển các hệ thống thông minh (PTIT)  
**Trạng thái:** Chưa nghiệm thu; chỉ chuyển Giai đoạn 2 sau khi sinh viên gửi kết quả PASS và xác nhận.

## 1. Mục tiêu và giới hạn

Theo PDF kiến trúc giảng viên, §3 (DL Prediction Agent), §6 (message contract), §7.1 (tích hợp model thật) và §9 (Phase 1), nhánh DL cần:

1. Model đã huấn luyện với dữ liệu thật / dữ liệu công khai có nhãn, không trả số đoán giả.
2. Tiền xử lý **giống hệt** giữa train và inference; giữ thứ tự và kiểu feature.
3. Lưu model, version, schema, thông tin dataset và chỉ số đánh giá.
4. Agent nhận input đã cấu trúc và xuất thông điệp `request_id, agent, status, payload, evidence, version`.
5. Có API độc lập chỉ để thử nghiệm DL, **không phải** toàn bộ quy trình Multi-Agent.

Trong PDF, model DL được giả định đã có từ bài trước. Vì project bắt đầu từ con số 0, Giai đoạn 1 huấn luyện mới một model gọn rồi tích hợp. **Đây là điều chỉnh thực hiện, không thay đổi chức năng agent theo giảng viên.**

### Vì sao dùng MLP scikit-learn?

Dùng `MLPClassifier` với **hai tầng ẩn (64, 32), ReLU**. Đây là mạng neural truyền thẳng nhiều tầng, có quá trình huấn luyện bằng backpropagation/Adam. Dùng scikit-learn để cài trên Windows/CPU gọn hơn TensorFlow/PyTorch. Đây là **DL tabular cơ bản cho học phần** — không quảng bá nó như model tiên tiến hoặc được kiểm chứng y tế. Nếu giảng viên yêu cầu framework cụ thể TensorFlow/PyTorch, cần thay model (giao tiếp Agent vẫn giữ nguyên).

### Dataset

Bộ dữ liệu đề xuất: **Diabetes Prediction Dataset** (Kaggle):

https://www.kaggle.com/datasets/iammustafatz/diabetes-prediction-dataset

Tham khảo định dạng schema: `gender`, `age`, `hypertension`, `heart_disease`, `smoking_history`, `bmi`, `HbA1c_level`, `blood_glucose_level`, nhãn `diabetes` (0/1).

> Phạm vi sử dụng: minh họa công nghệ với dữ liệu công khai. Chất lượng/nguồn gốc dữ liệu không chứng minh tính phù hợp cho bệnh nhân thực, nhóm dân số khác hay bối cảnh lâm sàng. Không nhập dữ liệu nhận dạng cá nhân. Kiểm tra điều kiện sử dụng dữ liệu trước khi chia sẻ.

## 2. Cài code cập nhật vào project giai đoạn 0

1. **Dừng Flask** trong VS Code bằng `Ctrl+C` ở Terminal đang chạy.
2. Đóng VS Code không bắt buộc; nên sao lưu thư mục project hiện có trước khi ghi đè.
3. Tải `diabetes-multiagent-giai-doan-1-cap-nhat.zip`.
4. Giải nén ZIP **vào thư mục cha chứa `diabetes-multiagent/` đang sử dụng**, rồi cho phép **Replace/Overwrite** file trùng tên. Đây là **ZIP cập nhật**, không phải một project mới. ZIP chỉ chứa file mới và file cần sửa, **không xóa thư mục `.venv`, `.env` hoặc các tài liệu giai đoạn 0**.
   - Ví dụ: project đang ở `D:\PTIT\diabetes-multiagent\`; giải nén ZIP vào `D:\PTIT\`, **không** giải nén vào `D:\PTIT\diabetes-multiagent\` (sẽ tạo thư mục lồng nhau).
5. Mở VS Code → **File → Open Folder** → chọn folder `diabetes-multiagent` cũ.
6. Kiểm tra đã có `backend/training/train_dl.py`, `backend/agents/dl_prediction_agent.py`, `backend/services/dl_service.py`, `backend/core/features.py`.

Nếu lo ghi đè, có thể giải nén ZIP vào chỗ khác, sau đó copy **các file bên trong thư mục `diabetes-multiagent` của ZIP** sang thư mục project đang dùng, giữ nguyên cấu trúc đường dẫn.

## 3. Cài thêm thư viện cho Giai đoạn 1

Tại terminal PowerShell đặt trong project root (nơi có `requirements.txt`):

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -c "import sklearn, pandas, numpy, joblib; print('ML libraries OK'); print('sklearn:', sklearn.__version__)"
```

Không cần tạo lại `.venv`. Không cần Node.js, TensorFlow, PyTorch hoặc Neo4j cho giai đoạn 1.

## 4. Tải CSV nguồn

1. Mở trang Kaggle được ghi ở mục 1.
2. Chọn Download (Kaggle có thể yêu cầu đăng nhập), giải nén file.
3. Copy CSV đúng tên **`diabetes_prediction_dataset.csv`** vào:

```text
diabetes-multiagent/
└── data/
    └── raw/
        └── diabetes_prediction_dataset.csv
```

4. Kiểm tra với PowerShell:

```powershell
Test-Path .\data\raw\diabetes_prediction_dataset.csv
.\.venv\Scripts\python.exe -c "import pandas as pd; d=pd.read_csv('data/raw/diabetes_prediction_dataset.csv'); print(d.shape); print(d.columns.tolist()); print(d['diabetes'].value_counts())"
```

**Mong đợi:** `True`, thông thường `(100000, 9)` đối với phiên bản phổ biến, danh sách 9 cột như trên và nhãn có cả `0` lẫn `1`. Nếu số dòng khác nhưng schema hợp lệ, vẫn có thể chạy. Không có CSV trong file ZIP; đừng lấy tập dữ liệu tổng hợp từ unit test để đánh giá mô hình.

## 5. Huấn luyện và lưu mô hình thật

Dùng PowerShell tại project root:

```powershell
.\.venv\Scripts\python.exe backend/training/train_dl.py
```

Chương trình sẽ:
- Kiểm tra schema đầu vào, nhãn, lỗi thiếu dữ liệu, trùng toàn bộ dòng.
- Tách **80% train / 20% test với stratify**, dùng early stopping nội bộ trên train.
- Học pipeline `StandardScaler` cho numeric → `OneHotEncoder` categorical → **MLP (64, 32)**.
- Đánh giá trên tập test và lưu file (đều được `.gitignore` khi phù hợp):

```text
models/diabetes_mlp_v1.joblib           # Model + preprocessing trong cùng Pipeline
config/model_manifest.json              # Version, feature order, SHA-256, metadata
outputs/dl_training_metrics.json        # Accuracy, precision, recall, F1, ROC-AUC, AP, confusion matrix
```

Kết thúc thành công có dòng:

```text
TRAINING COMPLETE (educational prototype; NOT a medical diagnostic model)
Model: models/diabetes_mlp_v1.joblib
Manifest: config/model_manifest.json
Metrics: outputs/dl_training_metrics.json
```

**Lưu ý:** các chỉ số thực tế là kết quả máy bạn tính từ dataset, **không có một con số accuracy cố định được hứa trước**. Accuracy cao một mình không đủ; xem `recall_positive`, `precision_positive`, `confusion_matrix_0_1` và ghi nhận mất cân bằng nhãn. Score từ `predict_proba` là đầu ra mô hình chưa hiệu chuẩn, **không nên diễn đạt là xác suất bệnh của người thật**.

## 6. Kiểm thử unit / training / agent

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
```

**Mong đợi:** toàn bộ test PASS (bộ 6 test giai đoạn 0 đã được cập nhật để phản ánh phase mới, đồng thời có thêm test cho validation + training + inference). Unit test sinh **dữ liệu tổng hợp tạm thời** để kiểm tra rằng model thực sự được fit, lưu, nạp và inference. Đây chỉ là thử mã nguồn, **không phải** đánh giá chất lượng y tế.

Để kiểm tra ba file kết quả:

```powershell
Test-Path .\models\diabetes_mlp_v1.joblib
Test-Path .\config\model_manifest.json
Test-Path .\outputs\dl_training_metrics.json
Get-Content .\outputs\dl_training_metrics.json
```

Cả ba `Test-Path` phải trả `True` sau khi huấn luyện. Khi chưa có CSV/training, unit test vẫn có thể PASS nhưng API Health vẫn phải trả `deep_learning: not_configured` (đó là hành vi đúng).

## 7. Chạy Flask và kiểm tra API thật

**Terminal 1:**

```powershell
.\.venv\Scripts\python.exe backend/app.py
```

**Terminal 2:**

```powershell
Invoke-RestMethod http://127.0.0.1:5000/api/health | ConvertTo-Json -Depth 5
Invoke-RestMethod http://127.0.0.1:5000/api/agents/status | ConvertTo-Json -Depth 5
```

**Mong đợi:**
- `phase`: `1-deep-learning`.
- `integrations.deep_learning`: `ready` **chỉ sau khi đã có model, manifest và SHA đúng**.
- `integrations.neo4j`: `not_configured`.
- `dl_prediction`: `ready`; các agent khác vẫn `not_implemented`.
- `count`: 8 (7 core + 1 RL optional).

**Gọi API dự đoán độc lập** với bản ghi hoàn toàn minh họa ở `data/samples/predict_input.json`:

```powershell
$body = Get-Content .\data\samples\predict_input.json -Raw
Invoke-RestMethod -Uri http://127.0.0.1:5000/api/predict -Method Post -ContentType 'application/json' -Body $body | ConvertTo-Json -Depth 8
```

Mong đợi **HTTP 200**, `status: ok`, `agent: dl_prediction`, `version: diabetes_mlp_v1`, `payload.prediction` là **0 hoặc 1**, `payload.model_score_class_1` trong khoảng **0..1**, `score_is_calibrated: false`, `evidence: []`. **Không có kết quả nhãn/score cố định**, vì phụ thuộc quá trình train.

**Kiểm tra đầu vào sai (HTTP 400):**

```powershell
try {
  Invoke-RestMethod -Uri http://127.0.0.1:5000/api/predict -Method Post -ContentType 'application/json' -Body '{"features":{"age":30}}'
} catch {
  Write-Host "Expected HTTP 400:" $_.Exception.Message
}
```

**Kiểm tra workflow chưa triển khai (HTTP 501):**

```powershell
try {
  Invoke-RestMethod -Uri http://127.0.0.1:5000/api/assess -Method Post -ContentType 'application/json' -Body '{}'
} catch {
  Write-Host "Expected HTTP 501:" $_.Exception.Message
}
```

`/api/predict` chỉ phục vụ thử nghiệm **DL Prediction Agent**. `/api/assess` chưa thể cho kết luận MAS vì chưa làm Patient Data Agent, Rule-Based Agent, Neo4j KG/RAG, Coordinator và Explanation Agent. Việc để 501 là **đúng**.

## 8. Cấu trúc triển khai Giai đoạn 1

```text
diabetes-multiagent/
├── backend/
│   ├── agents/dl_prediction_agent.py      # Agent thật trả AgentMessage
│   ├── services/dl_service.py             # Kiểm tra manifest/hash, load model, inference
│   ├── core/features.py                   # Schema feature (validation tối thiểu)
│   ├── training/train_dl.py               # Pipeline huấn luyện và metrics
│   ├── api/routes.py                      # /predict; /assess vẫn 501
│   └── tests/test_dl_phase1.py            # Tự test train/service/agent
├── data/raw/diabetes_prediction_dataset.csv    # Bạn tự tải, không có trong ZIP
├── models/diabetes_mlp_v1.joblib                # Sinh sau khi train
├── config/model_manifest.json                  # Sinh sau khi train
└── outputs/dl_training_metrics.json            # Sinh sau khi train
```

`backend/core/features.py` mới kiểm tra **hình dạng input** để inference không vỡ. **Patient Data Agent vẫn chưa được triển khai** (dự kiến Giai đoạn 3).

## 9. Các kết quả cần gửi để nghiệm thu

Chỉ xác nhận PASS khi đã làm đủ:

- [ ] Đã chép đúng các file cập nhật vào **project giai đoạn 0 đang dùng**.
- [ ] Đã cài dependencies ML trong `.venv` cũ.
- [ ] Có CSV dataset công khai đúng vị trí và schema.
- [ ] Chạy train thành công, tạo đủ `joblib`, `manifest.json`, `metrics.json`.
- [ ] Chạy tất cả unit tests PASS.
- [ ] Health báo `deep_learning: ready`, Neo4j vẫn `not_configured`.
- [ ] `/api/predict` cho response `status: ok`, đúng contract; input sai trả HTTP 400.
- [ ] `/api/assess` vẫn HTTP 501.

**Gửi tôi:** (1) kết quả terminal của `train_dl.py`, (2) dòng cuối unit tests, (3) JSON trả về từ `/api/health` và `/api/predict`, (4) nội dung `outputs/dl_training_metrics.json`. Không gửi dữ liệu cá nhân hoặc mật khẩu. **Tôi sẽ kiểm tra và chỉ khi bạn xác nhận mới chuyển sang Giai đoạn 2: Neo4j Knowledge Graph + KG/RAG Agent.**

## 10. Gỡ lỗi nhanh

| Hiện tượng | Cách xử lý |
|---|---|
| `No module named pandas/sklearn` | Chạy lại `...python.exe -m pip install -r requirements.txt` bằng đúng `.venv` cũ. |
| `Missing dataset` | Đặt đúng tên `data/raw/diabetes_prediction_dataset.csv`, chạy từ project root. |
| `Dataset missing columns` | Xem `print(d.columns.tolist())`; kiểm tra đúng phiên bản CSV (không đổi tên tùy ý). |
| `model_missing` trên `/api/agents/status` | Chưa train hoặc chưa có manifest hợp lệ; chạy train và **khởi động lại Flask**. |
| Model `SHA-256 does not match` | Artifact và manifest không khớp; chạy huấn luyện lại; không dùng file `.joblib` không rõ nguồn. |
| HTTP 400 `/api/predict` | Thiếu field, sai kiểu, category không trùng dataset, có field thừa. |
| `Address already in use` | Tắt Flask cũ (`Ctrl+C`) trước khi chạy phiên bản mới. |

**Không sử dụng mô hình này để chẩn đoán, kê đơn, điều chỉnh thuốc hoặc ra quyết định chăm sóc cho người thực.**
