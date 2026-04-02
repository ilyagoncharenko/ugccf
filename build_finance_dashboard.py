#!/usr/bin/env python3
"""
Строит JSON с финансовой аналитикой агентства из данных Adesk.
Результат: finance_dashboard_data.json → используется в finance.html
"""
import json, os, datetime, urllib.request, urllib.parse
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ADESK_TOKEN = os.environ.get('ADESK_TOKEN', 'cd1d78b8839a49db9557f2e9d3f9fd62c142678a05ad482883278f4811d2daa0')
ADESK_BASE = 'https://api.adesk.ru/v1'


def adesk_get(endpoint, params=None):
    p = {'api_token': ADESK_TOKEN}
    if params:
        p.update(params)
    url = f'{ADESK_BASE}/{endpoint}?{urllib.parse.urlencode(p)}'
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode())


def fetch_and_flatten():
    """Получает все транзакции из Adesk и разворачивает сплиты в плоский список."""
    print('Загружаю транзакции из Adesk API...')
    data = adesk_get('transactions')
    txns = data.get('transactions', [])
    print(f'  Получено: {len(txns)} транзакций')

    flat = []
    for t in txns:
        base = {
            'id': t['id'],
            'date': t['dateIso'],
            'type': 'income' if t['type'] == 1 else 'expense',
            'amount': float(t['amount']),
            'description': t.get('description', ''),
            'contractor': t.get('contractor', {}).get('name', '') if t.get('contractor') else '',
            'is_split': t.get('isSplitted', False),
            'is_transfer': t.get('isTransfer', False),
        }

        if t.get('isSplitted') and t.get('parts'):
            for i, p in enumerate(t['parts']):
                row = dict(base)
                row['part_index'] = i
                row['part_amount'] = float(p['amount'])
                row['category'] = p.get('category', {}).get('name', '') if p.get('category') else ''
                row['category_id'] = p.get('category', {}).get('id', None) if p.get('category') else None
                row['project'] = p.get('project', {}).get('name', '') if p.get('project') else ''
                row['project_id'] = p.get('project', {}).get('id', None) if p.get('project') else None
                flat.append(row)
        else:
            row = dict(base)
            row['part_index'] = None
            row['part_amount'] = float(t['amount'])
            row['category'] = t.get('category', {}).get('name', '') if t.get('category') else ''
            row['category_id'] = t.get('category', {}).get('id', None) if t.get('category') else None
            row['project'] = t.get('project', {}).get('name', '') if t.get('project') else ''
            row['project_id'] = t.get('project', {}).get('id', None) if t.get('project') else None
            flat.append(row)

    # Сохраняем для дебага
    with open(os.path.join(BASE_DIR, 'adesk_flat.json'), 'w', encoding='utf-8') as f:
        json.dump(flat, f, ensure_ascii=False, indent=2)
    print(f'  Развёрнуто: {len(flat)} строк')
    return flat

# ── Конфигурация проектов ──────────────────────────────────────────
# status: active / completed / ignore / withdrawal
PROJECTS_CONFIG = {
    'Twinby':      {'id': 740235, 'status': 'completed'},
    'Luvu':        {'id': 740234, 'status': 'active'},
    'О-Комплекс':  {'id': 740240, 'status': 'active'},
    'Trebute':     {'id': 740236, 'status': 'ignore'},
    'Quick-Пицца': {'id': 740239, 'status': 'completed'},
    'Банктоты':    {'id': 740238, 'status': 'completed'},
    'Biorepair':   {'id': 740233, 'status': 'completed'},
    'YouDo':       {'id': 740241, 'status': 'completed'},
    'ART FACT':    {'id': 775597, 'status': 'active'},
    'Grass':       {'id': 778807, 'status': 'active'},
    'Lic':         {'id': 778808, 'status': 'active'},
    'Приложение':  {'id': 829554, 'status': 'withdrawal'},
}

# Категории, которые НЕ являются операционными расходами
NON_OPERATIONAL = {
    'Вывод денег из бизнеса',
    'Ввод денег в бизнес',
    'перевод между счетами names',
    'возврат ошибочного перевода',
    'ошибочный перевод (с возвратом)',
}

