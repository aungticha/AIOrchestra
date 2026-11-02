"""Portable team identities independent of filesystem naming constraints."""
import hashlib
from pathlib import Path
import re
import unicodedata

LEGACY = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')
ENCODED = re.compile(r'_team_[0-9a-f]{64}')
RESERVED = {'con','prn','aux','nul',*(f'com{i}' for i in range(1,10)),*(f'lpt{i}' for i in range(1,10))}


def team_id(value):
    if not isinstance(value,str): raise ValueError('ระบุ ID ทีม')
    if any(unicodedata.category(c).startswith('C') for c in value):
        raise ValueError('ID ทีมไม่มีอักขระควบคุม')
    value=unicodedata.normalize('NFC',value.strip())
    if not value or len(value)>128 or any(unicodedata.category(c).startswith('C') for c in value):
        raise ValueError('ID ทีมต้องมี 1–128 ตัวอักษร และไม่มีอักขระควบคุม')
    return value


def folder_name(value):
    value=team_id(value)
    if len(value)<=64 and LEGACY.fullmatch(value) and value not in RESERVED:
        return value
    return '_team_'+hashlib.sha256(value.encode('utf-8')).hexdigest()


def team_dir(workspace,value):
    root=Path(workspace).resolve()/'teams'
    folder=(root/folder_name(value)).resolve()
    if not folder.is_relative_to(root): raise ValueError('Team path outside library')
    return folder
