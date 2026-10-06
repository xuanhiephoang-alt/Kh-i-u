# dienkit — tính tải, chọn cáp/aptomat, lập bảng vật tư & chi phí

Đầu vào: danh sách tải (CSV/Excel) + bảng giá vật tư (Excel, CSV, PDF — dùng được nhiều file).
Đầu ra: file Excel gồm sheet **Tính tải** và sheet **Vật tư** (đơn giá, thành tiền là công thức, có VAT).

```bash
pip install -r requirements.txt
python -m dienkit examples/loads.csv -p examples/bang_gia_mau.xlsx examples/bang_gia_cap_mau.pdf -o bom.xlsx
python -m unittest discover -s tests
```

## File danh sách tải
Cột: `ten,kw,pha,dien_ap,cosphi,hieu_suat,chieu_dai_m,kd,dong_co,so_loi` (xem `examples/loads.csv`).
`dong_co=x` → aptomat chọn theo 1,25×Ib. `so_loi` bỏ trống → 3 pha: 4 lõi, 1 pha: 3 lõi.

## Tùy chọn
`--method B1|C` cách lắp đặt cáp · `--ambient` nhiệt độ môi trường · `--grouping` hệ số nhóm cáp ·
`--max-vdrop` sụt áp tối đa (%) · `--ks` hệ số đồng thời · `--vat` · `--cable-prefix CVV|CXV`

## Cách đọc bảng giá
- Tự tìm dòng tiêu đề (Tên hàng / ĐVT / Đơn giá, có hoặc không dấu), chấp nhận số kiểu `1.250.000` hoặc `1,250,000đ`.
- PDF: ưu tiên đọc bảng có đường kẻ; nếu không có thì đọc từng dòng dạng `tên … ĐVT … giá`.
  **PDF dạng ảnh scan không đọc được** (cần OCR).
- Tên yêu cầu sinh ra theo dạng `MCB 3P 20A`, `MCCB 3P 100A`, `CVV 4x10`. Bảng giá của bạn phải ghi tên
  tương tự (hoặc dùng `--cable-prefix`). Đơn vị phải trùng nguyên (`10A` ≠ `10kA`, `4x10` ≠ `3x10`).
- Mặt hàng không khớp để trống giá và tô đỏ; khớp chưa đầy đủ tô vàng — **luôn kiểm tra lại sheet Vật tư**.

## Giới hạn quan trọng
- Bảng dòng điện cho phép là giá trị **tham khảo** (IEC 60364-5-52, Cu/PVC 70°C). Hãy đối chiếu TCVN 9207 /
  catalogue nhà sản xuất trước khi dùng cho hồ sơ thiết kế, hoặc truyền bảng riêng qua `ampacity`.
- Chưa tính: dòng khởi động động cơ, ngắn mạch/độ nhạy bảo vệ, phối hợp bảo vệ, cáp XLPE/nhôm, tụ bù, máy biến áp.
- Chỉ chọn aptomat theo dòng định mức; chưa chọn khả năng cắt (kA) và dòng chỉnh định.
