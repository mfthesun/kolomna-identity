from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output'
PNG = OUT / 'kolomna_pdf_slides'
PNG.mkdir(exist_ok=True)
PDF = OUT / 'Коломна_презентация_финальная.pdf'
W, H = 1920, 1080
PAPER, NAVY, INK, CORAL, BLUE, OCHRE, MUTED, WHITE, GRID = '#F4EFE6', '#102B3A', '#20343B', '#D86B4D', '#6FA6B6', '#D8A64E', '#6C7779', '#FFFDF8', '#D9D2C6'
ARIAL, ARIAL_B, GEORGIA, GEORGIA_B = 'C:/Windows/Fonts/arial.ttf', 'C:/Windows/Fonts/arialbd.ttf', 'C:/Windows/Fonts/georgia.ttf', 'C:/Windows/Fonts/georgiab.ttf'
AS = {
    'boundaries': ROOT/'kolomna_maps/carto_positron_wide/01_kolomna_boundaries_carto_positron.png',
    'okn': ROOT/'kolomna_maps/carto_positron_wide/02_kolomna_okn_carto_positron.png',
    'age': ROOT/'kolomna_maps/carto_positron_wide/04_kolomna_building_age_carto_positron.png',
    'projects': ROOT/'kolomna_maps/carto_positron_wide/05_kolomna_dominants_projects_carto_positron.png',
    'bridge': ROOT/'kolomna_photos/PRES_02_группа_мост_закат.jpg',
    'water': ROOT/'kolomna_photos/PRES_11_Крюков_канал_панорама.heic',
    'brick': ROOT/'kolomna_photos/PRES_01_группа_Фонтанка_кирпичный_корпус.jpg',
    'courtyard': ROOT/'kolomna_photos/PRES_08_двор_ветхая_застройка.heic',
    'church': ROOT/'kolomna_photos/PRES_16_церковь_кирпичный_фасад.jpg',
    'address': ROOT/'kolomna_photos/PRES_04_адрес_Крюков_канал_27.heic',
    'memory': ROOT/'kolomna_photos/PRES_17_мемориальные_таблички.jpg',
    'record': ROOT/'kolomna_photos/PRES_18_дверь_театр_завтра.jpg',
    'demolition': ROOT/'kolomna_photos/PRES_09_двор_снос_застройка.heic',
    'roof': ROOT/'kolomna_photos/PRES_14_крыши_и_порт_закат.jpg',
}

