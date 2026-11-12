# Hệ đa Agent cho bệnh tiểu đường — TensorFlow/Keras + Neo4j + Flask + React

> Project cuối môn **Phát triển các hệ thống thông minh**. Hệ thống chỉ là **bản demo học thuật**: dự đoán nhãn của bộ dữ liệu, không phải chẩn đoán, chỉ định điều trị hoặc lời khuyên y khoa cá nhân.

## 1. Kiến trúc

- **Patient Data Agent:** kiểm tra và chuẩn hóa 8 trường đầu vào.
- **DL Prediction Agent:** TensorFlow/Keras MLP `64 → 32 → 1`, `diabetes_keras_v1`; lựa chọn thay thế `diabetes_mlp_v1` (scikit-learn).
- **Rule-Based Agent:** luật minh bạch phục vụ demo.
- **KG/RAG Agent:** truy xuất Topic/Fact/Source có nguồn HTTPS trong Neo4j; **không phải RAG sinh văn bản bằng LLM**.
- **Coordinator Agent:** điều phối kết quả các Agent.
- **Explanation Agent:** tổng hợp báo cáo có giải thích theo template.
- **Monitoring Agent:** kiểm tra luồng và ghi audit metadata vào SQLite (không lưu các trường dữ liệu sức khỏe vào audit theo thiết kế của project).
- **Frontend:** React/Vite; **Backend:** Flask REST API. RL vẫn là tùy chọn, không triển khai.

Hệ thống có hai chế độ: **hỏi đáp kiến thức** qua `/api/knowledge/query` (không cần 8 đặc trưng) và **phân tích dữ liệu mẫu** qua `/api/assess` (cần 8 đặc trưng).

## 2. Yêu cầu môi trường

- Windows 11, **Python 3.13.3 (64-bit)**, pip, PowerShell, VS Code.
- Node.js >= **20.19.0**, npm; Git.
- Neo4j AuraDB hoặc Neo4j Server, có URI, tài khoản và quyền ghi để seed Knowledge Graph.
- TensorFlow **2.21.0**, chạy CPU trên Windows native, không cần CUDA.
- Dataset công khai: xem [`data/raw/README.md`](data/raw/README.md); kiểm tra giấy phép trước khi phân phối lại.

## 3. Clone từ GitHub và cài đặt

```powershell
# Thay URL bằng repository thực tế của bạn
 git clone https://github.com/USERNAME/REPOSITORY.git
 cd REPOSITORY

# VS Code có thể tự kích hoạt .venv khi mở terminal mới
 py -3.13 -m venv .venv
 .\.venv\Scripts\Activate.ps1
 python -m pip install --upgrade pip
 python -m pip install -r requirements.txt
 python -m pip check

# Cấu hình cơ sở dữ liệu và backend
 Copy-Item .env.example .env
```

Mở `.env`, sửa **`NEO4J_URI` và `NEO4J_PASSWORD`**; giữ `DL_MODEL_BACKEND=keras` sau khi tạo đủ artifact. Không commit `.env`, mật khẩu, dataset, model hoặc audit DB.

> **Lưu ý:** File model `.keras`/`.joblib`, dataset gốc và manifest đã huấn luyện nằm trong `.gitignore`. **Clone xong chưa thể dự đoán ngay**; cần huấn luyện lại từ dataset hoặc sao chép artifact đáng tin cậy từ máy của chính bạn. Không nhận/tải model nhị phân từ nguồn không tin cậy.

## 4. Khôi phục artifacts Deep Learning (trên máy mới)

Tải CSV theo hướng dẫn [`data/raw/README.md`](data/raw/README.md), đặt đúng đường dẫn `data/raw/diabetes_prediction_dataset.csv`. Từ thư mục gốc:

```powershell
# A. scikit-learn baseline và phương án rollback
python backend/training/train_dl.py

# B. Huấn luyện TensorFlow/Keras, tự lưu Keras model + preprocessor + manifest
python backend/training/keras_dlk1.py

# C. Xác minh hai backend đều sẵn sàng
python backend/scripts/dl_k2_check.py --backend sklearn
python backend/scripts/dl_k2_check.py --backend keras
```

Huấn luyện lại có thể tạo kết quả khác do môi trường và tối ưu; **số liệu trong báo cáo là của lần huấn luyện đã được cung cấp**, không cam kết tái hiện giống từng chữ số. Nếu chạy trên **máy gốc đã có artifact**, bỏ qua hoàn toàn phần huấn luyện.

## 5. Tạo Knowledge Graph Neo4j

