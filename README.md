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

---

# Bảng tag chung → GX Works3 / KV STUDIO / Weintek EasyBuilder Pro

Viết danh sách tag **một lần** trong Excel/CSV. Công cụ kiểm tra địa chỉ rồi xuất file import cho từng phần mềm.

```bash
python -m dienkit.tags examples/tags.csv --plc PLC_MITSU=fx5 --plc PLC_KV=kv -o tags_out
```
`--plc TÊN=DÒNG`: dòng PLC là `fx5` (FX5/FX3, X/Y đánh số bát phân), `iqr` hoặc `q` (X/Y hệ 16), `kv` (Keyence KV).
`TÊN` phải trùng với tên thiết bị PLC đã khai báo trong EasyBuilder (System Parameters → Device).

## Bảng tag
| cột | ý nghĩa |
|---|---|
| `tag` | tên tag, chỉ dùng chữ không dấu, số và `_` (bắt buộc) |
| `dia_chi` | `X10`, `Y0`, `M100`, `D200`, `D30.5` (bit của word), `R1015`, `MR500`, `DM100`… (bắt buộc) |
| `kieu` | `BOOL` `INT` `UINT` `WORD` `DINT` `UDINT` `DWORD` `REAL`; để trống thì bit → BOOL, thanh ghi → INT |
| `mo_ta` | chú thích (có dấu được) |
| `plc` | tên PLC khi dự án có nhiều PLC; để trống thì dùng PLC đầu tiên khai báo trong `--plc` |
| `hmi` | `x` = đưa tag sang HMI. Nếu không có cột này thì mọi tag đều sang HMI |
| `rw` | `R` (HMI chỉ đọc) hoặc `RW` (mặc định) |

## Những gì được kiểm tra (báo LỖI → không xuất file, trừ khi thêm `--force`)
- Địa chỉ sai hệ đếm: FX5 không có `X8`/`X9`; Keyence `R016` sai vì 2 số cuối là bit 00–15.
- Tiền tố không có ở dòng PLC đó, ví dụ `DM` trên Mitsubishi.
- Kiểu dữ liệu không hợp với thiết bị: `M10` khai báo INT, `D200` khai báo BOOL.
- Dữ liệu 32-bit (REAL/DINT) chồng lên tag khác, ví dụ REAL ở D100 trong khi D101 là tag khác.
- Trùng tên tag, tên có dấu cách hoặc bắt đầu bằng số.
- CẢNH BÁO (vẫn xuất file): hai tag cùng địa chỉ, bit nằm trong word đã khai báo, dữ liệu 32-bit đặt ở địa chỉ lẻ.

Kết quả kiểm tra nằm trong `tags_out/kiem_tra_tag.xlsx` (đỏ = lỗi, vàng = cảnh báo).

## File xuất ra
| file | nhập vào |
|---|---|
| `<PLC>_gx3_global_label.csv` | GX Works3 → nhãn toàn cục (Global Label) |
| `<PLC>_gx3_device_comment.csv` | GX Works3 → chú thích thiết bị (Device Comment) |
| `<PLC>_kv_device_comment.csv` | KV STUDIO → chú thích thiết bị |
| `weintek_address_tags.csv` | EasyBuilder Pro → Address Tag Library → Import CSV |

## ⚠️ Định dạng file import — đọc trước khi dùng
Cột, dấu phân cách và encoding của file import **thay đổi theo phiên bản và ngôn ngữ** phần mềm.
Định dạng mặc định ở trên **chưa được thử trên phần mềm thật**. Cách chắc chắn nhất:
1. Trong phần mềm của bạn, tạo 1–2 tag/chú thích bằng tay rồi **Export** ra CSV.
2. Truyền file đó vào: `--template-gx3 nhan.csv`, `--template-comment chuthich.csv`, `--template-weintek hmi.csv`.
3. Công cụ giữ nguyên dòng đầu, thứ tự cột, dấu phân cách (tab/phẩy) và encoding (UTF-8/UTF-16/Shift-JIS)
   của file mẫu. Cột nào không nhận ra (giá trị đầu, ngôn ngữ khác…) sẽ để trống.
   Tên cột được nhận ra bằng tiếng Anh, tiếng Nhật hoặc tiếng Việt.

Tag dạng bit của word (`D30.0`): sau khi import vào EasyBuilder, kiểm tra lại cách phần mềm hiểu địa chỉ.
