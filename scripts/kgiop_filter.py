"""Фильтр выгрузки ИСС КГИОП по Коломне и сверка с ЕГРОКН.

Вход:
  KGIOP_CSV   — выгрузка ИСС КГИОП на весь город (; , cp1251): «2026-10-09_14-35-23.csv» — без «элементов», с целым № ЕГРОКН;
                подходит и старая «для дениса.csv» (с элементами, № ЕГРОКН испорчен Excel — тогда сопоставление по адресу)
  EGROKN_CSV  — все объекты ЕГРОКН по СПб (из data-69-structure-16, колонки reg,name,type,cat,address,lon,lat;
                у 586 объектов нет точки — у них сопоставление только по адресу)
  HOITH_GPKG  — «Карта возраста домов», вырезка по Коломне (адреса зданий + контуры)
  BOUNDS      — kolomna_boundary_variants.geojson (версии 1–4)
Выход (OUT_DIR):
  okn_kolomna_kgiop.csv      — объекты КГИОП Адмиралтейского района в пределах версии 4 (+ неопределённые),
                               с координатой, способом привязки, столбцами «версия 1…4» и сопоставлением с ЕГРОКН
  okn_kgiop_vs_egrokn.csv    — сверка: объекты ЕГРОКН в версии 4 ↔ КГИОП
  okn_kolomna_kgiop.xlsx     — то же для команды: сводка по версиям, выявленные, объекты без пары, методика

В ИСС нет координат — поэтому привязка к карте по адресу:
  1) «улица + номер дома» ↔ адресам зданий HOITH и ЕГРОКН (точно);
  2) ближайший номер той же чётности на той же улице, разница ≤ 6 (приблизительно);
  3) совпадение наименования с ЕГРОКН (мосты, сады и т. п. без номера дома);
  4) точка другого объекта того же комплекса («Код Компл.») — ограды, сады, элементы ансамблей;
  0) вручную по карте (MANUAL ниже) — набережные, скверы, площади без номеров; применяется первым, координаты ±50 м.
Запуск: python3 kgiop_filter.py KGIOP_CSV EGROKN_CSV HOITH_GPKG BOUNDS OUT_DIR
"""
import re, sys, os
import pandas as pd, geopandas as gpd
from shapely.geometry import Point

TYPES = [  # (регэксп типа, канонический тип)
    (r'набережн\w*|наб\b\.?', 'наб'), (r'улиц\w*|ул\b\.?', 'ул'), (r'проспект\w*|просп\b\.?|пр-т\b|пр\b\.?', 'пр'),
    (r'переул\w*|пер\b\.?', 'пер'), (r'площад\w*|пл\b\.?', 'пл'), (r'бульвар\w*|бульв\b\.?|б-р\b', 'бул'),
    (r'шоссе|ш\b\.?', 'ш'), (r'проезд\w*', 'проезд'), (r'остров\w*', 'остров'), (r'линия|линии', 'линия')]
DROP = r'\b(канала|канал|кан|реки|река|р|г|санкт-петербург|дом|д|литера|лит|корпус|корп|к|строение|стр|сооружение)\b\.?'


def street_key(s):
    """«Грибоедова кан. наб.» и «набережная канала Грибоедова» → ('наб', 'грибоедова')."""
    s = s.lower().replace('ё', 'е')
    t = None
    for rx, canon in TYPES:
        if re.search(r'(?<![\w-])(' + rx + r')(?![\w-])', s):
            t = canon; s = re.sub(r'(?<![\w-])(' + rx + r')(?![\w-])', ' ', s); break
    s = re.sub(DROP, ' ', s)
    words = sorted(w for w in re.findall(r'[а-я0-9][а-я0-9\-]*', s) if not w.isdigit())
    return (t, ' '.join(words)) if words else None


