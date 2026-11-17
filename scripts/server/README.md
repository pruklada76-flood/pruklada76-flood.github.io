# ดึงระดับน้ำคลองรางจาก (WL.RJK.01) และฝนสถานี สนข.ทุ่งครุ (RF.TKU.01) จากเครื่องเซิร์ฟเวอร์หมู่บ้าน

เว็บ กทม. (weather.bangkok.go.th) ปิดกั้นเครื่องบนคลาวด์ จึงให้เครื่องเซิร์ฟเวอร์ของหมู่บ้านดึงแทน ทุกชั่วโมง
แล้วส่งไฟล์ `data/canal-rjk.json` (ระดับน้ำคลอง) และ `data/rain-tku.json` (ฝนทุก 5 นาที สะสมตั้งแต่ 00:00 น.) เข้ามาใน repo นี้ หน้าเว็บสาธารณะอ่านไฟล์นี้และแสดงในกราฟระดับน้ำคลองทันที

- ทดสอบแล้วบนเซิร์ฟเวอร์หมู่บ้าน (CentOS 7, Python 3.6.8) อ่านได้ 575 ค่า
- `bma_canal.py` อ่านตาราง 48 ชม. (ทุก 5 นาที) จากหน้า StationDetail?id=103 ใช้ Python มาตรฐานล้วน ตรวจใบรับรอง TLS เสมอ
- `canal_push.sh` ใช้ใน cron: ดึง → รวมกับข้อมูลเดิม (เก็บ 7 วัน) → commit → push ไป `main` ด้วย deploy key

## ติดตั้ง (ครั้งเดียว)

```bash
sudo yum install -y git python3            # CentOS/RHEL (Ubuntu/Debian ใช้ apt install) ถ้ามีอยู่แล้วข้ามได้
ssh-keygen -t ed25519 -f ~/.ssh/pruklada_deploy -N "" -C canal-bot
cat ~/.ssh/pruklada_deploy.pub              # คัดลอกบรรทัดนี้
```

เปิด https://github.com/pruklada76-flood/pruklada76-flood.github.io/settings/keys/new
วางกุญแจ ตั้งชื่อ `village-server` ติ๊ก **Allow write access** แล้วกด Add key (กุญแจนี้เขียนได้เฉพาะ repo นี้)

ตั้งชื่อเล่น `github-canal` ให้ SSH ใช้กุญแจนี้ (ใช้ได้กับ git รุ่นเก่าบน CentOS 7 ด้วย) แล้ว clone

```bash
cat >> ~/.ssh/config <<'CFG'
Host github-canal
  HostName github.com
  User git
  IdentityFile ~/.ssh/pruklada_deploy
  IdentitiesOnly yes
CFG
chmod 600 ~/.ssh/config
git clone git@github-canal:pruklada76-flood/pruklada76-flood.github.io.git ~/canal-bot
```

## ทดสอบ

```bash
python3 -I ~/canal-bot/scripts/server/bma_canal.py fetch > /dev/null   # ต้องขึ้น "NNN readings, newest ..."
~/canal-bot/scripts/server/canal_push.sh                               # ต้องขึ้น "pushed NNN new readings"
```

## ตั้งเวลา (crontab -e)

```
7 * * * * $HOME/canal-bot/scripts/server/canal_push.sh >> $HOME/canal-bot.log 2>&1
```

อยากถี่ขึ้นตอนฝนตก เปลี่ยน `7 * * * *` เป็น `*/15 * * * *`

## ถ้ามีปัญหา

- `CERTIFICATE_VERIFY_FAILED`: อย่าปิดการตรวจใบรับรอง ให้ดาวน์โหลดใบรับรองตัวกลางของเว็บ กทม. เป็นไฟล์ .pem แล้วใส่ใน crontab ว่า `CANAL_CA=/path/ca.pem` หน้าคำสั่ง
- `Permission denied (publickey)`: ยังไม่ได้ติ๊ก Allow write access หรือวางกุญแจผิด
- ต่อพอร์ต 22 ออกไป GitHub ไม่ได้: ใน `~/.ssh/config` ส่วน `Host github-canal` เปลี่ยนเป็น `HostName ssh.github.com` และเพิ่ม `Port 443`
- `no readings found`: หน้าเว็บ กทม. เปลี่ยนรูปแบบ หรือขึ้นหน้าตรวจบอท ส่ง log ให้ทีมดู

## ห้องสั่งการ (war room)

ห้องสั่งการไม่ได้อ่านไฟล์นี้เอง ระบบดึงข้อมูลรายชั่วโมงสามารถอ่าน
`https://pruklada76-flood.github.io/data/canal-rjk.json` แล้วเพิ่มแถวที่ยังไม่มี (id `wl-YYYYMMDDHHMM` ชุดเดียวกับการนำเข้า CSV จึงไม่ซ้ำ)
