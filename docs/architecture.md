# Kiến trúc được khóa cho project cuối môn

Nguồn ưu tiên: **PDF của giảng viên** `references/project_architecture_multiagent_diabet_v1.pdf`, đặc biệt §2–§10. Hai hình bảng `multiagent01.png` và `multiagent02.png` làm rõ hai nhánh DL và KG/RAG, không thay thế chi tiết workflow chính thức.

## Sáu tầng (PDF §2)

1. User Interaction Layer: frontend sau.
2. API and Data Processing Layer: Flask + nhận yêu cầu/chuẩn bị dữ liệu.
3. Multiagent Coordination Layer: Coordinator Agent.
4. Intelligent Agent Layer: Data, DL Prediction, Rule-Based, KG/RAG, Explanation, Monitoring; RL tùy chọn.
5. Knowledge and Model Layer: model DL thật, Neo4j graph, tài liệu/retrieval nếu có, RL simulation tùy chọn.
6. Evaluation and Audit Layer: trace, version, kết quả kiểm thử.

## Agent bắt buộc và tùy chọn (PDF §3)

| Agent | Vai trò | Triển khai |
|---|---|---|
| Patient Data | Kiểm tra kiểu, missing, chuẩn hóa | Giai đoạn 3 |
| DL Prediction | Inference với model thật | Giai đoạn 1 |
| Rule-Based | Luật tường minh, flag | Giai đoạn 4 |
| KG/RAG | Truy vấn Neo4j, tìm bằng chứng và nguồn | Giai đoạn 2 |
| Coordinator | Điều phối, lỗi, tổng hợp | Giai đoạn 5 |
| Explanation | Báo cáo có căn cứ | Giai đoạn 6 |
| Monitoring | Theo dõi, audit, phiên bản | Giai đoạn 5 và 8 |
| RL | Chỉ chạy môi trường giả lập | Giai đoạn 9, không bắt buộc |

## Workflow chính thức (PDF §5)

`UI → API → Coordinator → Patient Data → DL Prediction → Rule-Based → KG/RAG → Coordinator (aggregate) → Explanation → Monitoring → Report`.

Coordinator **gọi** các agent và chuyển đầu vào/đầu ra; các agent không cần microservices riêng. Nếu dữ liệu sai, dừng trước DL. Kết quả chỉ là hỗ trợ tham khảo; tách biệt **model prediction**, **rule flags**, **evidence**, **report**.

## Hợp đồng thông điệp (PDF §6)

`request_id`, `agent`, `status`, `payload`, `evidence`, `version`. Bộ khung định nghĩa tại `backend/core/contracts.py`, hiện chưa dùng để chạy agent.

## Quy tắc tích hợp

- Nhánh **DL** chỉ đưa ra nhãn/score mà mô hình thực sự được huấn luyện hỗ trợ. Không suy diễn nhị phân thành phân loại loại 1/loại 2.
- Nhánh **KG/RAG** thật phải đọc Neo4j, có nguồn và nhận biết khi không có bằng chứng. File `.cypher` là script nạp graph, không phải graph đang chạy.
- **Rule-Based** không thay thế bác sĩ và chỉ chạy luật có căn cứ, được trình bày minh bạch.
- **RL** nếu có chỉ mô phỏng; không tác động điều trị thực.

## Thay đổi khi sinh viên bắt đầu từ con số 0

PDF giả định đã có mô hình DL và graph Neo4j. Nếu người làm chưa có, Giai đoạn 1 sẽ **xây/train mô hình tối thiểu thật, đánh giá rồi lưu artifact**, Giai đoạn 2 sẽ **tạo KG nhỏ có provenance và import Neo4j**. Việc này là điều chỉnh cách triển khai, không sửa kiến trúc agent của tài liệu.

## Giai đoạn 0 đang chạy gì?

Chỉ có Flask API khởi động, health/status endpoints, registry agent (chưa implement), `AgentMessage` và unit tests. **Không có pipeline dự đoán nào.**
