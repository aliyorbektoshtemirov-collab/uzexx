"""Demo (sun'iy) UZEX bitimlar datasetini SQLite'ga aylantirish va qidirish.

Barcha ma'lumotlar o'ylab topilgan (dataset README'si). Maxfiy ustunlar
(STIR, broker kodlari) bazaga umuman kiritilmaydi.
"""
import csv, gzip, os, re, shutil, sqlite3, zipfile
from datetime import datetime

SCHEMA_VERSION = 2
DB_NAME = "uzex_demo.sqlite"
GZ_NAME = DB_NAME + ".gz"
CANCELLED = "Аннулирован(Не оплачен)"
DISCLAIMER = {
    "uz": "⚠️ Bu sun’iy sinov ma’lumotlari (demo dataset). Real vaqt bozor narxi emas.",
    "ru": "⚠️ Это искусственные тестовые данные (демо-датасет), а не рыночные цены в реальном времени.",
}
UNIT_UZ = {"тонна": "tonna", "килограмм": "kg", "куб.метр": "m³", "литр": "litr",
           "метр": "metr", "кв.метр": "m²", "штука": "dona"}
STATE_UZ = {"Исполнен": "Bajarilgan", "Исполнен(Частично)": "Qisman bajarilgan", "Оплачен": "To‘langan",
            "Ждёт оплату": "To‘lov kutilmoqda", "Заключен": "Tuzilgan", "Не подписан": "Imzolanmagan",
            "Новый": "Yangi", CANCELLED: "Bekor qilingan (to‘lanmagan)"}
# uz/ru so'z -> mahsulot nomi bo'lagi (kichik harflarda, rus)
PRODUCT_ALIASES = {
    "shakar": "сахар", "сахар": "сахар", "paxta": "хлопок", "хлопок": "хлопок",
    "un": "мука", "мука": "мука", "bug‘doy": "пшениц", "bugdoy": "пшениц", "пшениц": "пшениц",
    "guruch": "рис", "рис": "рис", "benzin": "бензин", "бензин": "бензин", "sement": "цемент",
    "цемент": "цемент", "портландцемент": "цемент", "karbamid": "карбамид", "карбамид": "карбамид",
    "armatura": "арматур", "арматур": "арматур", "yog‘": "масло", "yog": "масло", "масл": "масло",
    "dizel": "дизел", "дизел": "дизел", "mazut": "мазут", "мазут": "мазут", "gaz": "газ", "газ": "газ",
    "bitum": "битум", "битум": "битум", "kabel": "кабел", "кабел": "кабел", "yog‘och": "пиломатериал",
    "пиломатериал": "пиломатериал", "g‘isht": "кирпич", "кирпич": "кирпич", "suv": "вод",
    "вода": "вод", "ip": "пряжа", "пряж": "пряжа", "polietilen": "полиэтилен", "полиэтилен": "полиэтилен",
    "polipropilen": "полипропилен", "полипропилен": "полипропилен", "селитра": "селитра", "selitra": "селитра",
    "kunjara": "шрот", "шрот": "шрот", "yem": "комбикорм", "комбикорм": "комбикорм",
}
REGION_ALIASES = {
    "andijon": "Andijon viloyati", "андижан": "Andijon viloyati", "buxoro": "Buxoro viloyati",
    "бухар": "Buxoro viloyati", "farg‘ona": "Farg‘ona viloyati", "fargona": "Farg‘ona viloyati",
    "фергана": "Farg‘ona viloyati", "jizzax": "Jizzax viloyati", "джизак": "Jizzax viloyati",
    "namangan": "Namangan viloyati", "наманган": "Namangan viloyati", "navoiy": "Navoiy viloyati",
    "навои": "Navoiy viloyati", "qashqadaryo": "Qashqadaryo viloyati", "кашкадар": "Qashqadaryo viloyati",
    "qoraqalpog": "Qoraqalpog‘iston Respublikasi", "каракалпак": "Qoraqalpog‘iston Respublikasi",
    "samarqand": "Samarqand viloyati", "самарканд": "Samarqand viloyati", "sirdaryo": "Sirdaryo viloyati",
    "сырдар": "Sirdaryo viloyati", "surxondaryo": "Surxondaryo viloyati", "сурхандар": "Surxondaryo viloyati",
    "toshkent shahri": "Toshkent shahri", "ташкент город": "Toshkent shahri", "г. ташкент": "Toshkent shahri",
    "toshkent viloyati": "Toshkent viloyati", "ташкентская": "Toshkent viloyati",
    "xorazm": "Xorazm viloyati", "хорезм": "Xorazm viloyati",
}


