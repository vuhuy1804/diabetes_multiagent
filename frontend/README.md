# Frontend React/Vite — Giai đoạn 7

Giao diện học phần **Hệ đa Agent cho bệnh tiểu đường** (PTIT). Giao diện chỉ sử dụng **Flask Backend đã hoàn thành ở Giai đoạn 6**, không có model giả, không có cơ sở tri thức giả.

## Khởi động (Windows PowerShell)

**Terminal 1 (thư mục gốc project):**

```powershell
.\.venv\Scripts\python.exe backend/app.py
```

**Terminal 2:**

```powershell
cd frontend
node --version
npm install
npm run dev
```

Mở `http://127.0.0.1:5173`.

- Vite chuyển `/api/*` sang `http://127.0.0.1:5000/api/*` trong chế độ development.
- **Không thêm CORS cho Flask chỉ để phục vụ development.**
- Không tạo `.env` cho frontend nếu bạn dùng proxy mặc định.
- Ở chế độ build/deploy, cần reverse proxy cho `/api`, hoặc Backend hỗ trợ CORS nếu dùng hai origin khác nhau.

## Lệnh kiểm thử

```powershell
npm test        # 36 test JavaScript độc lập, không cần Neo4j
npm run build   # Vite build sản phẩm, tạo frontend/dist/
npm run smoke:api # Cần Flask+DL+Neo4j thật; gọi API thực tế với fixture học phần
```

Nếu PowerShell chặn `npm`, dùng `npm.cmd install`, `npm.cmd run dev`, `npm.cmd test`.

## Chức năng

1. Nhập 8 đặc trưng đúng với schema mô hình (được kiểm tra trước khi gửi).
2. Bật/tắt câu hỏi KG/RAG.
3. `POST /api/report/generate` thực thi luồng Coordinator 5 Agent.
4. Hiển thị nhãn DL/điểm kỹ thuật tách biệt với cờ luật, fact Neo4j, URL nguồn, giới hạn, trace từng Agent.
5. Hiển thị trạng thái thực tế từ `GET /api/health`, có nút kiểm tra lại.
6. Nạp fixture mẫu; xóa biểu mẫu; sao chép văn bản báo cáo bằng quyền trình duyệt.

## Bảo mật và giới hạn

Không có tính năng lưu lịch sử ở frontend, không dùng `localStorage`, cookie tùy chỉnh hay SDK phân tích. Dữ liệu vẫn được gửi đến Flask khi nhấn **Tạo báo cáo**. Chỉ nhập dữ liệu giả lập hoặc được phép xử lý. Đây là **demo học thuật, không dùng để chẩn đoán, kê đơn hoặc điều trị**.

Tài liệu chi tiết: `../docs/GIAI_DOAN_7_HUONG_DAN.md`.
