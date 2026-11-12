# DL-K3 — HƯỚNG DẪN CLONE, CHẠY VÀ KIỂM THỬ TỪ GITHUB

**Hệ điều hành mục tiêu:** Windows 11 · **Python:** 3.13.3 (64-bit) · **Môi trường:** `.venv` duy nhất (không tạo `.venv-keras`).  
**Phạm vi cập nhật:** tài liệu, `.env.example`, khai báo `matplotlib` trong `requirements.txt` và biểu đồ/báo cáo. **Không thay đổi DL Prediction Service, API hoặc các Agent ở DL-K2.**

## A. Trước khi push lên GitHub (máy đang phát triển)

1. Đảm bảo `.gitignore` tại root đang bỏ qua `.env`, `.env.*` (trừ `.env.example`), `.venv/`, `models/`, `outputs/`, `data/raw/`, `*.db`, `*.sqlite3`, `frontend/node_modules`, `frontend/dist`. Đừng copy credentials vào README hoặc ảnh chụp màn hình.
2. Giải nén bộ cập nhật DL-K3 vào **thư mục cha** của repo; ZIP có sẵn thư mục `diabetes-multiagent/`.
3. Kiểm tra và commit **đúng các file source/tài liệu được thay đổi**. Từ root project:

```powershell
git status --short
git check-ignore -v .env .venv/Scripts/python.exe models/keras_dlk1/diabetes_keras_v1.keras outputs/keras_dlk1/metrics.json data/raw/diabetes_prediction_dataset.csv
# Kiểm tra file theo dõi trước khi push
git add README.md .env.example requirements.txt docs/DL_K3_DANH_GIA_DEEP_LEARNING.md docs/DL_K3_HUONG_DAN_GITHUB.md docs/DL_K3_NGHIEM_THU.md docs/reports
git diff --cached --stat
git diff --cached --name-only
git commit -m "docs: finalize Keras evaluation and GitHub setup (DL-K3)"
# Nếu đã có remote origin và branch main:
git push origin main
```

`git check-ignore` chỉ hiển thị các đường dẫn thực tế có trên máy; nếu một file chưa tồn tại vẫn có thể kiểm tra pattern, nhưng không đại diện cho dữ liệu đã được commit từ trước. Kiểm tra `.env` có bị Git theo dõi từ trước hay không bằng `git ls-files .env`; nếu có, phải ngừng theo dõi và xử lý bí mật đã bị đưa vào lịch sử.

## B. Clone trên một máy Windows khác

```powershell
git clone https://github.com/USERNAME/REPOSITORY.git
cd REPOSITORY
py -3.13 --version
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python --version
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
python -c "import tensorflow as tf; print(tf.__version__)"
Copy-Item .env.example .env
```

- Thay `USERNAME/REPOSITORY` và thư mục sau `cd` bằng repository thực tế; không sử dụng URL ví dụ theo nghĩa đen.
- Nếu VS Code tự kích hoạt `(.venv)` khi mở terminal mới thì không cần `Activate.ps1` thêm lần nữa.
- Nếu PowerShell từ chối activate, có thể gọi trực tiếp `.\.venv\Scripts\python.exe` thay vì thay chính sách bảo mật PowerShell.
- `.env` được tạo cục bộ; điền Neo4j AuraDB URI/password của bạn; không chia sẻ hoặc push.

## C. Tạo model và manifest sau khi clone

Repo không chứa dataset/model do `.gitignore` (đúng mục đích an toàn, dung lượng, xuất xứ dữ liệu):

1. Download dataset theo `data/raw/README.md`, đặt `data/raw/diabetes_prediction_dataset.csv`.
2. Huấn luyện baseline scikit-learn **trước** để có đường quay lại và tạo metric đối chứng:

```powershell
python backend/training/train_dl.py
```

3. Huấn luyện TensorFlow/Keras:

```powershell
python backend/training/keras_dlk1.py
```

4. Kiểm tra 5 artifact cần thiết:

```powershell
@(
  '.\models\diabetes_mlp_v1.joblib',
  '.\config\model_manifest.json',
  '.\models\keras_dlk1\diabetes_keras_v1.keras',
  '.\models\keras_dlk1\preprocessor.joblib',
  '.\outputs\keras_dlk1\experiment_manifest.json'
) | ForEach-Object { "$_ : $(Test-Path $_)" }
python backend/scripts/dl_k2_check.py --backend sklearn
python backend/scripts/dl_k2_check.py --backend keras
```

Không sửa `experiment_manifest.json` từ trạng thái `EXPERIMENT_ONLY_NOT_INTEGRATED` thành chuỗi mới: đây là metadata do DL-K1 sinh; DL-K2 loader xác thực đúng trạng thái gốc. Artifact `.joblib` là định dạng có rủi ro khi load; chỉ dùng file do bạn tự huấn luyện hoặc tin tưởng.

Nếu máy đang phát triển đã có đầy đủ model và bạn chỉ cập nhật tài liệu DL-K3, **không train lại** và không dùng `--overwrite`.

## D. Khởi tạo Neo4j

