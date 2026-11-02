"""Portable, explicit avatar appearance stored as JSON in Markdown frontmatter."""
import json
import re
import agent_skills

DEFAULT = dict(gender='neutral', hairStyle='short', hairColor='#493749', shirtColor='#a995ef', skinTone='#e2b99b', outfit='shirt')
CHOICES = dict(gender=('neutral','male','female'), hairStyle=('short','long','bob','bald'), outfit=('shirt','hoodie','tshirt'))

def validate(value):
    if not isinstance(value,dict) or set(value)-set(DEFAULT): raise ValueError('Invalid avatar appearance')
    result={**DEFAULT,**value}
    for key,choices in CHOICES.items():
        if result[key] not in choices: raise ValueError('Invalid appearance '+key)
    for key in ('hairColor','shirtColor','skinTone'):
        if not isinstance(result[key],str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',result[key]): raise ValueError('Invalid appearance color')
    return result

def get(content):
    values=re.findall(r'^appearance\s*:\s*(.+)$',agent_skills.front(content).group(2),re.M)
    if len(values)>1: raise ValueError('appearance ซ้ำ')
    try: return validate(json.loads(values[0])) if values else dict(DEFAULT)
    except json.JSONDecodeError: raise ValueError('appearance ต้องเป็น JSON object บรรทัดเดียว') from None

def set_value(content,value):
    get(content)
    match=agent_skills.front(content)
    lines=[line for line in match.group(2).splitlines() if not re.match(r'^appearance\s*:',line)]
    lines.append('appearance: '+json.dumps(validate(value),ensure_ascii=False))
    return content[:match.start(2)]+'\n'.join(lines)+content[match.end(2):]
