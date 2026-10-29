"""Сборка таблицы численности населения МО Санкт-Петербурга из PDF Петростата.

Запуск (нужен poppler-utils: sudo apt install poppler-utils):
    python3 population_from_pdfs.py "/путь/к/папке/с/PDF" out.csv

Источник файлов: https://78.rosstat.gov.ru/folder/27595 (раздел «Население»).
"""
import os, re, subprocess, sys
import pandas as pd

FILES = {  # графа → имя файла, как скачано с сайта Петростата
    '01.01.2018': 'СПб+числ+на+01.01.2018+по+МО+в+чел.pdf',
    '01.01.2019': 'СПб числ на 01.01.2019 .pdf',
    '01.01.2020': 'Числ.СПб на 01.01.2020.pdf',
    '01.01.2021': 'Числ.СПб на 01.01.2021.pdf',
    '01.01.2022': 'Числ.СПб на 01.01.2022 .pdf',
    '01.01.2023': 'Числ.СПб на 01.01.2023.pdf',
    '01.01.2024': 'СПб числ на 01.01.2024 по МО.pdf',
    '01.01.2025': 'СПб числ на 01.01.2025 по МО .pdf',
}
CENSUS = 'Экспресс_ВПН-2020 СПБ(1).pdf'   # графы ВПН-2020 и ВПН-2010
RENAMED = {'МО Парнас': 'МО Сергиевское', 'МО Черная речка': 'МО Ланское', 'МО N 75': 'МО Александровский'}
TOWNS = {'Колпино', 'Красное Село', 'Кронштадт', 'Зеленогорск', 'Сестрорецк', 'Ломоносов', 'Петергоф', 'Павловск', 'Пушкин'}


def key(n):
    """Приводит название к единому виду: регистр, ё/ѐ, «г.», «Муниципальный округ»."""
    n = re.sub(r'\s+', ' ', n.strip()).replace('ѐ', 'е').replace('ё', 'е').replace('Ё', 'Е').replace('№', 'N')
    n = n.replace('г. Санкт-Петербург', 'Санкт-Петербург')
    n = re.sub(r'^муниципальный округ\s+', 'МО ', n, flags=re.I)
    n = re.sub(r'^МО округ ', 'МО ', n)
    n = re.sub(r'^г\. ?', 'город ', n)
    n = re.sub(r'^[Пп]оселок', 'поселок', n)
    if n in TOWNS: n = 'город ' + n
    if n == 'аэродром' or n.lower() == 'мо комендантский аэродром': n = 'МО Комендантский аэродром'  # перенос строки в PDF переписи
    return RENAMED.get(n, n)


def text(path):
    return subprocess.run(['pdftotext', '-layout', path, '-'], capture_output=True, text=True, check=True).stdout


def build(folder):
    data, order = {}, []
    def add(n, col, v):
        k = key(n); data.setdefault(k, {})[col] = v
        if k not in order: order.append(k)
    for col, fn in FILES.items():
        for line in text(os.path.join(folder, fn)).splitlines():
            m = re.match(r'\s*(\S.*?)\s{2,}(\d[\d ]*\d)\s*$', line)
            if m: add(m.group(1), col, int(m.group(2).replace(' ', '')))
    for line in text(os.path.join(folder, CENSUS)).splitlines():
        m = re.match(r'\s*(\S.*?)\s{2,}(\d+)\s+(\d+)\s+\S', line)
        if m:
            add(m.group(1), 'ВПН-2010', int(m.group(3)))
            add(m.group(1), 'ВПН-2020 (01.10.2021)', int(m.group(2)))
    cols = ['ВПН-2010', '01.01.2018', '01.01.2019', '01.01.2020', '01.01.2021', '01.01.2022',
            'ВПН-2020 (01.10.2021)', '01.01.2023', '01.01.2024', '01.01.2025']
    df = pd.DataFrame.from_dict(data, orient='index').reindex(order)[cols]
    district, d = [], ''
    for n in df.index:
        if n.endswith('район'): d = n
        district.append('' if n == 'Санкт-Петербург' else d)
    df.insert(0, 'район', district)
    df.index.name = 'территория'
    df['ВПН-2020 к ВПН-2010, %'] = (df['ВПН-2020 (01.10.2021)'] / df['ВПН-2010'] * 100).round(1)
    df['01.01.2025 к ВПН-2020, %'] = (df['01.01.2025'] / df['ВПН-2020 (01.10.2021)'] * 100).round(1)
    return df


if __name__ == '__main__':
    df = build(sys.argv[1])
    df.to_csv(sys.argv[2] if len(sys.argv) > 2 else 'population_spb_mo_2010_2025.csv', encoding='utf-8-sig')
    print(df.loc[['Санкт-Петербург', 'Адмиралтейский район', 'МО Коломна']].T)