def parse(addr):
    """Список (тип, улица, номер) из адреса НПА или КЗР (несколько улиц через «;» или «(…)»)."""
    if not isinstance(addr, str): return []
    a = re.sub(r'^\s*\d{6},?', '', addr)
    a = re.sub(r'г\.\s*Санкт-Петербург,?|Санкт-Петербург,?|муниципальный округ\s+[\w\-]+,?|Адмиралтейский район,?', '', a)
    out = []
    for part in re.split(r';|\(|\)', a):
        m = re.match(r'\s*([^,]+?),\s*(?:дом|д\.)?\s*(\d+)', part)
        if not m: continue
        k = street_key(m.group(1))
        if k: out.append((k[0], k[1], int(m.group(2))))
    return out


# линейные объекты на границе Центрального и Адмиралтейского районов: в ИСС числятся за Центральным,
# но проходят и по Коломне (граница районов идёт по Мойке, каналу Грибоедова и Фонтанке)
SHARED = {'10171': 'Набережные и мосты реки Мойки', '10172': 'Набережные со спусками (Мойка)',
          '10153': 'Набережные и мосты реки Фонтанки', '10160': 'Набережные со спусками (Фонтанка)'}


LINEAR_NAME = r'\bмост|набережн|\bканал\b|спуск'


def in_version(names, points, poly_m, buf=30):
    """Здания — строго внутри полигона; мосты, набережные, каналы — с допуском 30 м:
    они лежат на воде, по которой проходят границы версий (Фонтанка, Мойка, Крюков канал, Пряжка),
    и по смыслу принадлежат Коломне (семимостье, Египетский, Старо-Калинкин мосты)."""
    pts = gpd.GeoSeries([p if p is not None else Point() for p in points], crs=4326).to_crs(32636)
    return [False if p.is_empty else (poly_m.buffer(buf).contains(p) if re.search(LINEAR_NAME, str(n).lower()) else poly_m.contains(p))
            for n, p in zip(names, pts)]


def edge_bridges(names, points, bnd, sen):
    """Мосты на внешнем краю версии 4 в Сенном округе (Каменный, Обуховский, Измайловский): там край версии —
    граница МО Сенной округ по Гороховой и Фонтанке, а не граница Коломны; в версию 4 их не включаем.
    Мосты на Неве (Благовещенский) и на исторических границах Коломны остаются."""
    b = bnd.to_crs(32636)
    v4, v3 = b.loc['версия 4', 'geometry'], b.loc['версия 3', 'geometry']
    pts = gpd.GeoSeries([p if p is not None else Point() for p in points], crs=4326).to_crs(32636)
    return [bool(re.search(r'\bмост', str(n).lower())) and not p.is_empty
            and v4.buffer(30).contains(p) and not v3.buffer(30).contains(p)
            and v4.boundary.distance(p) < 30 and sen.buffer(30).contains(p) for n, p in zip(names, pts)]

