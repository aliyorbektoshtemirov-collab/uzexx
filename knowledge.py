"""Ikki tilli bilimlar bazasi: kalit so'zli qidiruv, til aniqlash, mavzu va aniqlashtirish qoidalari."""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
CALL_CENTER = "11-07"
TOPIC_RE = re.compile(
    r"uzex|узекс|birja|биржа|bitim|сделк|savdo|торг|ro‘yxat|royxat|регистрац|зарегистр|\beri\b|эцп|эри|imzo|"
    r"zakalat|закалат|залог|garov|xarid|закуп|тендер|davlat|госуд|shartnoma|контракт|договор|broker|брокер|"
    r"auksion|аукцион|narx|цен[аыу]|demo|демо|statistik|статистик|aylanma|оборот|e-imzo|депозит|depozit|call|колл", re.I)
INJECTION_RE = re.compile(r"ignore (all |previous |the )*(instructions|rules)|system prompt|игнорируй .*(инструкц|правил)|"
                          r"забудь .*(инструкц|правил)|oldingi ko‘rsatma|qoidalarni unut", re.I)

OFFTOPIC = {
    "uz": "Kechirasiz, men faqat UZEX, birja savdolari, bitimlar, ro‘yxatdan o‘tish, ERI, zakalat va davlat xaridlari mavzularida yordam bera olaman. Shu mavzularda savol bering 🙂",
    "ru": "Извините, я могу помочь только по темам UZEX, биржевых торгов, сделок, регистрации, ЭЦП, залога и госзакупок. Задайте вопрос по этим темам 🙂",
}
CLARIFY_ZAKALAT = {
    "uz": "Zakalat haqida aniqlashtiring: bu birja savdosiga oidmi yoki davlat xaridigami?",
    "ru": "Уточните, пожалуйста: вопрос про залог (закалат) относится к биржевым торгам или к госзакупкам?",
}
NO_INFO = {
    "uz": f"Bu bo‘yicha tasdiqlangan ma’lumotim yo‘q. Iltimos, UZEX call-markaziga murojaat qiling: {CALL_CENTER}.",
    "ru": f"Подтверждённой информации по этому вопросу у меня нет. Пожалуйста, обратитесь в колл-центр UZEX: {CALL_CENTER}.",
}


def norm(s):
    return s.lower().replace("’", "‘").replace("'", "‘").replace("ё", "е")


def detect_lang(text, default="uz"):
    cyr = len(re.findall(r"[а-яА-ЯёЁ]", text)); lat = len(re.findall(r"[a-zA-Z]", text))
    if cyr == lat == 0:
        return default
    return "ru" if cyr > lat else "uz"


def is_injection(text):
    return bool(INJECTION_RE.search(text))


def is_on_topic(text):
    return bool(TOPIC_RE.search(norm(text)))


def needs_zakalat_clarification(text):
    t = norm(text)
    if not re.search(r"zakalat|закалат|залог|garov", t):
        return False
    exchange = re.search(r"birja|биржа|савдо|savdo|торг|bitim|сделк|auksion|аукцион", t)
    proc = re.search(r"xarid|закуп|davlat|госуд|тендер", t)
    return not (exchange or proc)


class Knowledge:
    def __init__(self, path=None):
        path = path or os.path.join(HERE, "data", "knowledge.json")
        with open(path, encoding="utf-8") as f:
            self.entries = json.load(f)["entries"]

    def search(self, text, lang, limit=3):
        """Kalit so'z (ko'p so'zli iboralar og'irroq) bo'yicha mos parchalar. Ikkala til ham tekshiriladi."""
        t = norm(text)
        scored = []
        for e in self.entries:
            score = 0
            for lg in ("uz", "ru"):
                for kw in e["keywords"].get(lg, []):
                    k = norm(kw)
                    if k in t:
                        score += 1 + len(k.split()) + (1 if lg == lang else 0)
            if score:
                scored.append((score, e))
        scored.sort(key=lambda x: -x[0])
        return [e for _, e in scored[:limit]]

    @staticmethod
    def fact(e, lang):
        return e["facts"][lang]

    @staticmethod
    def sources_text(entries, lang):
        seen, lines = set(), []
        for e in entries:
            for s in e["sources"]:
                if s["url"] not in seen:
                    seen.add(s["url"]); lines.append(f"• {s['name']}: {s['url']}")
        head = "Rasmiy manbalar:" if lang == "uz" else "Официальные источники:"
        return head + "\n" + "\n".join(lines) if lines else ""

    def fallback_answer(self, entries, lang):
        """AI ishlamasa: faqat tasdiqlangan faktlar."""
        if not entries:
            return NO_INFO[lang]
        body = "\n\n".join(self.fact(e, lang) for e in entries)
        return body + "\n\n" + self.sources_text(entries, lang)
