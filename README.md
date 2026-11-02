# AI Orchestra

Local dashboard สำหรับรวบรวมทีม, Agent profiles, Skills และกฎส่วนกลาง เขียน Markdown ต้นฉบับครั้งเดียวแล้ว Export ให้แต่ละเครื่องมือ ไม่ต้องมี API key และไม่มีการส่งข้อมูลออกจากเครื่อง

## เริ่มใช้งาน

ต้องมี Python 3.10 ขึ้นไป ไม่ต้องติดตั้งแพ็กเกจเพิ่มเติม

```bash
python3 demo.py       # ไม่บังคับ: สร้าง 3 ทีมตัวอย่าง โดยไม่แก้ทีมที่มีอยู่แล้ว
python3 server.py
```

เปิด http://127.0.0.1:4310 ในเบราว์เซอร์ ปิดเซิร์ฟเวอร์ด้วย Ctrl+C เปลี่ยนพอร์ตด้วย `python3 server.py --port 4311`

1. กด **สร้างทีมใหม่** ตั้ง ID ทีมได้เอง เช่น `ทีมค้นคว้า 01`, `Studio A` หรือชื่อเฉพาะของคุณ และเลือกประเภทงาน
2. แก้ **ภาพรวม / README** เพื่อระบุเป้าหมายและการส่งต่องาน
3. แก้ **กฎกลาง / RULES** เพื่อกำหนดข้อปฏิบัติร่วมกันของทีม
4. เปิดแท็บ **Skills** หรือ **Agents** แล้วกดสร้าง เลือก Template และกรอกรายละเอียด
5. แก้ Markdown และกด **บันทึกไฟล์**
6. เปิด **Export** เลือกเครื่องมือและบทบาทหลัก แล้วดาวน์โหลด ZIP

มี Template ตามประเภทงาน 9 แบบ: งานทั่วไป, ค้นหาข้อมูล/วิจัย, ภาพกราฟิก, คิดวิเคราะห์, พัฒนาโค้ด, เขียน/แปลเนื้อหา, วิเคราะห์ข้อมูล, อ่านภาพ/เอกสาร และงานเร็ว/จัดหมวดหมู่ ครอบคลุมข้อมูลนำเข้า ขั้นตอน สิ่งที่ส่งมอบ เกณฑ์ตรวจรับ ข้อจำกัด และการส่งต่องาน

## ต้นฉบับชุดเดียว

```text
workspace/teams/<team-id>/
  README.md                    # ภาพรวม เป้าหมาย และการส่งต่องาน
  RULES.md                     # กฎที่ใช้ร่วมกันทั้งทีม
  skills/<skill-id>/SKILL.md    # frontmatter: name, description + วิธีทำงาน
  agents/<agent-id>.md          # frontmatter: name, description + บทบาท
```

ข้อมูลถูกบันทึกเป็น UTF-8 บนดิสก์จริง แก้ด้วย editor ภายนอกได้ แล้วรีเฟรช Dashboard เพื่อโหลดใหม่ ใช้ name ให้ตรงกับ ID และ description เป็นข้อความบรรทัดเดียวใน YAML frontmatter โดย Template สร้างข้อความที่ escape ไว้ให้แล้ว Dashboard ไม่ได้เป็น YAML editor เต็มรูปแบบ

`workspace/` ถูก ignore จาก Git เพื่อไม่เผลอ commit ข้อมูลส่วนตัว สำรองโฟลเดอร์นี้เองได้ แอปรองรับการใช้งานส่วนบุคคล หากเปิดหลายแท็บหรือหลาย editor พร้อมกัน การบันทึกล่าสุดจะเป็นข้อมูลปัจจุบัน

## การใช้ไฟล์ที่ Export

| ปลายทาง | ไฟล์ | วิธีใช้ |
| --- | --- | --- |
| Codex local CLI / App | `AGENTS.md`, `.agents/skills/`, `team-agents/` | แตก ZIP ที่ root ของโปรเจค เปิดโปรเจคใน Codex แล้วเลือกใช้ skill หรือสั่งให้อ่าน profile |
| Claude Code CLI / local UI | `CLAUDE.md`, `.claude/skills/`, `.claude/agents/` | แตก ZIP ที่ root ของโปรเจค เปิด Claude Code ในโปรเจคนั้น |
| Chat UI ทั่วไป | `CONTEXT.md` | แนบไฟล์หรือวางเนื้อหาในแชตด้วยตนเอง ตามความสามารถของ UI นั้น |

ก่อนแตก ZIP ให้ตรวจและรวมไฟล์คำสั่งเดิมในโปรเจค โดยเฉพาะ `AGENTS.md` และ `CLAUDE.md` เพื่อไม่เขียนทับเนื้อหาที่มีอยู่

- Export เป็น snapshot ของต้นฉบับล่าสุด แก้ใน Dashboard แล้ว Export ใหม่เพื่ออัปเดต
- กฎทีมรวมอยู่ในคำสั่งหลักทั้งสองเครื่องมือ และใน Claude agent แต่ละตัวเพื่อให้ได้รับบริบทของทีม
- Codex agent profiles เป็นเอกสารบทบาท ไม่ได้สร้าง native subagent config หรือสั่งให้หลาย Agent ทำงานพร้อมกัน บทบาทหลักที่เลือกจะถูกใส่ไว้ใน `AGENTS.md`
- ใน Claude Code บทบาทหลักจะรวมใน `CLAUDE.md`; ไฟล์ใน `.claude/agents/` เป็นนิยาม subagent ที่มี shared context และ Skill ของทีมแนบอยู่
- เว็บแชตไม่อ่านโฟลเดอร์ local อัตโนมัติ การใช้ Skill และ Agent แบบ native ขึ้นกับผลิตภัณฑ์ รุ่น และโหมดใช้งาน
- Dashboard นี้จัดการและประกอบคำสั่ง ไม่ได้เรียก AI หรือเรียก CLI รันงานให้

## ตรวจสอบ

```bash
python3 -m unittest discover -s tests -v
node --check static/app.js
```

ทดสอบการบันทึกข้อมูล การตรวจ metadata การป้องกัน path traversal/symlink การป้องกัน request ข้าม origin การไม่เขียนทับ ID เดิม และเนื้อหา ZIP ของแต่ละเครื่องมือ

เซิร์ฟเวอร์ bind เฉพาะ `127.0.0.1` และตรวจ Host/Origin ไม่มีระบบบัญชีผู้ใช้ ไม่ควรนำไปรันเป็น public service

## โครงสร้างแอป

- `server.py`: HTTP API, Markdown persistence และ ZIP adapters โดยใช้ Python standard library
- `static/`: Dashboard แบบ buildless HTML/CSS/JavaScript ไม่ใช้ CDN
- `demo.py`: สร้างทีมตัวอย่างโดยไม่เขียนทับทีมเดิม
- `tests/`: Integration tests ใช้ workspace ชั่วคราว ไม่แก้ข้อมูลจริง