def _num(s):
    s = (s or "").replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _date(s):
    return datetime.strptime(s.strip(), "%d.%m.%Y").strftime("%Y-%m-%d")


def build_db(src_dir, db_path):
    """CSV -> SQLite. STIR/broker/ishtirokchi ma'lumotlari kiritilmaydi."""
    if os.path.exists(db_path):
        os.remove(db_path)
    con = sqlite3.connect(db_path)
    con.executescript("""
    CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE deals(deal_no INTEGER PRIMARY KEY, deal_date TEXT, year INTEGER, product TEXT,
      product_lc TEXT, region TEXT, trade_type TEXT, contract_type TEXT, contract_form TEXT,
      state TEXT, qty REAL, lot REAL, unit TEXT, amount REAL, currency TEXT, rate REAL,
      amount_uzs REAL, delivered REAL, cancelled INTEGER);
    CREATE INDEX i_year ON deals(year); CREATE INDEX i_prod ON deals(product_lc);
    CREATE INDEX i_reg ON deals(region); CREATE INDEX i_date ON deals(deal_date);""")
    rd = lambda n: csv.DictReader(open(os.path.join(src_dir, n), encoding="utf-8-sig", newline=""))
    rates = {_date(r["Дата"]): _num(r["Курс"]) for r in rd("usd_rates.csv")}
    cur = {r["Номер контракта"]: r["Валюта"] for r in rd("contracts.csv")}
    rows = []
    for y in range(2022, 2027):
        p = os.path.join(src_dir, f"deals_{y}.csv")
        if not os.path.exists(p):
            continue
        for r in rd(f"deals_{y}.csv"):
            d = _date(r["Дата сделки"]); amt = _num(r["Сумма сделки"])
            c = "USD" if cur.get(r["Номер контракта"]) == "Доллар США" else "UZS"
            rate = rates.get(d, 0.0) if c == "USD" else 1.0
            lot = _num(r["Лот"]) or 1.0
            name = r["Наименование товара"].strip()
            rows.append((int(r["Номер сделки"]), d, int(d[:4]), name, name.lower(), r["Регион"],
                         r["Тип торгов"], r["Тип контракта"], r["Форма контракта"], r["Состояние сделки"],
                         _num(r["Количество"]), lot, r["Единица измерения"], amt, c, rate, amt * rate,
                         _num(r["Поставлено"]), 1 if r["Состояние сделки"] == CANCELLED else 0))
    con.executemany("INSERT INTO deals VALUES(%s)" % ",".join("?" * 19), rows)
    con.execute("INSERT INTO meta VALUES('schema_version',?)", (str(SCHEMA_VERSION),))
    con.commit(); con.execute("VACUUM"); con.close()


def pack_db(db_path, gz_path):
    with open(db_path, "rb") as f, gzip.open(gz_path, "wb", compresslevel=9) as g:
        shutil.copyfileobj(f, g)


def split_gz(gz_path, size=8 * 1024 * 1024):
    """Siqilgan bazani GitHub veb-yuklash limiti (25 MB) uchun bo'laklarga bo'ladi; butun fayl o'chiriladi."""
    with open(gz_path, "rb") as f:
        i = 1
        while True:
            chunk = f.read(size)
            if not chunk:
                break
            with open(f"{gz_path}.part{i:02d}", "wb") as o:
                o.write(chunk)
            i += 1
    os.remove(gz_path)


def _join_parts(gz_path):
    import glob
    parts = sorted(glob.glob(gz_path + ".part*"))
    if not parts:
        return None
    tmp = gz_path + ".joined.tmp"
    with open(tmp, "wb") as o:
        for p in parts:
            with open(p, "rb") as f:
                shutil.copyfileobj(f, o)
    return tmp


def _schema_ok(db_path):
    con = None
    try:
        con = sqlite3.connect(db_path)
        v = con.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        return bool(v) and int(v[0]) == SCHEMA_VERSION
    except sqlite3.Error:
        return False
    finally:
        if con is not None:
            con.close()  # Windows'da ochiq fayl almashtirilmaydi


