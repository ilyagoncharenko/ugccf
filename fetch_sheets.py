#!/usr/bin/env python3
"""
Content Factory — сбор данных по всем проектам из Google Sheets.
Добавь новый проект в PROJECTS ниже и запусти скрипт.
"""

import os, json, re, warnings, datetime, time
warnings.filterwarnings('ignore')

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ─── КОНФИГ ПРОЕКТОВ ───────────────────────────────────────────────────────────
PROJECTS = [
    {
        "name": "Twinby",
        "spreadsheet_id": "1DqVJAwEvxw7HoUrTNZNCw4jVAeK7_ow_beRiEiGVcHM",
        "color": "#a78bfa",   # фиолетовый
        "budget": 500000,     # бюджет кампании в рублях
    },
    {
        "name": "Luvu",
        "spreadsheet_id": "1j9DS35rRRmVjYGKBH3iEox1Ldk60k79qqSe2uyWL6-Y",
        "color": "#34d399",   # зелёный
        "budget": 1000000,    # бюджет кампании в рублях
    },
]
# ────────────────────────────────────────────────────────────────────────────────

SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(BASE_DIR, 'credentials.json')
TOKEN_FILE        = os.path.join(BASE_DIR, 'token.json')
OUTPUT_FILE       = os.path.join(BASE_DIR, 'projects_data.json')


def get_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as f:
            f.write(creds.to_json())
    return build('sheets', 'v4', credentials=creds)


def get_all_sheets(service, spreadsheet_id):
    spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return [
        {'title': s['properties']['title'], 'gid': s['properties']['sheetId']}
        for s in spreadsheet.get('sheets', [])
    ]


def fetch_sheet_rows(service, spreadsheet_id, sheet_title):
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_title}'"
    ).execute()
    return result.get('values', [])


def is_date_sheet(title):
    return bool(re.match(r'\d{4}-\d{2}-\d{2}', title.strip()))


def parse_int(val):
    try:
        return int(float(str(val).replace(' ', '').replace(',', '.').replace('\xa0', '')))
    except:
        return 0


def parse_channels(rows):
    """Парсит строки листа и возвращает список каналов."""
    if not rows:
        return []
    header = [h.strip().lower() for h in rows[0]]
    channels = []
    for row in rows[1:]:
        if not row:
            continue
        d = {header[i]: row[i] if i < len(row) else '' for i in range(len(header))}
        net = d.get('social_network', '').strip().upper()
        if net not in ('INSTAGRAM', 'TIKTOK', 'YOUTUBE'):
            continue
        channels.append({
            'social_network': net,
            'channel_url':    d.get('channel_url', '').strip(),
            'total_videos':   parse_int(d.get('total_videos', 0)),
            'total_views':    parse_int(d.get('total_views', 0)),
        })
    return channels


def aggregate(channels):
    """Суммирует просмотры по платформам."""
    by_platform = {'INSTAGRAM': 0, 'TIKTOK': 0, 'YOUTUBE': 0}
    total = 0
    for ch in channels:
        p = ch['social_network']
        v = ch['total_views']
        by_platform[p] = by_platform.get(p, 0) + v
        total += v
    return total, by_platform


def process_project(service, project):
    name = project['name']
    sid  = project['spreadsheet_id']
    print(f"\n{'='*50}")
    print(f"  Проект: {name}")
    print(f"{'='*50}")

    all_sheets = get_all_sheets(service, sid)
    date_sheets = [s for s in all_sheets if is_date_sheet(s['title'])]
    other_sheets = [s for s in all_sheets if not is_date_sheet(s['title'])]

    print(f"  Листов с датами: {len(date_sheets)}")
    print(f"  Прочих листов:   {len(other_sheets)}")

    # Данные каналов — из последнего по дате листа
    channels_data = []
    if date_sheets:
        last_sheet = sorted(date_sheets, key=lambda s: s['title'])[-1]
        rows = fetch_sheet_rows(service, sid, last_sheet['title'])
        channels_data = parse_channels(rows)
        print(f"  Каналов (на {last_sheet['title']}): {len(channels_data)}")

    # Временной ряд
    daily_data = []
    for s in sorted(date_sheets, key=lambda x: x['title']):
        title = s['title']
        try:
            rows  = fetch_sheet_rows(service, sid, title)
            chs   = parse_channels(rows)
            total, by_platform = aggregate(chs)
            daily_data.append({
                'date':        title,
                'total_views': total,
                'by_platform': by_platform,
                'channels':    len(chs),
            })
            print(f"    {title}: {total:>12,} views  ({len(chs)} каналов)")
        except Exception as e:
            print(f"    {title}: ОШИБКА — {e}")
        time.sleep(1.1)  # не превышаем лимит 60 req/min

    # Считаем дельты (новых просмотров за день)
    for i, row in enumerate(daily_data):
        if i == 0:
            row['delta'] = row['total_views']
            row['delta_by_platform'] = dict(row['by_platform'])
        else:
            prev = daily_data[i - 1]
            row['delta'] = max(0, row['total_views'] - prev['total_views'])
            row['delta_by_platform'] = {
                p: max(0, row['by_platform'].get(p, 0) - prev['by_platform'].get(p, 0))
                for p in row['by_platform']
            }

    return {
        'name':           name,
        'spreadsheet_id': sid,
        'color':          project.get('color', '#a78bfa'),
        'channels_data':  channels_data,
        'daily_data':     daily_data,
        'updated_at':     datetime.datetime.now().isoformat(),
    }


def main():
    print("Подключаюсь к Google Sheets API...")
    service = get_service()

    result = {'projects': {}, 'generated_at': datetime.datetime.now().isoformat()}

    for project in PROJECTS:
        data = process_project(service, project)
        result['projects'][data['name']] = data

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Данные сохранены: {OUTPUT_FILE}")
    for name, pdata in result['projects'].items():
        days  = len(pdata['daily_data'])
        total = pdata['daily_data'][-1]['total_views'] if pdata['daily_data'] else 0
        print(f"  {name}: {days} дней, итого {total:,} просмотров")


if __name__ == '__main__':
    main()
