"""Возрастно-половой состав по районам Санкт-Петербурга на 01.01.2024 из бюллетеня Петростата.

Источник: Петростат, статистический бюллетень «Возрастно-половой состав населения
Санкт-Петербурга» (код издания 14001024), файл «14001024_Возраст-пол нас СПб 2024.pdf»,
таблицы на с. 29–30 (основные возрастные группы), 35 (коэффициенты нагрузки), 36 (средний возраст).
Данные только по районам — в разрезе МО бюллетень их не даёт.

Запуск: python3 age_sex_from_pdf.py "/путь/к/14001024_Возраст-пол нас СПб 2024.pdf" out.csv
"""
import re, subprocess, sys
import pandas as pd

FILE = '14001024_Возраст-пол нас СПб 2024.pdf'
DISTRICTS = ['Санкт-Петербург', 'Адмиралтейский', 'Василеостровский', 'Выборгский', 'Калининский', 'Кировский',
             'Колпинский', 'Красногвардейский', 'Красносельский', 'Кронштадтский', 'Курортный', 'Московский',
             'Невский', 'Петроградский', 'Петродворцовый', 'Приморский', 'Пушкинский', 'Фрунзенский', 'Центральный']
NUM = r'(\d[\d,]*)'
DEC = r'(\d+,\d+)'   # числа с дробной частью: коэффициенты и средний возраст


def section(lines, start, n_rows=len(DISTRICTS), ncol=4, num=NUM):
    """Первые n_rows строк «район + ncol чисел» после строки с заголовком start."""
    i = next(k for k, l in enumerate(lines) if start in l and '....' not in l)
    out = {}
    for l in lines[i:]:
        m = re.match(r'\s*(' + '|'.join(DISTRICTS) + r')\s+' + r'\s+'.join([num] * ncol) + r'\s*$', l)
        if m and m.group(1) not in out:
            out[m.group(1)] = [float(x.replace(',', '.')) for x in m.groups()[1:]]
        if len(out) == n_rows: break
    return out


def build(pdf):
    lines = subprocess.run(['pdftotext', '-layout', pdf, '-'], capture_output=True, text=True, check=True).stdout.splitlines()
    k = next(i for i, l in enumerate(lines) if 'ПО ОСНОВНЫМ ВОЗРАСТНЫМ ГРУППАМ на 1 января 2024 года' in l and '....' not in l)
    rest = lines[k:]
    both = section(rest, 'Оба пола')
    men = section(rest, 'Мужчины')
    women = section(rest, 'Женщины')
    load = section(lines, 'КОЭФФИЦИЕНТЫ НАГРУЗКИ НА ТРУДОСПОСОБНОЕ НАСЕЛЕНИЕ', ncol=3, num=DEC)
    age = section(lines, 'СРЕДНИЙ ВОЗРАСТ НАСЕЛЕНИЯ ПО РАЙОНАМ', ncol=3, num=DEC)
    rows = []
    for d in DISTRICTS:
        t, y, w, o = both[d]
        rows.append({'район': d if d == 'Санкт-Петербург' else d + ' район',
                     'всего, чел.': int(t), 'моложе трудоспособного': int(y), 'трудоспособного': int(w), 'старше трудоспособного': int(o),
                     'моложе трудосп., %': round(y / t * 100, 1), 'трудосп., %': round(w / t * 100, 1), 'старше трудосп., %': round(o / t * 100, 1),
                     'мужчин': int(men[d][0]), 'женщин': int(women[d][0]), 'женщин на 1000 мужчин': round(women[d][0] / men[d][0] * 1000),
                     'нагрузка общая, на 1000 трудосп.': load[d][0], 'нагрузка детьми 0–15': load[d][1], 'нагрузка старшими': load[d][2],
                     'средний возраст, лет': age[d][0], 'средний возраст мужчин': age[d][1], 'средний возраст женщин': age[d][2]})
    df = pd.DataFrame(rows).set_index('район')
    # контроль: сумма групп = итог; сумма районов = город
    assert (df[['моложе трудоспособного', 'трудоспособного', 'старше трудоспособного']].sum(axis=1) == df['всего, чел.']).all()
    assert df['всего, чел.'].iloc[1:].sum() == df.loc['Санкт-Петербург', 'всего, чел.']
    return df


if __name__ == '__main__':
    df = build(sys.argv[1])
    df.to_csv(sys.argv[2] if len(sys.argv) > 2 else 'age_sex_spb_districts_2024.csv', encoding='utf-8-sig')
    print(df.loc[['Санкт-Петербург', 'Адмиралтейский район', 'Центральный район', 'Петроградский район']].T)
