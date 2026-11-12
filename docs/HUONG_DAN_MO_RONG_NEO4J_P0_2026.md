# Mở rộng Knowledge Graph — Bước P0 (15 chủ đề FAQ)

**Project:** Hệ đa Agent cho bệnh tiểu đường — PTIT, môn Phát triển các hệ thống thông minh.  
**Bước:** P0 = mở rộng tri thức. Chưa triển khai P1 và chưa làm thuật toán retrieval nâng cao.  
**Phiên bản tri thức:** `demo-kg-v1.2-p0` (12/11/2026).  
**Phạm vi:** Thông tin y học tổng quan dùng để học tập; không phải chẩn đoán, tư vấn điều trị hoặc thay thế nhân viên y tế.

## 1. Đã thêm những gì?

| Thành phần | Trước | Thêm mới | Tổng sau P0 |
|---|---:|---:|---:|
| `Topic` | 9 | 15 | **24** |
| `Fact` | 22 | 60 | **82** |
| `Source` | 6 | 12 | **18** |

15 Topic mới: `risk_factors`, `prediabetes`, `prevention`, `carb_rice`, `fruits`, `sweets`, `drinks`, `exercise`, `blood_glucose`, `high_glucose`, `low_glucose`, `emergency_dka`, `medicines_overview`, `complications`, `checkups`.

Mỗi Fact ngắn gọn bằng tiếng Việt, do project biên soạn/tóm tắt từ nội dung giáo dục của **CDC** và **NIDDK/NIH**, liên kết với đúng một `Source` có URL. Không có thông tin bệnh nhân, đơn thuốc hoặc liều thuốc trong Knowledge Graph.

**Lưu ý:** 24/82/18 là số node mà file dữ liệu của bản vá này định nghĩa. Neo4j thật có thể báo số lớn hơn nếu bạn đã nạp thêm dữ liệu riêng; không tự xóa dữ liệu lạ.

## 2. Các file trong ZIP

Các đường dẫn bên dưới đều tính từ thư mục `diabetes-multiagent/`:

| File | Mục đích |
|---|---|
| `data/knowledge/curated_knowledge.json` | 24 Topic + 82 Fact + 18 Source |
| `data/knowledge/DB_diabet.cypher` | Seed Neo4j bằng `MERGE`, không tự xóa dữ liệu cũ |
| `backend/scripts/build_kg_seed.py` | Kiểm tra/sinh Cypher từ JSON, tránh lệch hai file |
| `backend/scripts/faq_knowledge_p0.py` | Test 22 FAQ ở chế độ offline hoặc Neo4j thật |
| `data/samples/faq_knowledge_p0.json` | 22 câu hỏi và Topic mong đợi |
| `backend/tests/test_kg_p0_expanded.py` | 8 unit tests bổ sung cho dữ liệu, FAQ và seed |
| `backend/tests/test_kg_phase2.py` | Sửa kiểm tra số lượng cứng của giai đoạn cũ |
| `backend/scripts/neo4j_cli.py` | Nhận diện đúng dấu `;` nằm bên trong chuỗi Cypher, không cho phép hai lệnh trên một dòng |
| `backend/services/knowledge_service.py` | Cập nhật version và tránh trả kết quả sai chỉ vì khớp 1 từ quá chung |
| `backend/agents/kg_rag_agent.py` | Cập nhật nhãn phiên bản KG |
| `data/knowledge/README.md` | Tài liệu bảo trì Knowledge Graph |

Không thay Backend Deep Learning, Coordinator, Rule, Monitoring, Flask API hay Frontend.

## 3. Sao lưu trước khi cập nhật

1. **Dừng Flask và Vite** (`Ctrl+C`). Nếu project đã ở Git, commit mã nguồn hiện tại.
2. Sao lưu hai file `data/knowledge/curated_knowledge.json` và `data/knowledge/DB_diabet.cypher`, đặc biệt nếu bạn đã thêm Fact riêng.
3. Nếu Neo4j hiện chứa dữ liệu quan trọng tự nhập và chưa được sao lưu, thực hiện sao lưu bằng quy trình phù hợp với triển khai Neo4j của bạn trước khi nạp. Script này không xóa node nhưng sẽ cập nhật các node trùng ID.
4. Giải nén ZIP **vào thư mục cha** `D:\PTIT\N4-1\PTHTTM`, cho phép ghi đè các file trùng tên. ZIP có sẵn thư mục gốc `diabetes-multiagent`.
5. Không sao chép đè `.env`, `.venv`, model hoặc SQLite; bản ZIP không chứa chúng.

## 4. Kiểm thử mã nguồn trước khi nạp Neo4j

Trong PowerShell ở `D:\PTIT\N4-1\PTHTTM\diabetes-multiagent`:

```powershell
.\.venv\Scripts\python.exe backend/scripts/build_kg_seed.py --check
```

Kết quả dự kiến:

```text
SEED CHECK PASS {'topics': 24, 'facts': 82, 'sources': 18, 'relations': 23}
```

Tiếp tục chạy **FAQ offline**, không cần Neo4j:

```powershell
.\.venv\Scripts\python.exe backend/scripts/faq_knowledge_p0.py --offline
```

Kỳ vọng dòng cuối:

```text
FAQ P0 22/22 PASS (mode=offline)
```

