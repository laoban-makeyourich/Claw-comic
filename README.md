# Claw-comic

Hệ thống cào truyện theo link, hỗ trợ 3 dạng layout phổ biến:

1. **Lướt dọc (vertical scroll)** — một chương là một dải ảnh dài, cuộn xuống là hết chương.
2. **Chuyển từng trang (paginated)** — mỗi lần chỉ có 1–2 ảnh, phải bấm Next / sang trang mới để lấy tiếp.
3. **Một khung chứa nhiều trang (single container)** — toàn bộ ảnh của chương nằm trong một khung reader duy nhất (ví dụ chế độ "all pages"), hoặc một ảnh dài chứa nhiều trang xếp chồng lên nhau (xem `--split-long`).

## Cơ chế handoff khi gặp captcha (mới)

Khi hệ thống không pass được captcha / tường bot, nó **không tự vượt**:

1. Dừng lại, in cảnh báo và ghi `handoff.json` với trạng thái `awaiting_user`.
2. Kiểm tra danh sách tab đang mở (`--tabs-file tabs.json`, dạng `[{"window":..., "title":..., "url":...}]`). Chỉ khi có một tab chứa **đúng URL chương cần scan** (bỏ qua tham số tracking như `utm_*`, `serviceZone`) thì handoff mới được phép tới tab đó. Không khớp → báo rõ "chưa tìm thấy tab khớp, mở đúng URL trước, đừng mở tab trùng".
3. Người dùng tự tick captcha trong đúng tab đó, chờ Success, **không tải lại, không đóng tab, không mở tab trùng**.
4. Scan tiếp bằng 1 trong 2 cách, không dùng cookie/token của trình duyệt người dùng:
   - Cách chắc chắn: lưu trang đã pass thành file HTML rồi chạy `--html-file <file>`. Vì pass captcha trong trình duyệt của bạn không tự mở khóa session riêng của tool.
   - Cách thử lại: `--resume-from handoff.json` — tool fetch lại đúng 1 lần, nếu vẫn bị chặn thì dừng tiếp, không lặp.

```bash
# Gặp bot wall, có danh sách tab đang mở:
python -m claw_comic.cli "https://example.com/chapter-1" --metadata-only --handoff --tabs-file tabs.json --out out/chapter-1
# Sau khi bạn tự pass captcha trong tab đã khớp, lưu trang rồi:
python -m claw_comic.cli "https://example.com/chapter-1" --metadata-only --html-file saved-chapter.html
```

## Chặn quảng cáo (mới)

Ảnh quảng cáo không bao giờ lọt vào danh sách ảnh truyện, qua 3 lớp:

- Host quảng cáo: doubleclick, googlesyndication, popads, adcash, propellerads, taboola, outbrain, mgid... (xem `claw_comic/adblock.py`).
- Đường dẫn quảng cáo: `/ads/`, `ad-banner`, `popunder`, `sponsored`, tracking pixel.
- Khung quảng cáo: ảnh nằm trong div có id/class `ads`, `advertisement`, `sponsored`, `popunder`, hoặc link bao ngoài trỏ tới host quảng cáo.

Lớp này chạy ở cả trích xuất (`extract.py`), tải ảnh (`download.py` — lưới an toàn cuối) và chế độ trình duyệt (`browser.py` — chặn luôn request tới host quảng cáo khi render).

## Nguyên tắc chống bot — và giới hạn

Claw-comic chỉ dùng các cách hợp lệ, giống một trình duyệt thật đang đọc chậm:

- Session `requests` với User-Agent của Chrome/Firefox/Safari thật, `Accept-Language`, `Referer` đúng domain của chương.
- Scroll / render bằng trình duyệt thật khi có Playwright (để tải ảnh lazy-load, nội dung render bằng JS).
- Retry với backoff lũy thừa khi gặp `429` / `5xx`, tôn trọng header `Retry-After`, delay giữa các request, tối đa 1 request tại một thời điểm.
- Tự phát hiện tường bot và **dừng lại, không vượt qua**: Cloudflare "Just a moment", trang captcha, "Access denied", "Please verify you are human" → trạng thái `bot_wall` trong báo cáo, không tự giải captcha, không giả mạo token, không bẻ khóa đăng nhập hay DRM.