# объекты без номера дома: код ОКН → (lon, lat, где). Координаты сняты с карты вручную, ±50 м
MANUAL = {
    '22': (30.3080, 59.9365, 'Александровский сад'), '23': (30.3080, 59.9365, 'Александровский сад'),
    '25': (30.3080, 59.9365, 'Александровский сад'), '10400': (30.3080, 59.9365, 'Александровский сад'),
    '10183': (30.3060, 59.9375, 'Адмиралтейская наб.'), '10186': (30.3060, 59.9375, 'Адмиралтейская наб.'),
    '10191': (30.2935, 59.9345, 'Английская наб. (середина)'), '10192': (30.2935, 59.9345, 'Английская наб. (середина)'),
    '10598': (30.2935, 59.9345, 'Английская наб.'), '10599': (30.2935, 59.9345, 'Английская наб.'),
    '11036': (30.2965, 59.9330, 'пл. Труда'), '901': (30.2780, 59.9165, 'пл. Репина'),
    '360': (30.2795, 59.9155, 'Старо-Калинкин мост'), '11010': (30.3090, 59.9230, 'квартал пер. Бойцова – Фонтанка – Вознесенский – Садовая'),
    '300': (30.3305, 59.9200, 'Пионерская пл.'), '275': (30.3185, 59.9170, 'Обуховский мост'),
    '1065': (30.3305, 59.9205, 'Семёновская пл.'), '592': (30.3300, 59.9200, 'Загородный пр., 45–47'),
    '4': (30.3180, 59.9130, 'Московский пр. / 7-я Красноармейская'), '722': (30.2640, 59.9070, 'Лифляндская ул., 3'),
    '810': (30.2740, 59.9060, 'Нарвский пр., 9–11'), '819': (30.2720, 59.9030, 'Нарвский пр., 24'),
    '822': (30.2990, 59.9080, 'Балтийский вокзал'), '964': (30.2730, 59.9090, 'Старо-Петергофский пр., 40'),
    '2784': (30.2740, 59.9020, 'пл. Стачек'), '10870': (30.3430, 59.9190, 'ул. Марата, 86–90'),
    '10992': (30.3050, 59.9020, 'Малая Митрофаньевская ул.'), '11118': (30.2620, 59.9100, 'Рижский пр., 62'),
    '11159': (30.3100, 59.8980, 'Митрофаньевское шоссе'), '180': (30.2985, 59.9325, 'Конногвардейский бульвар'),
    '183': (30.2985, 59.9325, 'Конногвардейский бульвар'),
    '10171': (30.2860, 59.9268, 'левый берег Мойки в Коломне'), '10172': (30.2860, 59.9268, 'левый берег Мойки в Коломне'),
    '10153': (30.2950, 59.9170, 'правый берег Фонтанки в Коломне'), '10160': (30.2950, 59.9170, 'правый берег Фонтанки в Коломне'),
    '10166': (30.3191, 59.9304, 'Каменный мост, точка ЕГРОКН'), '800': (30.2970, 59.9090, 'наб. Обводного кан., 135'),
}


def norm_name(s):
    s = str(s).lower().replace('ё', 'е')
    s = re.split(r',\s*(?:\d{3,4}\s*[-–]|\d{3,4}\s*гг|арх\.|ск\.|гражд|инж\.|[xiv]+\s*в)', s)[0]  # отрезаем даты и авторов ЕГРОКН
    return re.sub(r'[^а-я0-9 ]', ' ', s).split()


