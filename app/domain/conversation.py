"""Mustafo conversations: language, intent, Order Brief interview, reply texts. Pure.

Deterministic first (ADR-0007): keyword rules for intents and opt-out, script-based
language detection, a fixed interview for the Order Brief (CLAUDE.md §8.2 step 4).
An AI layer may later improve wording; it never replaces the opt-out and
confirmation rules here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from app.domain.persona import PERSONA, Language, is_cyrillic
from app.domain.proposals import OWNER_NAME
from app.domain.quality_gate import Verdict, review
from app.domain.scoring import Service

MAX_ANSWER = 500


class Intent(str, Enum):
    OPT_OUT = "opt_out"
    HUMAN_REQUEST = "human_request"
    BOT_QUESTION = "bot_question"
    PRICE_REQUEST = "price_request"
    INTEREST = "interest"
    CONFIRM = "confirm"
    DENY = "deny"
    GREETING = "greeting"
    SPAM = "spam"
    OTHER = "other"


class ConversationState(str, Enum):
    OPEN = "OPEN"
    BRIEF = "BRIEF"  # collecting the Order Brief
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    ORDER_CONFIRMED = "ORDER_CONFIRMED"
    HANDOFF = "HANDOFF"  # the owner talks personally; Mustafo stays silent
    OPTED_OUT = "OPTED_OUT"  # terminal: never write again


class BriefStatus(str, Enum):
    COLLECTING = "COLLECTING"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class MessageDirection(str, Enum):
    IN = "in"
    OUT = "out"


class MessageStatus(str, Enum):
    RECEIVED = "RECEIVED"  # inbound
    DRAFT = "DRAFT"  # outbound, waiting for the owner
    APPROVED = "APPROVED"  # queued for sending
    SENT = "SENT"
    REJECTED = "REJECTED"  # the owner discarded the draft
    BLOCKED = "BLOCKED"  # kill switch / suppression / gate stopped it


class BriefField(str, Enum):
    SERVICE = "service"
    GOAL = "goal"
    FEATURES = "features"
    EXAMPLES = "examples"
    CONTENT = "content"
    DEADLINE = "deadline"
    CONTACT = "contact"


BRIEF_ORDER = tuple(BriefField)

# --- language -----------------------------------------------------------------

_CYR = re.compile(r"[а-яёўқғҳ]", re.I)
_UZ_CYR = re.compile(
    r"[ўқғҳ]|(?<![а-яё])(?:менга|сизга|бизга|керак|кераги|ассалому|салом|рахмат|нима|"
    r"учун|борми|йук|хизмат|буюртма|канча|яхши|илтимос)(?![а-яё])",
    re.I,
)
_LAT = re.compile(r"[a-z]", re.I)
_UZ_LATIN = re.compile(
    r"\b(?:salom|assalomu|rahmat|kerak|qancha|bormi|menga|sizga|bizga|qilib|qilish|"
    r"yo'q|yoq|ha|nima|qanday|uchun|sayt|buyurtma|kompaniya|yaxshi|xizmat|bilan|"
    r"emas|kerakmi|narxi|qiziq|siz|men|biz|bor|qachon|gaplash\w*|iltimos)\b|"
    r"\w+(?:misiz|misan|mi)\?|o['ʻ‘’`]|g['ʻ‘’`]",
    re.I,
)


def switch_language(current: Language, message: str) -> Language:
    """Mid-conversation switch only on clear evidence (names and phones are not)."""
    detected = detect_language(message, default=current)
    if is_cyrillic(detected) != is_cyrillic(current):
        return detected
    if current is Language.EN and detected is Language.UZ:
        return detected
    return current


def detect_language(text: str, default: Language = Language.UZ) -> Language:
    cyr = len(_CYR.findall(text))
    lat = len(_LAT.findall(text))
    if cyr == 0 and lat == 0:
        return default
    if cyr >= lat:
        # ў қ ғ ҳ exist in Uzbek Cyrillic, not in Russian.
        return Language.UZ_CYRL if _UZ_CYR.search(text) else Language.RU
    return Language.UZ if _UZ_LATIN.search(text) else Language.EN


# --- intent -------------------------------------------------------------------


def _rx(*parts: str) -> re.Pattern[str]:
    return re.compile("|".join(parts), re.I)


_APOS = "['ʻ‘’`]?"
_INTENT_RULES: tuple[tuple[Intent, re.Pattern[str]], ...] = (
    (
        Intent.OPT_OUT,
        _rx(
            r"kerak\s+emas",
            r"yozmang",
            r"bezovta\s+qilmang",
            r"керак\s+эмас",
            r"ёзманг",
            r"не\s+пиш",
            r"не\s+беспоко",
            r"отпиш",
            r"отписат",
            r"\bstop\b",
            r"\bunsubscribe\b",
            r"\bстоп\b",
        ),
    ),
    (
        Intent.HUMAN_REQUEST,
        _rx(
            r"\boperator",
            r"odam\s+bilan",
            r"rahbar",
            r"bahrullo",
            r"qo" + _APOS + r"ng" + _APOS + r"iroq",
            r"оператор",
            r"менеджер",
            r"с\s+человеком",
            r"позвон",
            r"\bhuman\b",
            r"real\s+person",
            r"talk\s+to\s+(?:a\s+)?(?:person|someone|manager|owner)",
            r"\bmanager\b",
            r"^\s*odam\s*$",
            r"^\s*одам\s*$",
        ),
    ),
    (
        Intent.BOT_QUESTION,
        _rx(
            r"\bbot(?:mi|misiz|misan|san)\b",
            r"\brobot",
            r"odam(?:mi|misiz|misan)",
            r"siz\s+kimsiz",
            r"(?:ты|вы)\s+бот",
            r"робот",
            r"(?:ты|вы)\s+(?:живой|человек)",
            r"are\s+you\s+(?:a\s+)?(?:bot|human|real|robot|ai)",
            r"ботмисиз",
            r"одаммисиз",
        ),
    ),
    (
        Intent.PRICE_REQUEST,
        _rx(
            r"qancha",
            r"\bnarx",
            r"necha\s+pul",
            r"сколько",
            r"цен[аы]",
            r"стоимост",
            r"стоит",
            r"\bprice",
            r"\bcost",
            r"how\s+much",
            r"нарх",
            r"қанча",
        ),
    ),
    (
        Intent.INTEREST,
        _rx(
            r"qiziq",
            r"\bkerak",
            r"boshlaylik",
            r"buyurtma",
            r"zakaz",
            r"xohlayman",
            r"istayman",
            r"интерес",
            r"хочу",
            r"нуж(?:ен|на|но|ны)",
            r"заказ",
            r"давайте",
            r"interested",
            r"\bwant\b",
            r"\bneed\b",
            r"\border\b",
            r"let" + _APOS + r"s\s+start",
            r"қизиқ",
            r"керак",
            r"буюртма",
        ),
    ),
    (
        Intent.GREETING,
        _rx(r"salom", r"assalom", r"привет", r"здравств", r"\bhello\b", r"\bhi\b", r"салом"),
    ),
)
_CONFIRM = re.compile(
    r"^(?:ha|xa|xo|ҳа|ха|да|yes|ok|ок|okay|to" + _APOS + r"g" + _APOS + r"ri|"
    r"hammasi\s+to" + _APOS + r"g" + _APOS + r"ri|ha,?\s*to" + _APOS + r"g" + _APOS + r"ri|"
    r"tasdiqlayman|тўғри|ҳаммаси\s+тўғри|верно|вс[её]\s+верно|да,?\s*верно|подтверждаю|"
    r"correct|yes,?\s*correct|confirm(?:ed)?|all\s+correct)[\s.!👍✅]*$",
    re.I,
)
_DENY = re.compile(
    r"^(?:yo" + _APOS + r"q|yoq|йўқ|нет|no|noto" + _APOS + r"g" + _APOS + r"ri|не\s+верно|"
    r"wrong|not\s+correct|нотўғри)\b",
    re.I,
)
_SPAM = _rx(r"casino|kazino|казино|crypto\s*signal|заработ\w*\s+от|earn\s+\$?\d+")


def classify(text: str) -> Intent:
    """Rules in priority order; opt-out always wins (CLAUDE.md §8.1)."""
    clean = text.strip()
    if not clean:
        return Intent.OTHER
    for intent, pattern in _INTENT_RULES[:3]:  # opt-out, human, bot question
        if pattern.search(clean):
            return intent
    if _SPAM.search(clean):
        return Intent.SPAM
    if _CONFIRM.match(clean):
        return Intent.CONFIRM
    if _DENY.match(clean):
        return Intent.DENY
    for intent, pattern in _INTENT_RULES[3:]:
        if pattern.search(clean):
            return intent
    return Intent.OTHER


_SERVICE_WORDS: tuple[tuple[Service, re.Pattern[str]], ...] = (
    (Service.ECOMMERCE, _rx(r"do" + _APOS + r"kon", r"магазин", r"\bshop\b", r"e-?commerce")),
    (Service.LANDING_PAGE, _rx(r"landing", r"лендинг")),
    (Service.WEBSITE_MODERNIZATION, _rx(r"yangila", r"обнов", r"redesign", r"qayta\s+qil")),
    (Service.BUSINESS_WEBSITE, _rx(r"\bsayt", r"сайт", r"website", r"\bweb\b", r"\bsite\b")),
    (Service.TELEGRAM_BOT, _rx(r"\bbot", r"бот", r"telegram")),
    (Service.CRM, _rx(r"\bcrm\b", r"црм")),
    (Service.AUTOMATION, _rx(r"avtomat", r"автомат", r"automat")),
    (Service.AI_ASSISTANT, _rx(r"\bai\b", r"\bии\b", r"sun" + _APOS + r"iy", r"assistant")),
    (Service.MAINTENANCE, _rx(r"qo" + _APOS + r"llab", r"поддерж", r"support", r"maintenance")),
)


def detect_services(text: str) -> list[Service]:
    found = [service for service, pattern in _SERVICE_WORDS if pattern.search(text)]
    if Service.WEBSITE_MODERNIZATION in found and Service.BUSINESS_WEBSITE in found:
        found.remove(Service.BUSINESS_WEBSITE)
    return found


# --- Order Brief --------------------------------------------------------------


@dataclass
class Brief:
    answers: dict[str, str] = field(default_factory=dict)
    services: list[str] = field(default_factory=list)
    # The client's own words about money, kept for the owner only (never echoed).
    budget_note: str | None = None

    def next_field(self) -> BriefField | None:
        return next((f for f in BRIEF_ORDER if f.value not in self.answers), None)

    def record(self, text: str) -> BriefField | None:
        """Store the answer to the current question; returns the field answered."""
        current = self.next_field()
        if current is None:
            return None
        answer = text.strip()[:MAX_ANSWER]
        self.answers[current.value] = answer
        for service in detect_services(answer):
            if service.value not in self.services:
                self.services.append(service.value)
        if "price" in _gate_codes(answer):
            self.budget_note = ((self.budget_note or "") + " " + answer).strip()[:MAX_ANSWER]
        return current


def _gate_codes(text: str) -> list[str]:
    return review(text, language=Language.UZ, evidence_count=None, client_reply=True).codes


def mentions_money(text: str) -> bool:
    """True when the text has a price/amount or a deadline commitment (gate rules)."""
    return any(code in ("price", "commitment") for code in _gate_codes(text))


# --- texts --------------------------------------------------------------------

L = Language
_TEXTS: dict[str, dict[Language, str]] = {
    "welcome": {
        L.UZ: (
            "Sizga qanday yordam bera olaman? Biz sayt, Telegram bot, internet do'kon, "
            "CRM va biznesni avtomatlashtirish bo'yicha ishlaymiz. Nima kerakligini qisqacha "
            "yozing."
        ),
        L.UZ_CYRL: (
            "Сизга қандай ёрдам бера оламан? Биз сайт, Telegram бот, интернет дўкон, CRM ва "
            "бизнесни автоматлаштириш бўйича ишлаймиз. Нима кераклигини қисқача ёзинг."
        ),
        L.RU: (
            "Чем могу помочь? Мы делаем сайты, Telegram-боты, интернет-магазины, CRM и "
            "автоматизацию бизнеса. Коротко напишите, что вам нужно."
        ),
        L.EN: (
            "How can I help? We build websites, Telegram bots, online shops, CRM and "
            "business automation. Briefly tell me what you need."
        ),
    },
    "brief_start": {
        L.UZ: "Ajoyib! Buyurtmani aniq tushunish uchun bir nechta qisqa savol beraman.",
        L.UZ_CYRL: "Ажойиб! Буюртмани аниқ тушуниш учун бир нечта қисқа савол бераман.",
        L.RU: "Отлично! Задам несколько коротких вопросов, чтобы точно понять заказ.",
        L.EN: "Great! I'll ask a few short questions to understand your order.",
    },
    "q.service": {
        L.UZ: "1/7. Aynan nima yaratmoqchisiz (sayt, Telegram bot, do'kon, CRM, boshqa)?",
        L.UZ_CYRL: "1/7. Айнан нима яратмоқчисиз (сайт, Telegram бот, дўкон, CRM, бошқа)?",
        L.RU: "1/7. Что именно хотите сделать (сайт, Telegram-бот, магазин, CRM, другое)?",
        L.EN: "1/7. What exactly would you like built (website, Telegram bot, shop, CRM, other)?",
    },
    "q.goal": {
        L.UZ: (
            "2/7. Asosiy maqsad nima: ko'proq mijoz, buyurtmalarni qulaylashtirish yoki vaqt "
            "tejash?"
        ),
        L.UZ_CYRL: (
            "2/7. Асосий мақсад нима: кўпроқ мижоз, буюртмаларни қулайлаштириш ёки вақт тежаш?"
        ),
        L.RU: "2/7. Главная цель: больше клиентов, удобные заказы или экономия времени?",
        L.EN: "2/7. Main goal: more customers, easier ordering or saving time?",
    },
    "q.features": {
        L.UZ: (
            "3/7. Qaysi imkoniyatlar bo'lishi shart (katalog, buyurtma, to'lov, til, admin "
            "panel...)?"
        ),
        L.UZ_CYRL: (
            "3/7. Қайси имкониятлар бўлиши шарт (каталог, буюртма, тўлов, тил, админ панел...)?"
        ),
        L.RU: "3/7. Какие функции обязательны (каталог, заказ, оплата, языки, админ-панель...)?",
        L.EN: "3/7. Which features are a must (catalog, ordering, payment, languages, admin...)?",
    },
    "q.examples": {
        L.UZ: "4/7. Yoqqan namunalar bormi (sayt yoki bot havolasi)? Bo'lmasa \"yo'q\" deb yozing.",
        L.UZ_CYRL: '4/7. Ёққан намуналар борми (сайт ёки бот ҳаволаси)? Бўлмаса "йўқ" деб ёзинг.',
        L.RU: "4/7. Есть примеры, которые нравятся (ссылки)? Если нет — напишите «нет».",
        L.EN: '4/7. Any examples you like (links)? If not, write "no".',
    },
    "q.content": {
        L.UZ: "5/7. Matn, rasm, logotip kabi materiallarni o'zingiz berasizmi?",
        L.UZ_CYRL: "5/7. Матн, расм, логотип каби материалларни ўзингиз берасизми?",
        L.RU: "5/7. Тексты, фото, логотип вы предоставите сами?",
        L.EN: "5/7. Will you provide texts, photos and a logo yourself?",
    },
    "q.deadline": {
        L.UZ: (
            "6/7. Qachongacha tayyor bo'lishini xohlaysiz? (bu faqat sizning istagingiz sifatida "
            "yoziladi)"
        ),
        L.UZ_CYRL: (
            "6/7. Қачонгача тайёр бўлишини хоҳлайсиз? (бу фақат сизнинг истагингиз сифатида "
            "ёзилади)"
        ),
        L.RU: "6/7. К какому сроку хотели бы получить результат? (записываем как ваше пожелание)",
        L.EN: "6/7. When would you like it ready? (noted as your wish only)",
    },
    "q.contact": {
        L.UZ: "7/7. Kompaniya nomi, ismingiz va qulay aloqa (telefon yoki Telegram)?",
        L.UZ_CYRL: "7/7. Компания номи, исмингиз ва қулай алоқа (телефон ёки Telegram)?",
        L.RU: "7/7. Название компании, ваше имя и удобный контакт (телефон или Telegram)?",
        L.EN: "7/7. Company name, your name and the best contact (phone or Telegram)?",
    },
    "summary_head": {
        L.UZ: "Buyurtmangizni shunday tushundim:",
        L.UZ_CYRL: "Буюртмангизни шундай тушундим:",
        L.RU: "Я понял ваш заказ так:",
        L.EN: "Here is how I understood your order:",
    },
    "summary_ask": {
        L.UZ: 'Hammasi to\'g\'rimi? "Ha" yoki "yo\'q" deb javob bering.',
        L.UZ_CYRL: 'Ҳаммаси тўғрими? "Ҳа" ёки "йўқ" деб жавоб беринг.',
        L.RU: "Всё верно? Ответьте «да» или «нет».",
        L.EN: 'Is everything correct? Reply "yes" or "no".',
    },
    "noted": {
        L.UZ: "(qayd etildi ✓)",
        L.UZ_CYRL: "(қайд этилди ✓)",
        L.RU: "(записано ✓)",
        L.EN: "(noted ✓)",
    },
    "confirmed": {
        L.UZ: (
            "Rahmat! Buyurtmangiz qabul qilindi. ITcoDe.Uz rahbari {owner} uni ko'rib chiqib, "
            "narx va muddatni sizga shaxsan yuboradi."
        ),
        L.UZ_CYRL: (
            "Раҳмат! Буюртмангиз қабул қилинди. ITcoDe.Uz раҳбари {owner} уни кўриб чиқиб, "
            "нарх ва муддатни сизга шахсан юборади."
        ),
        L.RU: (
            "Спасибо! Заказ принят. Руководитель ITcoDe.Uz {owner} рассмотрит его и лично "
            "пришлёт вам стоимость и сроки."
        ),
        L.EN: (
            "Thank you! Your order is received. {owner}, the head of ITcoDe.Uz, will review it "
            "and personally send you the price and timing."
        ),
    },
    "correct_what": {
        L.UZ: "Nimani o'zgartiramiz? Bir xabarda yozing.",
        L.UZ_CYRL: "Нимани ўзгартирамиз? Бир хабарда ёзинг.",
        L.RU: "Что исправить? Напишите одним сообщением.",
        L.EN: "What should I change? Write it in one message.",
    },
    "price_answer": {
        L.UZ: (
            "Aniq narx talablaringizga bog'liq — {owner} buyurtmani ko'rib chiqib, narxni "
            "shaxsan yuboradi. Keling, avval nima kerakligini aniqlab olamiz."
        ),
        L.UZ_CYRL: (
            "Аниқ нарх талабларингизга боғлиқ — {owner} буюртмани кўриб чиқиб, нархни "
            "шахсан юборади. Келинг, аввал нима кераклигини аниқлаб оламиз."
        ),
        L.RU: (
            "Точная стоимость зависит от требований — {owner} рассмотрит заказ и лично "
            "пришлёт цену. Давайте сначала уточним, что нужно."
        ),
        L.EN: (
            "The exact price depends on your requirements — {owner} will review the order and "
            "send the price personally. Let's first clarify what you need."
        ),
    },
    "bot_answer": {
        L.UZ: (
            "Ha, men AI yordamchiman, inson emasman. Xohlasangiz, sizni ITcoDe.Uz rahbari "
            '{owner} bilan bog\'layman — "odam" deb yozing.'
        ),
        L.UZ_CYRL: (
            "Ҳа, мен AI ёрдамчиман, инсон эмасман. Хоҳласангиз, сизни ITcoDe.Uz раҳбари "
            '{owner} билан боғлайман — "одам" деб ёзинг.'
        ),
        L.RU: (
            "Да, я AI-ассистент, не человек. Если хотите, я свяжу вас с руководителем "
            "ITcoDe.Uz {owner} — напишите «оператор»."
        ),
        L.EN: (
            "Yes, I'm an AI assistant, not a human. If you like, I can connect you with "
            '{owner}, the head of ITcoDe.Uz — write "human".'
        ),
    },
    "handoff": {
        L.UZ: "Sizni {owner} bilan bog'layman, u o'zi yozadi. Aloqa: {contact}",
        L.UZ_CYRL: "Сизни {owner} билан боғлайман, у ўзи ёзади. Алоқа: {contact}",
        L.RU: "Передаю ваш вопрос {owner}, он напишет вам сам. Контакт: {contact}",
        L.EN: "I'm passing you to {owner}, who will write to you personally. Contact: {contact}",
    },
    "fallback": {
        L.UZ: "Kechirasiz, tushunmadim. Sizga sayt, Telegram bot yoki boshqa dastur kerakmi?",
        L.UZ_CYRL: "Кечирасиз, тушунмадим. Сизга сайт, Telegram бот ёки бошқа дастур керакми?",
        L.RU: "Извините, не понял. Вам нужен сайт, Telegram-бот или другая программа?",
        L.EN: "Sorry, I didn't get that. Do you need a website, a Telegram bot or other software?",
    },
    "after_order": {
        L.UZ: "Buyurtmangiz {owner}da. U tez orada o'zi yozadi.",
        L.UZ_CYRL: "Буюртмангиз {owner}да. У тез орада ўзи ёзади.",
        L.RU: "Ваш заказ уже у {owner}. Он скоро напишет сам.",
        L.EN: "Your order is with {owner}, who will write to you soon.",
    },
}

_BRIEF_LABELS: dict[Language, dict[str, str]] = {
    L.UZ: {
        "service": "Nima kerak",
        "goal": "Maqsad",
        "features": "Imkoniyatlar",
        "examples": "Namunalar",
        "content": "Materiallar",
        "deadline": "Istalgan muddat",
        "contact": "Aloqa",
        "notes": "Tuzatishlar",
    },
    L.UZ_CYRL: {
        "service": "Нима керак",
        "goal": "Мақсад",
        "features": "Имкониятлар",
        "examples": "Намуналар",
        "content": "Материаллар",
        "deadline": "Исталган муддат",
        "contact": "Алоқа",
        "notes": "Тузатишлар",
    },
    L.RU: {
        "service": "Что нужно",
        "goal": "Цель",
        "features": "Функции",
        "examples": "Примеры",
        "content": "Материалы",
        "deadline": "Желаемый срок",
        "contact": "Контакт",
        "notes": "Исправления",
    },
    L.EN: {
        "service": "What you need",
        "goal": "Goal",
        "features": "Features",
        "examples": "Examples",
        "content": "Materials",
        "deadline": "Preferred timing",
        "contact": "Contact",
        "notes": "Corrections",
    },
}


def text(key: str, lang: Language, *, contact: str = "") -> str:
    template = _TEXTS[key][lang]
    return template.replace("{owner}", OWNER_NAME).replace("{contact}", contact)


def question(brief_field: BriefField, lang: Language) -> str:
    return text(f"q.{brief_field.value}", lang)


def summary(brief: Brief, lang: Language) -> str:
    """Brief shown back to the client. Money/deadline figures are never echoed."""
    labels = _BRIEF_LABELS[lang]
    lines = [text("summary_head", lang)]
    for f in BRIEF_ORDER:
        answer = brief.answers.get(f.value, "—")
        if f is not BriefField.CONTACT and mentions_money(answer):
            answer = text("noted", lang)
        lines.append(f"• {labels[f.value]}: {answer}")
    notes = brief.answers.get("notes")
    if notes:
        lines.append(
            f"• {labels['notes']}: {text('noted', lang) if mentions_money(notes) else notes}"
        )
    lines += ["", text("summary_ask", lang)]
    return "\n".join(lines)


def with_disclosure(body: str, lang: Language) -> str:
    """First message of every new conversation starts with the AI disclosure (§5.1)."""
    return f"{PERSONA[lang].disclosure}\n\n{body}"


def reply_is_safe(body: str, lang: Language, *, extra_blocked: tuple[str, ...] = ()) -> bool:
    """Quality Gate for client replies: no price, commitment or blocked word."""
    result = review(
        body,
        language=lang,
        evidence_count=None,
        client_reply=True,
        extra_blocked=extra_blocked,
    )
    return result.verdict is not Verdict.REJECTED