เอกสารรูปแบบที่ใช้อ้างอิง: [Codex Skills](https://developers.openai.com/codex/skills/), [AGENTS.md](https://developers.openai.com/codex/guides/agents-md/), [Claude Code Skills](https://code.claude.com/docs/en/skills), [Claude Code Subagents](https://code.claude.com/docs/en/sub-agents)

## API Keys กลาง (ไม่แยกตามทีม)

เปิด **API Keys กลาง** ในแถบซ้ายของ Dashboard แล้วเลือกไฟล์ `.json`, `.env` หรือ `.txt` แบบ UTF-8 ขนาดไม่เกิน 24 KB จากนั้นกด **นำเข้าและบันทึกไฟล์** หรือกด **＋ เพิ่มคีย์** กรอกชื่อและค่า token ในช่อง password แล้วกดบันทึก

ใช้ `api-tokens.example.json` เป็นตัวอย่างรูปแบบ โดยทำสำเนาเป็น `api-tokens.json` ก่อนใส่คีย์จริง อย่าใส่คีย์จริงในไฟล์ example ที่จะเข้า Git รองรับชื่อคีย์ที่กำหนดเอง เช่น `GITHUB_TOKEN` และสามารถใส่แค่บริการที่ต้องการ:

```json
{
  "OPENAI_API_KEY": "your-openai-api-key",
  "ANTHROPIC_API_KEY": "your-anthropic-api-key"
}
```

หรือใช้ `.env` (รองรับ comment เต็มบรรทัด, `export` และข้อความครอบด้วย quotes; ไม่ประมวลผล shell / variable substitution):

```dotenv
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
```

คีย์ถูกบันทึกที่ `workspace/secrets/api-tokens.json` เป็นไฟล์กลางของโปรเจค ไม่ผูกกับทีม การนำเข้าหรือกรอกคีย์เฉพาะผู้ให้บริการหนึ่งจะรักษาคีย์อีกผู้ให้บริการไว้ คีย์ที่ไม่ได้ส่งมาจะไม่เปลี่ยนค่าเดิม กดชื่อคีย์ในรายการที่บันทึกแล้วเพื่อกรอกค่าใหม่; ปุ่ม × นำแถวที่ยังไม่บันทึกออกจากฟอร์ม ไม่ลบคีย์ที่บันทึกไว้

- โฟลเดอร์มีสิทธิ์ `700` และไฟล์มีสิทธิ์ `600` บน macOS/Linux เก็บเป็นข้อความบนดิสก์ ไม่ใช่ encrypted keychain
- API ส่งกลับเฉพาะสถานะว่ามีคีย์หรือไม่ ไม่ส่งค่าคีย์กลับหน้าเว็บ และไม่ใส่คีย์ใน Markdown หรือ ZIP ที่ Export
- `workspace/`, `.env`, `.env.*` และ `api-tokens.json` ถูก ignore จาก Git
- สถานะ **บันทึกแล้ว** ไม่ใช่การตรวจสอบว่าคีย์ใช้งานได้ ไม่มีการเรียก provider หรือเสียค่า API จากการบันทึก
- การบันทึกนี้ยังไม่เปลี่ยนวิธีล็อกอินของ Codex/Claude CLI หรือ Desktop; Dashboard ยังไม่ได้เปิดรัน CLI การเชื่อมต่อ runtime ในอนาคตสามารถใช้ `token_store.load(workspace)` โหลดคีย์ฝั่งเซิร์ฟเวอร์โดยไม่ส่งผ่านเบราว์เซอร์
- ไม่รองรับการนำเข้าไฟล์บัญชี `auth.json`, OAuth session หรือ token ของ Desktop: ใช้เฉพาะ API keys ของผู้ให้บริการ

ชื่อคีย์กำหนดเองต้องใช้ A–Z, 0–9 และ `_` ไม่ขึ้นต้นด้วยตัวเลข ยาวไม่เกิน 64 ตัว รองรับสูงสุด 100 คีย์ และไฟล์รวมไม่เกิน 24 KB รายการสถานะแสดงเฉพาะชื่อคีย์ ไม่แสดงค่า token การเก็บ GitHub หรือบริการอื่นไม่ได้เชื่อมต่อบริการนั้นโดยอัตโนมัติ

## Setup Codex: เลือก Agent จากคลังกลางในโปรเจคอื่น

รองรับแอป local บน **macOS และ Windows** ด้วย Python 3.10+ ใช้ Python standard library ไม่ต้องมี Bash หรือ Node สำหรับรัน Dashboard บน Windows ใช้ `py server.py` (หรือ `python server.py`) บน macOS ใช้ `python3 server.py`

1. เปิด **Setup AI Clients** ในแถบซ้าย แล้วเลือก **Codex**
2. ระบบตรวจ `CODEX_HOME` ของ process ที่รันเซิร์ฟเวอร์ก่อน หากไม่ได้ตั้งไว้จะใช้ `.codex` ใน home directory ของผู้ใช้ปัจจุบัน (`Path.home()`)
3. แสดงตำแหน่ง `AGENTS.md` และตัวอย่างคำสั่งภาษาอังกฤษ พร้อม path คลังจริงที่คำนวณจากตำแหน่งโปรแกรม ไม่ hardcode ชื่อผู้ใช้หรือไดรฟ์
4. หากไม่พบไฟล์ สามารถสร้างที่ตำแหน่งแนะนำ หรือใส่ absolute path เอง เช่น `C:\Users\YourName\.codex\AGENTS.md` หรือ `/Users/YourName/.codex/AGENTS.md` กรอกแค่โฟลเดอร์ Codex home ได้เช่นกัน แล้วกด **ตรวจตำแหน่ง / ดูตัวอย่าง**
5. กด **Setup · บันทึก AGENTS.md** เพื่อบันทึก หากมีเนื้อหาเดิมจะคงไว้ พร้อมสำรองเป็น `AGENTS.md.aiorchestra-*.bak` ในโฟลเดอร์เดียวกันก่อนแก้
6. เริ่มเซสชัน Codex ใหม่ในโปรเจคปลายทาง แล้วลองสั่งงาน เช่น “ตรวจโค้ดนี้และบอกว่าเลือก Agent และ Skill ใด”

Setup เพิ่มเฉพาะ block ระหว่าง `AIORCHESTRA:BEGIN` และ `AIORCHESTRA:END` กดซ้ำไม่ทำให้ข้อความซ้ำ ย้ายโปรแกรมแล้ว Setup ใหม่เพื่ออัปเดต path หากไฟล์ถูกแก้หลังดูตัวอย่าง ระบบจะหยุดให้ดูตัวอย่างใหม่ก่อน เพื่อไม่เขียนทับการแก้ล่าสุด

- ระบบตรวจเฉพาะตำแหน่ง Codex home ที่มีความหมาย ไม่ค้นหาทั่วดิสก์ ซึ่งอาจเจอ `AGENTS.md` ของโปรเจคอื่น
- หากพบ `AGENTS.override.md` ที่มีเนื้อหา ระบบแจ้งว่า Codex จะเลือก override แทน และไม่แก้ไฟล์นั้นเอง
- หากเลือกตำแหน่งอื่น ต้องตั้ง `CODEX_HOME` ของ Codex ให้ตรงกัน Setup ไม่เปลี่ยน environment variable ให้โดยอัตโนมัติ
- Path ทั้งหมดอ้างอิงเครื่องที่รัน Python server ไม่ใช่เครื่องของ browser และไม่ตั้งค่าเครื่องอื่น/remote/cloud โดยอัตโนมัติ
- Agent เป็น role profile; Codex ยังต้องมีสิทธิ์อ่านคลังกลาง และปฏิบัติตามกฎของโปรเจคปัจจุบัน การตั้งค่านี้ไม่เปิด native subagents หรือใช้ API keys
- บน Windows สิทธิ์ไฟล์ใช้กลไกของระบบ Windows/ACL; ตัวเลข mode `600`/`700` ของส่วน API keys มีความหมายเต็มรูปแบบเฉพาะ POSIX ไม่ใช่การตั้ง Windows ACL
- ไม่ได้ติดตั้ง Python หรือ Codex ให้โดย Setup ปุ่มนี้ และไม่เขียนไฟล์จริงจนกดบันทึก

อ้างอิง: [OpenAI: Global AGENTS.md and CODEX_HOME](https://learn.chatgpt.com/docs/agent-configuration/agents-md)


## Setup Claude Code

หน้า **Setup AI Clients** เลือก **Claude Code · CLAUDE.md** เพื่อเชื่อมคลัง Agent เดียวกับ Codex:

1. ตรวจ `CLAUDE_CONFIG_DIR` ของเซิร์ฟเวอร์ หรือใช้ `~/.claude/CLAUDE.md` ตาม home ของผู้ใช้เครื่องนั้น
2. ตรวจตัวอย่างคำสั่งภาษาอังกฤษและ path คลังที่คำนวณอัตโนมัติ ใส่ path เองได้ เช่น `C:\Users\YourName\.claude\CLAUDE.md`
3. กด **Setup · บันทึก CLAUDE.md** แล้วเริ่มเซสชัน Claude Code ใหม่

รักษาเนื้อหาเดิม สำรองเป็น `CLAUDE.md.aiorchestra-*.bak` และอัปเดตเฉพาะ block AIOrchestra เช่นเดียวกับ Codex ไม่แก้ `AGENTS.md` ของ Codex เมื่อเลือก Claude และไม่เปลี่ยนการล็อกอินหรือ API keys

การเชื่อมนี้ใช้กับ **Claude Code** ที่มีสิทธิ์อ่านไฟล์ในเครื่อง รวมโหมด Code ของ Desktop ที่ใช้ instruction files นี้ ไม่ได้ติดตั้งคำสั่งในแชต Claude ทั่วไปหรือบน cloud เครื่องอื่นโดยอัตโนมัติ โปรไฟล์ Agent ยังเป็นคำสั่งบทบาท ไม่ได้ติดตั้ง native Claude subagents ใน `~/.claude/agents/` หากต้องการ native subagents ของทีม ให้ใช้ Export ของ Claude ตามเดิม

เอกสาร: [Claude Code memory](https://code.claude.com/docs/en/memory), [CLAUDE_CONFIG_DIR](https://code.claude.com/docs/en/env-vars)

## โควตาบน Dashboard

หน้า Overview มีการ์ด **Codex** และ **Claude Code** แสดงเปอร์เซ็นต์โควตาสมาชิกคงเหลือ เวลารีเซ็ต และเวลาที่ได้รับข้อมูลล่าสุด กด **อัปเดต** เพื่ออ่านข้อมูล ไม่เรียกโมเดลหรือสร้างงานเพิ่ม ข้อมูลที่ไม่ทราบจะแสดง “ยังไม่มีข้อมูล” แทน 0% ส่วน 0% ที่ผู้ให้บริการรายงานจริงจะแสดงตามจริง

### Codex

ใช้ Codex CLI ที่ล็อกอินไว้ ผ่าน `codex app-server --stdio` แล้วเรียกเฉพาะ `initialize`, `account/read`, `account/rateLimits/read` ไม่อ่านหรือส่งไฟล์ auth มาให้ Dashboard ไม่เปลี่ยนบัญชี ไม่ล็อกเอาต์ และไม่เรียก generate/model

- ค้น `codex` ใน PATH พร้อมตำแหน่งแอปมาตรฐานบน macOS บน Windows ให้มีคำสั่ง Codex CLI ใน PATH แล้วเริ่มเซิร์ฟเวอร์ใหม่
- หากยังไม่ล็อกอินให้รัน `codex login` เอง จากนั้นกดอัปเดต ใช้บัญชีสมาชิกเดิม ไม่ต้องใส่ `OPENAI_API_KEY`
- Cache ผล 60 วินาทีเพื่อไม่เรียกบริการซ้ำถี่เกินไป และจำกัดเวลารอ App Server
- หาก CLI ใช้ API key จะแสดง **โหมด API** พร้อมปุ่มไปหน้า API Keys กลาง รายงาน usage/cost และยอด API credits **ยังไม่ได้เชื่อมต่อ** คีย์ API ธรรมดาไม่ทำให้เห็นโควตาแพ็กเกจสมาชิก
- ไม่แสดง email/account identifier หรือ credentials ในผลลัพธ์

### Claude Code CLI

กด **ตั้งค่าตัวเชื่อม CLI** บนการ์ด Claude เพื่อตรวจตัวอย่าง command จากนั้นกด **ติดตั้งตัวเชื่อมโควตา** ระบบเพิ่ม `statusLine` ใน `settings.json` ของ `CLAUDE_CONFIG_DIR` หรือ `~/.claude` พร้อมสำรองไฟล์และรักษา settings อื่นไว้ ใช้ Python ตัวเดียวกับที่รัน Dashboard; Windows เรียกผ่าน PowerShell โดยเข้ารหัส command เพื่อรองรับ path ที่มีช่องว่าง

เปิด Claude Code CLI ใหม่และส่งข้อความตามการใช้งานปกติ ตัวเชื่อม `claude_quota_bridge.py` จะรับ JSON จาก status line โดยเก็บเฉพาะโควตา 5 ชั่วโมง/7 วัน และเวลารีเซ็ตใน `workspace/usage/claude.json` ไม่เก็บ prompt, transcript, session identifier, API key หรือข้อมูล auth จาก payload จากนั้นกด **อัปเดต** บน Dashboard

- ไม่มีการส่งข้อความหาโมเดลให้อัตโนมัติเพื่อเช็กโควตา CLI จะมีข้อมูลเมื่อบัญชี/เวอร์ชันรองรับและได้รับ response ตามการใช้งานของคุณ
- ไม่มีการนำ API key ไปขอข้อมูลสมาชิก ไม่มีการคัดลอก OAuth token
- ถ้าตั้ง status line อื่นไว้ ระบบจะ **ไม่เขียนทับ** ให้ดู command ตัวเชื่อมในตัวอย่างแล้วรวมกับ status line ของคุณเองโดยส่ง JSON stdin เดียวกันให้ทั้งสองสคริปต์ กรณีนี้ต้องปรับสคริปต์ status line เดิมด้วยตนเอง
- ข้อมูลอายุมากกว่า 5 นาทีหรือเลยเวลารีเซ็ตจะแสดง **ข้อมูลเก่า** ค่าที่แสดงเป็น snapshot ไม่ใช่การคาดการณ์โควตาหลังรีเซ็ต
- Snapshot ล่าสุดมาจาก CLI ที่ส่งเข้าคลังนี้ ไม่รับประกันว่าจะตรงกับบัญชีอื่นที่เปิดพร้อมกัน
- ตัวเชื่อมนี้เป็นของ Claude Code **CLI** ไม่รับประกันการส่ง status line จาก Code ใน Desktop หรือ Claude chat ทั่วไป
- ย้ายโฟลเดอร์โปรแกรมแล้วต้องอัปเดต statusLine command ให้ตรงตำแหน่งใหม่ หาก command เดิมยังอยู่ระบบจะไม่เขียนทับเอง
- หากต้องการยกเลิกตัวเชื่อม ให้คืน settings จากไฟล์สำรอง หรือลบเฉพาะ `statusLine` ของ AIOrchestra

โควตาสมาชิก, tokens ใน context window, rate limit ต่อเวลา, API cost และยอด prepaid credits เป็นคนละค่า Dashboard รุ่นนี้แสดง **โควตาสมาชิก** เท่านั้น ไม่ตีความเป็นจำนวน tokens ที่ซื้อเหลืออยู่

อ้างอิง: [Codex App Server](https://learn.chatgpt.com/docs/app-server), [Claude status line](https://code.claude.com/docs/en/statusline)

## Live Agents และ Activity

หน้า Overview แสดงตาราง **Agent / Engine / Project / Status** พร้อม Activity รูปแบบ `เวลา | project | engine | เหตุการณ์` หน้าแต่ละทีมกรองเฉพาะข้อมูลของทีมนั้น ป้าย **● Active สีเขียว** ปรากฏใน sidebar และการ์ดทีมเมื่อมีอย่างน้อยหนึ่งเซสชันกำลังทำงานตามรายงานล่าสุด

### เริ่มใช้กับ Codex และ Claude

1. รีสตาร์ตเซิร์ฟเวอร์และรีเฟรช Dashboard
2. กด **Setup AI Clients** เลือก Codex แล้วบันทึก `AGENTS.md` ใหม่; หากใช้ Claude ให้เลือก Claude แล้วบันทึก `CLAUDE.md` ใหม่ด้วย
3. เริ่มเซสชันใหม่ในเครื่องมือที่เลือก คำสั่ง Setup รุ่นใหม่จะให้ Agent เรียก `report_agent.py` หลังเลือกโปรไฟล์ หลังโหลด Skill และเมื่อเปลี่ยนสถานะ
4. Dashboard อ่านรายงานใหม่ทุก 5 วินาที ไม่ต้องเปิดโมเดลเพิ่มหรือใช้ API key เพื่อรายงาน

เป็น **สถานะที่ client รายงาน** ไม่ใช่การสอดส่องหรือยืนยันว่ามี native subagent process แยกทำงานอยู่ เครื่องมือต้องทำตามคำสั่งรายงานและได้รับสิทธิ์เรียกสคริปต์/เขียน runtime storage หาก sandbox ของโปรเจคอื่นไม่อนุญาต ให้ใช้วิธีอนุญาตตามปกติของเครื่องมือนั้น ห้ามข้ามข้อจำกัด หากส่งรายงานไม่ได้ให้แสดงว่าไม่พร้อมติดตาม ไม่อ้างว่า Dashboard เชื่อมแล้ว

ไม่มีการติดตั้ง hooks หรือแก้ instruction files จริงโดยอัตโนมัติจากการอัปเดตโค้ด ต้องกด Setup เพื่อใช้คำสั่งรุ่นใหม่ งานหรือเซสชันเก่าที่ไม่เคยส่งรายงานจะไม่แสดงเอง และจะไม่มีการสร้างแถวตัวอย่างให้ดูเหมือนงานจริง

### สถานะ

| Status | ความหมาย | Active |
| --- | --- | --- |
| กำลังทำงาน | รับ selected / working / skill หรือ heartbeat ล่าสุด | เขียว |
| รอรับงาน / รอผู้ใช้ | Client รายงาน waiting | ไม่ขึ้น |
| เสร็จแล้ว | Client รายงาน done | ไม่ขึ้น |
| ล้มเหลว | Client รายงาน failed | ไม่ขึ้น |
| ไม่ทราบสถานะ | ไม่มีการยืนยันเกิน 180 วินาที หรือ Dashboard ติดต่อ server ไม่ได้ | ไม่ขึ้น |

Client ควรรายงานความคืบหน้าหรือ heartbeat ภายใน 120 วินาทีขณะทำงาน ไม่เปิด heartbeat daemon ที่ทำให้ Active ค้างหลังงานหยุด เมื่อรอหรือจบให้รายงานทันที ค่าไม่ทราบสถานะไม่ได้แปลว่างานเสร็จ; อาจเป็นงานยาวที่ยังไม่ส่งรายงาน

### เรียกรายงานด้วยตนเอง / สำหรับ integrations

รันจากโฟลเดอร์โปรแกรม (Windows ใช้ `py` หรือ `python` แทน `python3`):

```text
python3 report_agent.py --engine Codex --team developer --agent software-engineer --project /absolute/path/to/shop-app --event selected
```

ผลตอบกลับมี `session` ให้ใช้ ID เดิมในเหตุการณ์ถัดไป โดยคง engine/team/agent/project เดิม เช่น:

```text
python3 report_agent.py --engine Codex --team developer --agent software-engineer --project /absolute/path/to/shop-app --session SESSION_ID --event skill --skill implementation-review
python3 report_agent.py --engine Codex --team developer --agent software-engineer --project /absolute/path/to/shop-app --session SESSION_ID --event done
```

Windows ให้ใส่ project เป็น absolute path เช่น `"C:\Projects\shop-app"` เลือก `--engine Claude` เมื่อรายงานจาก Claude รองรับเหตุการณ์ `selected`, `skill`, `working`, `waiting`, `done`, `failed`, `heartbeat`; หากไม่ส่ง `--session` ใน selected ระบบสร้าง UUID ให้ ไม่รองรับข้อความรายงานอิสระที่อาจมีโค้ดหรือ secrets ปะปน

ใช้ `--workspace` ระบุคลังอื่นได้ โดย default ใช้ workspace ข้างตัวโปรแกรม รายงานจะตรวจว่า team/agent/skill มีจริงในคลัง Engine+session แยกกันเพื่อรองรับหลายโปรเจคพร้อมกัน หากเปลี่ยนโปรไฟล์ในเซสชันเดิมให้ส่ง selected ใหม่ ตารางจะแสดงโปรไฟล์ล่าสุด ส่วนเหตุการณ์เก่าเก็บใน Activity

ข้อมูล local อยู่ที่ `workspace/runtime/activity.sqlite3` (SQLite, ไม่รวมใน Git/ZIP) เก็บ 1,000 เหตุการณ์ล่าสุด, ส่งให้ Dashboard 100 เหตุการณ์ล่าสุด และแสดงไม่เกิน 200 เซสชันล่าสุด เก็บชื่อทีม Agent/Skill, engine, project path, session, event และเวลาเท่านั้น ไม่เก็บ prompts, API keys หรือเนื้อหางาน งานเก่ากว่า 30 วันถูกล้างเมื่อมีรายงานใหม่


## ID ทีมอิสระและ Template ตามประเภทงาน

หน้า Overview เหลือปุ่ม **เพิ่มทีมใหม่** ในรายการทีม ไม่แสดงปุ่มสร้างซ้ำด้านบน ID ทีมใช้ภาษาไทย อังกฤษ ตัวเลข ช่องว่าง หรือสัญลักษณ์ได้ 1–128 ตัวอักษร โดยตัดช่องว่างหัวท้ายและ normalize Unicode เป็น NFC ไม่รับอักขระควบคุม

ID ทีมไม่ใช่ path โดยตรง: ID แบบเดิมที่เป็น slug ยังคงใช้โฟลเดอร์เดิม ส่วน ID ที่มีอักขระอื่นหรือชื่อสงวน Windows จะใช้ `_team_<hash>` ซึ่งเป็นชื่อไฟล์ ASCII ปลอดภัย ข้อมูล `TEAM.json` เก็บ ID จริงและแนวทางเลือกโมเดล Dashboard, Export และ Live Agents ใช้ ID จริง ไม่ใช้ hash ของโฟลเดอร์เป็นชื่อทีม Agent และ Skill ยังใช้ ID แบบ `a-z`, `0-9`, ขีดกลางตามรูปแบบที่เครื่องมือรองรับ

Template ไม่ผูกกับชื่อทีม:

| ประเภทงาน | ความสามารถหลัก | แนวทางกลุ่มโมเดล |
| --- | --- | --- |
| งานทั่วไป | ประสานงานและใช้เครื่องมือ | Claude Sonnet / GPT reasoning |
| ค้นข้อมูล / วิจัย | ค้นเว็บและอ้างอิง | Gemini + Google Search grounding |
| ภาพกราฟิก | สร้างและแก้ไขภาพ | GPT Image / Gemini Image |
| คิดวิเคราะห์ | ให้เหตุผลและเปรียบเทียบทางเลือก | Claude Opus/Fable / GPT reasoning |
| พัฒนาซอฟต์แวร์ | เขียนโค้ดและใช้เครื่องมือ | Codex / Claude Opus / Sonnet |
| เขียน / แปลเนื้อหา | สร้างและเรียบเรียงข้อความ | Claude Sonnet / GPT reasoning |
| วิเคราะห์ข้อมูล | ให้เหตุผลและวิเคราะห์ข้อมูล | GPT reasoning / Claude Opus |
| อ่านภาพ / เอกสาร | เข้าใจภาพและสกัดบริบท | Gemini / Claude / GPT ที่รองรับ vision |
| งานเร็ว / จัดหมวดหมู่ | Classification และ extraction | Claude Haiku |

คำแนะนำเป็นการจัดกลุ่มจากความสามารถที่ผู้ให้บริการระบุ ไม่ใช่ benchmark ว่าแบรนด์ใดดีที่สุด และไม่ครอบคลุมโมเดลทั้งหมดในตลาด รุ่นจริง สิทธิ์ เครื่องมือ ราคา และคุณภาพของงานต้องตรวจ/ประเมินก่อนใช้งาน Catalog อยู่ใน `task_templates.py` พร้อม source URLs และวันที่ตรวจเอกสาร ปรับ catalog ได้เมื่อโมเดลเปลี่ยน โดยไม่ต้องเปลี่ยน ID ทีม

- **Recommended:** บันทึกกลุ่มโมเดลแนะนำตาม Template เป็นค่าเริ่มต้น
- **Auto:** บันทึกประเภทงานและความสามารถที่ต้องใช้ เพื่อเป็นเกณฑ์ให้ระบบรันหรือ router เลือกภายหลัง
- ทั้งสองโหมดยังเป็นค่ากำหนดและคำแนะนำ ไม่ได้เรียก provider หรือสลับโมเดลเอง และไม่ได้ยืนยันว่าโมเดลนั้นเชื่อมต่อพร้อมใช้
- `TEAM.json` เก็บ `workType`, `routingMode`, `requiredCapabilities`, `recommendedModels` โดย ID ใน recommendedModels เป็น alias ของกลุ่มใน catalog ไม่ใช่ model ID ที่ส่งเข้า API ได้โดยตรง
- README ทีมใหม่มีแนวทางประเภทงาน และ Agent/Skill ที่สร้างจากฟอร์มมี frontmatter ระบุ `work_type`, `routing_mode`, `recommended_models` พร้อมขั้นตอน/ผลลัพธ์/เกณฑ์ตรวจรับตามประเภทงาน
- ทีมเก่าที่ไม่มี TEAM.json จะแสดงเป็นงานทั่วไป / Recommended โดยไม่แก้ไฟล์เก่าเอง
- หลังอัปเดตนี้กด Setup ใหม่เพื่อให้ Codex/Claude อ่าน ID จริงจาก TEAM.json เมื่อเลือกทีมที่มีชื่อโฟลเดอร์เป็น hash

เอกสารความสามารถ: [OpenAI models](https://developers.openai.com/api/docs/models), [Claude models](https://platform.claude.com/docs/en/models/overview), [Gemini Search](https://ai.google.dev/gemini-api/docs/google-search), [Gemini Image](https://ai.google.dev/gemini-api/docs/image-generation)

## จัดการทีม, Agent และ Skill

- เปิดทีมเพื่อใช้ **เปลี่ยนชื่อทีม / ลบทีม** การเปลี่ยนชื่อทีมแก้ชื่อที่แสดงใน README โดยรักษา ID และโฟลเดอร์เดิม
- ในแท็บ **Agents / Skills** เลือกรายการแล้วใช้ **เปลี่ยนชื่อ / ลบ** บนแถบ editor ID ใหม่ต้องใช้ a-z, 0-9 และขีดกลางตามรูปแบบของเครื่องมือ
- เปลี่ยนชื่อ Skill จะย้ายโฟลเดอร์และอัปเดต `name`, หัวข้อที่ตรงกับชื่อเดิม, รายการผูก Skill ของ Agent และ relative Markdown paths ที่อ้างอิงรายการนั้น
- ลบ Skill จะนำออกจากรายการผูก Agent และแทน relative paths ที่อ้างถึง Skill ที่ลบด้วยข้อความแจ้งว่า removed โดยไม่แก้ข้อความทั่วไปที่บังเอิญตรงกับชื่อ Skill
- การเปลี่ยนชื่อ/ผูก Skill/แก้ Description จะสำรองทีมก่อนแก้ใน `workspace/.trash/<operation-id>/before/` พร้อม `operation.json` การลบเป็นการลบถาวร ไม่มีการสำรองหรือย้ายไปถังขยะ ส่วนการแก้ไขที่ไม่ใช่การลบยังคืนค่าจากสำเนาก่อนแก้เมื่อเกิดข้อผิดพลาด
- กู้คืนได้ด้วยการตรวจ `operation.json` เพื่อหา `teamFolder` และนำไฟล์ที่ต้องการจาก `before/` (หรือ `removed/` ของรุ่นเก่าที่เคยสำรองไว้) กลับไปยัง `workspace/teams/<teamFolder>/` หลังตรวจว่าไม่มีงานกำลังทำและไม่เขียนทับงานใหม่ การกู้คืนยังไม่มีปุ่มใน Dashboard

### ล็อกระหว่างทำงาน

เมื่อทีมมีเซสชันใดที่ยังไม่จบ โปรแกรมจะล็อกการเปลี่ยนชื่อ ลบ บันทึก Markdown และเปลี่ยนรายการ Skill ของทั้งทีมเพื่อไม่ให้กระทบงานที่กำลังอ่านไฟล์อยู่ ตรวจทั้งใน UI และเซิร์ฟเวอร์ (HTTP 409) ใช้ transaction เดียวกับการรายงาน lifecycle เพื่อป้องกันการลบพร้อมกับเริ่มเซสชัน

- working / waiting ยังถือว่ามีเซสชันค้าง
- ขาด heartbeat จนขึ้น “ไม่ทราบสถานะ” จะไม่ปลดล็อกเอง เพราะยังสรุปไม่ได้ว่างานหยุดแล้ว
- หลังหยุดงานจริง ให้ใช้ done/failed จาก client หรือกด **ปิดรายงานเซสชัน** ของรายการ waiting/unknown และยืนยันว่าหยุด CLI แล้ว โปรแกรมเปลี่ยนสถานะเป็น closed และปลดล็อกเมื่อไม่มีเซสชันค้างอื่น
- ปิดรายงานไม่ได้ kill process หรือยกเลิกงานใน Codex/Claude ต้องหยุดงานที่เครื่องมือนั้นก่อน ไม่อนุญาตให้ปิดรายงานของ working ที่ยังอัปเดตสดอยู่
- การล็อกอ้างอิงเฉพาะเซสชันที่ส่งรายงานเข้า AIOrchestra; ไม่สอดส่อง process ภายนอกและไม่สามารถป้องกันการแก้ไฟล์ตรงจาก editor อื่น

### ป้าย Skill ใต้ Agent ใน Team Library

ใต้ชื่อ Agent แสดงป้าย `✧ <skill-id>` พร้อมแยกว่าเป็น **สกิลร่วมของทีม** หรือ **สกิลที่กำหนด** เลือก checkbox ใน editor แล้วกด **บันทึก Skills ของ Agent** เพื่อบันทึกเป็น frontmatter:

```yaml
skills: ["implementation-review", "fact-check"]
```

รองรับ JSON list, YAML inline list ของ IDs และ YAML block list แบบ IDs ไม่มี `skills` หมายถึง Skill ของทีมเป็นตัวเลือกที่ใช้ร่วมกัน (เข้ากันได้กับไฟล์เดิม); `skills: []` หมายถึงไม่ได้กำหนด Skill ใดเลย ป้ายเหล่านี้คือรายการที่ Agent ใช้ได้ ไม่ใช่หลักฐานว่าโหลดจริง ให้ดูเหตุการณ์โหลดจริงใน Activity

Export Claude แนบเฉพาะ Skill ที่มีผลสำหรับ Agent แต่ละตัว ส่วน global Setup อธิบายให้ใช้รายการผูกใน frontmatter แล้ว กด Setup ใหม่เพื่อโหลดแนวทางนี้ในเซสชันถัดไป ตัว reporter ปฏิเสธรายงาน skill ที่อยู่นอก explicit assignment ด้วย


## การลบถาวรและ Description ทีม

การลบทีม, Agent และ Skill รุ่นปัจจุบันลบไฟล์/โฟลเดอร์จริงโดยไม่สร้าง backup, ไม่สร้าง operation archive และไม่ย้ายไปถังขยะ หน้าต่างยืนยันจะแจ้งว่าลบถาวร การล็อกขณะมีเซสชันยังไม่จบและการนำ Skill ออกจาก Agent ยังคงทำงาน ไฟล์สำรองจากการใช้งานรุ่นเก่าจะไม่ถูกล้างเอง และการแก้ไข/เปลี่ยนชื่อที่ไม่ใช่การลบยังใช้ระบบสำรองเดิม

ทีมมี **ชื่อทีม** และ **Description** แยกกัน: กรอก Description ตอนสร้าง หรือกด **แก้ไข Description** ในหน้าทีม แสดงบนการ์ดและหัวหน้าทีม รองรับหลายบรรทัด สูงสุด 4000 ตัวอักษรและเว้นว่างได้

Description อยู่ใน README ระหว่าง `AIORCHESTRA:DESCRIPTION:BEGIN/END` และบันทึกคู่ใน TEAM.json อ่านค่าจาก README เป็นหลักจึงแก้ผ่าน Markdown editor ได้ด้วย สำหรับไฟล์เก่าจะใช้ข้อความระหว่างหัวข้อชื่อทีมและหัวข้อระดับสองแรกเป็น Description โดยไม่ต้องแก้ไฟล์เดิมล่วงหน้า การเปลี่ยน Description ไม่เปลี่ยน ID ทีมและไม่กระทบหัวข้ออื่น

## Pixel Office · ออฟฟิศจำลองของแต่ละทีม

ใต้ชื่อแต่ละทีมใน sidebar มีเมนู **Pixel Office** แสดงห้องทำงานแบบ pixel ที่วาดด้วย Canvas ในเครื่อง มีโต๊ะคอม โต๊ะเขียน โซฟา มุมกาแฟ และชั้นหนังสือ ไม่โหลดรูปจาก CDN และไม่เรียก AI เพิ่ม

- ตัวละครหนึ่งตัวต่อ Agent ในคลัง พร้อมป้ายชื่อ สถานะ และโปรเจคเหนือหัว
- **กำลังทำงาน:** นั่งที่โต๊ะคอมหรือโต๊ะเขียนตามประเภทงาน/บทบาท ภาพเป็นการสื่อประเภทงาน ไม่ใช่การจับหน้าจอของเครื่องมือจริง
- **รอผู้ใช้ / รองาน:** เดินคุยโทรศัพท์ตามทางเดินจากด้านหนึ่งไปอีกด้านหนึ่งของออฟฟิศ
- **พัก:** เดินไปมุมกาแฟ ชั้นหนังสือ โซฟา และกลับมาหลับ สลับเป็นรอบพร้อมช่วงหยุดพัก โดยใช้เมื่อไม่มีรายงานเซสชันค้าง หรือเซสชันล่าสุดจบแล้ว คำว่า “พัก” ไม่ใช่การยืนยันว่าไม่มี process ภายนอกทำงาน
- **ไม่ทราบสถานะ:** แสดง ? และป้ายเฉพาะเมื่อรายงานหมดอายุหรือขาดการเชื่อมต่อ ไม่แปลงเป็นพัก
- **งานผิดพลาด:** แสดง ! แยกจากการพัก

กดป้ายชื่อตัวละครหรือรายชื่อใน **Office Roster** เพื่อดู Engine, Project, เวลาข้อมูลล่าสุด และ Skills ที่ใช้ได้ หาก Agent มีหลายเซสชัน ให้ความสำคัญกับ working → waiting → unknown → failed → งานจบ และรวมชื่อโปรเจคที่ยังมีเซสชันค้าง ภาพยังเป็นโปรไฟล์ Agent ไม่ใช่ native subprocess แยก

ใช้ข้อมูล Live Agents เดิม อัปเดตสถานะทุก 5 วินาทีและโหลดรายชื่อในคลังใหม่ประมาณทุก 30 วินาทีเมื่ออยู่ในหน้า Office ไม่มีรายงานเซสชันใหม่จนกว่า Codex/Claude จะเรียก reporter ตาม Setup การเปิด Office ไม่แก้สถานะหรือสร้างงานจำลองเอง

มีปุ่มหยุด/เล่นภาพเคลื่อนไหว รองรับ reduced-motion ของระบบ สามารถกดป้ายชื่อด้วยคีย์บอร์ดได้ และหน้าแคบจะเลื่อนฉากแนวนอนเพื่อให้ตัวหนังสืออ่านได้ ภาพ pixel วาดประมาณ 12 เฟรมต่อวินาที

ตรวจ state mapping เพิ่มเติมได้ด้วย:

```text
node tests/test_office_state.cjs
```


### การเดินในออฟฟิศ

ตัวละคร idle เดินตาม waypoint จริงด้วยความเร็วประมาณ 42–53 pixel ของฉากต่อวินาที ไม่ใช่แกว่งอยู่กับที่ เมื่อถึงจุดหมายจะดื่มกาแฟ อ่านหนังสือ นั่งพัก หรือหลับก่อนเดินต่อ ตัวละคร waiting เดินคุยโทรศัพท์ตามทางเดิน ส่วน working เดินกลับโต๊ะแล้วพิมพ์หรือเขียน งาน unknown/failed ไม่เดินพักเพื่อไม่สื่อว่าจบงานแล้ว

ป้ายชื่อเคลื่อนตามตัวละครและมีข้อความกิจกรรมภาพจำลองเหนือหัว ไม่เพิ่มรายการใน Activity งานจริง ไม่บันทึกลงฐานข้อมูล และไม่เรียก AI เพิ่ม

ปุ่มหยุดตรึงเวลาและตำแหน่งภาพปัจจุบัน เล่นต่อจากที่หยุดได้ ส่วนการ polling Live Agents ยังอัปเดตสถานะงานตามปกติ หากระบบเปิด reduced motion จะเริ่มแบบหยุด พร้อมแถบแจ้งและปุ่มเล่นให้เลือก ไม่ควรตีความภาพหยุดเป็น CLI หยุดทำงาน

ตรวจเส้นทางเดิน การหยุดเวลา และการคงเส้นทางเมื่อ poll ด้วย:

```text
node tests/test_office_motion.cjs
```

หลังอัปเดตต้องหยุด Python server รุ่นเดิมแล้วเปิดใหม่ เพื่อให้เสิร์ฟ `office_motion.js` ได้ จากนั้นรีเฟรชหน้าเว็บ


## ชื่อ Agent และ Role

ฟอร์ม Agent แยกช่อง **ID**, **ชื่อ Agent ที่แสดง**, **Role / บทบาท** และ **Description / เมื่อใดควรใช้** เช่น:

```yaml
name: "developer"
display_name: "ไอซ์"
role: "Developer"
description: "ใช้เมื่อต้องพัฒนาโค้ด แก้บั๊ก และตรวจสอบซอฟต์แวร์"
skills: ["implementation-review"]
```

`name` ยังคงเป็น technical ID ให้ตรงกับชื่อไฟล์และรูปแบบของเครื่องมือ ส่วนชื่อบุคคล/ชื่อเล่นภาษาไทยให้ใส่ `display_name` และใช้ `role` บอกบทบาท ไม่ควรใส่ชื่อเล่นใน description เพราะใช้เป็นคำอธิบายหน้าที่และเงื่อนไขเลือก Agent

Team Library แสดงชื่อและ Role ก่อนป้าย Skill หากชื่อแสดงต่างจาก ID จะมีบรรทัด ID กำกับ เปลี่ยนชื่อที่แสดงและ Role ได้จากปุ่ม **แก้ชื่อ / Role** เหนือรายการ Skills โดยไม่ย้ายไฟล์หรือเปลี่ยนความสัมพันธ์ ส่วนปุ่ม **เปลี่ยน ID** ใช้เปลี่ยนชื่อไฟล์/technical ID โดยเฉพาะ

ไฟล์เดิมที่ไม่มี `display_name` / `role` ใช้ ID เป็นชื่อที่แสดงและ description เป็น Role ชั่วคราว ไม่ย้ายหรือสลับค่าด้วยการเดา หากเคยใส่ชื่อเล่นใน description ให้เปิด **แก้ชื่อ / Role** แล้วกรอกให้ตรงช่อง ชื่อแสดงถูกใช้ใน Live Agents, Pixel Office และตัวเลือก Export ส่วน reporter และประวัติเหตุการณ์ยังอ้างอิง ID เดิม

## Pixel Office และ Terminal ของ Agent

- เปิด **Pixel Office** ใต้ชื่อทีม: ฉากออฟฟิศมุมเอียงพร้อมขอบนีออน ตัวละครเดิน พัก และทำงานตาม Live Agents โดยไม่มี Office Life log
- ตอนสร้าง Agent หรือกด **แก้ชื่อ / Role / ตัวละคร** เลือกเพศ ทรงผม สีผม สีผิว สีเสื้อ และชุดได้ ข้อมูลอยู่ใน `appearance` แบบ JSON บรรทัดเดียวใน frontmatter ของ Agent เดิมที่ไม่มี field นี้ใช้รูปลักษณ์เริ่มต้น
- กดตัวละครหรือป้ายชื่อเพื่อเลือก Codex / Claude, Model, absolute Project path และงานเริ่มต้น ค่าเริ่มต้นใช้โมเดลแนะนำของทีมที่มี CLI ติดตั้งแล้ว หากเป็น Gemini / โมเดลภาพ ต้องเลือก CLI ที่รองรับเอง หน้านี้ยังไม่เปิด Gemini/image engines
- CLI ทำงานจริงใน PTY ของเครื่องที่รัน server ใช้บัญชี login และ environment ของ CLI ตามปกติ ไม่ฉีด API keys กลางทั้งหมดเข้า process โดยอัตโนมัติ และไม่ข้าม permission prompts ของ CLI
- Terminal อยู่ด้านล่าง มีแท็บแยก Agent พิมพ์โต้ตอบและปรับขนาดตามหน้าจอได้ ปุ่ม **⌄** ย่อแผงโดยงานยังทำต่อ ปุ่ม **× ของแท็บ** หยุด CLI/process group ที่โปรแกรมเปิดและจบรายงานเพื่อปลดล็อกทีม การ refresh/ปิดแท็บเว็บไม่ได้หยุด CLI; เปิด Dashboard กลับมาเพื่อเชื่อม session เดิมได้ตราบใดที่ server ยังรัน
- การปิด server ตามปกติจะหยุด CLI ที่โปรแกรมเป็นเจ้าของด้วย หากเครื่องดับ/บังคับ kill server รายงานจะเป็นไม่ทราบสถานะเมื่อเกิน 3 นาที และปิดรายงานค้างเองได้หลังตรวจว่าหยุด process แล้ว
- สถานะ working/waiting มาจากคำสั่งเริ่มต้นและรายงานของ Agent ไม่ได้ตีความข้อความทุกบรรทัดใน Terminal ว่าโมเดลกำลังคิด งานที่เปิดอยู่ยังล็อกทีมตลอดอายุ CLI รวมถึงระหว่างรอคำสั่ง
- macOS/Linux ใช้ Python standard library ฝั่ง Windows ใช้ [pywinpty / ConPTY](https://github.com/andfoy/pywinpty) ติดตั้งด้วย `py -m pip install -r requirements.txt` และต้องติดตั้ง CLI ใน environment เดียวกับที่รัน server

Terminal renderer ใช้ [xterm.js](https://xtermjs.org/) 5.5.0 + addon-fit 0.10.0 แบบ bundle ใน `static/vendor/` พร้อม license ไม่โหลดจาก CDN และเก็บ output เฉพาะหน่วยความจำแบบจำกัดขนาด ไม่เก็บ transcript ลงดิสก์โดย Dashboard

## Team Resources

เมนู **Resources** ใต้แต่ละทีม หรือแท็บ Resources ในหน้าทีม เก็บรูปภาพ ต้นแบบ และไฟล์อ้างอิงพร้อมคำอธิบาย อัปโหลดได้หลายไฟล์ (10 MB ต่อไฟล์ / 100 MB ต่อทีม) รองรับ PNG/JPEG/GIF/WebP, PDF, TXT/MD/CSV/JSON, DOCX/PPTX/XLSX และ ZIP โดยไม่แตก archive หรือรันไฟล์ให้ อิมเมจมีภาพตัวอย่าง ส่วนไฟล์อื่นดาวน์โหลดได้

ไฟล์อยู่ใน `workspace/teams/<team-folder>/resources/` ใช้ชื่อจัดเก็บสุ่มและเก็บชื่อจริงในฐานข้อมูล มี `RESOURCES.md` เป็นดัชนีให้ Agent เลือกอ่านไฟล์ที่เกี่ยวข้อง การลบ Resource เป็นการลบถาวร และล็อกเมื่อทีมมีงานค้าง ไฟล์อ้างอิงเป็นข้อมูลประกอบ ไม่ใช่คำสั่งที่มีสิทธิ์เหนือคำสั่งผู้ใช้ ไฟล์ Resource ยังไม่รวมใน ZIP Export ของโปรไฟล์/Skills

## Coins, Rank และ Review

เป็น **virtual coins ในแอป ไม่มีการชำระเงินจริง** กองกลางเริ่มต้น 86,400 ครั้งเดียว งานที่รายงาน `done` รับ 1 coin โดยหักจากกองกลาง ถ้าเงินหมด งานยังบันทึกสำเร็จแต่ไม่ได้ coin และไม่มีการเติมเงินเอง ยอดและประวัติอยู่ใน SQLite เดียวกับ Activity ที่ `workspace/runtime/activity.sqlite3` จึงคงเดิมหลังปิดเปิดโปรแกรม ไม่คำนวณย้อนหลังจากงานเก่าก่อนอัปเดตนี้

- งานหนึ่งครั้ง = ตั้งแต่รายงาน `selected`/`working` จนถึง `done` ไม่ใช่จำนวนครั้งที่เปิด Terminal ใน CLI ที่ Dashboard เปิด สามารถทำหลายงานต่อ session ได้ โดยรายงาน `working` ก่อนงานใหม่แต่ละงาน การรายงาน `done` ซ้ำของงานเดิมไม่เพิ่ม coins ซ้ำ
- ต้องรายงาน `done` หลังส่งมอบสำเร็จจริง การปิด CLI/ยกเลิก/ล้มเหลว/ทักทาย ไม่ได้รับรางวัล การออกจาก CLI ด้วย exit 0 อย่างเดียวไม่ยืนยันว่าเนื้องานสำเร็จ
- Dashboard แนบวิธีใช้ reporter ให้ CLI ใหม่อัตโนมัติ การใช้งานผ่าน Codex/Claude นอก Dashboard ต้องกด **Setup AI Clients** เพื่ออัปเดตคำสั่ง แล้วเริ่มแชตใหม่ การติดตามงานและ Skill ยังขึ้นกับ CLI ทำตามคำสั่งรายงาน ไม่ได้อ่านข้อความใน Terminal เพื่อเดาว่าทำงานเสร็จ
- Rank จาก coins สะสม: Rookie 0, Bronze 5, Silver 20, Gold 50, Diamond 100 แสดงป้ายและรายละเอียดใน Pixel Office และตารางอันดับหน้าแรก
- หลังงานสำเร็จ แถบ Review ด้านข้างแสดงชื่องาน ผลลัพธ์ โปรเจค และ Skills ที่รายงานว่าใช้ เลือก 1–5 ดาวและเขียนคอมเมนต์ได้ โดย Rating เพิ่มตามจำนวนดาวครั้งเดียวต่อ Review แยกจาก coins
- ปุ่ม “ข้าม · ไม่ Review” ไม่มีคะแนนเพิ่มหรือหัก ปุ่ม × ย่อแถบและเก็บรายการรอไว้ เปิดประวัติเพื่ออ่าน Review ที่ให้หรือข้ามแล้วได้
- ก่อนเริ่มงานใหม่ `agent_feedback.py --team <id> --agent <id>` อ่าน Review ล่าสุดให้ Agent ใช้หลีกเลี่ยงข้อผิดพลาดซ้ำและเสนอปรับ Skill ที่เกี่ยวข้อง รายงาน Review ไม่ใช่การ fine-tune โมเดล ไม่มีการรับประกันว่าโมเดลจะเรียนรู้โดยตัวมันเอง และไม่เขียนทับ Skill อัตโนมัติ
- เปลี่ยน ID Agent ผ่าน Dashboard จะย้ายยอดและประวัติไป ID ใหม่ ประวัติ Agent ที่ลบยังคงอยู่เพื่อการตรวจสอบ

ตัวอย่างรายงาน (เพิ่ม engine/team/agent/project/session ตามปกติ):

```text
--event working --summary "แก้ checkout validation"
--event skill --skill implementation-review
--event done --summary "แก้ checkout validation" --result "แก้ validation และทดสอบกรณีขอบเขตครบแล้ว"
```
