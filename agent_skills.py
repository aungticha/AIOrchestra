"""Read/write the portable skills field without a full YAML dependency."""
import json
import re

ID = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')


def front(content):
    match = re.match(r'\A(\ufeff?---\r?\n)(.*?)(\r?\n---(?:\r?\n|$))',content,re.S)
    if not match: raise ValueError('Agent ต้องมี YAML frontmatter')
    return match


def assigned(content):
    lines=front(content).group(2).splitlines()
    locations=[i for i,line in enumerate(lines) if re.match(r'^skills\s*:',line)]
    if not locations: return None
    if len(locations)>1: raise ValueError('skills ซ้ำใน frontmatter')
    index=locations[0]
    value=lines[index].split(':',1)[1].strip()
    if value:
        try: result=json.loads(value)
        except json.JSONDecodeError:
            if not value.startswith('[') or not value.endswith(']'): raise ValueError('skills ต้องเป็น list ของ Skill IDs') from None
            result=[x.strip().strip('\"\'') for x in value[1:-1].split(',')] if value[1:-1].strip() else []
    else:
        result=[]
        for line in lines[index+1:]:
            if line.strip() and not line.startswith((' ','\t','-')): break
            if not line.strip() or line.lstrip().startswith('#'): continue
            match=re.match(r'^\s*-\s+([a-z0-9-]+)\s*(?:#.*)?$',line)
            if not match: raise ValueError('ใช้ skills แบบ JSON list หรือ YAML list ของ Skill IDs')
            result.append(match.group(1))
    if not isinstance(result,list) or len(result)>200 or any(not isinstance(x,str) or len(x)>64 or not ID.fullmatch(x) for x in result):
        raise ValueError('skills ต้องเป็น list ของ Skill IDs ที่ถูกต้อง')
    if len(result)!=len(set(result)): raise ValueError('Skill IDs ต้องไม่ซ้ำ')
    return result


def set_assigned(content,values):
    match=front(content)
    # Validate both the new list and any existing syntax before rewriting.
    assigned(content)
    replacement='skills: '+json.dumps(values,ensure_ascii=False)
    lines=match.group(2).splitlines()
    result=[];skip=False
    for line in lines:
        if re.match(r'^skills\s*:',line):
            result.append(replacement);skip=True;continue
        if skip:
            if not line.strip() or line.startswith((' ','\t','-')): continue
            skip=False
        result.append(line)
    if not any(re.match(r'^skills\s*:',line) for line in lines): result.append(replacement)
    newline='\r\n' if '\r\n' in content else '\n'
    updated=content[:match.start(2)]+newline.join(result)+content[match.end(2):]
    assigned(updated)
    return updated


def effective(content,available):
    values=assigned(content)
    return sorted(available) if values is None else values


def text_field(content,key):
    matches=re.findall(r'^'+re.escape(key)+r'[ \t]*:[ \t]*(.*)$',front(content).group(2),re.M)
    if len(matches)>1: raise ValueError(key+' ซ้ำใน frontmatter')
    if not matches: return None
    raw=matches[0].strip()
    if raw.startswith('"'):
        try: value=json.loads(raw)
        except json.JSONDecodeError: raise ValueError(key+' ต้องเป็นข้อความบรรทัดเดียว') from None
    elif raw.startswith("'") and raw.endswith("'"): value=raw[1:-1].replace("''", "'")
    else: value=raw
    if not isinstance(value,str) or any(ord(c)<32 for c in value): raise ValueError(key+' ต้องเป็นข้อความบรรทัดเดียว')
    return value.strip()


def identity(content,fallback):
    return {'displayName':text_field(content,'display_name') or fallback,
            'role':text_field(content,'role') or text_field(content,'description') or 'ยังไม่ระบุ Role',
            'description':text_field(content,'description') or ''}


def set_profile(content,display_name,role,description):
    fields={'display_name':display_name,'role':role,'description':description}
    for key,value in fields.items():
        limit=2000 if key=='description' else 200
        if not isinstance(value,str) or not value.strip() or len(value)>limit or any(ord(c)<32 for c in value):
            raise ValueError(key+f' ต้องเป็นข้อความบรรทัดเดียวที่ไม่ว่าง ไม่เกิน {limit} ตัวอักษร')
    match=front(content)
    lines=match.group(2).splitlines()
    for key,value in fields.items():
        text_field(content,key)
        replacement=key+': '+json.dumps(value.strip(),ensure_ascii=False)
        found=False
        for index,line in enumerate(lines):
            if re.match(r'^'+re.escape(key)+r'\s*:',line): lines[index]=replacement;found=True
        if not found: lines.append(replacement)
    newline='\r\n' if '\r\n' in content else '\n'
    return content[:match.start(2)]+newline.join(lines)+content[match.end(2):]
