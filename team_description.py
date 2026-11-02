"""Editable team descriptions with compatibility for existing README files."""
import re

BEGIN='<!-- AIORCHESTRA:DESCRIPTION:BEGIN -->'
END='<!-- AIORCHESTRA:DESCRIPTION:END -->'


def validate(value):
    if not isinstance(value,str) or len(value)>4000 or any(ord(c)<32 and c not in '\r\n\t' for c in value):
        raise ValueError('Description ต้องเป็นข้อความไม่เกิน 4000 ตัวอักษร')
    if BEGIN in value or END in value: raise ValueError('Description ไม่รองรับ marker ภายใน')
    return value.strip()


def region(text):
    if BEGIN in text or END in text:
        if text.count(BEGIN)!=1 or text.count(END)!=1 or text.index(BEGIN)>text.index(END):
            raise ValueError('Description markers ใน README ไม่ครบหรือซ้ำ')
        return text.index(BEGIN), text.index(END)+len(END), True
    heading=re.search(r'^# [^\r\n]*',text,re.M)
    start=heading.end() if heading else 0
    section=re.search(r'^## ',text[start:],re.M)
    return start,start+section.start() if section else len(text),False


def get(text):
    start,end,marked=region(text)
    value=text[start:end]
    if marked: value=value[len(BEGIN):-len(END)]
    return value.strip()


def replace(text,value):
    value=validate(value)
    start,end,marked=region(text)
    block=BEGIN+'\n'+value+'\n'+END
    return text[:start]+('' if marked else '\n\n')+block+('' if marked else '\n\n')+text[end:]