def main(kgiop_csv, egrokn_csv, hoith_gpkg, bounds, out_dir):
    k = pd.read_csv(kgiop_csv, sep=';', dtype=str, encoding='cp1251')
    k = k[(k['Район'] == 'Адмиралтейский') | k['Код ОКН'].isin(SHARED)].copy()
    k = k.drop(columns=['Название', 'ИНН собственника'])     # сведения о собственниках в учебный файл не выносим
    eg = pd.read_csv(egrokn_csv, dtype={'reg': str})
    eg['reg'] = eg['reg'].str.strip()          # в выгрузке ЕГРОКН встречаются лишние пробелы и табуляции
    hz = gpd.read_file(hoith_gpkg).to_crs(4326)
    hz['pt'] = hz.geometry.representative_point()
    bnd = gpd.read_file(bounds).set_index('key')

    # --- газеттир: (тип, улица, номер) → точка
    gaz = {}
    for addr, p in zip(hz['r_adress'], hz['pt']):
        for t, s, n in parse(addr): gaz.setdefault((t, s, n), p)
    for addr, x, y in zip(eg['address'], eg['lon'], eg['lat']):
        if pd.isna(x): continue
        for t, s, n in parse(addr): gaz.setdefault((t, s, n), Point(x, y))
    by_street = {}
    for (t, s, n), p in gaz.items(): by_street.setdefault((t, s), []).append((n, p))

    eg_names = [(norm_name(n), Point(x, y), r) for n, x, y, r in zip(eg['name'], eg['lon'], eg['lat'], eg['reg']) if not pd.isna(x)]

    def locate(row):
        if row['Код ОКН'] in MANUAL:      # ручная точка важнее автоматической (линейные объекты, площади)
            x, y, where = MANUAL[row['Код ОКН']]
            return Point(x, y), 'вручную: ' + where
        keys = parse(row['Адрес КЗР']) + parse(row['Адрес НПА'])
        for t, s, n in keys:
            if (t, s, n) in gaz: return gaz[(t, s, n)], 'адрес: точно'
        best = None
        for t, s, n in keys:
            for m, p in by_street.get((t, s), []):
                if m % 2 == n % 2 and abs(m - n) <= 6 and (best is None or abs(m - n) < best[0]): best = (abs(m - n), p)
        if best: return best[1], 'адрес: соседний дом'
        nm = norm_name(row['Наименование объекта'])
        if len(nm) >= 2:
            hits = [p for w, p, r in eg_names if w[:len(nm)] == nm]
            if len(hits) == 1: return hits[0], 'по наименованию (ЕГРОКН)'
        return None, 'не привязан'

    res = k.apply(locate, axis=1, result_type='expand'); k['geom'], k['привязка'] = res[0], res[1]
    k['geom'] = [p if isinstance(p, Point) else None for p in k['geom']]
    # 4) по комплексу: родитель и «братья» по Код Компл.
    pts = dict(zip(k['Код ОКН'], k['geom']))
    sib = k[k['geom'].notna()].groupby('Код Компл.')['geom'].first().to_dict()
    for i, r in k[k['geom'].isna()].iterrows():
        p = sib.get(r['Код ОКН']) or (sib.get(r['Код Компл.']) if r['Код Компл.'] != '0' else None) or pts.get(r['Код Компл.'])
        if p is None and r['Код Компл.'] in MANUAL: p = Point(*MANUAL[r['Код Компл.']][:2])
        if p is not None: k.at[i, 'geom'], k.at[i, 'привязка'] = p, 'по комплексу'
    # 5) вручную
    for i, r in k[k['geom'].isna()].iterrows():
        if r['Код ОКН'] in MANUAL:
            x, y, where = MANUAL[r['Код ОКН']]
            k.at[i, 'geom'], k.at[i, 'привязка'] = Point(x, y), 'вручную: ' + where
    k['geom'] = [p if isinstance(p, Point) else None for p in k['geom']]
    k['lon'] = [p.x if p is not None else None for p in k['geom']]
    k['lat'] = [p.y if p is not None else None for p in k['geom']]
    bnd_m = bnd.to_crs(32636)
    for v in ['версия 1', 'версия 2', 'версия 3', 'версия 4']:
        k[v] = in_version(k['Наименование объекта'], k['geom'], bnd_m.loc[v, 'geometry'])
    sen = gpd.read_file(os.path.join(os.path.dirname(bounds), 'osm_polygons_simplified.geojson')).set_index('name').to_crs(32636).loc['Сенной округ', 'geometry']
    k.loc[edge_bridges(k['Наименование объекта'], k['geom'], bnd, sen), 'версия 4'] = False

    # --- сопоставление с ЕГРОКН: пары-кандидаты (общий адрес; ≤ 60 м; ≤ 300 м для именных объектов со сходством ≥ 0,6; ≤ 1 км при полном совпадении), вес — сходство наименований,
    #     затем жадно один к одному. Выявленные в ЕГРОКН не входят, но тоже проверяются (вдруг уже включены).
    ek = pd.read_csv(os.path.join(os.path.dirname(bounds), 'okn_kolomna_egrokn.csv'), dtype={'reg': str})
    ek['reg'] = ek['reg'].str.strip()
    pool = pd.concat([ek[['reg', 'name', 'type', 'cat', 'address', 'lon', 'lat']], eg[['reg', 'name', 'type', 'cat', 'address', 'lon', 'lat']]]).drop_duplicates('reg').reset_index(drop=True)
    pool_m = gpd.GeoSeries([Point(x, y) if not pd.isna(x) else Point() for x, y in zip(pool['lon'], pool['lat'])], crs=4326).to_crs(32636)
    eg_keys = {}
    for j, addr in enumerate(pool['address']):
        for key in parse(addr): eg_keys.setdefault(key, set()).add(j)
    kk = k.reset_index(drop=True)
    k_m = gpd.GeoSeries([p if p is not None else Point() for p in kk['geom']], crs=4326).to_crs(32636)
    sidx = pool_m.sindex
    GENERIC = {'дом', 'здание', 'жилой', 'доходный', 'с', 'и', 'в', 'на', 'где', 'жил', 'жила', 'жили', 'гг', 'г', 'корпус', 'особняк'}
    TYPEWORDS = {'ограда', 'ограды', 'сад', 'флигель', 'флигели', 'ворота', 'воротами', 'палисадник', 'сквер', 'фонтан', 'главный',
                 'главное', 'служебный', 'служб', 'службы', 'павильон', 'бульвар', 'каретник', 'двора', 'парадного', 'во', 'дворе', 'две', 'два',
                 'набережная', 'набережные', 'со', 'спусками', 'спуски', 'лестничные', 'съездами', 'решетками'}
    def generic(a):  # «Ограда с воротами», «Жилой дом», «Сад» — без собственного имени
        return not (set(norm_name(a)) - GENERIC - TYPEWORDS)
    def sim(a, b):
        na, nb = norm_name(a), norm_name(b)
        if na == nb: return 1.0                        # «Сад» = «Сад», «Ограда» = «Ограда» внутри ансамбля
        a, b = set(na) - GENERIC, set(nb) - GENERIC
        return len(a & b) / max(len(a | b), 1)
    pairs = []
    for i, r in kk.iterrows():
        cand = set()
        for key in parse(r['Адрес КЗР']) + parse(r['Адрес НПА']): cand |= eg_keys.get(key, set())
        if not k_m[i].is_empty:
            near = {j: pool_m[j].distance(k_m[i]) for j in sidx.query(k_m[i].buffer(1000))}
        else:
            near = {}
        for j in cand | set(near):
            sc = sim(r['Наименование объекта'], pool.at[j, 'name'])
            d = near.get(j)
            if j not in cand and d is not None and d > 60:
                if generic(r['Наименование объекта']) or sc < 0.6: continue   # дальше 60 м — только именные объекты
            if j not in cand and d is not None and d > 300 and sc < 1: continue  # 300–1000 м — только полное совпадение
            same_type = (r['Тип'] == 'Ансамбль') == (pool.at[j, 'type'] == 'Ансамбль')
            if sc >= 0.25:
                pairs.append((sc + 0.1 * same_type + 0.5 * (j in cand), i, j))   # общий адрес важнее расстояния
    used_i, used_j, match = set(), set(), {}
    for sc, i, j in sorted(pairs, reverse=True):
        if i in used_i or j in used_j: continue
        used_i.add(i); used_j.add(j); match[i] = (j, sc)
    # остаток — по полному совпадению именного наименования, единственного в Петербурге, если у записи ЕГРОКН нет адреса и точки
    # или у записи КГИОП нет номера дома (набережные, мосты, площади)
    blind = pool.index[pool['address'].fillna('').str.strip().eq('') & pool['lon'].isna()]
    by_name = {}
    for j in pool.index: by_name.setdefault(' '.join(norm_name(pool.at[j, 'name'])), []).append(j)
    for i in kk.index:
        if i in match: continue
        js = by_name.get(' '.join(norm_name(kk.at[i, 'Наименование объекта'])), [])
        no_addr = not (parse(kk.at[i, 'Адрес КЗР']) + parse(kk.at[i, 'Адрес НПА']))   # набережные, мосты, площади
        if len(js) == 1 and js[0] not in used_j and (js[0] in blind or no_addr) and not generic(kk.at[i, 'Наименование объекта']):
            used_i.add(i); used_j.add(js[0]); match[i] = (js[0], 1.0)

    # второй проход — элементы ансамблей: если «родитель» по Код Компл. сопоставлен с ансамблем ЕГРОКН,
    # ищем пару среди элементов того же ансамбля (у них общие цифры 6–12 рег. номера)
    fam = lambda reg: str(reg)[5:12]
    code2i = dict(zip(kk['Код ОКН'], kk.index))
    def root_reg(i, depth=0):
        if i in match: return pool.at[match[i][0], 'reg']
        p = kk.at[i, 'Код Компл.']
        return root_reg(code2i[p], depth + 1) if p != '0' and p in code2i and depth < 3 else None
    pairs2 = []
    for i in kk.index:
        if i in match: continue
        rr = root_reg(i)
        if rr is None: continue
        for j in pool.index[pool['reg'].map(fam) == fam(rr)]:
            if j in used_j: continue
            sc = sim(kk.at[i, 'Наименование объекта'], pool.at[j, 'name'])
            if sc >= 0.25: pairs2.append((sc, i, j))
    for sc, i, j in sorted(pairs2, reverse=True):
        if i in used_i or j in used_j: continue
        used_i.add(i); used_j.add(j); match[i] = (j, sc)
    # если в выгрузке ИСС номер ЕГРОКН цел (выгрузка от 09.10.2026), он важнее любого сопоставления по адресу
    how = {i: 'по адресу и наименованию' for i in match}
    true_reg = kk['№ ЕГРОКН'].fillna('').str.strip()
    true_reg = true_reg.where(true_reg.str.fullmatch(r'\d{15}'), '')
    reg2j = {r: j for j, r in zip(pool.index, pool['reg'])}
    claimed = {reg2j[r] for r in true_reg if r in reg2j}
    for i in kk.index:
        if true_reg[i] and true_reg[i] in reg2j:
            match[i], how[i] = (reg2j[true_reg[i]], 1.0), 'по номеру ЕГРОКН из ИСС'
        elif i in match and match[i][0] in claimed:          # эта запись ЕГРОКН по номеру принадлежит другому объекту
            del match[i]; how.pop(i, None)
    kk['сопоставление с ЕГРОКН'] = [how.get(i) for i in kk.index]
    kk['ЕГРОКН рег. №'] = [pool.at[match[i][0], 'reg'] if i in match else None for i in kk.index]
    kk['ЕГРОКН наименование'] = [pool.at[match[i][0], 'name'] if i in match else None for i in kk.index]
    kk['ЕГРОКН категория'] = [pool.at[match[i][0], 'cat'] if i in match else None for i in kk.index]
    kk['сходство наименований'] = [round(min(match[i][1], 1.0), 2) if i in match else None for i in kk.index]
    cat_map = {'Федеральные': 'Федерального значения', 'Региональные': 'Регионального значения', 'Выявленные': 'Выявленный'}
    kk['категория совпадает'] = [None if pd.isna(e) else cat_map[c] == e for c, e in zip(kk['Кат'], kk['ЕГРОКН категория'])]
    LINEAR = r'^\s*(Через|По обоим|Оба берега|от |От )|наб\. - |по обоим берегам'
    kk['примечание к привязке'] = ['линейный объект: точка условная' if re.search(LINEAR, str(x)) else None for x in kk['Адрес НПА']]
    kk.loc[kk['Код ОКН'].isin(SHARED), 'примечание к привязке'] = 'общий с Центральным районом линейный объект: точка условная'

    out = kk[kk['версия 4'] | (kk['привязка'] == 'не привязан')].drop(columns=['geom'])
    if out['№ ЕГРОКН'].fillna('').str.contains('E', case=False).any():     # в старой выгрузке номер испорчен Excel
        out = out.drop(columns=['№ ЕГРОКН'])
    V = ['версия 1', 'версия 2', 'версия 3', 'версия 4']
    first = ['Код ОКН', 'Код Компл.', 'Тип', 'Кат', 'Наименование объекта', 'Построен', 'Автор', 'Тип объекта', 'Адрес НПА', 'Адрес КЗР',
             'Основание', '№КАДАСТР', 'Вид(минкульт)', 'lon', 'lat', 'привязка', 'примечание к привязке'] + V + [
             'ЕГРОКН рег. №', 'сопоставление с ЕГРОКН', 'ЕГРОКН категория', 'ЕГРОКН наименование', 'сходство наименований', 'категория совпадает']
    # «Элемент» — внутренняя классификация КГИОП (здание в составе ансамбля без собственного номера ЕГРОКН), не ОКН
    out.insert(0, 'является ОКН', out['Тип'] != 'Элемент')
    out = out[['является ОКН'] + first + [c for c in out.columns if c not in first + ['является ОКН']]]
    os.makedirs(out_dir, exist_ok=True)
    out.to_csv(os.path.join(out_dir, 'okn_kolomna_kgiop.csv'), index=False, encoding='utf-8-sig')

    # --- сверка со стороны ЕГРОКН: каждый объект ЕГРОКН в версии 4 — есть ли пара в КГИОП
    m = kk.dropna(subset=['ЕГРОКН рег. №']).set_index('ЕГРОКН рег. №')[['Код ОКН', 'Кат', 'Наименование объекта', 'Адрес НПА']]
    m.columns = ['КГИОП код', 'КГИОП категория', 'КГИОП наименование', 'КГИОП адрес']
    ek = ek.merge(m, left_on='reg', right_index=True, how='left')
    ek.to_csv(os.path.join(out_dir, 'okn_kgiop_vs_egrokn.csv'), index=False, encoding='utf-8-sig')
    return out, ek


