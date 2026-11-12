# NÂNG CẤP KG/RAG AGENT V2 — XẾP HẠNG TOPIC VÀ FACT

**Project:** Hệ đa Agent hỗ trợ ra quyết định về bệnh tiểu đường  
**Môn:** Phát triển các hệ thống thông minh (PTIT)  
**Điểm xuất phát:** P0 đã PASS, Neo4j có 24 Topic, 82 Fact, 18 Source.  
**Phạm vi:** Chỉ nâng cấp thuật toán **truy xuất tri thức**, không thay dữ liệu Neo4j, mô hình Deep Learning, các luật hay giao diện.

> Đây là prototype giáo dục. Kết quả KG/RAG không phải chẩn đoán y tế. Chỉ trích dẫn thông tin đã có trong Knowledge Graph; không kê thuốc, liều dùng hoặc điều trị.

## 1. Nguyên nhân cần nâng cấp

Trước V2, dịch vụ chọn tối đa hai Topic và yêu cầu Neo4j lấy Fact theo `ORDER BY t.id, f.id LIMIT...`. Thứ tự lưu trữ `fact_id` **không phải độ liên quan**; câu hỏi cụ thể có thể nhận Fact tổng quan trước và thêm chủ đề phụ ngoài ý muốn.

Ví dụ điển hình:

- “Người tiểu đường có ăn cơm được không?” → cần ưu tiên `f36` (không nhất thiết phải bỏ hoàn toàn cơm), thay vì Fact mô tả chung carbohydrate `f35`.
- “Có nên uống nước ép khi mắc tiểu đường?” → cần ưu tiên `f49` (nước ép cung cấp carbohydrate), không phải Fact nước lọc `f47`.
- “Dấu hiệu khi đường huyết cao?” → ưu tiên `f60` về biểu hiện, thay vì Fact định nghĩa.

## 2. Những gì V2 thay đổi

1. **Chọn Topic có chủ đích:** thường chọn một Topic cụ thể; chỉ dùng hai khi câu hỏi ghép hai chủ đề (ví dụ “ăn cơm và trái cây”). Duy trì nhóm `nutrition` hỗ trợ một số câu hỏi “nên uống gì” để tương thích bộ kiểm thử cũ.
2. **Nạp nhiều Fact ứng viên:** Neo4j lấy các Fact cho **từng Topic riêng biệt**, không để một Topic chứa nhiều Fact làm chiếm toàn bộ giới hạn của Topic thứ hai.
3. **Xếp hạng Fact:** dựa vào từ khóa tiếng Việt bỏ dấu, cụm hai từ, từ ít phổ biến trong nhóm Fact ứng viên và một số biểu thức tương đương có kiểm soát (ví dụ gạo lứt/ngũ cốc nguyên hạt).
4. **Giới hạn đầu ra:** mặc định trả tối đa **4 Fact có nguồn**, không tự xuất tất cả Fact của Topic.
5. **Giữ định dạng trích dẫn:** `evidence[i]` luôn tương ứng với `[Nguồn i+1]` trong `payload.answer`.
6. **Từ chối khi thiếu thông tin:** câu hỏi không có chủ đề phù hợp hoặc yêu cầu liều dùng, thuốc cụ thể chưa có Fact tương ứng sẽ trả `response_kind: no_evidence`.
7. **Giữ tính tương thích:** `/api/knowledge/query`, `/api/report/generate`, `/api/assess`, Coordinator và Frontend giữ nguyên cấu trúc. Trường `retrieval_method` mới chỉ là thông tin bổ sung.

**Không có:** LLM, embeddings, vector database, sinh thông tin mới, truy vấn web trực tiếp hay lời khuyên điều trị. Đây vẫn là Graph-first Extractive RAG.

## 3. Các file trong ZIP

Giải nén ZIP vào **thư mục cha** chứa project `diabetes-multiagent` (ví dụ `D:\PTIT\N4-1\PTHTTM`), cho phép ghi đè file cũ.

