# Vá lỗi SQLite WinError 32 — Giai đoạn 8

## Vấn đề

Một số kiểm thử dùng `with sqlite3.connect(path) as db:`. Context manager này commit/rollback transaction khi kết thúc **nhưng không đóng** SQLite connection. Khi `TemporaryDirectory.cleanup()` chạy trên Windows, file `audit.sqlite3`/`test.sqlite3` vẫn có thể bị khóa và phát sinh `PermissionError: [WinError 32]`.

## Nội dung bản vá

1. `backend/tests/test_monitoring_phase8.py`: dùng `contextlib.closing` để đảm bảo đóng cả ba kết nối SQLite thủ công; test cập nhật ngày giữ transaction `with db:` để commit trước khi đóng.
2. `backend/tests/test_monitoring_api_phase8.py`: dùng `closing` cho kết nối đọc dữ liệu audit trong test API.
3. `backend/api/routes.py`: đăng ký `_kg_repo.close` khi Python thoát để giải phóng Neo4j driver (giải quyết cảnh báo `unclosed Neo4jDriver` thường gặp khi chạy tests).

Không sửa schema SQLite, không sửa dữ liệu Neo4j, không đổi endpoint hay thuật toán.

## Áp dụng

1. Dừng Flask và Vite. Sao lưu/commit file nếu bạn đã sửa ba file nói trên.
2. Giải nén ZIP vào `D:\PTIT\N4-1\PTHTTM` (thư mục CHA của `diabetes-multiagent`); đồng ý ghi đè ba file.
3. Tại terminal VS Code ở thư mục gốc `diabetes-multiagent`, chạy theo thứ tự:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p test_monitoring_phase8.py -v
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p test_monitoring_api_phase8.py -v
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
```

Kỳ vọng nhóm đầu 18/18 PASS, nhóm API 12/12 PASS và toàn bộ backend 222/222 PASS. Nếu có test khác FAIL, hãy gửi đoạn lỗi mới.

Sau đó mới tiếp tục nghiệm thu `api/assess`, `audit_cli.py summary` và `evaluate_phase8.py` theo tài liệu Giai đoạn 8; chưa chuyển sang giai đoạn kế tiếp.

## Tại sao phải dùng `closing`?

```python
from contextlib import closing
import sqlite3

# SELECT:
with closing(sqlite3.connect(dbpath)) as db:
    rows = db.execute('SELECT * FROM audit_runs').fetchall()

# UPDATE/DELETE/INSERT:
with closing(sqlite3.connect(dbpath)) as db:
    with db:  # commit / rollback transaction
        db.execute('UPDATE audit_runs SET result_status = ? WHERE request_id = ?', ('ok', 'req-example'))
```

`with db:` quản lý transaction; `with closing(db)` quản lý tài nguyên và đóng kết nối.
