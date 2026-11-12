# DL-K2 — Tích hợp TensorFlow/Keras vào Backend Multi-Agent (Windows 11, Python 3.13)

**Phạm vi:** chỉ đổi backend suy luận của Deep Learning Prediction Agent. Không huấn luyện lại và **không** sửa model `.keras`, preprocessor `.joblib` hay dataset. Deep Learning và KG/RAG trong project phục vụ **thực nghiệm học tập**, không phải chẩn đoán.

## 1. Mục tiêu và thiết kế

- Mô hình **TensorFlow/Keras** từ DL-K1: `models/keras_dlk1/diabetes_keras_v1.keras`.
- Preprocessing Keras tương ứng: `models/keras_dlk1/preprocessor.joblib`.
- Manifest DL-K1 (giữ nguyên trạng thái `EXPERIMENT_ONLY_NOT_INTEGRATED`): `outputs/keras_dlk1/experiment_manifest.json`.
- Mô hình **scikit-learn cũ**: `models/diabetes_mlp_v1.joblib` và `config/model_manifest.json` (giữ nguyên).
- Chọn bằng `.env`: `DL_MODEL_BACKEND=keras` hoặc `DL_MODEL_BACKEND=sklearn`.
- Khi backend đang chọn bị thiếu, sai SHA256 hoặc lỗi inference: báo lỗi `model_unavailable`/HTTP 503, **không lặng lẽ chuyển backend**.
- Backend nhận đúng 8 trường của `core.features.FEATURE_NAMES`, sử dụng đúng preprocessor của Keras, Sigmoid đầu ra, ngưỡng 0.5. Output giữ nguyên schema:

```json
{
  "prediction": 1,
  "model_score_class_1": 0.68,
  "score_is_calibrated": false,
  "output_kind": "dataset_label_classification",
  "model_version": "diabetes_keras_v1",
  "input_feature_names": [
    "gender", "age", "hypertension", "heart_disease", "smoking_history",
    "bmi", "HbA1c_level", "blood_glucose_level"
  ]
}
```

> Số `0.68` chỉ minh họa định dạng, **không** phải kết quả thực tế từ model trên máy bạn. Điểm sigmoid **chưa được hiệu chuẩn** và **không phải** xác suất mắc bệnh được kiểm chứng.

**Phạm vi thay đổi file:** `backend/services/dl_service.py`, thêm `backend/services/keras_dl_service.py`, `backend/scripts/dl_k2_check.py`, `backend/tests/test_keras_dlk2.py`, cấu hình mẫu `.env.example`, và `requirements.txt` / `requirements-keras.txt`. Không thay `backend/api/routes.py`, các Agent khác, frontend, Neo4j, SQLite, hay biểu đồ đã tạo.

## 2. Backup trước khi áp dụng

Trong VS Code, mở Terminal tại thư mục gốc `D:\PTIT\N4-1\PTHTTM\diabetes-multiagent`.

```powershell
# Nếu project đang dùng Git, lưu trạng thái và commit các thay đổi mà bạn muốn giữ.
git status
# Lưu cấu hình, service và manifest cũ ở máy cá nhân (KHÔNG commit .env).
Copy-Item .env .env.before-dlk2.bak
Copy-Item backend/services/dl_service.py backend/services/dl_service.before-dlk2.bak.py
```

**Quan trọng:** File `.env.before-dlk2.bak` chứa mật khẩu Neo4j, phải giữ riêng tư, **không push lên GitHub**. Sau khi nghiệm thu, xóa các bản `.bak` hoặc chuyển ra ngoài repo; xem `git status` trước khi push. Không chia sẻ các file này trong chat.

Dừng Flask bằng `Ctrl+C`. Giải nén `diabetes-multiagent-DL-K2-TICH-HOP-KERAS.zip` vào **thư mục cha** `D:\PTIT\N4-1\PTHTTM` và cho phép ghi đè. ZIP đã có thư mục `diabetes-multiagent/`.

**Không thay đổi hoặc xóa:** `.env`, `models/diabetes_mlp_v1.joblib`, `models/keras_dlk1/`, `config/model_manifest.json`, `outputs/keras_dlk1/`, `.venv`.

## 3. Kiểm tra đầy đủ artifact từ DL-K1

```powershell
Test-Path .\models\keras_dlk1\diabetes_keras_v1.keras
Test-Path .\models\keras_dlk1\preprocessor.joblib
Test-Path .\outputs\keras_dlk1\experiment_manifest.json
Test-Path .\models\diabetes_mlp_v1.joblib
Test-Path .\config\model_manifest.json
```

