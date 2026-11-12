# Knowledge Graph — P1 (`demo-kg-v1.3-p1`)

35 Topic, 137 Fact, 29 Source và 34 quan hệ `RELATED_TO`, bao gồm dữ liệu cũ từ P0/V2. Đây là kho kiến thức giáo dục được biên soạn và gắn nguồn, không phải dữ liệu y khoa đã thẩm định dùng để chẩn đoán.

- `curated_knowledge.json` là nguồn dữ liệu chuẩn.
- `DB_diabet.cypher` được tạo tự động từ JSON bằng `backend/scripts/build_kg_seed.py --write` và nạp bằng `MERGE` để tránh trùng ID.
- `priority` là metadata tùy chọn trên Topic để tăng ưu tiên alias đầy đủ của chủ đề chuyên biệt; P0 để 0. Neo4j trả `coalesce(t.priority,0)`.
- Các Agent khác không thay đổi hợp đồng. KG/RAG vẫn trả Fact có nguồn và không suy diễn từ các dữ kiện ngoài kho.

## Lệnh nhanh (chạy từ thư mục project)

```powershell
.\.venv\Scripts\python.exe backend/scripts/build_kg_seed.py --check
.\.venv\Scripts\python.exe backend/scripts/neo4j_cli.py seed
.\.venv\Scripts\python.exe backend/scripts/neo4j_cli.py check
.\.venv\Scripts\python.exe backend/scripts/evaluate_kg_p1.py --offline
.\.venv\Scripts\python.exe backend/scripts/evaluate_kg_p1.py
```

Tài liệu đầy đủ: `docs/HUONG_DAN_MO_RONG_NEO4J_P1_2026.md`.