Nếu một trang trả về `bot_wall`, cách hợp lệ duy nhất là người dùng tự mở trang đó trong trình duyệt của mình, xác minh thủ công, rồi mới quay lại — giống quy trình handoff xác minh thủ công đã dùng trước đây.

## Chỉ dùng cho nội dung hợp lệ

Chỉ cào nội dung bạn sở hữu, được chủ sở hữu cho phép, thuộc phạm vi công cộng (public domain) hoặc được cấp phép tự do. Đừng dùng tool này để tải trọn bộ truyện có bản quyền từ các trang lậu. Chế độ quét mặc định là `--metadata-only`: chỉ lấy tiêu đề, số ảnh, layout, trạng thái bot — **không tải ảnh**.

## Cài đặt

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Playwright là tùy chọn, chỉ cần khi trang render bằng JS / lazy-load nặng:

```bash
.venv/bin/pip install playwright
.venv/bin/playwright install chromium
```

## Cách dùng

Quét thử một link (không tải ảnh, an toàn nhất để kiểm tra bot-wall):

```bash
.venv/bin/python -m claw_comic.cli "https://example.com/manga/chapter-1" --metadata-only
```

Cào một chương (chỉ khi bạn có quyền với nội dung đó):

```bash
.venv/bin/python -m claw_comic.cli "https://example.com/manga/chapter-1" --out out/chapter-1
```

Ép dạng layout, giới hạn số trang, dùng trình duyệt thật:

```bash
.venv/bin/python -m claw_comic.cli "https://example.com/manga/chapter-1" \
  --mode paginated --max-pages 50 --browser --out out/chapter-1
```

Ảnh dài chứa nhiều trang xếp chồng: cắt theo khoảng trắng giữa các trang:

```bash
.venv/bin/python -m claw_comic.cli "https://example.com/manga/chapter-1" \
  --split-long --out out/chapter-1
# cần Pillow: pip install Pillow
```

Quét hàng loạt link từ file (mỗi dòng một URL):

```bash
.venv/bin/python -m claw_comic.cli --scan-file tests/urls_vertical.txt --metadata-only
```

## Output

- `report.json` trong thư mục out (hoặc in ra stdout với `--metadata-only`): `url`, `title`, `layout`, `images_found`, `pages_fetched`, `status` (`ok` / `bot_wall` / `error`), `bot_evidence`, `next_url`.
- Ảnh tải về đặt tên `001.jpg`, `002.jpg`, ... theo đúng thứ tự xuất hiện / thứ tự trang.
- `report.json` cũng ghi rõ trang nào bị chặn, để không nhầm "không có ảnh" với "bị chặn".

## Phân loại layout — heuristic

| Dấu hiệu | Kết luận |
|---|---|
| 1–2 ảnh/trang + có link Next | `paginated` |
| Nhiều ảnh trong một container, không có Next, container mang tên reader/viewer/chapter | `single_container` |
| Nhiều ảnh xếp dọc trong một trang chương, không có Next | `vertical` |
| Không đủ dấu hiệu | `unknown` (vẫn trả danh sách ảnh tìm được) |

Bộ lọc ảnh loại bỏ logo, avatar, banner, quảng cáo theo tên file / class / id (`logo`, `avatar`, `banner`, `ads`, `icon`, `thumbnail` khi đi kèm các từ trên), và chỉ giữ `.jpg/.jpeg/.png/.webp/.gif/.avif`.

## QA

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Test dùng fixture HTML nội bộ, không cần mạng, bao phủ cả 3 layout + phát hiện bot-wall + cắt ảnh dài.