| File trong project | Nội dung |
|---|---|
| `backend/services/knowledge_service.py` | Thuật toán chọn Topic và xếp hạng Fact V2 |
| `backend/services/neo4j_service.py` | Lấy Fact ứng viên riêng cho từng Topic |
| `backend/tests/test_kg_retrieval_v2.py` | 13 bài kiểm thử riêng |
| `backend/scripts/evaluate_kg_retrieval_v2.py` | CLI kiểm thử 24 câu hỏi; offline/live |
| `data/samples/faq_retrieval_v2.json` | Bộ 24 câu hỏi kỳ vọng về Topic, Fact và từ chối khi thiếu tri thức |
| `docs/HUONG_DAN_NANG_CAP_KG_RAG_AGENT_V2.md` | Tài liệu này |

**Giữ nguyên:** `.env`, `.venv`, `models/`, `config/model_manifest.json`, `outputs/audit.sqlite3`, `data/knowledge/curated_knowledge.json`, `data/knowledge/DB_diabet.cypher`, và `frontend/`.

## 4. Cách cài đặt trên Windows 11 + VS Code

### Bước 1 — Sao lưu và cập nhật

Dừng Flask và Frontend (`Ctrl+C`). Sao lưu hoặc commit project; giải nén ZIP vào:

```text
D:\PTIT\N4-1\PTHTTM\
└── diabetes-multiagent\
    ├── backend\
    ├── data\
    ├── docs\
    └── frontend
```

Không giải nén thêm một cấp `diabetes-multiagent` lồng nhau. Không cần `pip install` hoặc `npm install` thêm.

### Bước 2 — Test riêng thuật toán mới

Tại root project:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p test_kg_retrieval_v2.py -v
```

Kỳ vọng:

```text
Ran 13 tests in ...s
OK
```

### Bước 3 — Test FAQ offline (chưa cần Neo4j)

```powershell
.\.venv\Scripts\python.exe backend/scripts/faq_knowledge_p0.py --offline
.\.venv\Scripts\python.exe backend/scripts/evaluate_kg_retrieval_v2.py --offline
```

Kỳ vọng:

```text
FAQ P0 22/22 PASS (mode=offline)
KG RETRIEVAL V2 24/24 PASS (mode=offline)
```

### Bước 4 — Test Neo4j thật

Kiểm tra kết nối:

```powershell
.\.venv\Scripts\python.exe backend/scripts/neo4j_cli.py check
```

Neo4j phải có tối thiểu `24 Topic / 82 Fact / 18 Source`, `readiness: ready`.

Sau đó chạy:

```powershell
.\.venv\Scripts\python.exe backend/scripts/faq_knowledge_p0.py
.\.venv\Scripts\python.exe backend/scripts/evaluate_kg_retrieval_v2.py
```

Kỳ vọng:

```text
FAQ P0 22/22 PASS (mode=live)
KG RETRIEVAL V2 24/24 PASS (mode=live)
```

**Không cần chạy `seed` lại**, vì bản V2 chỉ thay mã truy xuất, không sửa dữ liệu. Nếu kiểm thử live sai nhưng offline PASS, hãy kiểm tra Neo4j đã được nạp bản P0 trước đó và không có bản ghi tự chỉnh sửa gây khác biệt.

### Bước 5 — Chạy toàn bộ kiểm thử Backend

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
```

Kỳ vọng **248 tests PASS** (235 trước + 13 mới). Số lượng này giả định project của bạn đã cập nhật đầy đủ P0 như lần nghiệm thu vừa rồi. Cảnh báo `ConvergenceWarning` của bài test huấn luyện giả lập không đồng nghĩa test thất bại.

### Bước 6 — Test API trên Flask

Terminal 1 (root project):

```powershell
.\.venv\Scripts\python.exe backend/app.py
```

Terminal 2:

```powershell
$body = @{ question = "Người tiểu đường có ăn cơm được không?" } | ConvertTo-Json -Compress
$result = Invoke-RestMethod `
  -Uri http://127.0.0.1:5000/api/knowledge/query `
  -Method POST `
  -ContentType "application/json; charset=utf-8" `
  -Body ([System.Text.Encoding]::UTF8.GetBytes($body))

