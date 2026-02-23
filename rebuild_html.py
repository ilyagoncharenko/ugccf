#!/usr/bin/env python3
"""Вставляет данные из projects_data.json в index.html и dashboard.html."""
import json, re

with open('projects_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

json_str = json.dumps(data['projects'], ensure_ascii=False, separators=(',', ':'))

for filename in ['index.html', 'dashboard.html']:
    with open(filename, 'r', encoding='utf-8') as f:
        html = f.read()

    new_html = re.sub(
        r'const PROJECTS_DATA = \{.*?\};',
        f'const PROJECTS_DATA = {json_str};',
        html,
        flags=re.DOTALL
    )

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(new_html)

    print(f'  {filename} — обновлён')

print('Готово.')
