# Rule-Based Agent — Giai đoạn 4

Rule Engine gồm **7 luật tường minh và có thứ tự** trong `rule_engine.py`.
Đây là luật **mô phỏng học thuật**; dùng đầu vào từ `Patient Data Agent` và payload dự đoán từ `DL Prediction Agent`.

- `RB001`–`RB003`: cờ tham khảo HbA1c/glucose, có nguồn NIDDK; không chẩn đoán.
- `RB004`: thông tin lịch sử hút thuốc thiếu trong dataset.
- `RB005`–`RB007`: giải thích giới hạn nhãn dự đoán, trường hợp cần đối chiếu và score chưa hiệu chuẩn.

Mọi luật đều có `rule_id`, điều kiện kích hoạt, `severity`, lời giải thích, nguồn. Kết quả đi theo `core.contracts.AgentMessage`.
Không lưu dữ liệu bệnh nhân, không dùng Neo4j/LLM trong Rule Agent và không kê thuốc/đề xuất điều trị.

Xem hướng dẫn đầy đủ tại `docs/GIAI_DOAN_4_HUONG_DAN.md`.