**Cả năm dòng phải là `True`.** Các model không có trong ZIP/GitHub vì `.gitignore`; chúng được tạo sau huấn luyện trên máy bạn.

Nếu chưa cài TensorFlow trong `.venv` thì cài; nếu bạn đã cài để train DL-K1 thì không cần cài lại. Chạy:

```powershell
python -m pip install -r requirements.txt
python -m pip check
python -c "import tensorflow as tf; print(tf.__version__)"
```

TensorFlow 2.21.0 hỗ trợ CPU trên Windows 64-bit với Python 3.13. Không cần GPU. Các bản khác có thể có ràng buộc thư viện khác nhau.

## 4. Kiểm thử hai backend riêng biệt — CHƯA kích hoạt chính thức

Chạy:

```powershell
python -m unittest discover -s backend/tests -p test_keras_dlk2.py -v
python backend/scripts/dl_k2_check.py --backend keras
python backend/scripts/dl_k2_check.py --backend sklearn
```

Mong đợi:

- Unit tests mới **14 bài** (có 1 bài `live` dùng model Keras thật khi artifact hiện diện). Không chấp nhận ERROR/FAIL.
- Cả hai CLI đều kết thúc bằng `DL-K2 CHECK PASS`.
- Keras trả `model_version: diabetes_keras_v1`, sklearn trả `model_version: diabetes_mlp_v1`.
- `prediction` có thể khác nhau giữa hai mô hình, đó không phải lỗi; `model_score_class_1` phải nằm trong `[0,1]` và chưa hiệu chuẩn.

**Lưu ý:** lệnh CLI `--backend keras` chỉ chọn cho một lần chạy, **không** đổi `.env` hoặc model đang dùng bởi Flask.

## 5. Bật Keras cho Flask

Mở `.env` hiện tại và **thêm** dòng này (hoặc sửa nếu đã có):

```dotenv
DL_MODEL_BACKEND=keras
```

`MODEL_MANIFEST_PATH=config/model_manifest.json` **cứ giữ nguyên** cho trường hợp chuyển lại scikit-learn. File `.env.example` chỉ là mẫu; **không ghi đè `.env`** bằng file mẫu.

Nếu trước đó bạn có biến `$env:DL_MODEL_BACKEND` trong PowerShell, nó sẽ được ưu tiên hơn `.env`. Kiểm tra và bỏ biến này trong Terminal hiện tại nếu cần:

```powershell
Get-Item Env:DL_MODEL_BACKEND -ErrorAction SilentlyContinue
Remove-Item Env:DL_MODEL_BACKEND -ErrorAction SilentlyContinue
```

Dừng Flask đang chạy và khởi động lại để áp dụng chế độ Keras:

```powershell
python backend/app.py
```

## 6. Kiểm tra API dùng **đúng Keras** (không chỉ xem health)

Mở Terminal khác tại thư mục gốc:

```powershell
$health = Invoke-RestMethod http://127.0.0.1:5000/api/health
$health.integrations.deep_learning

$raw = Get-Content .\data\samples\predict_input.json -Raw -Encoding UTF8
$answer = Invoke-RestMethod `
  -Uri http://127.0.0.1:5000/api/predict `
  -Method Post `
  -ContentType 'application/json; charset=utf-8' `
  -Body ([System.Text.Encoding]::UTF8.GetBytes($raw))

$answer.status
$answer.payload.model_version
$answer.payload.model_score_class_1
$answer.payload.score_is_calibrated
```

Kỳ vọng:

```text
ready
ok
diabetes_keras_v1
<điểm số thực tế trong [0,1]>
False
```

Nếu `/health` trả `ready` mà `model_version` vẫn là `diabetes_mlp_v1`, Flask đang chạy bằng chế độ sklearn (hoặc chưa khởi động lại). Kiểm tra `.env`, biến môi trường và tiến trình Flask cũ.

## 7. Kiểm thử hồi quy toàn hệ thống

```powershell
python -m unittest discover -s backend/tests -v
```

Kết quả cuối cần là `OK` (không có `FAIL` / `ERROR`). Số test có thể khác nhau tùy phiên bản project. Bản phát hành này bổ sung 14 test mới so với mã DL-K1.

Kiểm tra luồng Coordinator → Rule → KG/RAG → Explanation → Monitoring:

```powershell
$raw = Get-Content .\data\samples\report_with_question.json -Raw -Encoding UTF8
$result = Invoke-RestMethod `
  -Uri http://127.0.0.1:5000/api/assess `
  -Method Post `
  -ContentType 'application/json; charset=utf-8' `
  -Body ([System.Text.Encoding]::UTF8.GetBytes($raw))