Sau đó kiểm tra 8 unit tests mở rộng:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p test_kg_p0_expanded.py -v
```

Kỳ vọng `Ran 8 tests ... OK`. Ngoài ra chạy toàn bộ tests Backend để phát hiện hồi quy (tổng số dự kiến **235 tests**):

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
```

Cảnh báo từ sklearn về số vòng lặp giới hạn trong test huấn luyện không đồng nghĩa bài test thất bại.

## 5. Nạp dữ liệu lên Neo4j thật

Hãy bảo đảm `.env` có `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `NEO4J_DATABASE` đúng từ các giai đoạn trước (không gửi mật khẩu).

Chạy lệnh:

```powershell
.\.venv\Scripts\python.exe backend/scripts/neo4j_cli.py seed
.\.venv\Scripts\python.exe backend/scripts/neo4j_cli.py check
```

Kỳ vọng khi Neo4j ban đầu chỉ có dữ liệu dự án mẫu:

```json
{
  "seed": "ok",
  "counts": {"topics": 24, "facts": 82, "sources": 18},
  "readiness": "ready"
}
```

Nếu counts cao hơn, có thể đang có dữ liệu ngoài bản mẫu. **Không xóa** dữ liệu chỉ để khớp con số.

**Kiểm thử idempotent:** chạy lại `seed`, rồi `check`. Tổng số node phải **không tự tăng** khi dữ liệu không đổi.

## 6. Test FAQ trên Neo4j thật

```powershell
.\.venv\Scripts\python.exe backend/scripts/faq_knowledge_p0.py
```

Kỳ vọng:

```text
FAQ P0 22/22 PASS (mode=live)
```

Lệnh kiểm tra câu hỏi đơn lẻ:

```powershell
.\.venv\Scripts\python.exe backend/scripts/neo4j_cli.py query "Bệnh tiểu đường có di truyền không?"
.\.venv\Scripts\python.exe backend/scripts/neo4j_cli.py query "Người tiểu đường có ăn cơm được không?"
.\.venv\Scripts\python.exe backend/scripts/neo4j_cli.py query "Tụt đường huyết có những dấu hiệu gì?"
.\.venv\Scripts\python.exe backend/scripts/neo4j_cli.py query "Nhiễm toan ceton là gì?"
```

Phản hồi nên có `status=ok`, `payload.response_kind=grounded_extractive`, `payload.matched_topics`, `evidence[*].source.url`, và câu chữ tiếng Việt bình thường.

## 7. Kiểm tra giao diện và các chức năng cũ

Khởi động Backend lại:

```powershell
.\.venv\Scripts\python.exe backend/app.py
```

Trong terminal `frontend`, chạy:

```powershell
npm test
npm run build
npm run dev
```

Kỳ vọng phần test Frontend vẫn **46/46 PASS** như bản nâng cấp hai chế độ trước. Mở `http://127.0.0.1:5173` → **Hỏi đáp kiến thức** để thử các câu trong file `faq_knowledge_p0.json`. Không cần nhập chỉ số sức khỏe. Thử thêm chế độ dự đoán/báo cáo để bảo đảm các Agent cũ không bị ảnh hưởng.

## 8. Cách bảo trì dữ liệu ở các bước sau

Khi muốn thêm Fact/Source/Topic sau này:

1. Chỉnh **`curated_knowledge.json`**; dùng ID không trùng, có một URL nguồn hợp lệ cho mỗi Fact.
2. Chạy `build_kg_seed.py --write` để sinh `DB_diabet.cypher` từ JSON.
3. Chạy `build_kg_seed.py --check` và unit tests.
4. Chạy `neo4j_cli.py seed` để cập nhật Neo4j thật.

Không chỉnh riêng một trong hai file dữ liệu vì có thể làm mã nguồn khác với database.

### Giới hạn hiện tại

- `P0` mở rộng **nội dung và alias** cho chủ đề FAQ. Không đồng nghĩa trả lời được mọi câu hỏi thực tế.
- Bộ xếp hạng hiện còn lấy tối đa hai Topic/6 Fact, một số câu có thể được thêm Fact từ chủ đề phụ. Việc chọn Fact sát câu hỏi là **bước cải thiện retrieval kế tiếp**, sau khi P0 nghiệm thu.
- Thông tin y tế phổ thông không phải chẩn đoán, không hướng dẫn tự dùng hoặc chỉnh thuốc. Hệ thống cần ghi nguồn và đề nghị hỗ trợ y tế khẩn cấp với tình huống nguy hiểm.
- Không dùng 22/22 FAQ PASS như số liệu đánh giá độc lập. Đây chỉ là bộ kiểm thử hồi quy của những câu hỏi đã biết; đánh giá thật cần bộ FAQ khác độc lập với alias dùng khi biên soạn.

## 9. Bạn cần gửi kết quả để nghiệm thu

1. Kết quả `build_kg_seed.py --check`.
2. Kết quả `faq_knowledge_p0.py --offline` và `faq_knowledge_p0.py` trên Neo4j thật.
3. JSON counts từ `neo4j_cli.py check` và lần chạy lại `seed`.
4. Tổng kết unit tests Backend và `npm test`.
5. Một đoạn output câu trả lời thực tế trên giao diện, có nguồn URL.

**Sau khi bạn xác nhận P0 đã PASS, mới chuyển sang bước nâng cấp retrieval.**