# Категории общих расходов агентства (не проектные)
SHARED_CATEGORIES = {
    'ЗП Основа', 'Аренда офиса', 'Комиссия банка', 'банковские услуги',
    'Сервисы', 'Лицензии и программное обеспечение', 'Налог на прибыль',
}


def load_flat():
    return fetch_and_flatten()


def month_key(date_str):
    """'2026-03-15' → '2026-03'"""
    return date_str[:7]


def months_between(start, end):
    """Возвращает список месяцев ['2025-11', '2025-12', ...] от start до end включительно."""
    result = []
    y, m = int(start[:4]), int(start[5:7])
    ey, em = int(end[:4]), int(end[5:7])
    while (y, m) <= (ey, em):
        result.append(f'{y:04d}-{m:02d}')
        m += 1
        if m > 12:
            m = 1
            y += 1
    return result


def build():
    rows = load_flat()
    today = datetime.date.today().isoformat()
    current_month = month_key(today)

    # ── 1. Определяем сроки проектов (от первой транзакции до последней или сейчас) ──
    project_dates = {}  # name → {first, last}
    for r in rows:
        proj = r['project']
        if not proj:
            continue
        d = r['date']
        if proj not in project_dates:
            project_dates[proj] = {'first': d, 'last': d}
        else:
            if d < project_dates[proj]['first']:
                project_dates[proj]['first'] = d
            if d > project_dates[proj]['last']:
                project_dates[proj]['last'] = d

    # Для проектов без транзакций — используем дату создания из Adesk
    project_created = {
        'Twinby': '2026-01-14', 'Luvu': '2026-01-14', 'О-Комплекс': '2026-01-14',
        'Trebute': '2026-01-14', 'Quick-Пицца': '2026-01-14', 'Банктоты': '2026-01-14',
        'Biorepair': '2026-01-14', 'YouDo': '2026-01-14',
        'ART FACT': '2026-03-12', 'Grass': '2026-03-17', 'Lic': '2026-03-17',
        'Приложение': '2026-03-28',
    }

    for name, cfg in PROJECTS_CONFIG.items():
        if name not in project_dates:
            project_dates[name] = {
                'first': project_created.get(name, '2026-01-14'),
                'last': today if cfg['status'] == 'active' else project_created.get(name, today),
            }
        # Завершённые проекты — last = последняя транзакция
        # Активные — last = сегодня
        if cfg['status'] == 'active':
            project_dates[name]['last'] = today

    # ── 2. Классифицируем все строки ──
    project_income = defaultdict(lambda: defaultdict(float))   # project → month → amount
    project_expense = defaultdict(lambda: defaultdict(float))  # project → month → amount
    project_direct_expense = defaultdict(lambda: defaultdict(float))  # только прямые расходы
    shared_expense = defaultdict(lambda: defaultdict(float))   # category → month → amount
    unassigned = defaultdict(lambda: defaultdict(float))       # 'unassigned' → month → amount
    non_operational_items = []  # вывод денег и т.д.
    withdrawal_items = []  # Приложение

    all_months = set()

    for r in rows:
        m = month_key(r['date'])
        all_months.add(m)
        amt = r['part_amount']
        proj = r['project']
        cat = r['category']
        proj_cfg = PROJECTS_CONFIG.get(proj, {})

        # Неоперационные транзакции
        if cat in NON_OPERATIONAL:
            non_operational_items.append(r)
            continue

        # Проект "Приложение" = вывод
        if proj == 'Приложение' or proj_cfg.get('status') == 'withdrawal':
            withdrawal_items.append(r)
            continue

        # Проект Trebute — игнорируем
        if proj_cfg.get('status') == 'ignore':
            continue

        # Транзакция привязана к проекту
        if proj and proj in PROJECTS_CONFIG:
            if r['type'] == 'income':
                project_income[proj][m] += amt
            else:
                project_expense[proj][m] += amt
                project_direct_expense[proj][m] += amt
            continue

        # Без проекта — определяем shared vs unassigned
        if r['type'] == 'income':
            # Доходы без проекта — тоже учитываем
            if cat in SHARED_CATEGORIES or not cat:
                unassigned['income'][m] += amt
            else:
                unassigned['income'][m] += amt
            continue

        # Расходы без проекта
        if cat in SHARED_CATEGORIES:
            shared_expense[cat][m] += amt
        elif cat:
            # Есть категория но нет проекта (PR-менеджеры, UGC-креаторы и тд без проекта)
            shared_expense[cat][m] += amt
        else:
            # Совсем без категории и проекта
            unassigned['expense'][m] += amt

    # ── 3. Распределяем общие расходы по проектам (равными долями, с учётом сроков) ──
    all_months_sorted = sorted(all_months)

    # Для каждого месяца определяем активные проекты (кроме ignore/withdrawal)
    def active_projects_in_month(m):
        """Проекты, которые были активны в данном месяце."""
        active = []
        for name, cfg in PROJECTS_CONFIG.items():
            if cfg['status'] in ('ignore', 'withdrawal'):
                continue
            dates = project_dates.get(name)
            if not dates:
                continue
            first_m = month_key(dates['first'])
            last_m = month_key(dates['last'])
            if first_m <= m <= last_m:
                active.append(name)
        return active

    # Распределение shared + unassigned расходов
    shared_distributed = defaultdict(lambda: defaultdict(float))  # project → month → amount

    for m in all_months_sorted:
        active = active_projects_in_month(m)
        if not active:
            continue
        n = len(active)

        # Shared categories
        for cat, months_data in shared_expense.items():
            if m in months_data:
                per_project = months_data[m] / n
                for proj in active:
                    shared_distributed[proj][m] += per_project

        # Unassigned expenses
        if m in unassigned.get('expense', {}):
            per_project = unassigned['expense'][m] / n
            for proj in active:
                shared_distributed[proj][m] += per_project

    # ── 4. Прогноз расходов для проектов без затрат (50% от бюджета) ──
    forecast = {}
    for name, cfg in PROJECTS_CONFIG.items():
        if cfg['status'] != 'active':
            continue
        total_direct = sum(sum(v.values()) for k, v in project_direct_expense.items() if k == name)
        total_income = sum(sum(v.values()) for k, v in project_income.items() if k == name)
        if total_income > 0 and total_direct < total_income * 0.15:
            # Мало прямых расходов (<15% от бюджета) — прогноз 50% минус уже потраченное
            forecast[name] = max(0, total_income * 0.5 - total_direct)

    # ── 5. Собираем итоговые данные ──
    projects_data = {}
    for name, cfg in PROJECTS_CONFIG.items():
        if cfg['status'] == 'ignore':
            continue

        dates = project_dates.get(name, {})
        proj_months = months_between(
            month_key(dates.get('first', '2026-01-01')),
            month_key(dates.get('last', today))
        ) if dates else []

        monthly = {}
        for m in proj_months:
            inc = project_income.get(name, {}).get(m, 0)
            direct_exp = project_expense.get(name, {}).get(m, 0)
            shared_exp = shared_distributed.get(name, {}).get(m, 0)
            total_exp = direct_exp + shared_exp
            monthly[m] = {
                'income': round(inc, 2),
                'direct_expense': round(direct_exp, 2),
                'shared_expense': round(shared_exp, 2),
                'total_expense': round(total_exp, 2),
                'profit': round(inc - total_exp, 2),
            }

        total_income = sum(d['income'] for d in monthly.values())
        total_direct = sum(d['direct_expense'] for d in monthly.values())
        total_shared = sum(d['shared_expense'] for d in monthly.values())
        total_expense = total_direct + total_shared
        forecast_exp = forecast.get(name, 0)

        projects_data[name] = {
            'id': cfg['id'],
            'status': cfg['status'],
            'start': dates.get('first', ''),
            'end': dates.get('last', ''),
            'total_income': round(total_income, 2),
            'total_direct_expense': round(total_direct, 2),
            'total_shared_expense': round(total_shared, 2),
            'total_expense': round(total_expense, 2),
            'forecast_expense': round(forecast_exp, 2),
            'profit': round(total_income - total_expense, 2),
            'profit_with_forecast': round(total_income - total_expense - forecast_exp, 2),
            'monthly': monthly,
        }

    # ── 6. Сводка по месяцам (всё агентство) ──
    agency_monthly = {}
    for m in all_months_sorted:
        inc = sum(projects_data[p]['monthly'].get(m, {}).get('income', 0) for p in projects_data)
        # Добавляем доходы без проекта
        inc += unassigned.get('income', {}).get(m, 0)
        direct = sum(projects_data[p]['monthly'].get(m, {}).get('direct_expense', 0) for p in projects_data)
        shared = sum(shared_expense[cat].get(m, 0) for cat in shared_expense)
        unass_exp = unassigned.get('expense', {}).get(m, 0)
        total_exp = direct + shared + unass_exp
        agency_monthly[m] = {
            'income': round(inc, 2),
            'direct_expense': round(direct, 2),
            'shared_expense': round(shared + unass_exp, 2),
            'total_expense': round(total_exp, 2),
            'profit': round(inc - total_exp, 2),
        }

    # ── 7. Разбивка общих расходов по категориям ──
    shared_by_category = {}
    for cat, months_data in shared_expense.items():
        total = sum(months_data.values())
        shared_by_category[cat] = {
            'total': round(total, 2),
            'monthly': {m: round(v, 2) for m, v in sorted(months_data.items())},
        }
    # Неразнесённые
    if unassigned.get('expense'):
        total = sum(unassigned['expense'].values())
        shared_by_category['Неразнесённые'] = {
            'total': round(total, 2),
            'monthly': {m: round(v, 2) for m, v in sorted(unassigned['expense'].items())},
        }

    # ── 8. Неоперационные ──
    non_op_total = sum(float(r['part_amount']) for r in non_operational_items if r['type'] == 'expense')
    withdrawal_total = sum(float(r['part_amount']) for r in withdrawal_items if r['type'] == 'expense')

    result = {
        'updated_at': today,
        'months': all_months_sorted,
        'projects': projects_data,
        'agency_monthly': agency_monthly,
        'shared_by_category': shared_by_category,
        'non_operational_total': round(non_op_total, 2),
        'withdrawal_total': round(withdrawal_total, 2),
        'total_forecast': round(sum(forecast.values()), 2),
        'agency_totals': {
            'income': round(sum(d['income'] for d in agency_monthly.values()), 2),
            'expense': round(sum(d['total_expense'] for d in agency_monthly.values()), 2),
            'profit': round(sum(d['profit'] for d in agency_monthly.values()), 2),
        },
    }

    out = os.path.join(BASE_DIR, 'finance_dashboard_data.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f'✓ Сохранено: {out}')
    print(f'  Проектов: {len(projects_data)}')
    print(f'  Месяцев: {len(all_months_sorted)}')
    print(f'  Доход агентства: {result["agency_totals"]["income"]:,.0f} ₽')
    print(f'  Расход агентства: {result["agency_totals"]["expense"]:,.0f} ₽')
    print(f'  Прибыль: {result["agency_totals"]["profit"]:,.0f} ₽')
    print(f'  Прогноз доп. расходов: {result["total_forecast"]:,.0f} ₽')
    print(f'  Неоперационные: {non_op_total:,.0f} ₽')
    print(f'  Вывод (Приложение): {withdrawal_total:,.0f} ₽')


def inline_into_html():
    """Встраивает JSON-данные прямо в finance.html (для работы без сервера)."""
    import re
    html_path = os.path.join(BASE_DIR, 'finance.html')
    json_path = os.path.join(BASE_DIR, 'finance_dashboard_data.json')

    with open(json_path, 'r', encoding='utf-8') as f:
        json_str = f.read().strip()

    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()

    # Заменяем инлайн-данные между маркерами
    pattern = r'const data = \{.*?\};\n\{'
    replacement_start = f'const data = {json_str};\n{{'
    html = re.sub(pattern, replacement_start, html, count=1, flags=re.DOTALL)

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f'✓ Данные встроены в {html_path}')


if __name__ == '__main__':
    build()
    inline_into_html()