```powershell
# Kiểm tra DB_diabet.cypher được sinh đúng từ curated_knowledge.json
python backend/scripts/build_kg_seed.py --check

# Seed vào Neo4j được cấu hình trong .env (MERGE tránh trùng ID)
python backend/scripts/neo4j_cli.py seed
python backend/scripts/neo4j_cli.py check
```

Kho curated hiện tại có **35 Topic, 137 Fact, 29 Source**; nếu `--check` báo out of sync, chỉ dùng `--write` khi bạn chủ động sửa JSON và muốn sinh lại Cypher. Không chạy seed vào database Neo4j không thuộc quyền quản lý của bạn.

## 6. Chạy Backend và Frontend

**Terminal 1** — từ thư mục gốc, `.venv` đã kích hoạt:

```powershell
python backend/app.py
```

**Terminal 2** — cũng mở tại thư mục gốc:

```powershell
cd frontend
npm ci
npm run dev
```

Mở `http://127.0.0.1:5173`. Vite dev proxy gửi `/api/*` đến Flask `http://127.0.0.1:5000`, không cần bật CORS cho local development. Nếu PowerShell chặn `npm`, thử `npm.cmd ci` và `npm.cmd run dev`.

## 7. Kiểm thử bắt buộc

Từ **thư mục gốc** (Terminal khác khi Flask đang chạy):

```powershell
python -m unittest discover -s backend/tests -v
python backend/scripts/dl_k2_check.py --backend keras
python backend/scripts/dl_k2_check.py --backend sklearn
```

API mẫu `/predict` (đã có mẫu dữ liệu mô phỏng):

```powershell
$raw = Get-Content .\data\samples\predict_input.json -Raw -Encoding UTF8
$response = Invoke-RestMethod -Uri http://127.0.0.1:5000/api/predict `
  -Method Post -ContentType 'application/json; charset=utf-8' `
  -Body ([System.Text.Encoding]::UTF8.GetBytes($raw))
$response.status
$response.payload.model_version   # kỳ vọng diabetes_keras_v1
```

Kiểm tra full workflow:

```powershell
$raw = Get-Content .\data\samples\report_with_question.json -Raw -Encoding UTF8
$response = Invoke-RestMethod -Uri http://127.0.0.1:5000/api/assess `
  -Method Post -ContentType 'application/json; charset=utf-8' `
  -Body ([System.Text.Encoding]::UTF8.GetBytes($raw))
$response.status
$response.payload.results.dl_prediction.model_version
```

Trong thư mục `frontend/`:

```powershell
npm test
npm run build
npm run smoke:api
```

`npm run smoke:api` yêu cầu Flask và Neo4j đang chạy. Xác minh `GET /api/health` báo các thành phần sẵn sàng; kết quả API thực tế phải có `model_version=diabetes_keras_v1`.

## 8. Quay lại scikit-learn (rollback)

Trong `.env`, đổi `DL_MODEL_BACKEND=sklearn`, **khởi động lại Flask**; `/api/predict` phải trả `model_version=diabetes_mlp_v1`. Khi cần bật Keras lại, đổi thành `keras` và restart. Hệ thống **không tự động fallback** nếu model được chọn bị lỗi. Dữ liệu/mô hình được huấn luyện trên máy của bạn vẫn giữ nguyên.

## 9. Tài liệu

- [`docs/DL_K3_DANH_GIA_DEEP_LEARNING.md`](docs/DL_K3_DANH_GIA_DEEP_LEARNING.md) — báo cáo Keras, chỉ số và biểu đồ.
- [`docs/reports/DL_K3_DANH_GIA_KERAS.docx`](docs/reports/DL_K3_DANH_GIA_KERAS.docx) — bản Word để đưa vào báo cáo môn học.
- [`docs/DL_K3_HUONG_DAN_GITHUB.md`](docs/DL_K3_HUONG_DAN_GITHUB.md) — chi tiết lần đầu clone/chạy/khắc phục lỗi.
- [`docs/DL_K3_NGHIEM_THU.md`](docs/DL_K3_NGHIEM_THU.md) — checklist PASS cho DL-K3.
- [`docs/DL_K2_TICH_HOP_TENSORFLOW_KERAS.md`](docs/DL_K2_TICH_HOP_TENSORFLOW_KERAS.md) — hướng dẫn tích hợp service và rollback.

**An toàn GitHub:** `.gitignore` loại `.env`, `models/`, `outputs/`, `data/raw/`, `frontend/node_modules/`, `frontend/dist/`. Các file kiến thức `data/knowledge/*.json|*.cypher`, test, docs, source và `frontend/package-lock.json` vẫn được theo dõi. Nếu đã commit bí mật trước đó, `.gitignore` không xóa bí mật khỏi lịch sử Git; cần xử lý lịch sử và đổi credentials bị lộ.