def ensure_db(data_dir):
    """Birinchi ishga tushishda siqilgan bazani ochadi; eski/buzuq schema bo'lsa xavfsiz yangilaydi."""
    db, gz = os.path.join(data_dir, DB_NAME), os.path.join(data_dir, GZ_NAME)
    if os.path.exists(db) and _schema_ok(db):
        return db
    joined = None
    if not os.path.exists(gz):
        joined = _join_parts(gz)  # bo'laklardan (.part01, .part02 ...) birlashtirish
        if joined is None:
            raise FileNotFoundError(f"{gz} yoki uning bo‘laklari topilmadi")
        gz = joined
    tmp = db + ".tmp"
    try:
        with gzip.open(gz, "rb") as g, open(tmp, "wb") as f:
            shutil.copyfileobj(g, f)
    finally:
        if joined and os.path.exists(joined):
            os.remove(joined)
    if not _schema_ok(tmp):
        os.remove(tmp)
        raise RuntimeError("Siqilgan baza schema versiyasi mos emas")
    os.replace(tmp, db)  # atomik almashtirish
    return db


# ---------------------------------------------------------------- so'rovlar
class Market:
    def __init__(self, db_path):
        self.con = sqlite3.connect(db_path, check_same_thread=False)
        self.con.row_factory = sqlite3.Row

    def _where(self, f, with_cancelled=False):
        w, p = [], []
        if f.get("year"): w.append("year=?"); p.append(f["year"])
        if f.get("product"): w.append("product_lc LIKE ?"); p.append("%" + f["product"].replace("%", "") + "%")
        if f.get("region"): w.append("region=?"); p.append(f["region"])
        if f.get("trade_type"): w.append("trade_type=?"); p.append(f["trade_type"])
        if f.get("contract_type"): w.append("contract_type=?"); p.append(f["contract_type"])
        if f.get("contract_form"): w.append("contract_form=?"); p.append(f["contract_form"])
        if f.get("state"): w.append("state=?"); p.append(f["state"])
        if f.get("date_from"): w.append("deal_date>=?"); p.append(f["date_from"])
        if f.get("date_to"): w.append("deal_date<=?"); p.append(f["date_to"])
        if not with_cancelled: w.append("cancelled=0")
        return (" WHERE " + " AND ".join(w)) if w else "", p

    def get_deal(self, no):
        r = self.con.execute("SELECT * FROM deals WHERE deal_no=?", (int(no),)).fetchone()
        return dict(r) if r else None

    def count(self, f):
        w, p = self._where(f)
        n = self.con.execute("SELECT COUNT(*) FROM deals" + w, p).fetchone()[0]
        w2, p2 = self._where(f, True)
        c = self.con.execute("SELECT COUNT(*) FROM deals" + w2 + (" AND " if w2 else " WHERE ") + "cancelled=1", p2).fetchone()[0]
        return {"active": n, "cancelled": c, "total": n + c}

    def turnover(self, f):
        """Umumiy aylanma (so'm): bekor qilinganlar kirmaydi, eksport sana kursi bilan."""
        w, p = self._where(f)
        return self.con.execute("SELECT COALESCE(SUM(amount_uzs),0) FROM deals" + w, p).fetchone()[0]

    def cancelled_stats(self, f):
        w, p = self._where(f, True)
        w += (" AND " if w else " WHERE ") + "cancelled=1"
        r = self.con.execute("SELECT COUNT(*), COALESCE(SUM(amount_uzs),0) FROM deals" + w, p).fetchone()
        return {"count": r[0], "amount_uzs": r[1]}

    def by_unit(self, f):
        """Hajm va o'rtacha narx faqat bir xil o'lchov birligi ichida (aralashtirilmaydi)."""
        w, p = self._where(f)
        q = ("SELECT unit, COUNT(*) n, SUM(qty*lot) vol, SUM(delivered*lot) dvol, SUM(amount_uzs) s "
             "FROM deals" + w + " GROUP BY unit ORDER BY n DESC")
        out = []
        for r in self.con.execute(q, p):
            d = dict(r); d["avg_price_uzs"] = d["s"] / d["vol"] if d["vol"] else None
            out.append(d)
        return out

    def group(self, f, col, limit=5):
        assert col in ("region", "product", "trade_type", "contract_form", "state", "year")
        w, p = self._where(f)
        col_sql = "region" if col == "region" else col
        q = (f"SELECT {col_sql} k, COUNT(*) n, SUM(amount_uzs) s FROM deals{w} GROUP BY {col_sql} "
             "ORDER BY n DESC LIMIT ?")
        return [dict(r) for r in self.con.execute(q, p + [limit])]

    def top_products(self, f, limit=5):
        w, p = self._where(f)
        q = ("SELECT substr(product,1,60) k, COUNT(*) n, SUM(amount_uzs) s FROM deals" + w +
             " GROUP BY k ORDER BY n DESC LIMIT ?")
        return [dict(r) for r in self.con.execute(q, p + [limit])]


