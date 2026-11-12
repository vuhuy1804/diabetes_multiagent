# Hệ đa Agent cho bệnh tiểu đường — Giai đoạn 6 (PTIT)

Project cuối môn **Phát triển các hệ thống thông minh**, tuân theo PDF kiến trúc 6 lớp do giảng viên cung cấp. Đây chỉ là **bản demo học thuật**: không chẩn đoán, không kê đơn và không thay thế ý kiến chuyên môn.

## Tiến độ

| Giai đoạn | Thành phần | Trạng thái |
|---|---|---|
| 0 | Khởi tạo Flask + AgentMessage | Người học xác nhận PASS |
| 1 | Deep Learning Prediction Agent | Người học xác nhận PASS |
| 2 | Neo4j + KG/RAG Agent, sửa UTF-8 | 25/25 tests PASS trên máy người học |
| 3 | Patient Data Agent | 47/47 tests PASS trên máy người học |
| 4 | Rule-Based Agent | 78/78 tests PASS trên máy người học |
| 5 | Coordinator Agent | Người học xác nhận 120/120 tests PASS |
| **6** | **Explanation Agent** | **Đã chuẩn bị bản cập nhật; cần người học kiểm thử 180 tests và xác nhận** |
| 7 | Giao diện React/Vite | Chưa làm |
| 8 | Monitoring/Audit tối thiểu + đánh giá tích hợp | Chưa làm |
| 9 | RL trong môi trường mô phỏng | Tùy chọn |

## Giai đoạn 6 có gì mới?

- **`ExplanationAgent`** dùng template tường minh, không gọi LLM, chỉ tổng hợp đầu ra đã được Coordinator tạo từ model DL và Neo4j thật.
- Báo cáo gồm 4 phần: **prediction, rule_assessment, knowledge, limitations**; citation nối chính xác Rule `R1...` và Neo4j fact `K1...` đến các nguồn được cung cấp.
- **`Coordinator.run_with_explanation()`** thực hiện 5 Agent tuần tự, giữ request ID, trace và từng kết quả riêng. Không dựng báo cáo từ workflow lỗi hoặc evidence không hợp lệ.
- **`POST /api/report/generate`** nhận `features` và `question` tùy chọn, trả AgentMessage với `payload.report` và `report_ready=true` khi thành công.
- **`POST /api/workflow/run`** giữ nguyên hợp đồng 4 Agent của Giai đoạn 5 để tránh ảnh hưởng test cũ.
- **Monitoring Agent, RL và `/api/assess` hoàn chỉnh chưa triển khai**; chưa lưu lịch sử/trace xuống CSDL.
- Không cần cài thư viện mới, train lại mô hình hoặc seed lại Neo4j. Giữ `app.json.ensure_ascii=True` để tránh lỗi Unicode PowerShell 5.1.

## Chạy thử (PowerShell, thư mục project)

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p test_explanation_phase6.py -v
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p test_report_workflow_phase6.py -v
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
.\.venv\Scripts\python.exe backend/scripts/report_cli.py data/samples/report_with_question.json
.\.venv\Scripts\python.exe backend/app.py
```

Kỳ vọng tổng **180 tests**. Để gọi API report bằng PowerShell với body UTF-8 và hiển thị báo cáo có nguồn, xem **[`docs/GIAI_DOAN_6_HUONG_DAN.md`](docs/GIAI_DOAN_6_HUONG_DAN.md)**.

## API hiện có

| API | Chức năng |
|---|---|
| `GET /api/health` | Readiness; `phase=6-explanation-agent` |
| `GET /api/agents/status` | Danh mục 8 Agent; Explanation ready, Monitoring/RL chưa làm |
| **`POST /api/report/generate`** | **Mới — 5 bước gồm Explanation, báo cáo 4 phần có nguồn** |
| `POST /api/workflow/run` | Luồng 4 Agent cũ, trả kết quả dạng cấu trúc |
| `POST /api/patient/validate` | Dữ liệu đầu vào |
| `POST /api/predict` | Dự đoán từ DL |
| `POST /api/knowledge/query` | Truy vấn Neo4j |
| `GET /api/knowledge/topics` | Danh mục KG |
| `GET /api/rules/catalog` | Danh sách 7 luật demo |
| `POST /api/rules/evaluate` | Kiểm thử Rule Agent độc lập |
| `POST /api/assess` | HTTP 501 — chưa triển khai Monitoring và quy trình đánh giá cuối cùng |

Không sử dụng dữ liệu bệnh nhân thật; không chia sẻ `.env`, mật khẩu Neo4j hoặc các dữ liệu nhạy cảm. **Chỉ chuyển Giai đoạn 7 sau khi người học kiểm thử và xác nhận.**
