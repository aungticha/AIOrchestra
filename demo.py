"""Create optional starter teams; existing teams are never changed."""
import server

TEAMS = [
    ('marketing', 'Marketing', 'วางกลยุทธ์ สร้างแคมเปญ และสื่อสารแบรนด์', 'campaign-planner', 'campaign-brief'),
    ('editor', 'Editorial', 'ตรวจภาษา โครงสร้าง และความถูกต้องก่อนเผยแพร่', 'content-editor', 'editorial-review'),
    ('developer', 'Development', 'ออกแบบ พัฒนา และตรวจสอบซอฟต์แวร์', 'software-engineer', 'implementation-review'),
]

def seed():
    for team, title, goal, agent, skill in TEAMS:
        if server.teamdir(team).exists():
            continue
        server.create_team(team, title, goal)
        server.write(server.document(team, 'agent', agent), server.frontmatter(agent, goal,
            f'# บทบาท\n\n{goal}\n\n## วิธีทำงาน\n1. อ่านกฎและเป้าหมายของทีม\n2. ตรวจโจทย์ ข้อมูลนำเข้า และข้อจำกัด\n3. ใช้ Skill ที่เกี่ยวข้องและตรวจผลลัพธ์\n\n## สิ่งที่ส่งมอบ\n- ผลงานพร้อมเหตุผล หลักฐาน และข้อจำกัด\n\n## ส่งต่องาน\n- ระบุสถานะ ขั้นตอนถัดไป และผู้รับผิดชอบ'))
        server.write(server.document(team, 'skill', skill), server.frontmatter(skill, f'ใช้เมื่อต้องการ{goal}',
            f'# {skill}\n\n## ข้อมูลนำเข้า\n- โจทย์ กลุ่มเป้าหมาย ข้อจำกัด และเกณฑ์ตรวจรับ\n\n## ขั้นตอน\n1. สรุปโจทย์และข้อมูลที่ขาด\n2. {goal}\n3. ตรวจสอบตามกฎส่วนกลาง\n\n## รูปแบบผลลัพธ์\n- สรุปข้อเสนอ ผลงาน และรายการตรวจสอบ\n\n## เกณฑ์ตรวจรับ\n- ตรงโจทย์ ตรวจสอบได้ และไม่แต่งข้อมูล'))
        print(f'Created {team}')

if __name__ == '__main__':
    seed()
