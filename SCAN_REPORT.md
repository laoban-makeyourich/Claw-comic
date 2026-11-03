# Báo cáo QA + scan thử — 2026-11-03 (cập nhật: handoff + chặn quảng cáo)

## Cập nhật mới: handoff captcha + chặn quảng cáo

QA mới: `python -m unittest discover -s tests` → **12/12 pass**
(5 test cũ + 7 test mới cho handoff và adblock).

### Handoff, test thật với Comic Book Plus bị 403

- Tab khớp (`dlid=15452` đang mở): tool in cảnh báo, ghi
  `handoff.json` với `status: awaiting_user` và đúng tab đó
  (`[Comic] Racket Squad in Action 4`), không mở tab mới, không
  tải lại, không đọc cookie/token.
- Tab không khớp (chỉ có `dlid=99999` và xkcd): tool báo rõ
  "no open tab matches", `matching_tab: null`, vẫn ghi handoff
  và yêu cầu mở đúng URL trước, đừng mở tab trùng.
- Resume bằng file HTML đã lưu sau khi tự pass: trích xuất đúng
  2 ảnh truyện, ảnh quảng cáo doubleclick bị lọc.
- Resume bằng `--resume-from handoff.json` (fetch lại 1 lần):
  vẫn `bot_wall HTTP 403` — đúng như dự kiến, vì pass captcha
  trong trình duyệt của người dùng không mở khóa session riêng
  của tool. Vì vậy đường resume đáng tin là `--html-file`.

### Chặn quảng cáo, test bằng fixture

Ảnh từ doubleclick, đường dẫn `/ads/`, ảnh trong khung
`ads-container`, ảnh bao bởi link tới popads đều bị loại;
chỉ còn ảnh truyện thật (p1, p2). Lớp lọc chạy ở trích xuất,
tải ảnh và render trình duyệt.

---

# Báo cáo QA + scan thử — 2026-11-03 (bản đầu)

Chế độ scan: `--metadata-only` — chỉ lấy tiêu đề / số ảnh / layout / trạng thái bot,
**không tải ảnh**. Các link dưới đây đều là nội dung đọc miễn phí hợp pháp
(xkcd CC BY-NC, WEBTOON Canvas miễn phí, Comic Book Plus public domain).

## QA nội bộ (không cần mạng)

```
python -m unittest discover -s tests -v
Ran 5 tests — OK
```

Bao phủ: vertical (4 ảnh, logo bị lọc), paginated (1 ảnh + link Next),
single_container (5 ảnh trong khung reader-viewer), phát hiện bot-wall
(Cloudflare "Just a moment" + HTTP 403), cắt ảnh dài thành 3 mảnh theo
khoảng trắng.

## Scan thật, thể loại 1: lướt dọc — WEBTOON Canvas, 5/5 OK, không bị chặn

| Tập | Layout tự phân loại | Ảnh tìm được | Trạng thái |
|---|---|---|---|
| Chilling Emblem — Reboot Announcement (ep 19) | vertical | 6 | ok |
| My Boyfriend is a Shark — On the List (ep 96) | vertical | 2 | ok |
| Lemonade — Ep. 2: Boys will be boys | vertical | 11 | ok |
| Midnight Poppy Land — Cover (ep 5) | vertical | 1 | ok |
| Limelight — 1.04 (ep 16) | vertical | 13 | ok |

Ảnh lấy từ khung duy nhất `div#_imageList` của WEBTOON. Lưu ý: số ảnh
thấp ở vài tập là đúng format của tập đó (Cover chỉ có 1 ảnh, tập
"On the List" là 2 dải dài), không phải lỗi thiếu ảnh.

## Scan thật, thể loại 2: chuyển từng trang — xkcd, 5/5 OK, không bị chặn

Mỗi link chạy với `--max-pages 3`: hệ thống tự đi theo link Next và
dừng đúng giới hạn.

| Bắt đầu từ | Layout | Trang đã lấy | Ảnh (đúng ảnh truyện, không lẫn ảnh site) |
|---|---|---|---|
| xkcd 1 — Barrel - Part 1 | paginated | 3 | barrel, tree, island |
| xkcd 2 — Petit Trees | paginated | 3 | tree, island, landscape |
| xkcd 3 — Island | paginated | 3 | island, landscape, blownapart |
| xkcd 4 — Landscape | paginated | 3 | landscape, blownapart, irony |
| xkcd 5 — Blown apart | paginated | 3 | blownapart, irony, girl_sleeping |

Container nhận diện: `div#comic`.

## Scan thật, thể loại 3: một khung chứa nhiều trang — 2 kết quả

### a) Comic Book Plus (public domain), 5/5 bị chặn — hệ thống DỪNG, không vượt

Tất cả 5 link (`dlid=15452, 82481, 60066, 18916, 69896`) đều trả
`status: bot_wall, bot_evidence: HTTP 403, images_found: 0`.
Đây là hành vi đúng thiết kế: phát hiện tường bot thì báo cáo và dừng,
không đổi UA/IP, không giải captcha, không thử đường vòng.

### b) Khung chứa nhiều trang, kiểm chứng bằng WEBTOON + fixture

Khung `div#_imageList` của WEBTOON chính là một khung chứa toàn bộ
dải ảnh của tập. Chạy lại 5 link trên với `--mode single_container`
(ép mode) trả về đúng cùng số ảnh: 6, 2, 11, 1, 13.
Fixture nội bộ cho layout này cũng pass (5 ảnh trong `reader-viewer`).
Ngoài ra `--split-long` xử lý trường hợp một ảnh dài chứa nhiều trang
xếp chồng, bằng cách cắt theo khoảng trắng.

## Bot có vượt được không? — Kết luận thẳng

- **WEBTOON + xkcd: không cần "vượt"** — request trình duyệt thật,
  delay, session ổn định là đủ, trả về `ok`, không gặp captcha.
- **Comic Book Plus: không vượt được, và không cố vượt** — 403 là
  tường bot, hệ thống dừng và báo cáo. Muốn đọc nội dung ở đó, cách
  hợp lệ là mở bằng trình duyệt thật của người dùng, không phải để
  tool tự tìm cách lách.

## Lỗi thật gặp trong lúc QA và đã sửa

1. **Brotli (`br`) làm hỏng toàn bộ trang**: `Accept-Encoding: gzip,
   deflate, br` khiến xkcd trả về byte nén mà requests không giải mã
   được → 0 ảnh, tiêu đề rỗng. Sửa: chỉ quảng cáo `gzip, deflate`.
2. **Ảnh site lẫn vào ảnh truyện (xkcd)**: fallback toàn trang lấy cả
   logo/store/news. Sửa: container có tên `comic/reader/viewer/chapter`
   được tin cậy ngay cả khi chỉ có 1 ảnh.
3. **WEBTOON dùng `data-url`, không dùng `src`**: `src` chỉ là ảnh
   trong suốt placeholder. Sửa: ưu tiên `data-url`, lọc
   `bg_transparency`, ưu tiên khung `#_imageList` thay vì wrapper lớn.
4. **"Next Episode" bị nhầm thành phân trang**: đi theo link này sẽ
   cào cả series. Sửa: bỏ qua link có chữ episode/chapter trong
   text khi tìm Next.