def F(n, bold=False, serif=False): return ImageFont.truetype(GEORGIA_B if serif and bold else GEORGIA if serif else ARIAL_B if bold else ARIAL, n)
def fit(key, size): return ImageOps.fit(Image.open(AS[key]).convert('RGB'), size, Image.Resampling.LANCZOS)
def contain(key, size, bg=PAPER):
    src = Image.open(AS[key]).convert('RGB'); src.thumbnail(size, Image.Resampling.LANCZOS)
    out = Image.new('RGB', size, bg); out.paste(src, ((size[0]-src.width)//2, (size[1]-src.height)//2)); return out
def put(im, key, box, mode='fit', bg=PAPER): im.paste(fit(key, (box[2]-box[0], box[3]-box[1])) if mode=='fit' else contain(key, (box[2]-box[0], box[3]-box[1]), bg), (box[0], box[1]))
def txt(d, xy, value, size, color=INK, bold=False, serif=False, maxw=None, spacing=5):
    font=F(size,bold,serif); value=str(value)
    if maxw:
        words=value.split(); lines=[]; line=''
        for word in words:
            test=(line+' '+word).strip()
            if d.textbbox((0,0),test,font=font)[2] <= maxw: line=test
            else: lines.append(line); line=word
        if line: lines.append(line)
        value='\n'.join(lines)
    d.multiline_text(xy,value,font=font,fill=color,spacing=spacing)
def footer(d, value, dark=False): txt(d,(72,1025),value,16,'#B8C9CD' if dark else MUTED)
def page(bg=PAPER): return Image.new('RGB',(W,H),bg)
def heading(im, section, title, subtitle, dark=False):
    d=ImageDraw.Draw(im); d.rectangle((0,0,18,H),fill=CORAL); fg=WHITE if dark else INK; sub='#B8C9CD' if dark else MUTED
    txt(d,(72,50),section,24,OCHRE if dark else CORAL,True); txt(d,(72,105),title,58,fg,True,True,maxw=1660); txt(d,(72,230),subtitle,27,sub,maxw=1080); return d

slides=[]
# 1
im=fit('bridge',(W,H)); im=Image.blend(im,Image.new('RGB',(W,H),NAVY),0.55); d=ImageDraw.Draw(im); d.rectangle((0,0,18,H),fill=CORAL); txt(d,(72,65),'ГОРОДСКАЯ ИДЕНТИЧНОСТЬ',25,'#EBC9B8',True); txt(d,(72,285),'Коломна',96,WHITE,True,True); txt(d,(72,410),'район между водой, памятью\nи повседневной жизнью',48,WHITE,False,True,maxw=920); txt(d,(72,710),'Исследование локальной идентичности',30,'#EBC9B8'); footer(d,'Коломна · Санкт-Петербург',True); slides.append(im)
# 2
im=page(); d=heading(im,'01 / ТЕРРИТОРИЯ','Четыре Коломны','Официальная граница почти совпадает с ядром; вернакулярная территория расширяется к театрам и Сенной'); put(im,'boundaries',(110,400,1810,980),'contain'); vals=[('1,81 км²','три острова',CORAL),('2,49 км²','МО Коломна',BLUE),('3,35 км²','театральная',OCHRE),('5,08 км²','литературная',INK)];
for i,(n,label,col) in enumerate(vals): x=80+i*450; txt(d,(x,280),n,32,col,True,True); txt(d,(x,320),label,22,INK,True); d.rectangle((x,360,x+300,367),fill=col)
footer(d,'Карты команды · версии границ 1–4'); slides.append(im)
# 3
im=page(); d=heading(im,'02 / ОБРАЗ РАЙОНА','Почему Коломну узнают','Вода, рядовая застройка, локальные адреса и дворы задают узнаваемость сильнее отдельных достопримечательностей');
for i,(key,label,sub,col) in enumerate([('water','ВОДА','каналы, набережные, мосты',BLUE),('brick','ЗАСТРОЙКА','доходные дома и промкорпуса',CORAL),('address','АДРЕС','локальные знаки и названия',OCHRE),('courtyard','ДВОР','замкнутость и тишина',INK)]):
    x=72+i*462; put(im,key,(x,350,x+410,720)); txt(d,(x,750),label,20,col,True); txt(d,(x,785),sub,21,INK,True,maxw=390)
footer(d,'Личная фотофиксация команды'); slides.append(im)
# 4
im=page(NAVY); d=heading(im,'03 / ЧЕТЫРЕ КОМПОНЕНТА','Как устроена идентичность','Каждый слой задаёт отдельный вопрос для анализа и будущего поля',True); blocks=[('КОГНИТИВНЫЙ','Что узнают и где проводят границу',CORAL),('АФФЕКТИВНЫЙ','Что чувствуют: тишина, уют, край',BLUE),('ЦЕННОСТНЫЙ','Что считают важным: миф, память, среда',OCHRE),('ПРАКТИЧЕСКИЙ','Как пользуются: двор, маршрут, сцена',WHITE)]
for i,(a,b,col) in enumerate(blocks): x=80+(i%2)*900; y=355+(i//2)*280; txt(d,(x,y),a,22,col,True); txt(d,(x,y+45),b,32,WHITE,True,True,maxw=760); d.rectangle((x,y+130,x+760,y+136),fill=col)
footer(d,'Структура исследования Коломны',True); slides.append(im)
# 5
im=page(NAVY); d=heading(im,'04 / ПОВСЕДНЕВНОСТЬ','Тишина видна в цифрах','Сервис плотнее в расширенных версиях, а тихое ядро остаётся главным аффективным ресурсом',True); put(im,'water',(1210,0,1920,1080)); rows=[('55','кафе, баров и ресторанов / км²','ядро',CORAL),('99','кафе, баров и ресторанов / км²','театральное кольцо',BLUE),('171','кафе, баров и ресторанов / км²','литературное кольцо',OCHRE),('205 / 582','торговля и услуги / км²','от ядра к кольцу',WHITE)]
for i,(n,a,b,col) in enumerate(rows): y=335+i*155; txt(d,(80,y),n,46,col,True,True); txt(d,(390,y+8),a,23,WHITE,True,maxw=700); txt(d,(390,y+48),b,19,'#B8C9CD')
footer(d,'OSM · плотность по центрам объектов и площадям версий границ',True); slides.append(im)
# 6
im=page(); d=heading(im,'05 / НАСЛЕДИЕ','ОКН собираются в пространстве','ЕГРОКН: 93 объекта внутри МО и 311 в расширенной версии; реестр не заменяет историческую ткань района'); put(im,'okn',(110,330,1810,990),'contain'); footer(d,'ЕГРОКН · ИСС КГИОП'); slides.append(im)
# 7
im=page(); d=heading(im,'06 / ЗАСТРОЙКА','Район держится на рядовом доме','Медианный год постройки в МО — 1896; 79% датированных зданий построены до 1918 года'); put(im,'age',(110,330,1810,990),'contain'); footer(d,'«Карта возраста домов» · HOITH'); slides.append(im)
# 8
im=page(); d=heading(im,'07 / СМЫСЛЫ','Три мифа Коломны','Район расширяется в языке литературы, искусства и городского края'); put(im,'roof',(1320,0,1920,1080)); myths=[('ОТСТАВКА','«Тут не столица и не провинция»','Гоголь · скромность и неспешность',CORAL),('ИСКУССТВО','Мариинка, Глинка, Мусоргский','творческая преемственность',BLUE),('КРАЙ','Пряжка, Блок, тревожная тишина','образ границы города',OCHRE)]
for i,(a,b,c,col) in enumerate(myths): y=350+i*190; txt(d,(80,y),a,20,col,True); txt(d,(80,y+35),b,31,INK,True,True,maxw=1110); txt(d,(80,y+88),c,21,MUTED); d.rectangle((80,y+135,1160,y+141),fill=col)
footer(d,'Гоголь · Пушкин · Блок · городская мифология'); slides.append(im)
# 9
im=page(); d=heading(im,'08 / ПОЛЬЗОВАТЕЛИ','У района несколько географий','Жители осваивают глубину Коломны; остальные чаще остаются у воды и на восточном краю'); put(im,'memory',(1350,0,1920,1080)); rows=[('ЖИТЕЛИ','магазины, дворы, прогулки вдоль воды',BLUE),('РАБОТНИКИ','верфи, больница, фабрика',CORAL),('ЗРИТЕЛИ','Мариинка и театральный вечер',OCHRE),('ТУРИСТЫ','литературные и религиозные маршруты',INK)]
for i,(a,b,col) in enumerate(rows): y=350+i*145; txt(d,(80,y),a,22,col,True); txt(d,(370,y),b,28,INK,True,True,maxw=820); d.rectangle((80,y+70,1180,y+76),fill=col)
footer(d,'Практический компонент · полевая проверка ещё нужна'); slides.append(im)
# 10
im=page(); d=heading(im,'09 / ПЕРЕМЕНЫ','Восточный край станет доступнее','Метро и новые проекты могут снять труднодоступность, на которой держится тишина'); put(im,'projects',(110,330,1810,990),'contain'); for_text=[('СЕЙЧАС','тихое ядро и закрытые территории',INK),('2029–2030','вестибюль «Театральной»',CORAL),('РИСК','пешеходный поток вытесняет приватность',BLUE)]
for i,(a,b,col) in enumerate(for_text): x=100+i*600; txt(d,(x,1000),a,18,col,True); txt(d,(x,1025),b,17,INK,True,maxw=530)
slides.append(im)
# 11
im=page(NAVY); d=heading(im,'10 / ОДИН КЕЙС','Дом Иофа / «Рекорд»','Один пример смены публичной функции на фоне общей истории района',True); put(im,'record',(1260,0,1920,520)); put(im,'demolition',(1260,560,1920,1080)); timeline=[('1916','театр миниатюр',CORAL),('1920-е–1946','кинотеатр «Рекорд»',BLUE),('2006','Дом молодёжи',OCHRE),('2023–2025','проект четвёртой сцены',WHITE)]
for i,(a,b,col) in enumerate(timeline): y=330+i*150; txt(d,(80,y),a,27,col,True,True); txt(d,(360,y),b,31,WHITE,True,True); d.rectangle((80,y+72,1110,y+78),fill=col)
footer(d,'Кейс помогает увидеть смену функции, но не заменяет исследование всего района',True); slides.append(im)
# 12
im=page(NAVY); d=heading(im,'11 / ВЫВОД','Коломна держится на трёх связках','граница и вода · тихая повседневность · публичная память',True);
for i,(a,b,col) in enumerate([('ТЕРРИТОРИЯ','Официальная Коломна почти совпадает с ядром; вернакулярная расширяется к символам.',CORAL),('СРЕДА','Ценность живёт в рядовой застройке, дворах и низком ритме района.',BLUE),('БУДУЩЕЕ','Новые проекты должны усилить доступность, не разрушив приватность и память.',OCHRE)]): y=350+i*190; txt(d,(80,y),a,22,col,True); txt(d,(80,y+42),b,30,WHITE,True,True,maxw=1450); d.rectangle((80,y+125,1650,y+131),fill=col)
footer(d,'Следующий шаг: ментальные карты · интервью · go-along · подсчёт пешеходов',True); slides.append(im)

for i,im in enumerate(slides,1): im.save(PNG/f'slide_{i:02d}.png')
slides[0].save(PDF,save_all=True,append_images=slides[1:],resolution=144)
print(PDF)
