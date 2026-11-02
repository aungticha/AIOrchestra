"""Capability-based authoring defaults, not a live provider or a model benchmark."""
CHECKED_AT='2026-11-01'
SOURCES={
 'openai':'https://developers.openai.com/api/docs/models',
 'claude':'https://platform.claude.com/docs/en/models/overview',
 'gemini-search':'https://ai.google.dev/gemini-api/docs/google-search',
 'gemini-image':'https://ai.google.dev/gemini-api/docs/image-generation',
}
MODELS={
 'codex':{'label':'Codex / GPT coding models','provider':'OpenAI','capabilities':['coding','reasoning','tools'],'source':'openai'},
 'gpt-reasoning':{'label':'GPT reasoning models','provider':'OpenAI','capabilities':['reasoning','writing','data','vision','tools'],'source':'openai'},
 'gpt-image':{'label':'GPT Image','provider':'OpenAI','capabilities':['image-generation','image-editing'],'source':'openai'},
 'claude-opus':{'label':'Claude Opus / Fable','provider':'Anthropic','capabilities':['reasoning','coding','writing','data','vision','tools'],'source':'claude'},
 'claude-sonnet':{'label':'Claude Sonnet','provider':'Anthropic','capabilities':['writing','coding','reasoning','vision','data','tools'],'source':'claude'},
 'claude-haiku':{'label':'Claude Haiku','provider':'Anthropic','capabilities':['extraction','classification','fast-text','tools'],'source':'claude'},
 'gemini-search':{'label':'Gemini + Google Search grounding','provider':'Google','capabilities':['web-search','citations','vision','reasoning'],'source':'gemini-search'},
 'gemini-image':{'label':'Gemini Image','provider':'Google','capabilities':['image-generation','image-editing'],'source':'gemini-image'},
}
TEMPLATES=[
 {'id':'general','label':'งานทั่วไป / ประสานงาน','goal':'รับโจทย์ แยกงาน เลือกวิธีทำงาน และสรุปสิ่งที่ต้องส่งต่อ','capabilities':['tools'],'models':['claude-sonnet','gpt-reasoning'],'deliverable':'สรุปผล รายการงาน และสิ่งที่ต้องทำต่อ','checks':'ตรวจว่าครบโจทย์และระบุข้อจำกัด'},
 {'id':'research','label':'ค้นหาข้อมูล / งานวิจัย','goal':'ค้นข้อมูลจากแหล่งที่น่าเชื่อถือ ตรวจวันที่ เปรียบเทียบหลักฐาน และอ้างอิงที่มา','capabilities':['web-search','citations'],'models':['gemini-search'],'deliverable':'รายงานสรุปพร้อมลิงก์อ้างอิง วันที่ข้อมูล และข้อเท็จจริงที่ยังยืนยันไม่ได้','checks':'ตรวจแหล่งอ้างอิงและความทันสมัย แยกข้อเท็จจริงออกจากข้อสรุป'},
 {'id':'graphics','label':'ภาพกราฟิก / สร้างและแก้ไขภาพ','goal':'กำหนด art direction องค์ประกอบ สี ขนาด และสร้างหรือแก้ไขภาพตาม brief','capabilities':['image-generation','image-editing'],'models':['gpt-image','gemini-image'],'deliverable':'ไฟล์ภาพตามขนาดที่ต้องการ พร้อมแนวทางภาพและคำอธิบายเวอร์ชัน','checks':'ตรวจข้อความบนภาพ อัตราส่วน ความละเอียด และความตรงกับ brief'},
 {'id':'analysis','label':'คิดวิเคราะห์ / วางกลยุทธ์','goal':'แยกปัญหา ตรวจสมมติฐาน เปรียบเทียบทางเลือก และประเมินข้อดีข้อเสียด้วยหลักฐาน','capabilities':['reasoning'],'models':['claude-opus','gpt-reasoning'],'deliverable':'ข้อเสนอพร้อมเหตุผล ทางเลือก หลักฐาน และความไม่แน่นอน','checks':'ตรวจสมมติฐาน ตัวเลข ความสอดคล้อง และผลกระทบของทางเลือก'},
 {'id':'coding','label':'พัฒนาซอฟต์แวร์ / เขียนโค้ด','goal':'วิเคราะห์ความต้องการ ออกแบบ พัฒนา แก้บั๊ก และทดสอบซอฟต์แวร์','capabilities':['coding','tools'],'models':['codex','claude-opus','claude-sonnet'],'deliverable':'โค้ดที่แก้พร้อมผลการทดสอบและวิธีใช้งาน','checks':'ตรวจพฤติกรรมที่เปลี่ยน ความปลอดภัย และความเข้ากันได้'},
 {'id':'writing','label':'เขียนเนื้อหา / เรียบเรียง / แปลภาษา','goal':'กำหนดกลุ่มผู้อ่าน น้ำเสียง โครงสร้าง และเรียบเรียงเนื้อหาให้ชัดเจน','capabilities':['writing'],'models':['claude-sonnet','gpt-reasoning'],'deliverable':'เนื้อหาพร้อมใช้ตามภาษา น้ำเสียง และรูปแบบที่กำหนด','checks':'ตรวจข้อเท็จจริง ภาษา ความสม่ำเสมอ และความเหมาะสมกับผู้อ่าน'},
 {'id':'data','label':'วิเคราะห์ข้อมูล / ตาราง / คำนวณ','goal':'ตรวจคุณภาพข้อมูล วิเคราะห์ คำนวณ และสรุปผลที่ทำซ้ำตรวจสอบได้','capabilities':['data','reasoning'],'models':['gpt-reasoning','claude-opus'],'deliverable':'ผลวิเคราะห์พร้อมวิธีคำนวณ ตารางหรือกราฟ และข้อจำกัดของข้อมูล','checks':'ตรวจสูตร หน่วย missing values และความสามารถทำซ้ำ'},
 {'id':'vision','label':'อ่านภาพ / เอกสาร / ข้อมูลหลายรูปแบบ','goal':'อ่านและตีความภาพหรือเอกสาร ดึงข้อมูลโดยรักษาบริบทและระบุส่วนที่อ่านไม่ชัด','capabilities':['vision'],'models':['gemini-search','claude-sonnet','gpt-reasoning'],'deliverable':'ข้อมูลที่สกัดได้พร้อมตำแหน่งอ้างอิงและส่วนที่ไม่แน่ใจ','checks':'ตรวจเทียบกับต้นฉบับ ไม่เดาข้อความหรือตัวเลขที่อ่านไม่ได้'},
 {'id':'fast','label':'งานเร็ว / จัดหมวดหมู่ / สกัดข้อมูล','goal':'จัดหมวดหมู่ สกัดข้อมูล และสรุปข้อความสั้นตาม schema ที่กำหนด','capabilities':['extraction','classification'],'models':['claude-haiku'],'deliverable':'ผลลัพธ์แบบมีโครงสร้างตาม schema','checks':'ตรวจ schema ความครบถ้วน และจัดการกรณีข้อมูลไม่ตรงเงื่อนไข'},
]
BY_ID={item['id']:item for item in TEMPLATES}