$result.status
$result.payload.workflow_status
$result.payload.steps | Format-Table agent,status,version,duration_ms
$result.payload.results.dl_prediction.model_version
$result.payload.audit_recorded
```

Kỳ vọng `status: ok`, `workflow_status: completed`, DL `model_version: diabetes_keras_v1`, `audit_recorded: True`, danh sách 6 Agent đúng thứ tự, có `kg_rag` và `explanation`. Nếu endpoint trả 503, kiểm tra Neo4j hoặc SQLite Audit thay vì tự coi là PASS.

Frontend React (mở Terminal trong `frontend/`):

```powershell
cd frontend
npm test
npm run build
npm run smoke:api
```

Chạy `smoke:api` khi Backend và Neo4j đã hoạt động. Trên giao diện, thử **Phân tích dữ liệu** và **Hỏi đáp kiến thức**. Giao diện phân tích phải hiển thị `diabetes_keras_v1` trong phần kết quả mô hình, còn chế độ hỏi đáp vẫn truy vấn Neo4j như cũ.

## 8. Quay về scikit-learn trong vài thao tác

Nếu Keras bị lỗi, mở `.env` và đổi:

```dotenv
DL_MODEL_BACKEND=sklearn
```

Khởi động lại Flask:

```powershell
# Ctrl+C trong terminal đang chạy Flask
python backend/app.py
```

Kiểm tra:

```powershell
python backend/scripts/dl_k2_check.py --backend sklearn
```

Gọi `/api/predict` và xác nhận `model_version: diabetes_mlp_v1`. Không cần sửa source code, không cần train lại, không cần xóa `.keras` hay uninstall TensorFlow. Khi muốn bật lại Keras, đổi thành `DL_MODEL_BACKEND=keras` và restart.

**Thiết kế không tự động fallback:** Nếu chọn Keras mà Keras lỗi, API trả `model_unavailable`/503. Cách này tránh báo cáo dùng sai model mà người sử dụng không biết.

## 9. Các lỗi thường gặp

| Hiện tượng | Nguyên nhân cần kiểm tra |
|---|---|
| `deep_learning: not_configured` | Thiếu `.keras`, `.joblib`, manifest, hash không khớp, hoặc thiếu TensorFlow |
| `model_unavailable` với Keras | File artifact bị thay đổi, lỗi nạp model/preprocessor, mismatch input dimension |
| `model_version` vẫn là sklearn | Chưa thêm `.env`, chưa restart Flask hoặc shell đang override `DL_MODEL_BACKEND` |
| Import TensorFlow chậm / log oneDNN | Thông thường ở lượt tải model đầu tiên trên Windows CPU |
| Backend tests cũ báo lỗi | Chạy `python -m pip check`, kiểm tra versions, tạm rollback `DL_MODEL_BACKEND=sklearn` |
| Kaggle CSV chưa có | Không cần CSV cho **inference DL-K2**; chỉ cần artifacts DL-K1 đã huấn luyện |
| Mở zip vào nhầm vị trí | Kiểm tra `backend/services/keras_dl_service.py` tồn tại trong thư mục project hiện tại |

## 10. Điều kiện nghiệm thu DL-K2

1. 14 test DL-K2 chạy không `FAIL/ERROR`, bài kiểm thử live không bị skip trên máy có artifacts.
2. CLI của Keras và sklearn đều `DL-K2 CHECK PASS`.
3. API `/predict` trả `model_version = diabetes_keras_v1` sau khi bật cấu hình.
4. `/api/assess` trả báo cáo thành công, có kết quả Rule-Based, KG/RAG, Explanation, Audit.
5. Toàn bộ Backend tests và Frontend tests/build/smoke đều đạt.
6. Rollback về sklearn thành công, sau đó bật lại Keras thành công.

**Khi tất cả PASS**, gửi: (a) dòng tổng kết unit tests, (b) kết quả hai CLI, (c) `/health`, (d) `model_version` của `/predict` và `/assess`, (e) kết quả rollback. Không gửi `.env`, dữ liệu bệnh nhân hay model nhị phân.

**Dừng tại DL-K2.** Không chuyển DL-K3/tài liệu cuối môn trước khi người dùng xác nhận.
