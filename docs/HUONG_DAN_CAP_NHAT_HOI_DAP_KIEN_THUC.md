# Bản sửa Hỏi đáp kiến thức & dinh dưỡng — bổ sung sau Giai đoạn 8

Mục đích: cho phép **hỏi KG/RAG không cần 8 đặc trưng**, giữ chế độ Phân tích và báo cáo đầy đủ; bổ sung chủ đề **dinh dưỡng** (tri thức chung, có nguồn).

## Cách cài

1. Sao lưu/commit project; tắt Flask và Vite.
2. Giải nén ZIP vào thư mục **cha chứa `diabetes-multiagent`**; cho phép ghi đè các file liệt kê trong ZIP (không chứa `.env`, model, `.venv`, audit database).
3. Gói này thay `data/knowledge/DB_diabet.cypher` và `curated_knowledge.json`. Nếu bạn đã tự bổ sung các Fact trong file đó, hãy **so sánh và gộp thay đổi** thay vì ghi đè không kiểm tra.
4. Tại thư mục gốc, đảm bảo `.env` Neo4j còn hoạt động và nạp thêm Fact vào graph (MERGE không nhân đôi các ID hiện tại):

   ```powershell
   .\.venv\Scripts\python.exe backend/scripts/neo4j_cli.py seed
   .\.venv\Scripts\python.exe backend/scripts/neo4j_cli.py query "Bệnh tiểu đường nên ăn gì?"
   ```

   Kết quả seed dự kiến **9 Topic, 22 Fact, 6 Source** trên database seed gốc. Nếu đã có dữ liệu tự bổ sung, con số có thể lớn hơn.
   `matched_topics` phải có `nutrition`, `evidence` phải trỏ nguồn `cdc-meal-planning` hoặc `niddk-healthy-living`, không được chỉ trả thông tin định nghĩa bệnh.

5. Khởi động Flask và gọi API riêng:

   ```powershell
   $body = @{ question = 'Bệnh tiểu đường nên ăn gì?' } | ConvertTo-Json
   Invoke-RestMethod -Uri http://127.0.0.1:5000/api/knowledge/query -Method Post -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($body)) | ConvertTo-Json -Depth 8
   ```

6. Chạy frontend (thư mục `frontend`): `npm run dev`. Mở `http://127.0.0.1:5173` và chọn chế độ **Hỏi kiến thức**; chỉ nhập câu hỏi và nhấn **Hỏi KG/RAG**. Khi chọn **Phân tích dữ liệu & báo cáo**, luồng cũ 8 đặc trưng vẫn hoạt động.

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p test_kg_nutrition_patch.py -v
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
cd frontend
npm test
npm run build
npm run smoke:api
```

- Kiểm thử mới: 5 Python + 10 JavaScript; tổng dự kiến **227 Backend tests và 46 Frontend tests**, nếu bộ hiện tại của bạn là 222 và 36. Sau khi sửa số lượng seed trong một bài test cũ, tất cả test cần PASS.
- Neo4j thực, Flask API, Vite build và trình duyệt cần chạy trên máy Windows của bạn; không có mô hình huấn luyện mới.
- Không phải chatbot AI tự do: KG/RAG chỉ tìm và trích dẫn Fact có sẵn. Nếu nguồn không bao phủ câu hỏi, hệ thống phải nói không tìm được, không bịa thêm.
- Nội dung dinh dưỡng chỉ mang tính thông tin chung; không dùng để kê thực đơn riêng, quyết định điều trị hoặc thay thế nhân viên y tế.

Nguồn kiến thức bổ sung:
- CDC: https://www.cdc.gov/diabetes/healthy-eating/diabetes-meal-planning.html
- NIDDK: https://www.niddk.nih.gov/health-information/diabetes/overview/healthy-living-with-diabetes
