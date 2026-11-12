# GIAI ĐOẠN P1 — MỞ RỘNG KNOWLEDGE GRAPH VÀ ĐÁNH GIÁ 90 CÂU HỎI

**Project:** Hệ đa Agent hỗ trợ ra quyết định về bệnh tiểu đường  
**Môn học:** Phát triển các hệ thống thông minh (PTIT)  
**Phiên bản:** `demo-kg-v1.3-p1` — 12/11/2026  
**Phạm vi:** Bản cập nhật cho project đã hoàn thành P0 + KG/RAG V2. Không tạo project mới.

> Đây là phần mềm minh họa học thuật, không phải hệ thống chẩn đoán hay điều trị. Dữ liệu tri thức là thông tin giáo dục tổng quan có trích dẫn; không thay thế bác sĩ hoặc đánh giá cá nhân. KHÔNG nhập hồ sơ bệnh nhân thật vào bộ đánh giá.

## 1. P1 bổ sung những gì?

| Chỉ số | Trước P1 (P0) | Sau P1 | Tăng |
|---|---:|---:|---:|
| `Topic` | 24 | **35** | +11 |
| `Fact` | 82 | **137** | +55 |
| `Source` | 18 | **29** | +11 |
| `RELATED_TO` | 23 | **34** | +11 |

Các ID `f01...f82` vẫn được giữ. Fact P1 được thêm theo ID `f083...f137`.

### 11 chủ đề mới

| `topic_id` | Nhóm câu hỏi | Fact |
|---|---|---:|
| `insulin_basics` | Insulin ở mức kiến thức sinh học | 5 |
| `eye_health` | Mắt, võng mạc, thị lực | 5 |
| `kidney_health` | Thận, albumin nước tiểu, chức năng lọc | 5 |
| `foot_health` | Bàn chân, tê chân, vết thương | 5 |
| `heart_health` | Tim mạch và đột quỵ | 5 |
| `after_gestational` | Theo dõi sau đái tháo đường thai kỳ | 5 |
| `sick_days` | Khi bị ốm, thay đổi đường huyết | 5 |
| `sleep_stress` | Giấc ngủ, căng thẳng | 5 |
| `daily_living` | Học tập, làm việc, tự chăm sóc | 5 |
| `travel_health` | Đi lại, du lịch | 5 |
| `misconceptions` | Những hiểu lầm thường gặp | 5 |

Mỗi Fact chỉ là **một thông tin ngắn đã biên soạn bằng tiếng Việt**, có `topic_id` và `source_id`. Không có dữ liệu bệnh nhân hoặc hướng dẫn sử dụng thuốc cá nhân.