- Tạo Neo4j AuraDB hoặc dùng Neo4j server bạn kiểm soát; sao chép connection URI, user, password vào `.env`.
- Mở `data/knowledge/README.md` để xem phạm vi dữ liệu 35 Topic / 137 Fact / 29 Source.
- Chạy từ root:

```powershell
python backend/scripts/build_kg_seed.py --check
python backend/scripts/neo4j_cli.py seed
python backend/scripts/neo4j_cli.py check
```

`seed` dùng MERGE (idempotent theo ID). Lần đầu seed yêu cầu quyền ghi/CREATE CONSTRAINT. Không ghi vào cơ sở dữ liệu dùng chung khi chưa được phép.

## E. Chạy hệ thống

**Terminal 1 (root, có `.venv`):**

```powershell
python backend/app.py
```

**Terminal 2 (root):**

```powershell
cd frontend
npm ci
npm run dev
```

Truy cập `http://127.0.0.1:5173`. Trên PowerShell, nếu `npm` bị chặn script thì dùng `npm.cmd`. Vite development proxy đã trỏ `/api` về Flask 5000; mặc định không cần CORS.

## F. Kiểm thử cuối và xác nhận Keras

```powershell
# ở thư mục root
python -m unittest discover -s backend/tests -v
python backend/scripts/dl_k2_check.py --backend keras
python backend/scripts/dl_k2_check.py --backend sklearn
python backend/scripts/build_kg_seed.py --check
```

Khi Flask chạy:

```powershell
$health = Invoke-RestMethod http://127.0.0.1:5000/api/health
$health.integrations
$raw = Get-Content .\data\samples\predict_input.json -Raw -Encoding UTF8
$r = Invoke-RestMethod -Uri http://127.0.0.1:5000/api/predict -Method Post -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes($raw))
$r.status
$r.payload.model_version
# Cần là diabetes_keras_v1
```

Kiểm tra Coordinator, KG/RAG, Rule, Explanation, Monitoring:

```powershell
$raw = Get-Content .\data\samples\report_with_question.json -Raw -Encoding UTF8
$r = Invoke-RestMethod -Uri http://127.0.0.1:5000/api/assess -Method Post -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes($raw))
$r.status
$r.payload.workflow_status
$r.payload.results.dl_prediction.model_version
$r.payload.audit_recorded
```

Kiểm tra frontend (đang đứng trong `frontend/`):

```powershell
npm test
npm run build
npm run smoke:api
```

Ngoài việc test PASS, thao tác trực tiếp trên UI cả chế độ hỏi kiến thức và phân tích dữ liệu mẫu; không đưa dữ liệu bệnh nhân thật vào demo.

## G. Rollback Keras → scikit-learn

```dotenv
DL_MODEL_BACKEND=sklearn
```

Dừng Flask bằng `Ctrl+C`, khởi động lại `python backend/app.py`, kiểm tra `/api/predict` có `model_version=diabetes_mlp_v1`. Khi bật lại `DL_MODEL_BACKEND=keras`, restart lần nữa và xác nhận version `diabetes_keras_v1`.

**Không có fallback ngầm**: nếu chọn Keras nhưng thiếu artifact, API báo không sẵn sàng/503 thay vì tự trả kết quả từ sklearn. Nếu shell PowerShell từng đặt `$env:DL_MODEL_BACKEND` thủ công, shell sẽ ưu tiên hơn `.env`; dùng `Get-Item Env:DL_MODEL_BACKEND -ErrorAction SilentlyContinue` để kiểm tra.

## H. Các lỗi thường gặp

| Vấn đề | Cách kiểm tra |
|---|---|
| Keras model `not_configured` | Đủ 3 file `.keras`, `preprocessor.joblib`, `experiment_manifest.json`; checksum đúng; TensorFlow có trong `.venv` |
| sklearn không ready | Thiếu `models/diabetes_mlp_v1.joblib` hoặc `config/model_manifest.json` |
| TensorFlow cài xong nhưng DL-K1 thiếu đồ thị | `python -m pip install -r requirements.txt` (bao gồm `matplotlib`) |
| Neo4j lỗi kết nối | Kiểm tra `.env` URI, password, kết nối mạng, AuraDB instance có online |
| `model_version` vẫn là sklearn | Sửa `.env`, bỏ biến môi trường override, restart Flask |
| `npm test` lỗi | Kiểm tra Node >=20.19, chạy `npm ci` trong frontend |
| `git push` lỗi vì remote | `git remote -v`, `git branch --show-current`; không thêm origin lần thứ hai |
| Không tái hiện chính xác metric trong báo cáo | Seed/split, versions, CPU numerical differences; bản snapshot report là từ lần chạy đã cung cấp |

## I. Lưu ý về bảo mật và tái lập

- Không commit `.env` hay file chứa mật khẩu; không đưa file dataset tải về hoặc model lớn lên repository mặc định.
- Artifact `.keras` và `.joblib` nên tự tạo từ script đã kiểm tra; không tải model lạ để chạy.
- Biểu đồ trong `docs/reports/figures` và bản metrics JSON đã tổng hợp có thể commit để trình bày; chúng không chứa raw patient features.
- Tài liệu này không thay thế log nghiệm thu thực tế trên máy người thực hiện. Kết quả chạy Runtime **chỉ được công nhận sau khi người dùng kiểm tra**.
