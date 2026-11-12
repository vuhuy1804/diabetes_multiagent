# Bản vá Giai đoạn 2 — tiếng Việt bị lỗi mã hóa trong PowerShell

## Triệu chứng

`/api/health` báo `neo4j: ready`, `deep_learning: ready`, nhưng kết quả
`Invoke-RestMethod ... | ConvertTo-Json` có dạng `thÃ¡o`, `ÄÆ°...`.
Đây thường là lỗi **giải mã UTF-8**, không phải phông chữ.

## Nguyên nhân nghi ngờ từ mã nguồn

`backend/app.py` trước đây đặt `app.json.ensure_ascii = False`, nên Flask xuất
ký tự Unicode dưới dạng UTF-8 trực tiếp. Một số phiên bản Windows PowerShell 5.1
có thể giải mã phản hồi `application/json` thiếu `charset` sai.

## Cách sửa

1. Dừng Flask (`Ctrl+C`).
2. Sao lưu `backend/app.py` nếu đã tự sửa.
3. Giải nén ZIP bản vá vào **thư mục cha của** `diabetes-multiagent`, cho phép ghi
   đè `backend/app.py`. Không xóa hoặc ghi đè `.env`, `.venv`, model, CSV hay Neo4j.
4. Nội dung thay đổi cốt lõi:

   ```python
   app.json.ensure_ascii = True
   ```

   JSON được xuất qua mạng ở dạng ASCII (`\uXXXX`), nhưng thư viện JSON ở client
   vẫn tự chuyển về tiếng Việt chuẩn. Dữ liệu Neo4j **không thay đổi**.

5. Chạy unit tests:

   ```powershell
   .\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
   ```

   Gói thêm 2 test regression, nên tổng số unit tests dự kiến là 25 (nếu không có
   test riêng bổ sung). Không thực hiện Giai đoạn 3 khi chưa nghiệm thu.

6. Khởi động lại Flask:

   ```powershell
   .\.venv\Scripts\python.exe backend/app.py
   ```

7. Trong terminal thứ hai:

   ```powershell
   $body = Get-Content .\data\samples\knowledge_query.json -Raw -Encoding UTF8
   $result = Invoke-RestMethod -Uri http://127.0.0.1:5000/api/knowledge/query `
       -Method Post -ContentType 'application/json; charset=utf-8' `
       -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
   $result.payload.answer
   $result.evidence[0].excerpt
   ```

   Kỳ vọng chữ `Thông tin tham khảo`, `Đái tháo đường` hiển thị đúng.

## Nếu vẫn lỗi: phân biệt lỗi dữ liệu Neo4j với lỗi Terminal

- Mở Neo4j Browser, chạy:

  ```cypher
  MATCH (f:Fact {id: 'f01'}) RETURN f.text AS text;
  ```

  Nếu chữ tiếng Việt chuẩn, **không cần seed lại**. Nên thử PowerShell 7 (`pwsh`) hoặc
  đặt Terminal UTF-8:

  ```powershell
  chcp 65001 > $null
  [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
  $OutputEncoding = [System.Text.UTF8Encoding]::new()
  $env:PYTHONIOENCODING = 'utf-8'
  ```

- Nếu chữ **ngay trong Neo4j Browser** cũng bị hỏng, kiểm tra file
  `data/knowledge/DB_diabet.cypher` trên VS Code phải hiển thị đúng tiếng Việt
  và được lưu UTF-8. Sau đó chạy lại:

  ```powershell
  .\.venv\Scripts\python.exe backend/scripts/neo4j_cli.py seed
  ```

  Lệnh này dùng MERGE/SET để cập nhật các node theo `id`, không tạo node trùng.
  Chỉ chạy khi xác nhận DB đang chứa text hỏng; không xóa cơ sở dữ liệu.

## Những gì không thay đổi

- Không chỉnh sửa model Deep Learning, cấu hình Neo4j, hợp đồng Agent hay API.
- `/api/predict`, `/api/health` và `/api/knowledge/query` giữ nguyên chức năng.
- Chưa chuyển sang Giai đoạn 3.
