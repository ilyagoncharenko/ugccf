#!/usr/bin/env python3
"""
Получает финансовые данные по проектам из Adesk и сохраняет в adesk_data.json.
Запускается автоматически каждую ночь как часть пайплайна обновления дашборда.
"""
import os, json, urllib.request, urllib.parse, datetime

ADESK_TOKEN = os.environ.get('ADESK_TOKEN', 'cd1d78b8839a49db9557f2e9d3f9fd62c142678a05ad482883278f4811d2daa0')
BASE_URL = 'https://api.adesk.ru/v1'

# Соответствие: название проекта на дашборде → ID проекта в Adesk
PROJECT_IDS = {
    'Twinby':   740235,
    'Luvu':     740234,
    'Ocomplex': 740240,
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(BASE_DIR, 'adesk_data.json')


def adesk_get(endpoint, params=None):
    p = {'api_token': ADESK_TOKEN}
    if params:
        p.update(params)
    url = f'{BASE_URL}/{endpoint}?{urllib.parse.urlencode(p)}'
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode())


def fetch_project(name, project_id):
    print(f'  {name} (id={project_id})')
    data = adesk_get('transactions', {'project': project_id})
    txns = data.get('transactions', [])
    result = []
    for t in txns:
        result.append({
            'date':     t['dateIso'],
            'type':     t['type'],          # 1=доход, 2=расход
            'category': t['category']['name'],
            'amount':   float(t['amount']),
            'desc':     t['description'][:80].replace('\n', ' ').strip(),
        })
    result.sort(key=lambda x: x['date'])
    income  = sum(t['amount'] for t in result if t['type'] == 1)
    outcome = sum(t['amount'] for t in result if t['type'] == 2)
    print(f'    транзакций: {len(result)}, доход: {income:,.0f} ₽, расход: {outcome:,.0f} ₽')
    return result


def main():
    print('Подключаюсь к Adesk API...')
    today = datetime.date.today().isoformat()
    result = {'updated_at': today, 'projects': {}}

    for name, pid in PROJECT_IDS.items():
        try:
            txns = fetch_project(name, pid)
            result['projects'][name] = {
                'updated_at':   today,
                'transactions': txns,
            }
        except Exception as e:
            print(f'    ОШИБКА: {e}')

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f'\n✓ Сохранено: {OUTPUT_FILE}')


if __name__ == '__main__':
    main()
