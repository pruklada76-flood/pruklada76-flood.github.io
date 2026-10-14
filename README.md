# สถานการณ์น้ำ พฤกษ์ลดา ประชาอุทิศ 76

เว็บ: https://pruklada76-flood.github.io

หน้าเว็บสาธารณะ (ดูอย่างเดียว) แสดงฝน พยากรณ์ฝน ระดับน้ำ และเวลาก่อนน้ำขึ้นถนนของหมู่บ้าน

- `index.html` สร้างจากหน้า war-room ด้วย `scripts/build_public.py` อย่าแก้ตรง ๆ
- `data/*.json` ข้อมูลที่หน้าเว็บอ่าน
  - `scripts/fetch.py` รันอัตโนมัติทุก 15 นาทีผ่าน GitHub Actions (`.github/workflows/fetch.yml`): พยากรณ์ Open-Meteo, ฝนรวมรายวันจากแบบจำลอง, ระดับน้ำคลอง (thaiwater) ถ้ามี
  - `scripts/sync_from_db.py` คัดลอกค่าที่ทีม war-room บันทึก (ปั๊ม ประตูน้ำ ค่าที่อ่านได้) มาไว้ที่นี่
- เปิดใช้งาน: Settings → Pages → Deploy from a branch → `main` / `(root)`
