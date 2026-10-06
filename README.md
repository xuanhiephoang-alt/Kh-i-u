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

---

# Sinh bản vẽ đấu nối I/O PLC (DXF + PDF)

```bash
python -m dienkit.iodraw examples/io_list.csv -o io.dxf --pdf io.pdf --project "Tên công trình" --drawer "Tên"
```
Mở `io.dxf` bằng AutoCAD / ZWCAD / LibreCAD; PDF để in hoặc gửi khách hàng. Xem mẫu: `examples/io_mau.pdf`.

## Bảng I/O (CSV/Excel)
| cột | bắt buộc | ý nghĩa |
|---|---|---|
| `dia_chi` | có | địa chỉ PLC: `X0`, `Y10`, `R000`, `D8000`… (không được trùng) |
| `loai` | có | `DI` / `DO` / `AI` / `AO` |
| `tag`, `mo_ta` | | tên tag, mô tả (có dấu được) |
| `thiet_bi` | | chọn ký hiệu: nút nhấn/NO, NC/nút dừng/E-stop, cảm biến, đèn, rơ le/contactor, van, 4-20mA |
| `dau_day` | | số domino; để trống thì tự đánh XT1 (DI), XT2 (AI), XT3 (DO), XT4 (AO) |
| `module` | | tên module; đổi module sẽ sang tờ mới |

Mỗi tờ A3 có tối đa 16 điểm và khung tên. Các tờ đặt cạnh nhau trong model space, cách nhau 450 mm.
Layer: `WIRE`, `SYMBOL`, `TERMINAL`, `PLC`, `TEXT`, `FRAME`. Ký hiệu là block, nên có thể sửa một lần cho toàn bộ bản vẽ.

## Chiều nguồn — chọn theo đúng model PLC
- `--di pnp` (mặc định): thiết bị lấy +24V, chân COM/S/S nối 0V. Dùng `--di npn` khi chân S/S nối +24V.
- `--do source` (mặc định, ví dụ FX5U-…MT/ESS): COM +24V, tải về 0V. Dùng `--do sink` cho FX5U-…MT/ES.
- Nếu cột `thiet_bi` ghi PNP/NPN ngược với kiểu đã chọn, chương trình in CẢNH BÁO.

## Giới hạn
- Đây là sơ đồ đấu nối dạng "một dòng cho một điểm". Cảm biến 3 dây và AI 4 dây chỉ vẽ dây tín hiệu,
  chưa vẽ dây nguồn và dây 0V riêng của từng thiết bị.
- Chưa vẽ: mạch động lực, cầu chì/nguồn 24V, đầu ra relay có nhiều COM riêng, sơ đồ module truyền thông.
- Ký hiệu đơn giản hóa theo kiểu IEC. Kiểm tra lại theo tiêu chuẩn bản vẽ của công ty trước khi phát hành.
