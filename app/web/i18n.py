"""Interface translations: Uzbek (Latin, default), Russian, English (CLAUDE.md §3).

Client-facing content (Mustafo) has its own language handling; this is UI text only.
Missing keys fall back to Uzbek, then to the key itself, so a gap never breaks a page.
"""

from __future__ import annotations

from collections.abc import Callable

LANGUAGES = ("uz", "ru", "en")
DEFAULT_LANGUAGE = "uz"
LANG_COOKIE = "smy_lang"
LANGUAGE_NAMES = {"uz": "O'zbekcha", "ru": "Русский", "en": "English"}

_T: dict[str, dict[str, str]] = {
    # navigation / layout
    "nav.home": {"uz": "Bosh sahifa", "ru": "Главная", "en": "Home"},
    "nav.companies": {"uz": "Kompaniyalar", "ru": "Компании", "en": "Companies"},
    "nav.logout": {"uz": "Chiqish", "ru": "Выйти", "en": "Log out"},
    "nav.main": {"uz": "Asosiy menyu", "ru": "Главное меню", "en": "Main menu"},
    "global_state": {"uz": "Global holat", "ru": "Общий статус", "en": "Global state"},
    "language": {"uz": "Til", "ru": "Язык", "en": "Language"},
    # login
    "login.title": {"uz": "Kirish", "ru": "Вход", "en": "Log in"},
    "login.subtitle": {
        "uz": "ITcoDe.Uz boshqaruv paneli",
        "ru": "Панель управления ITcoDe.Uz",
        "en": "ITcoDe.Uz control panel",
    },
    "login.username": {"uz": "Login", "ru": "Логин", "en": "Username"},
    "login.password": {"uz": "Parol", "ru": "Пароль", "en": "Password"},
    "login.submit": {"uz": "Kirish", "ru": "Войти", "en": "Log in"},
    "login.error.invalid": {
        "uz": "Login yoki parol noto'g'ri.",
        "ru": "Неверный логин или пароль.",
        "en": "Invalid username or password.",
    },
    "login.error.throttled": {
        "uz": "Juda ko'p urinish. 15 daqiqadan so'ng qayta urinib ko'ring.",
        "ru": "Слишком много попыток. Повторите через 15 минут.",
        "en": "Too many attempts. Try again in 15 minutes.",
    },
    "login.error.stale": {
        "uz": "Sahifa eskirgan. Qaytadan urinib ko'ring.",
        "ru": "Страница устарела. Попробуйте ещё раз.",
        "en": "The page expired. Please try again.",
    },
    # home
    "home.hello": {"uz": "Salom", "ru": "Здравствуйте", "en": "Hello"},
    "home.paused": {
        "uz": "Agentlar holati: {state} — yangi ishlar olinmaydi.",
        "ru": "Статус агентов: {state} — новые задачи не берутся.",
        "en": "Agent state: {state} — no new jobs are taken.",
    },
    "stats.companies": {"uz": "Kompaniyalar", "ru": "Компании", "en": "Companies"},
    "stats.leads": {"uz": "Lidlar", "ru": "Лиды", "en": "Leads"},
    "stats.queued": {"uz": "Navbatda", "ru": "В очереди", "en": "Queued"},
    "stats.running": {"uz": "Ishlayapti", "ru": "Выполняются", "en": "Running"},
    "stats.failed": {"uz": "Xato", "ru": "Ошибки", "en": "Failed"},
    "home.empty": {
        "uz": "Hali kompaniyalar yo'q. Qo'lda kiritish va CSV import M4 bosqichida qo'shiladi.",
        "ru": "Компаний пока нет. Ручной ввод и импорт CSV появятся на этапе M4.",
        "en": "No companies yet. Manual entry and CSV import arrive in milestone M4.",
    },
    # companies list
    "companies.title": {"uz": "Kompaniyalar", "ru": "Компании", "en": "Companies"},
    "companies.search": {
        "uz": "Nom yoki domen bo'yicha qidirish",
        "ru": "Поиск по названию или домену",
        "en": "Search by name or domain",
    },
    "companies.country": {"uz": "Davlat", "ru": "Страна", "en": "Country"},
    "companies.state": {"uz": "Holat", "ru": "Статус", "en": "State"},
    "companies.sort": {"uz": "Saralash", "ru": "Сортировка", "en": "Sort"},
    "companies.sort.newest": {"uz": "Eng yangi", "ru": "Сначала новые", "en": "Newest"},
    "companies.sort.oldest": {"uz": "Eng eski", "ru": "Сначала старые", "en": "Oldest"},
    "companies.sort.name": {"uz": "Nomi (A–Z)", "ru": "Название (А–Я)", "en": "Name (A–Z)"},
    "companies.all": {"uz": "Hammasi", "ru": "Все", "en": "All"},
    "companies.apply": {"uz": "Qo'llash", "ru": "Применить", "en": "Apply"},
    "companies.total": {"uz": "Jami: {n}", "ru": "Всего: {n}", "en": "Total: {n}"},
    "companies.empty": {
        "uz": "Hech narsa topilmadi.",
        "ru": "Ничего не найдено.",
        "en": "Nothing found.",
    },
    "companies.loading": {"uz": "Yuklanmoqda…", "ru": "Загрузка…", "en": "Loading…"},
    "pager.prev": {"uz": "← Oldingi", "ru": "← Назад", "en": "← Previous"},
    "pager.next": {"uz": "Keyingi →", "ru": "Далее →", "en": "Next →"},
    "pager.page": {"uz": "{page} / {pages}", "ru": "{page} / {pages}", "en": "{page} / {pages}"},
    # company detail
    "company.back": {"uz": "← Ro'yxatga", "ru": "← К списку", "en": "← Back to list"},
    "company.city": {"uz": "Shahar", "ru": "Город", "en": "City"},
    "company.industry": {"uz": "Soha", "ru": "Отрасль", "en": "Industry"},
    "company.domains": {"uz": "Domenlar", "ru": "Домены", "en": "Domains"},
    "company.sources": {"uz": "Manbalar", "ru": "Источники", "en": "Sources"},
    "company.fixture": {
        "uz": "TEST MA'LUMOT",
        "ru": "ТЕСТОВЫЕ ДАННЫЕ",
        "en": "TEST DATA",
    },
    "company.research": {"uz": "Tadqiqotlar", "ru": "Исследования", "en": "Research runs"},
    "company.lead": {"uz": "Lid", "ru": "Лид", "en": "Lead"},
    "company.history": {"uz": "Tarix", "ru": "История", "en": "History"},
    "company.none": {"uz": "Yo'q", "ru": "Нет", "en": "None"},
    "company.unknown": {"uz": "Noma'lum", "ru": "Неизвестно", "en": "Unknown"},
    "company.retrieved": {"uz": "olingan", "ru": "получено", "en": "retrieved"},
    # errors
    "error.not_found": {"uz": "Topilmadi", "ru": "Не найдено", "en": "Not found"},
    "error.network": {
        "uz": "Ulanishda xato. Qayta urinib ko'ring.",
        "ru": "Ошибка соединения. Попробуйте ещё раз.",
        "en": "Connection error. Please try again.",
    },
    # control center
    "nav.control": {"uz": "Boshqaruv", "ru": "Управление", "en": "Control"},
    "control.title": {
        "uz": "Agentlar boshqaruvi",
        "ru": "Управление агентами",
        "en": "Agent control",
    },
    "control.stop_all": {"uz": "HAMMASINI TO'XTATISH", "ru": "ОСТАНОВИТЬ ВСЁ", "en": "STOP ALL"},
    "control.stop_all.confirm": {
        "uz": "Barcha agentlar to'xtatilsinmi? Navbatdagi chiquvchi xabarlar bekor qilinadi.",
        "ru": "Остановить всех агентов? Исходящие сообщения в очереди будут отменены.",
        "en": "Stop all agents? Queued outbound messages will be cancelled.",
    },
    "control.resume_all": {
        "uz": "Hammasini faollashtirish",
        "ru": "Включить всё",
        "en": "Resume all",
    },
    "control.activate": {"uz": "Faol", "ru": "Включить", "en": "Activate"},
    "control.pause": {"uz": "Pauza", "ru": "Пауза", "en": "Pause"},
    "control.stop": {"uz": "To'xtatish", "ru": "Стоп", "en": "Stop"},
    "control.queued": {"uz": "navbatda", "ru": "в очереди", "en": "queued"},
    "control.running": {"uz": "ishlayapti", "ru": "выполняется", "en": "running"},
    "control.failed": {"uz": "xato (1 soat)", "ru": "ошибок (1 ч)", "en": "failed (1h)"},
    "control.feed": {"uz": "Faoliyat", "ru": "Активность", "en": "Activity"},
    "control.feed.empty": {
        "uz": "Hali faoliyat yo'q — agentlar keyingi bosqichlarda qo'shiladi.",
        "ru": "Активности пока нет — агенты появятся на следующих этапах.",
        "en": "No activity yet — agents arrive in later milestones.",
    },
    "control.cost": {
        "uz": "AI xarajati bugun",
        "ru": "Расходы на AI сегодня",
        "en": "AI cost today",
    },
    "control.updated": {"uz": "Yangilandi", "ru": "Обновлено", "en": "Updated"},
    "control.viewer": {
        "uz": "Faqat ko'rish huquqi: holatni faqat egasi o'zgartiradi.",
        "ru": "Только просмотр: менять статус может только владелец.",
        "en": "View only: only the owner can change states.",
    },
    "control.changed": {
        "uz": "Holat o'zgartirildi.",
        "ru": "Статус изменён.",
        "en": "State changed.",
    },
    "status.running": {"uz": "ishlayapti", "ru": "работает", "en": "running"},
    "status.idle": {"uz": "bo'sh", "ru": "свободен", "en": "idle"},
    "status.paused": {"uz": "pauza", "ru": "пауза", "en": "paused"},
    "status.stopped": {"uz": "to'xtatilgan", "ru": "остановлен", "en": "stopped"},
    "status.error": {"uz": "xato", "ru": "ошибка", "en": "error"},
    "status.stalled": {"uz": "javob bermayapti", "ru": "не отвечает", "en": "stalled"},
    "agent.orchestrator": {"uz": "Orkestrator", "ru": "Оркестратор", "en": "Orchestrator"},
    "agent.discovery": {"uz": "Qidiruv", "ru": "Поиск", "en": "Discovery"},
    "agent.research_audit": {
        "uz": "Tadqiqot va audit",
        "ru": "Исследование и аудит",
        "en": "Research & Audit",
    },
    "agent.opportunity_scoring": {
        "uz": "Imkoniyat va baho",
        "ru": "Возможности и оценка",
        "en": "Opportunity & Scoring",
    },
    "agent.proposal_requirements": {
        "uz": "Taklif va talablar",
        "ru": "Предложение и ТЗ",
        "en": "Proposal & Requirements",
    },
    "agent.quality_gate": {"uz": "Sifat nazorati", "ru": "Контроль качества", "en": "Quality Gate"},
    "agent.conversation": {
        "uz": "Mustafo (suhbat)",
        "ru": "Мустафо (диалог)",
        "en": "Mustafo (conversation)",
    },
    "agent.global": {"uz": "Barcha agentlar", "ru": "Все агенты", "en": "All agents"},
    # research states
    "state.NEW": {"uz": "Yangi", "ru": "Новая", "en": "New"},
    "state.RESEARCH_PENDING": {"uz": "Navbatda", "ru": "В очереди", "en": "Queued"},
    "state.RESEARCHED": {"uz": "O'rganilgan", "ru": "Изучена", "en": "Researched"},
    "state.ANALYZED": {"uz": "Tahlil qilingan", "ru": "Проанализирована", "en": "Analyzed"},
    "state.RESEARCH_FAILED": {"uz": "Xato", "ru": "Ошибка", "en": "Failed"},
    "state.ARCHIVED": {"uz": "Arxivda", "ru": "В архиве", "en": "Archived"},
}


def normalize_language(value: str | None) -> str:
    if value:
        code = value.strip().lower()[:2]
        if code in LANGUAGES:
            return code
    return DEFAULT_LANGUAGE


def language_from_header(accept_language: str | None) -> str:
    """First supported language in an Accept-Language header (q-values ignored)."""
    for part in (accept_language or "").split(","):
        code = part.split(";")[0].strip().lower()[:2]
        if code in LANGUAGES:
            return code
    return DEFAULT_LANGUAGE


def translate(key: str, lang: str, **params: object) -> str:
    entry = _T.get(key)
    text = key if entry is None else entry.get(lang) or entry.get(DEFAULT_LANGUAGE) or key
    return text.format(**params) if params else text


def translator(lang: str) -> Callable[..., str]:
    def t(key: str, **params: object) -> str:
        return translate(key, lang, **params)

    return t


def missing_keys() -> dict[str, list[str]]:
    """Keys lacking a translation per language (used by tests)."""
    return {lang: sorted(k for k, v in _T.items() if not v.get(lang)) for lang in LANGUAGES}