# ------------------------------------------------- savolni tahlil + javob
def parse_filters(text):
    t = text.lower().replace("’", "‘").replace("'", "‘")
    f = {}
    m = re.search(r"\b(20[2][2-6])\b", t)
    if m: f["year"] = int(m.group(1))
    for k, v in PRODUCT_ALIASES.items():
        # qisqa kalitlar (un, ip, suv, gaz) faqat butun so'z (+qo'shimcha) sifatida; "universitet" -> un emas
        pat = (r"(?<!\w)" + re.escape(k) + r"(?:lar|ni|ning|da|ga|dan)?(?!\w)") if len(k) <= 3 else (r"(?<!\w)" + re.escape(k))
        if re.search(pat, t): f["product"] = v; break
    for k, v in sorted(REGION_ALIASES.items(), key=lambda kv: -len(kv[0])):
        if k in t: f["region"] = v; break
    if re.search(r"eksport|экспорт", t): f["contract_type"] = "Экспортный"
    elif re.search(r"ichki|внутрен", t): f["contract_type"] = "Внутренний"
    if re.search(r"forvard|форвард", t): f["contract_form"] = "Форвард"
    elif re.search(r"fyuchers|фьючерс", t): f["contract_form"] = "Фьючерс"
    elif re.search(r"\bspot\b|спот", t): f["contract_form"] = "Спот"
    if re.search(r"ingliz|английск", t): f["trade_type"] = "Английский аукцион"
    elif re.search(r"teskari|обратн", t): f["trade_type"] = "Обратный аукцион"
    elif re.search(r"ikki tomonlama|двусторон", t): f["trade_type"] = "Двусторонний аукцион"
    return f


def extract_deal_no(text):
    m = re.search(r"(?:bitim|сделк\w*|deal)?\s*(?:№|#|raqam\w*|номер)\s*(\d{4,9})", text, re.I) \
        or re.search(r"(?:bitim|сделк\w*)\s+(\d{5,9})\b", text, re.I)
    return int(m.group(1)) if m else None


def is_market_question(text):
    """Dataset savoli: bitim/demo haqida va statistika niyati (nechta, aylanma, eng ko'p, bekor ...) bo'lsa."""
    t = text.lower()
    about = re.search(r"bitim|сделк|demo|демо|statistik|статистик|aylanma|оборот", t)
    intent = re.search(r"nechta|сколько|statistik|статистик|aylanma|оборот|demo|демо|eng ko.p|"
                       r"больше всего|наибольш|bekor|аннулир|jami|всего|hajm|объ[её]м", t)
    # "2025 yildagi bitim", "shakar bitimlari", "сделки по сахару" kabi filtr (yil/mahsulot/hudud/tur) bor savollar ham statistika
    return bool(about and (intent or parse_filters(text)))


def money(x, lang):
    unit = "so‘m" if lang == "uz" else "сум"
    if abs(x) >= 1e9: return f"{x/1e9:,.2f} mlrd {unit}".replace(",", " ") if lang == "uz" else f"{x/1e9:,.2f} млрд {unit}".replace(",", " ")
    if abs(x) >= 1e6: return f"{x/1e6:,.2f} mln {unit}".replace(",", " ") if lang == "uz" else f"{x/1e6:,.2f} млн {unit}".replace(",", " ")
    return f"{x:,.0f} {unit}".replace(",", " ")


def _n(x): return f"{x:,.0f}".replace(",", " ")


def _u(unit, lang): return UNIT_UZ.get(unit, unit) if lang == "uz" else unit


def format_deal(d, lang):
    """Maxfiy ma'lumot (STIR, broker) bazada yo'q — shuning uchun oshkor bo'lmaydi."""
    st = STATE_UZ.get(d["state"], d["state"]) if lang == "uz" else d["state"]
    cur = "USD" if d["currency"] == "USD" else ("so‘m" if lang == "uz" else "сум")
    L = {"uz": ["Bitim", "Sana", "Mahsulot", "Hudud", "Savdo turi", "Shartnoma", "Holat", "Miqdor", "Summa", "Yetkazilgan"],
         "ru": ["Сделка", "Дата", "Товар", "Регион", "Тип торгов", "Контракт", "Состояние", "Количество", "Сумма", "Поставлено"]}[lang]
    form = f"{d['contract_type']} / {d['contract_form']}"
    lines = [f"{L[0]} №{d['deal_no']}", f"{L[1]}: {d['deal_date']}", f"{L[2]}: {d['product']}",
             f"{L[3]}: {d['region']}", f"{L[4]}: {d['trade_type']}", f"{L[5]}: {form}", f"{L[6]}: {st}",
             f"{L[7]}: {d['qty']:g} × {d['lot']:g} {_u(d['unit'], lang)}",
             f"{L[8]}: {d['amount']:,.0f} {cur}".replace(",", " ")]
    if d["currency"] == "USD":
        lines.append(f"  ≈ {money(d['amount_uzs'], lang)} (kurs {d['rate']:g})" if lang == "uz"
                     else f"  ≈ {money(d['amount_uzs'], lang)} (курс {d['rate']:g})")
    lines.append(f"{L[9]}: {d['delivered']:g} / {d['qty']:g}")
    return "\n".join(lines) + "\n\n" + DISCLAIMER[lang]