**Nguồn chính:** NIDDK/NIH, CDC và ADA. Ví dụ các nguồn công khai: [NIDDK – Diabetic Eye Disease](https://www.niddk.nih.gov/health-information/diabetes/overview/preventing-problems/diabetic-eye-disease), [NIDDK – Diabetic Kidney Disease](https://www.niddk.nih.gov/health-information/diabetes/overview/preventing-problems/diabetic-kidney-disease), [NIDDK – Diabetes & Foot Problems](https://www.niddk.nih.gov/health-information/diabetes/overview/preventing-problems/foot-problems), [CDC – Living with Diabetes](https://www.cdc.gov/diabetes/living-with/), [CDC – Diabetes and Mental Health](https://www.cdc.gov/diabetes/living-with/mental-health.html), [CDC – Tips for Traveling With Diabetes](https://www.cdc.gov/diabetes/about/tips-for-traveling-with-diabetes.html). Danh sách đầy đủ nằm trong trường `sources` của JSON; từng Fact liên kết tới nguồn cụ thể qua `source_id`.

## 2. Các file có trong ZIP

ZIP có một thư mục gốc `diabetes-multiagent/`, chứa **chỉ những file P1 mới hoặc sửa đổi**.

| File | Vai trò |
|---|---|
| `data/knowledge/curated_knowledge.json` | Dữ liệu chuẩn: 35 Topic, 137 Fact, 29 Source |
| `data/knowledge/DB_diabet.cypher` | Seed Neo4j được sinh từ JSON, dùng `MERGE` |
| `data/knowledge/README.md` | Tóm tắt quản lý Knowledge Graph |
| `backend/scripts/build_kg_seed.py` | Sinh/kiểm tra đồng bộ Cypher, có `priority` |
| `backend/services/neo4j_service.py` | Đọc thêm `t.priority` từ Neo4j |
| `backend/services/knowledge_service.py` | Ưu tiên alias đầy đủ của Topic chuyên biệt; giảm nhiễu do từ thông dụng |
| `backend/agents/kg_rag_agent.py` | Cập nhật `version` lên `demo-kg-v1.3-p1` |
| `data/samples/faq_p1_evaluation_90.json` | 90 câu hỏi giáo dục và nhãn kỳ vọng |
| `backend/scripts/evaluate_kg_p1.py` | Đánh giá offline hoặc Neo4j live; xuất JSON |
| `backend/tests/test_kg_p1_expanded.py` | 16 unit tests P1 |
| `backend/tests/test_kg_p0_expanded.py` | Cập nhật test volume để cho phép tăng dữ liệu |
| `backend/tests/test_kg_retrieval_v2.py` | Cập nhật test phiên bản KG |
| `docs/HUONG_DAN_MO_RONG_NEO4J_P1_2026.md` | Tài liệu này |

**Không thay đổi** model Deep Learning, `.env`, `.venv`, API workflow/report, SQLite hoặc Frontend React. JSON API vẫn có `payload.answer`, `matched_topics`, `evidence`, `version`.

## 3. Bước 1 — Sao lưu và chép mã nguồn

1. Dừng Flask và Vite bằng `Ctrl+C`.
2. Sao lưu hoặc commit project đang chạy P0/V2. Đặc biệt sao lưu `data/knowledge/curated_knowledge.json` và `DB_diabet.cypher` nếu đã có chỉnh sửa riêng.
3. **Giải nén ZIP vào `D:\PTIT\N4-1\PTHTTM`** — thư mục CHA của `diabetes-multiagent` — và cho phép ghi đè file trùng tên.
4. Mở lại project `D:\PTIT\N4-1\PTHTTM\diabetes-multiagent` trong VS Code.

> Nếu công cụ giải nén tự tạo thêm thư mục `diabetes-multiagent`, kiểm tra để tránh đường dẫn lồng `diabetes-multiagent/diabetes-multiagent`.
>
> Nếu nhóm đã thêm Fact/Topic riêng sau P0, **đừng chép đè mù**; cần gộp JSON trước rồi chạy lại bộ sinh seed. Lệnh `seed` dùng `MERGE`, không xóa các node bổ sung đang tồn tại trên Neo4j.

## 4. Bước 2 — Kiểm tra cấu trúc và dữ liệu trước khi nạp

Mở PowerShell tại **thư mục gốc project**:

```powershell
.\.venv\Scripts\python.exe backend/scripts/build_kg_seed.py --check
```

Kết quả mong đợi:

```text
SEED CHECK PASS {'topics': 35, 'facts': 137, 'sources': 29, 'relations': 34}
```

Nếu báo `SEED OUT OF SYNC`, chỉ chạy lệnh dưới đây **khi đã xác nhận JSON là dữ liệu nguồn đúng**:

```powershell
.\.venv\Scripts\python.exe backend/scripts/build_kg_seed.py --write
```

JSON/Cypher đều phải sử dụng UTF-8. Không chỉnh tay cả hai file độc lập.

## 5. Bước 3 — Kiểm thử offline trước khi thay Neo4j

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p test_kg_p1_expanded.py -v
.\.venv\Scripts\python.exe backend/scripts/faq_knowledge_p0.py --offline
.\.venv\Scripts\python.exe backend/scripts/evaluate_kg_retrieval_v2.py --offline
.\.venv\Scripts\python.exe backend/scripts/evaluate_kg_p1.py --offline
```

Kết quả chuẩn của bản P1 (trong môi trường tạo mã):

```text
Ran 16 tests ... OK
FAQ P0 22/22 PASS (mode=offline)
KG RETRIEVAL V2 24/24 PASS (mode=offline)
full_case_pass: 88/90 (97.8%)
topical_accuracy: 82/84 (97.6%)
target_fact_recall_at_4: 54/55 (98.2%)
citation_provenance_integrity: 90/90 (100.0%)
out_of_scope_abstention: 6/6 (100.0%)
P1 EVALUATION PASS (mode=offline)
```

**Quan trọng:** 88/90, **không phải** 90/90. Hai trường hợp được ghi vào `review_cases` để nhóm trình bày trung thực:

- Câu hỏi vừa đề cập **đo đường huyết** vừa đề cập **sinh hoạt hằng ngày**: hệ thống chọn Topic `blood_glucose` thay vì nhãn tham chiếu `daily_living`.
- Câu hỏi **so sánh type 1 và type 2**: hệ thống lấy Fact từ hai Topic riêng nhưng nhãn tham chiếu là Topic `types`.

Hai trường hợp này phản ánh cách phân loại Topic còn đơn giản; không có bằng chứng hệ thống đã trả lời hoàn hảo toàn bộ câu hỏi ngoài đời thực.

### Ý nghĩa của các chỉ số

- `topical_accuracy`: Topic đứng đầu có khớp nhãn của bộ kiểm thử hay không (84 câu thuộc phạm vi).
- `target_fact_recall_at_4`: Fact mong đợi có nằm trong tối đa 4 Fact được chọn hay không (55 câu có nhãn Fact).
- `citation_provenance_integrity`: trích dẫn `[Nguồn n]` có Fact/Topic/Source/HTTPS khớp JSON hay không (90 câu).
- `out_of_scope_abstention`: hệ thống có từ chối các câu ngoài phạm vi không (6 câu).
- `full_case_pass`: đạt tất cả điều kiện áp dụng cho từng câu hỏi.

**Giới hạn khoa học:** 90 câu hỏi được tự biên soạn và **đã được dùng để phát hiện lỗi, chỉnh alias trong quá trình P1**; vì thế **không phải test set mù độc lập**, không thể xem 97,8% là tỷ lệ trả lời đúng câu hỏi ngoài đời hay hiệu năng chẩn đoán. Các nhãn phản ánh kiểm tra khớp chủ đề/dữ kiện do nhóm xây dựng, chưa có chuyên gia lâm sàng thẩm định.

Báo cáo offline được ghi tại `outputs/evaluation_kg_p1_offline.json`.

## 6. Bước 4 — Nạp Neo4j thật

Kiểm tra `.env` đã có các biến `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`; **không gửi nội dung `.env` lên chat hoặc GitHub**.

```powershell
.\.venv\Scripts\python.exe backend/scripts/neo4j_cli.py seed
.\.venv\Scripts\python.exe backend/scripts/neo4j_cli.py check
```

Neo4j phải báo `readiness: ready`, và số lượng **ít nhất** 35 Topic, 137 Fact, 29 Source. Nếu database chỉ chứa bộ của project, các số thường bằng chính xác giá trị này. Nếu có dữ liệu nhóm bổ sung từ trước, số lượng có thể lớn hơn.

**Kiểm tra nạp lặp không tạo trùng:** chạy thêm một lần `seed` và `check`, so sánh bộ đếm trước và sau. Việc nạp lại đúng bộ seed P1 không được làm tăng số node.

Có thể kiểm tra bằng Neo4j Browser:

```cypher
MATCH (t:Topic) RETURN count(t) AS topics;
MATCH (f:Fact) RETURN count(f) AS facts;
MATCH (s:Source) RETURN count(s) AS sources;
MATCH (t:Topic {id:'eye_health'})-[:HAS_FACT]->(f:Fact)-[:SUPPORTED_BY]->(s:Source)
RETURN t.name AS topic, f.id AS fact_id, f.text AS content, s.url AS source_url;
```

## 7. Bước 5 — Kiểm thử live với Neo4j

```powershell
.\.venv\Scripts\python.exe backend/scripts/faq_knowledge_p0.py
.\.venv\Scripts\python.exe backend/scripts/evaluate_kg_retrieval_v2.py
.\.venv\Scripts\python.exe backend/scripts/evaluate_kg_p1.py
```

Các lệnh dùng **database thật**, không dùng JSON offline. Kỳ vọng P0 22/22, V2 24/24 và P1 đạt *quality gate* (ngưỡng kiểm thử định nghĩa trong script). Tệp báo cáo live được ghi tại:

```text
outputs/evaluation_kg_p1_live.json
```

Nếu số liệu live khác offline, **không sửa nhãn bộ test để lấy điểm cao**. Kiểm tra: đã nạp `seed` chưa; `t.priority` có được lưu chưa; có node trùng ID do script cũ không; Fact có trích dẫn nguồn hay không. Dùng `review_cases` để phát hiện câu hỏi lệch chủ đề.

## 8. Bước 6 — Kiểm thử toàn bộ Backend và Frontend

Backend:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
```

Nếu project trùng với bản chúng ta đã phát triển và không có test riêng của nhóm, dự kiến **264 tests** (248 cũ + 16 mới). Môi trường tạo mã đã chạy **198/198 test Python không phụ thuộc Flask PASS**; các test HTTP/Flask cần chạy trên Windows của bạn.

Frontend, từ thư mục project:

```powershell
cd frontend
npm test
npm run build
```

Kỳ vọng Frontend **46/46 tests PASS** và build thành công. Do không thay đổi Frontend, không bắt buộc `npm install` lại nếu dependencies đã có. Khi Flask và Neo4j đang chạy, chạy tiếp:

```powershell
npm run smoke:api
```

## 9. Bước 7 — Thử qua giao diện React

Chạy Backend Flask ở Terminal thứ nhất tại gốc project:

```powershell
.\.venv\Scripts\python.exe backend/app.py
```

Chạy Frontend ở Terminal thứ hai trong thư mục `frontend`:

```powershell
npm run dev
```

Mở `http://127.0.0.1:5173`, chọn **Hỏi đáp kiến thức** (không cần nhập 8 đặc trưng).

Hãy thử ít nhất:

1. `Tiểu đường có gây bệnh võng mạc không?` → `eye_health`.
2. `Đái tháo đường có ảnh hưởng đến thận không?` → `kidney_health`.
3. `Vì sao người tiểu đường dễ bị tê chân?` → `foot_health`.
4. `Sau sinh từng bị tiểu đường thai kỳ có cần theo dõi không?` → `after_gestational`.
5. `Thiếu ngủ có làm đường huyết thay đổi không?` → `sleep_stress`.
6. `Người tiểu đường có được đi du lịch không?` → `travel_health`.
7. `Tiểu đường có lây qua tiếp xúc không?` → `misconceptions`.
8. `Phi hành gia mèo và Sao Hỏa` → thông báo không có bằng chứng, không bịa câu trả lời.

Các câu trả lời hợp lệ phải có Fact liên quan, mã nguồn hoặc đường dẫn HTTPS chính xác và tiếng Việt hiển thị đúng. Chú ý không đánh đồng **thông tin giáo dục tổng quát** với dự đoán DL hoặc chẩn đoán cá nhân.

### Gọi API trực tiếp từ PowerShell

```powershell
$body = @{question = 'Bệnh tiểu đường có ảnh hưởng đến mắt không?'} | ConvertTo-Json
$result = Invoke-RestMethod `
  -Uri http://127.0.0.1:5000/api/knowledge/query `
  -Method Post `
  -ContentType 'application/json; charset=utf-8' `
  -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
$result.payload.matched_topics
$result.payload.answer
$result.evidence | Format-Table fact_id,topic_id -AutoSize
```

## 10. Lỗi thường gặp

| Hiện tượng | Cách kiểm tra |
|---|---|
| `SEED OUT OF SYNC` | JSON/Cypher lệch; kiểm tra JSON trước khi dùng `--write` |
| `Neo4j unavailable` | Kiểm tra máy chủ, `.env`, internet, instance Aura đã bật |
| Số node vẫn 24/82/18 | Có thể chưa nạp P1; chạy `seed`, `check` |
| Offline đạt nhưng live khác | Neo4j chứa dữ liệu cũ; seed, so sánh `t.priority`, Fact và Source |
| UTF-8 bị thành `Ä...` | Kiểm tra file UTF-8 và cách PowerShell giải mã phản hồi; giữ cách trả JSON tương thích PowerShell ở Flask |
| Full tests cũ kiểm tra chính xác volume P0 | Dùng file `test_kg_p0_expanded.py` trong ZIP để cho phép mở rộng dữ liệu nhưng vẫn kiểm tra ID P0 |
| Không có đủ 90/90 P1 | Xem `review_cases`; hai câu giao thoa Topic được giữ để thảo luận, không phải lỗi khi phần mềm đáp ứng quality gate |
| Câu ngoài phạm vi được trả lời chung chung | Kiểm tra Topic aliases quá rộng và file `knowledge_service.py` đã cập nhật |

## 11. Điều kiện nghiệm thu P1

- [ ] Đồng bộ JSON/Cypher **PASS**, có 35 Topic / 137 Fact / 29 Source.
- [ ] **16/16** test P1 PASS.
- [ ] FAQ P0 offline & live **22/22**, V2 offline & live **24/24**.
- [ ] P1 offline và Neo4j live đều trả `P1 EVALUATION PASS`, có báo cáo JSON và tỷ lệ minh bạch.
- [ ] Chạy `seed` hai lần không làm tăng số node.
- [ ] Full Backend tests PASS; Frontend 46/46, build, smoke API PASS.
- [ ] Giao diện chế độ hỏi đáp trả thông tin có nguồn cho các chủ đề mới và không trả lời vô căn cứ.

**Chỉ khi bạn chạy xong, gửi log và xác nhận PASS mới chuyển sang bất kỳ bước nào tiếp theo.**
