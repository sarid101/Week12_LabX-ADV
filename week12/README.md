# Week 12 — LabX ADV: Agentic Communication Workflows (Advanced Email & SMS)

**ชื่อ:** สาริษฐ์ บุตรช่วง  **รหัสนักศึกษา:** 663380365-3
**รายวิชา:** SP352301 Script Programming (1/2569)

`CommunicationAgent` อ่าน workflow จาก `configs/comm_pipeline_config.json` แล้วทำงานตามลำดับ
ใช้ `context` กลางในการเติมค่าลง template (`{report_date}`, `{sales_figure:,.2f}` …) และบันทึกทุกขั้นลง audit report

## Workflow

| # | Task | type | สิ่งที่ทำ |
|---|------|------|----------|
| 1 | Send Daily Sales Report Email | `send_email` | ส่งรายงานถึง To + Cc พร้อมแนบ `sales_report.pdf` และ `summary_data.xlsx` |
| 2 | Send Sales Alert SMS | `send_sms` | ส่งข้อความสั้นยอดขายผ่าน email-to-SMS gateway |
| 3 | Simulate Incoming Request Email | `send_email` | ส่งเมล "Data Request … - Urgent" หาตัวเองพร้อมไฟล์แนบ |
| 4 | Process Incoming Data Requests | `process_inbox` | ค้นเมลที่ยังไม่อ่านจากตัวเองที่มีคำว่า "Data Request" → โหลดไฟล์แนบไป `data/incoming_attachments/` → mark as read → ใช้ rules |

**Rules ใน process_inbox**
- ถ้า subject มี `Urgent` **และ** มีไฟล์แนบ → ส่ง SMS แจ้งเตือน
- ถ้า body มี `new data processing` → ตอบกลับอัตโนมัติ `Re: … - Received & Processing`

## Screenshots

### ทดสอบแบบ DEMO (ไม่ได้ส่งเมลจริง)
`python main.py --demo` รันทุก task ครบ โดยบันทึกเมลเป็นไฟล์ `.eml` ใน `data/demo_outbox/` แทนการส่งจริง

![demo terminal run](screenshots/demo_terminal_run.png)
![demo outbox](screenshots/demo_outbox_emails.png)

### รันจริงกับ Gmail
<!-- ใส่ภาพหลังรัน python main.py ด้วย .env ของตัวเอง -->
![Gmail - Daily Sales Report](screenshots/gmail_daily_report.png)
![Gmail - Data Request + Auto reply](screenshots/gmail_request_and_reply.png)
![Gmail - SMS alert](screenshots/gmail_sms_alert.png)
![Terminal - live run](screenshots/live_terminal_run.png)

## วิธีรัน

```bash
pip install -r requirements.txt
python create_sample_files.py      # สร้าง data/reports/sales_report.pdf และ summary_data.xlsx

python main.py --demo              # ทดสอบ workflow โดยไม่ส่งเมลจริง

cp .env.example .env               # Windows: copy .env.example .env  แล้วแก้ค่าในไฟล์
python main.py                     # ส่งเมลจริงผ่าน Gmail
```

**Gmail App Password:** เปิด 2-Step Verification ก่อน แล้วไปที่ Google Account → Security → App passwords
สร้างรหัส 16 ตัวมาใส่ใน `SENDER_APP_PASSWORD` (รหัสผ่าน Gmail ปกติใช้ไม่ได้) และต้องเปิด IMAP ใน Gmail Settings → Forwarding and POP/IMAP

**SMS:** ผู้ให้บริการมือถือในไทยไม่มี email-to-SMS gateway จึงตั้ง `TEST_SMS_PHONE_NUMBER` เป็นอีเมลที่เปิดดูบนมือถือได้แทน
(โค้ดรองรับทั้งเบอร์ + `carrier_name` แบบ US และที่อยู่เต็มรูปแบบ `number@gateway`)

## สิ่งที่แก้จากโค้ดตัวอย่างในใบงาน

1. **`${ENV_VAR}` ใน config ไม่เคยถูกแทนค่า** – โค้ดเดิมส่ง `${SENDER_EMAIL}` เข้า `str.format` ตรง ๆ จึงเกิด `KeyError` → เพิ่ม `expand_env_vars()` แทนเฉพาะชื่อตัวพิมพ์ใหญ่จาก `.env` (`${sales_figure:.2f}` ยังเป็นเครื่องหมาย $ + ตัวเลขเหมือนเดิม)
2. **config ตรวจไม่ผ่าน** – validator เดิมหา `to` ใน `parameters` แต่ config เก็บไว้ใน `parameters.recipients.to`
3. **IMAP ใช้ sequence number แล้วตัดการเชื่อมต่อระหว่าง search กับ fetch** → เปลี่ยนเป็น `UID SEARCH / UID FETCH / UID STORE` บน connection เดียว และ quote ค่าที่มีเว้นวรรค (`SUBJECT "Data Request"`)
4. **เมลที่เพิ่งส่งหาตัวเองยังไม่ถึง inbox** → `process_inbox` รอและค้นซ้ำ (`wait_seconds`, `max_retries`)
5. **ตอบกลับวนซ้ำ** – เมลตอบกลับมีคำว่า "Data Request" ด้วย รอบถัดไปจะถูกประมวลผลอีก → ข้ามเมลที่ขึ้นต้นด้วย `Re:` (`exclude_subject_prefix`)
6. **template `{attachments_meta.0.filepath}` ใช้ไม่ได้กับ `str.format`** → เปลี่ยนเป็น `{attachments_meta[0][filename]}`
7. ไฟล์แนบที่ไม่มีจริงจะถูกข้ามพร้อม WARNING (conditional attachments), Cc ซ้ำกับ To ถูกตัดออก, ที่อยู่อีเมลใน audit report ถูก mask
8. เพิ่ม **DEMO mode** (`--demo`) และ `create_sample_files.py`

## โครงสร้างโฟลเดอร์

```
week12/
├── src/
│   ├── communication_agent.py   # ตัว agent: dispatch task, context, rules, audit
│   ├── email_tasks.py           # SMTP ส่งเมล / IMAP ค้น-อ่าน-โหลดไฟล์แนบ
│   ├── demo_email_tasks.py      # DEMO mode: เก็บเมลเป็น .eml + inbox จำลอง
│   ├── sms_tasks.py             # ส่ง SMS ผ่าน email gateway
│   ├── config_parser.py         # โหลด/ตรวจ config + แทน ${ENV_VAR}
│   ├── template_renderer.py     # เติมค่า {placeholder}
│   └── utils.py                 # logging, .env, audit entry
├── configs/comm_pipeline_config.json
├── data/reports/                # sales_report.pdf, summary_data.xlsx
├── screenshots/
├── .env.example                 # ตัวอย่าง .env (ไฟล์ .env จริงไม่ถูก commit)
├── AllCode.md
├── create_sample_files.py
├── main.py
└── requirements.txt
```