def defaults(category='general',mode='recommended'):
    if not isinstance(category,str) or category not in BY_ID: raise ValueError('เลือกประเภทงานที่รองรับ')
    if mode not in ('auto','recommended'): raise ValueError('เลือก Auto หรือ Recommended')
    template=BY_ID[category]
    return {'workType':category,'routingMode':mode,'requiredCapabilities':template['capabilities'],
            'recommendedModels':template['models'],'recommendationOnly':True,'checkedAt':CHECKED_AT}


def catalog():
    return {'templates':TEMPLATES,'models':MODELS,'sources':SOURCES,'checkedAt':CHECKED_AT,
            'note':'คำแนะนำตามความสามารถ ไม่ใช่คะแนนเปรียบเทียบหรือการยืนยันสิทธิ์ใช้งาน ต้องตรวจโมเดลและเครื่องมือที่เชื่อมต่อก่อนรัน'}


def markdown(category='general',mode='recommended'):
    settings=defaults(category,mode)
    item=BY_ID[category]
    return f"## ประเภทงานและแนวทางเลือกโมเดล\n- ประเภทงาน: {item['label']} ({category})\n- หน้าที่: {item['goal']}\n- รูปแบบผลลัพธ์: {item['deliverable']}\n- เกณฑ์ตรวจรับ: {item['checks']}\n- โหมดเลือก: {mode}\n- ความสามารถที่ต้องใช้: {', '.join(settings['requiredCapabilities'])}\n- กลุ่มโมเดลแนะนำ: {', '.join(MODELS[m]['label'] for m in settings['recommendedModels'])}\n- เป็นคำแนะนำ ยังไม่ใช่การเรียกโมเดลอัตโนมัติ ต้องตรวจรุ่น สิทธิ์ และเครื่องมือที่พร้อมใช้ก่อน\n"