def report(out, ek, out_dir):
    """Сводка по версиям и xlsx для команды."""
    V = ['версия 1', 'версия 2', 'версия 3', 'версия 4']
    rows = []
    for v in V:
        s, e = out[out[v] & out['является ОКН']], ek[ek[v]]
        rows.append({'версия': v.replace('версия ', ''),
                     'ЕГРОКН: федеральные': int(e['cat'].str.startswith('Фед').sum()), 'ЕГРОКН: региональные': int(e['cat'].str.startswith('Рег').sum()),
                     'ЕГРОКН: всего': len(e), 'ЕГРОКН: есть пара в КГИОП': int(e['КГИОП код'].notna().sum()),
                     'КГИОП: федеральные': int((s['Кат'] == 'Федеральные').sum()), 'КГИОП: региональные': int((s['Кат'] == 'Региональные').sum()),
                     'КГИОП: выявленные': int((s['Кат'] == 'Выявленные').sum()), 'КГИОП: всего ОКН': len(s),
                     'КГИОП: фед.+рег. с парой в ЕГРОКН': int(((s['Кат'] != 'Выявленные') & s['ЕГРОКН рег. №'].notna()).sum()),
                     'категория расходится': int((s['категория совпадает'] == False).sum()),
                     'справочно: элементы ансамблей (не ОКН)': int((out[v] & ~out['является ОКН']).sum())})
    summ = pd.DataFrame(rows)
    np_k = out[out['версия 4'] & out['является ОКН'] & (out['Кат'] != 'Выявленные') & out['ЕГРОКН рег. №'].isna()]
    np_k = np_k.assign(причина='в ЕГРОКН не найден по адресу и наименованию', источник='КГИОП')
    np_e = ek[ek['версия 4'] & ek['КГИОП код'].isna()]
    np_e = np_e.assign(причина='в ИСС КГИОП числится за Центральным районом (в выгрузку по Адмиралтейскому не попал)', источник='ЕГРОКН')
    np_e = np_e.rename(columns={'reg': 'Код ОКН', 'type': 'Тип', 'cat': 'Кат', 'name': 'Наименование объекта', 'address': 'Адрес НПА'})
    cols = ['источник', 'Код ОКН', 'Тип', 'Кат', 'Наименование объекта', 'Адрес НПА', 'версия 2', 'причина']
    with pd.ExcelWriter(os.path.join(out_dir, 'okn_kolomna_kgiop.xlsx')) as w:
        summ.to_excel(w, sheet_name='Сводка', index=False)
        out.to_excel(w, sheet_name='КГИОП в версии 4', index=False)
        out[out['Кат'] == 'Выявленные'].to_excel(w, sheet_name='Выявленные', index=False)
        ek.to_excel(w, sheet_name='ЕГРОКН → КГИОП', index=False)
        pd.concat([np_k[cols], np_e[cols]]).to_excel(w, sheet_name='Без пары', index=False)
        pd.DataFrame({'шаг': [l.split(':')[0] for l in METHOD], 'описание': [l.split(':', 1)[1].strip() for l in METHOD]}).to_excel(
            w, sheet_name='Методика', index=False)
    return summ


