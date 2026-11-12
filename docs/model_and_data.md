# Kiểm kê dữ liệu và model — Giai đoạn 0

Tài liệu kiến trúc của giảng viên nói đã có model Deep Learning và đồ thị Neo4j. Tuy nhiên khi **khởi tạo project mới hoàn toàn**, có thể chưa có chúng. Ghi `MISSING` là bình thường; **không cần tự tạo giả file model hoặc giả graph để qua Phase 0**.

| Hạng mục | Trạng thái (AVAILABLE / MISSING) | Đường dẫn và ghi chú |
|---|---|---|
| Dataset công khai / phù hợp để xây model | MISSING | |
| Notebook/script huấn luyện DL | MISSING | |
| Model DL đã huấn luyện | MISSING | |
| Bộ preprocessing tương ứng | MISSING | |
| Danh sách và thứ tự feature model | MISSING | |
| Mapping nhãn đầu ra DL (vd. nhị phân) | MISSING | |
| Đánh giá mô hình (metrics) | MISSING | |
| `DB_diabet.cypher` hoặc script Neo4j thật | MISSING | |
| Danh sách nguồn tri thức và citations | MISSING | |
| Neo4j server / Neo4j Aura DB instance | MISSING | |

## Điều kiện chuyển Phase 1

- Bảng trên được rà soát và biết rõ còn thiếu gì; **không bắt buộc phải có tất cả**.
- Nếu thiếu mô hình DL: giai đoạn 1 chọn dataset và tạo một model thật, có kiểm thử rõ ràng.
- Nếu thiếu Neo4j/Cypher: giai đoạn 2 tạo knowledge graph tối thiểu có trích nguồn và import Neo4j.
- Giữ nguyên vai trò agent và luồng chuẩn theo PDF.

## Cập nhật Giai đoạn 1

- Tải dataset public `diabetes_prediction_dataset.csv` vào `data/raw/` theo `docs/GIAI_DOAN_1_HUONG_DAN.md`.
- Train bằng `backend/training/train_dl.py`, artefact + preprocessor trong `models/diabetes_mlp_v1.joblib`.
- Schema và phiên bản trong `config/model_manifest.json`; test metrics trong `outputs/dl_training_metrics.json`.
- **Không** tự điền `AVAILABLE` vào bảng phía trên khi các file chưa thực sự tồn tại.