def answer(market, text, lang):
    """Dataset bo'yicha javob matni (AI'siz, deterministik). None — bu dataset savoli emas."""
    no = extract_deal_no(text)
    if no is not None:
        d = market.get_deal(no)
        if d: return format_deal(d, lang)
        return (f"Bitim №{no} demo datasetda topilmadi.\n\n" if lang == "uz"
                else f"Сделка №{no} в демо-датасете не найдена.\n\n") + DISCLAIMER[lang]
    if not is_market_question(text):
        return None
    f = parse_filters(text); t = text.lower()
    uz = lang == "uz"
    only_cancel = bool(re.search(r"bekor|аннулир", t))
    scope = ", ".join(f"{k}={v}" for k, v in f.items()) or ("barcha davr" if uz else "весь период")
    out = [("📊 Demo bitimlar statistikasi" if uz else "📊 Статистика демо-сделок") + f" ({scope})"]
    if only_cancel:
        c = market.cancelled_stats(f)
        out.append((f"Bekor qilingan bitimlar: {c['count']} ta, summa {money(c['amount_uzs'], lang)} "
                    "(umumiy aylanmaga kiritilmaydi)") if uz else
                   (f"Аннулированные сделки: {c['count']}, сумма {money(c['amount_uzs'], lang)} "
                    "(в общий оборот не входят)"))
        return "\n".join(out) + "\n\n" + DISCLAIMER[lang]
    cnt = market.count(f)
    out.append((f"Bitimlar soni: {cnt['total']} ta (shundan bekor qilingan {cnt['cancelled']} ta; amalga oshgan/faol {cnt['active']} ta)") if uz else
               (f"Количество сделок: {cnt['total']} (из них аннулировано {cnt['cancelled']}; состоявшихся/активных {cnt['active']})"))
    if cnt["active"] == 0:
        return "\n".join(out) + "\n\n" + DISCLAIMER[lang]
    if re.search(r"eng ko‘p|eng ko'p|больше всего|наиболее|какой|qaysi", t) and re.search(r"viloyat|hudud|регион|област", t):
        out.append("🏆 " + ("Hududlar bo‘yicha:" if uz else "По регионам:"))
        for i, r in enumerate(market.group(f, "region", 3), 1):
            out.append(f"{i}. {r['k']} — {r['n']}")
    else:
        out.append((f"Umumiy aylanma: {money(market.turnover(f), lang)}") if uz else
                   (f"Общий оборот: {money(market.turnover(f), lang)}"))
        out.append(("Hajm (o‘lchov birligi bo‘yicha alohida, aralashtirilmaydi):" if uz else
                    "Объём (по единицам измерения отдельно, без смешивания):"))
        units = market.by_unit(f)
        for r in units[:6]:
            line = (f"• {_u(r['unit'], lang)}: {r['n']} ta bitim, hajm {_n(r['vol'])}, yetkazilgan {_n(r['dvol'])}" if uz else
                    f"• {_u(r['unit'], lang)}: {r['n']} сделок, объём {_n(r['vol'])}, поставлено {_n(r['dvol'])}")
            if f.get("product") and r["avg_price_uzs"]:
                line += (f", o‘rtacha narx {_n(r['avg_price_uzs'])} so‘m/{_u(r['unit'], lang)}" if uz else
                         f", средняя цена {_n(r['avg_price_uzs'])} сум/{_u(r['unit'], lang)}")
            out.append(line)
        if len(units) > 1:
            out.append("ℹ️ " + ("Turli birliklar qo‘shilmadi." if uz else "Разные единицы не суммировались."))
        if not f.get("region"):
            out.append("🏆 " + ("Top hududlar:" if uz else "Топ регионов:"))
            for i, r in enumerate(market.group(f, "region", 3), 1):
                out.append(f"{i}. {r['k']} — {r['n']}")
    return "\n".join(out) + "\n\n" + DISCLAIMER[lang]
