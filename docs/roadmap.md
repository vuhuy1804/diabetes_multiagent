# Lộ trình từng giai đoạn và điều kiện dừng

**Nguyên tắc:** hoàn thành test → người dùng xác nhận → mới gửi code ZIP giai đoạn kế tiếp. Trong một lần chỉ triển khai **một** giai đoạn.

| Giai đoạn của chúng ta | Tương ứng PDF §9 | Công việc chính | Điều kiện chuyển |
|---|---|---|---|
| **0** | Chuẩn bị thêm trước Phase 1 | Khởi tạo Flask, cấu trúc, hợp đồng agent, kiểm thử, kiểm kê tài nguyên | Unit tests PASS, API health OK, xác nhận người dùng |
| **1** | Phase 1 | Có model DL thật (tận dụng nếu có, hoặc huấn luyện mô hình tối thiểu), lưu preprocess và DL Agent | So sánh inference gốc với service; test prediction PASS |
| **2** | Phase 2 | Neo4j KG có nguồn và KG/RAG Agent | Truy vấn graph thật + evidence, test PASS |
| **3** | Phase 3 | Patient Data Agent | test input hợp lệ/thiếu/sai PASS |
| **4** | Phase 4 | Rule-Based Agent | test mỗi rule, rule ID, flag PASS |
| **5** | Phase 5 | Coordinator Agent + audit tối thiểu | Luồng điều phối + lỗi + trace PASS |
| **6** | Phase 6 | Explanation Agent dựa trên evidence | Báo cáo có đủ 4 phần và không bịa nguồn |
| **7** | Phase 7 | Giao diện React/Vite + API đánh giá | Người dùng thử demo qua UI PASS |
| **8** | Phase 8 + lớp Audit trong §2 | Monitoring/Audit Agent tối thiểu, unit/integration tests và báo cáo đánh giá | Audit metadata không lưu dữ liệu bệnh nhân; kịch bản happy/invalid/Neo4j down PASS |
| **9 (tùy chọn)** | Phase 9 | RL Agent trong mô phỏng độc lập | Chỉ nếu có yêu cầu/đủ thời gian |

**Không dựng giao diện chính ở Phase 0**, không giả kết quả dự đoán, không coi Neo4j đã tích hợp nếu chưa có truy vấn thực tế.

**Cập nhật tiến độ 12/11/2026:** Giai đoạn 0–5 đã được người học xác nhận PASS (Giai đoạn 5: 120/120 tests). Giai đoạn 6 đã bàn giao dưới dạng bản vá, yêu cầu nghiệm thu 180 tests trên máy người học. Chưa triển khai Giai đoạn 7.
