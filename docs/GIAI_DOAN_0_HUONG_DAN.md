# HƯỚNG DẪN GIAI ĐOẠN 0 — Khởi tạo project từ đầu

**Mục tiêu:** cài được backend Flask đơn giản, kiểm tra chính xác mã nguồn và trạng thái 8 agent (7 lõi + RL tùy chọn). Chưa xây model, không cài Neo4j, chưa làm frontend.

## Bước 1: Giải nén và mở trong VS Code

1. Tải `diabetes-multiagent-phase0.zip`.
2. Giải nén để có **một** thư mục `diabetes-multiagent`.
3. Mở VS Code → **File → Open Folder** → chọn chính thư mục `diabetes-multiagent` (trong đó nhìn thấy `requirements.txt`, `backend`, `docs`).
4. Vào **Terminal → New Terminal**, chọn PowerShell.

> Nếu thư mục có dạng `...\diabetes-multiagent\diabetes-multiagent\`, hãy mở thư mục **bên trong** có `requirements.txt`.

## Bước 2: Kiểm tra Python

Trong terminal ở thư mục project:

```powershell
py -3.11 --version
```

Kết quả mong đợi: `Python 3.11.x`. Python 3.11 khuyến nghị vì dễ tích hợp các thư viện ML sau này. Nếu lệnh này báo *No suitable Python runtime*, cần cài Python 3.11 trước; mở VS Code/terminal lại. (Có thể dùng Python 3.12 nếu chủ động kiểm tra được tương thích của framework DL giai đoạn 1.)

## Bước 3: Tạo môi trường ảo

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe --version
```

Kết quả mong đợi: `Python 3.11.x`. Các lệnh dưới đây **không yêu cầu** `Activate.ps1`, do đó tránh được lỗi PowerShell Execution Policy.

## Bước 4: Cài đúng dependencies của giai đoạn 0

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

> Nếu `Copy-Item` báo `.env` đã tồn tại, không cần ghi đè. `.env` chỉ chứa cấu hình cục bộ và được `.gitignore` bỏ qua.

Bộ cài giai đoạn này có Flask + python-dotenv. **Chưa** cài torch, tensorflow, neo4j, Ollama, ChromaDB hay NodeJS — sẽ cài theo nhu cầu từng giai đoạn, không cài thừa.

## Bước 5: Chạy unit tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
```

Mong đợi: **6 tests**, toàn bộ `ok`, cuối cùng `Ran 6 tests ... OK`. Bài kiểm thử xác nhận:

- Endpoint health 200.
- Không báo sai rằng DL/Neo4j đã được kết nối.
- Registry có đúng 7 agent cơ bản, 1 RL tùy chọn; tất cả chưa implement.
- Endpoint `/api/assess` trả HTTP 501 (chưa triển khai).
- Hợp đồng `AgentMessage` có các trường cấu trúc rõ ràng.
- AgentMessage không chia sẻ mutable defaults.

## Bước 6: Chạy backend

Mở **Terminal 1** ở project root:

```powershell
.\.venv\Scripts\python.exe backend/app.py
```

Mong đợi có dòng `Running on http://127.0.0.1:5000`. **Giữ terminal này đang chạy** để kiểm thử HTTP. Nếu port 5000 bị chiếm, chỉnh `FLASK_PORT=5001` trong `.env` và dùng port 5001 ở bước sau.

## Bước 7: Gọi API bằng PowerShell

Mở **Terminal 2** từ cùng thư mục:

```powershell
Invoke-RestMethod http://127.0.0.1:5000/api/health | ConvertTo-Json -Depth 5
```

Phải thấy `"status": "ok"`, `"phase": "0-bootstrap"`, `"deep_learning": "not_configured"` và `"neo4j": "not_configured"`.

Tiếp theo:

```powershell
Invoke-RestMethod http://127.0.0.1:5000/api/agents/status | ConvertTo-Json -Depth 7
```

Phải thấy `count: 8`, các agent trong danh sách và mỗi agent `status: not_implemented`. `rl` có `optional: true`.

Có thể mở trực tiếp trên trình duyệt:

- `http://127.0.0.1:5000/api/health`
- `http://127.0.0.1:5000/api/agents/status`

## Bước 8: Kiểm kê tài nguyên

Mở file `docs/model_and_data.md`. Vì đây là project khởi tạo mới, nếu chưa có dataset/model/script Neo4j thì **giữ `MISSING`** và mô tả rõ tình trạng. Chưa cần tải/cài những thành phần này ở Giai đoạn 0.

## Bước 9: Gửi kết quả để xác nhận

Gửi lại ba phần (có thể copy console hoặc ảnh chụp):

1. Kết quả `python -m unittest` có **6 tests PASS**.
2. JSON từ `GET /api/health`.
3. JSON từ `GET /api/agents/status` (hoặc ít nhất `count: 8` và `rl` optional).

Kèm câu **“Giai đoạn 0 đã hoàn thành”** sau khi tự xác nhận. Chỉ lúc đó mới bắt đầu Giai đoạn 1.

## Xử lý lỗi thường gặp

| Triệu chứng | Giải pháp |
|---|---|
| `py` không nhận diện | Kiểm tra Python installation và Python launcher; mở lại terminal |
| `No suitable Python runtime` | Cài Python 3.11 hoặc chủ động dùng Python 3.12 đã xác minh |
| `No module named flask` | Cài đúng `requirements.txt` bằng **Python trong `.venv`** |
| `Activate.ps1 cannot be loaded` | Không activate; dùng trực tiếp `.\.venv\Scripts\python.exe` như trên |
| `Connection refused` khi gọi API | Terminal 1 chưa chạy hoặc sai port |
| Port `5000` đang được dùng | Sửa `FLASK_PORT` ở `.env` và gọi URL port mới |
| `python: can't open file backend/app.py` | Terminal không đứng ở thư mục gốc, kiểm tra `pwd` và `ls` |
| PowerShell từ chối chạy lệnh `Invoke-RestMethod` | Dùng URL API trong trình duyệt |

## Không làm trong giai đoạn 0

Không tạo `dl_prediction_agent.py` giả đoán bệnh, không dựng giao diện, không gắn nhãn bệnh tiểu đường loại 1/2 chưa được model hỗ trợ, không dùng dữ liệu thật nhạy cảm, không tự động kê đơn. Sẽ tiếp tục từng giai đoạn với ZIP mã nguồn và test riêng sau khi được xác nhận.