$result.status
$result.payload.matched_topics
$result.evidence | Select-Object -ExpandProperty fact_id
$result.payload.answer
```

Kỳ vọng: `status = ok`; Topic đầu tiên `carb_rice`; Fact đầu tiên `f36`; nội dung tiếng Việt và `[Nguồn 1]` rõ ràng. Test thêm:

```powershell
$body = @{question="Có nên uống nước ép khi mắc tiểu đường?"} | ConvertTo-Json -Compress
$result = Invoke-RestMethod -Uri http://127.0.0.1:5000/api/knowledge/query -Method POST -ContentType "application/json; charset=utf-8" -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
$result.evidence[0].fact_id
```

Kỳ vọng: `f49`.

### Bước 7 — Frontend và API cũ

Trong `frontend/`:

```powershell
npm test
npm run build
npm run smoke:api
```

Kỳ vọng: 46/46 test Frontend PASS; build và smoke API PASS. Trên trình duyệt, thử **Hỏi đáp kiến thức** không cần thông tin bệnh nhân, sau đó thử **Phân tích + Báo cáo** để chắc chắn Coordinator/Explanation vẫn hoạt động.

## 5. Các tình huống demo

| Câu hỏi | Topic đầu | Fact đầu tiên |
|---|---|---|
| Người tiểu đường có ăn cơm được không? | `carb_rice` | `f36` |
| Người tiểu đường ăn gạo lứt được không? | `carb_rice` | `f37` |
| Bị tiểu đường ăn chuối được không? | `fruits` | `f40` |
| Có nên uống nước ngọt khi bị tiểu đường? | `drinks` | `f48` |
| Có nên uống nước ép khi mắc tiểu đường? | `drinks` | `f49` |
| Dấu hiệu khi đường huyết cao? | `high_glucose` | `f60` |
| Các dấu hiệu khi tụt đường huyết là gì? | `low_glucose` | `f64` |
| Ăn cơm và trái cây thế nào? | `carb_rice` + `fruits` | Có Fact từ cả hai |
| Metformin là gì? | Không đủ Fact về thuốc cụ thể | `no_evidence` |
| Mèo phi hành gia trên Sao Hỏa | Không liên quan | `no_evidence` |

## 6. Phân biệt các kết quả kiểm thử

- **Unit tests:** logic Agent, bảo toàn hợp đồng dữ liệu, kiểm tra tình huống sai và hồi quy.
- **FAQ offline:** đúng kỳ vọng trên dữ liệu JSON đóng gói; không xác nhận Neo4j thật.
- **FAQ live:** sử dụng Neo4j thật, kiểm tra chủ đề và Fact đã nạp.
- **Build/Smoke:** xác nhận API và giao diện hoạt động.
- **24/24 FAQ:** chỉ là độ khớp trên **24 câu đã chọn**, không chứng minh trả lời đúng toàn bộ câu hỏi y khoa ngoài thực tế.

## 7. Hạn chế còn lại

V2 dùng so khớp từ và cụm từ, **không phải semantic search**. Câu diễn đạt khác biệt có thể không tìm được; một số Fact được cung cấp theo nhóm (như lời khuyên chung về trái cây), không nên coi là trả lời chuyên biệt cho từng thực phẩm. Để mở rộng về sau, ưu tiên tăng Fact có nguồn chính xác theo câu hỏi trước khi cân nhắc embeddings, vector search hay LLM. Không tự điền liều thuốc hoặc tạo lời khuyên điều trị.

## 8. Điều kiện nghiệm thu

1. `test_kg_retrieval_v2.py`: **13/13 PASS**.
2. FAQ P0 offline/live: **22/22** cả hai chế độ.
3. FAQ Retrieval V2 offline/live: **24/24** cả hai chế độ.
4. Backend: **248/248 PASS**.
5. Frontend: **46/46 PASS**, `npm run build` và `npm run smoke:api` PASS.
6. `/api/knowledge/query` trả Fact `f36` cho câu cơm, `f49` cho nước ép và citation tương ứng; không ảnh hưởng `/api/report/generate` và `/api/assess`.

**Chỉ khi bạn chạy PASS và xác nhận, chúng ta mới tiếp tục bước nâng cấp khác.**
