# AI Orchestra

Local dashboard สำหรับรวบรวมทีม, Agent profiles, Skills และกฎส่วนกลาง เขียน Markdown ต้นฉบับครั้งเดียวแล้ว Export ให้แต่ละเครื่องมือ ไม่ต้องมี API key และไม่มีการส่งข้อมูลออกจากเครื่อง

## เริ่มใช้งาน

ต้องมี Python 3.10 ขึ้นไป ไม่ต้องติดตั้งแพ็กเกจเพิ่มเติม

```bash
python3 demo.py       # ไม่บังคับ: สร้าง 3 ทีมตัวอย่าง โดยไม่แก้ทีมที่มีอยู่แล้ว
python3 server.py
```

เปิด http://127.0.0.1:4310 ในเบราว์เซอร์ ปิดเซิร์ฟเวอร์ด้วย Ctrl+C เปลี่ยนพอร์ตด้วย `python3 server.py --port 4311`

1. กด **สร้างทีมใหม่** ตั้ง ID ภาษาอังกฤษ เช่น `marketing` และชื่อที่แสดง ภาษาไทยได้
2. แก้ **ภาพรวม / README** เพื่อระบุเป้าหมายและการส่งต่องาน
3. แก้ **กฎกลาง / RULES** เพื่อกำหนดข้อปฏิบัติร่วมกันของทีม
4. เปิดแท็บ **Skills** หรือ **Agents** แล้วกดสร้าง เลือก Template และกรอกรายละเอียด
5. แก้ Markdown และกด **บันทึกไฟล์**
6. เปิด **Export** เลือกเครื่องมือและบทบาทหลัก แล้วดาวน์โหลด ZIP

มี Template สำหรับ General, Marketing, Editor และ Developer ครอบคลุมข้อมูลนำเข้า ขั้นตอน สิ่งที่ส่งมอบ เกณฑ์ตรวจรับ ข้อจำกัด และการส่งต่องาน

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
