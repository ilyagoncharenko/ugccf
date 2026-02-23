#!/usr/bin/env python3
"""Вставляет данные из projects_data.json и adesk_data.json в index.html и dashboard.html."""
import json, re, os, datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ─── Google Sheets данные ───────────────────────────────────────────────────
with open(os.path.join(BASE_DIR, 'projects_data.json'), 'r', encoding='utf-8') as f:
    data = json.load(f)

projects_json = json.dumps(data['projects'], ensure_ascii=False, separators=(',', ':'))

# ─── Adesk данные ────────────────────────────────────────────────────────────
adesk_file = os.path.join(BASE_DIR, 'adesk_data.json')
adesk_by_project = {}

if os.path.exists(adesk_file):
    with open(adesk_file, 'r', encoding='utf-8') as f:
        adesk_raw = json.load(f)
    adesk_by_project = adesk_raw.get('projects', {})
    print(f'  Adesk данные загружены: {list(adesk_by_project.keys())}')
else:
    print('  adesk_data.json не найден, секция финансов пропущена')

# Строим объект ADESK_DATA для JS
adesk_js_obj = {}
for proj_name, proj_data in adesk_by_project.items():
    adesk_js_obj[proj_name] = {
        'updated_at':   proj_data.get('updated_at', ''),
        'transactions': proj_data.get('transactions', []),
    }

adesk_json = json.dumps(adesk_js_obj, ensure_ascii=False, separators=(',', ':'))

# ─── Дата обновления ─────────────────────────────────────────────────────────
now = datetime.datetime.now()
gen_at_str = now.isoformat()

# ─── Обновляем файлы ─────────────────────────────────────────────────────────
for filename in ['index.html', 'dashboard.html']:
    filepath = os.path.join(BASE_DIR, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()

    # 1. PROJECTS_DATA
    html = re.sub(
        r'const PROJECTS_DATA = \{.*?\};',
        f'const PROJECTS_DATA = {projects_json};',
        html, flags=re.DOTALL
    )

    # 2. ADESK_DATA (только если есть данные)
    if adesk_js_obj:
        html = re.sub(
            r'const ADESK_DATA = \{.*?\};',
            f'const ADESK_DATA = {adesk_json};',
            html, flags=re.DOTALL
        )

    # 3. Дата обновления (genAt)
    html = re.sub(
        r'const genAt = new Date\("[^"]*"\);',
        f'const genAt = new Date("{gen_at_str}");',
        html
    )

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f'  {filename} — обновлён')

print('Готово.')