METHOD = [
    'Источник: выгрузка ИСС КГИОП на весь город («2026-10-09_14-35-23.csv», 9 053 записи, cp1251; без «элементов», с целым № ЕГРОКН). Наименование и ИНН собственника в файл не перенесены.',
    'Отбор: район = Адмиралтейский (1 077 записей) — все четыре версии границ лежат в нём; плюс 4 линейных объекта, которые в ИСС числятся за Центральным районом, но идут по границе районов (набережные Мойки и Фонтанки) — словарь SHARED.',
    'Привязка 1: улица + номер дома из «Адрес КЗР» / «Адрес НПА» ↔ адреса зданий «Карты возраста домов» (HOITH) и ЕГРОКН.',
    'Привязка 2: ближайший номер той же чётности на той же улице, разница ≤ 6.',
    'Привязка 3: совпадение наименования с объектом ЕГРОКН (мосты, памятники, скверы без номера дома).',
    'Привязка 4: точка другого объекта того же комплекса («Код Компл.»).',
    'Привязка 5: вручную по карте (словарь MANUAL в скрипте), точность ±50 м.',
    'Версии: здание — точка строго внутри полигона; мосты, набережные, каналы — с допуском 30 м (граница версий идёт по воде); мосты на внешнем краю версии 4 в Сенном округе (Каменный, Обуховский, Измайловский — граница МО Сенной округ, а не Коломны) в неё не включены; у линейных объектов (набережные, каналы, мосты) точка условная — см. «примечание к привязке».',
    'Сверка: у федеральных и региональных ОКН — по № ЕГРОКН из ИСС; у записей без номера — пары по общему адресу; остаток — по полному совпадению именного наименования, единственного в Петербурге, если у одной из записей нет адреса с номером дома; ≤ 60 м; ≤ 300 м для именных объектов со сходством наименований ≥ 0,6; ≤ 1 км при полном совпадении; затем элементы внутри сопоставленного ансамбля (общие цифры 6–12 рег. номера); один к одному по убыванию сходства.',
    'Выявленные: в открытые данные ЕГРОКН не входят — для них ИСС КГИОП единственный источник.',
    'Элементы: тип «Элемент» — внутренняя классификация КГИОП (здание в составе ансамбля или объекта без собственного номера ЕГРОКН), не ОКН; в выгрузке от 09.10.2026 их нет. При запуске на старой выгрузке такие строки получают «является ОКН» = ложь и в подсчёты не входят.']


if __name__ == '__main__':
    out, ek = main(*sys.argv[1:6])
    for v in ['версия 1', 'версия 2', 'версия 3', 'версия 4']:
        out[v] = out[v].astype(bool); ek[v] = ek[v].astype(str).eq('True')
    print(report(out, ek, sys.argv[5]).set_index('версия').T)
    print(out['привязка'].value_counts())
    print(pd.crosstab(out['Кат'], [out[v] for v in ['версия 2']]))
