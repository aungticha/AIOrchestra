---
name: "pipeline-engineering"
description: "สร้างหรือแก้ pipeline/CI/CD เฉพาะเมื่อผู้ใช้สั่งเรื่อง pipeline โดยชัดเจน ไม่เปิดใช้จาก feature หรือ commit/push ปกติ"
---

# pipeline-engineering

1. ตรวจว่าคำสั่งปัจจุบันระบุงาน pipeline ถ้าไม่ระบุ ให้ข้ามและไม่สร้างไฟล์รอไว้
2. ใช้ runner/trigger/checks ตามโจทย์ ลด permissions และอ้าง secrets ผ่านกลไกของผู้ให้บริการ
3. ตรวจ syntax/คำสั่งที่รันได้ในเครื่องและบอกสิ่งที่ยังต้องตรวจบน runner จริง ไม่เพิ่ม deploy โดยไม่มีคำสั่ง
