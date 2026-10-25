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
    # discovery (M4)
    "companies.add": {"uz": "+ Qo'shish", "ru": "+ Добавить", "en": "+ Add"},
    "companies.import": {"uz": "CSV import", "ru": "Импорт CSV", "en": "CSV import"},
    "new.title": {"uz": "Yangi kompaniya", "ru": "Новая компания", "en": "New company"},
    "new.name": {"uz": "Nomi *", "ru": "Название *", "en": "Name *"},
    "new.country": {"uz": "Davlat *", "ru": "Страна *", "en": "Country *"},
    "new.domain": {"uz": "Sayt / domen", "ru": "Сайт / домен", "en": "Website / domain"},
    "new.phone": {"uz": "Telefon", "ru": "Телефон", "en": "Phone"},
    "new.email": {
        "uz": "Email (ochiq, ish manzili)",
        "ru": "Email (публичный, рабочий)",
        "en": "Email (public business address)",
    },
    "new.telegram": {
        "uz": "Telegram (kompaniya akkaunti)",
        "ru": "Telegram (аккаунт компании)",
        "en": "Telegram (business account)",
    },
    "new.source_url": {"uz": "Manba havolasi", "ru": "Ссылка на источник", "en": "Source link"},
    "new.notes": {"uz": "Izoh", "ru": "Заметки", "en": "Notes"},
    "new.multi_hint": {
        "uz": "Bir nechta qiymatni | bilan ajrating.",
        "ru": "Несколько значений разделяйте символом |.",
        "en": "Separate several values with |.",
    },
    "new.business_only": {
        "uz": "Faqat kompaniyaning ochiq ish kontaktlari. Shaxsiy ma'lumot kiritmang.",
        "ru": "Только публичные рабочие контакты компании. Не вводите личные данные.",
        "en": "Public business contacts only. Do not enter private personal data.",
    },
    "new.allow_duplicate": {
        "uz": "Bu nom va shahar bo'yicha boshqa kompaniya — baribir qo'shish",
        "ru": "Это другая компания с тем же названием и городом — всё равно добавить",
        "en": "This is a different company with the same name and city — add anyway",
    },
    "new.submit": {"uz": "Saqlash", "ru": "Сохранить", "en": "Save"},
    "new.duplicate": {
        "uz": "Bunday kompaniya allaqachon bor ({reason}).",
        "ru": "Такая компания уже есть ({reason}).",
        "en": "This company already exists ({reason}).",
    },
    "new.open_existing": {
        "uz": "Mavjudini ochish",
        "ru": "Открыть существующую",
        "en": "Open existing",
    },
    "new.invalid": {"uz": "Xato: {reason}", "ru": "Ошибка: {reason}", "en": "Error: {reason}"},
    "import.title": {"uz": "CSV import", "ru": "Импорт CSV", "en": "CSV import"},
    "import.help": {
        "uz": (
            "Ustunlar: name, country (majburiy), city, industry, domain, phone, "
            "email, telegram, source_url, notes. O'zbekcha/ruscha sarlavhalar ham "
            "qabul qilinadi. UTF-8 yoki Windows-1251, 1 MB / 2000 qatorgacha."
        ),
        "ru": (
            "Колонки: name, country (обязательно), city, industry, domain, phone, "
            "email, telegram, source_url, notes. Заголовки на русском/узбекском "
            "тоже принимаются. UTF-8 или Windows-1251, до 1 МБ / 2000 строк."
        ),
        "en": (
            "Columns: name, country (required), city, industry, domain, phone, "
            "email, telegram, source_url, notes. Uzbek/Russian headers are accepted "
            "too. UTF-8 or Windows-1251, up to 1 MB / 2000 rows."
        ),
    },
    "import.file": {"uz": "Fayl", "ru": "Файл", "en": "File"},
    "import.dry_run": {
        "uz": "Faqat tekshirish (saqlamasdan)",
        "ru": "Только проверить (без сохранения)",
        "en": "Check only (do not save)",
    },
    "import.submit": {"uz": "Yuklash", "ru": "Загрузить", "en": "Upload"},
    "import.summary": {
        "uz": "{created} ta yangi · {duplicates} ta dublikat · {invalid} ta xato",
        "ru": "{created} новых · {duplicates} дубликатов · {invalid} ошибок",
        "en": "{created} new · {duplicates} duplicates · {invalid} errors",
    },
    "import.dry_note": {
        "uz": "Bu tekshiruv natijasi — hech narsa saqlanmadi.",
        "ru": "Это результат проверки — ничего не сохранено.",
        "en": "This is a preview — nothing was saved.",
    },
    "import.row": {"uz": "Qator", "ru": "Строка", "en": "Row"},
    "status.created": {"uz": "yangi", "ru": "новая", "en": "new"},
    "status.duplicate": {"uz": "dublikat", "ru": "дубликат", "en": "duplicate"},
    "status.invalid": {"uz": "xato", "ru": "ошибка", "en": "error"},
    "company.contacts": {"uz": "Kontaktlar", "ru": "Контакты", "en": "Contacts"},
    "company.notes": {"uz": "Izoh", "ru": "Заметки", "en": "Notes"},
    # automatic discovery
    "auto.link": {"uz": "🔎 Avto-qidiruv", "ru": "🔎 Автопоиск", "en": "🔎 Auto discovery"},
    "auto.title": {
        "uz": "Avtomatik qidiruv",
        "ru": "Автоматический поиск",
        "en": "Automatic discovery",
    },
    "auto.intro": {
        "uz": "Qidiruv agenti quyidagi shaharlarda bizneslarni o'zi topadi (har 7 kunda), "
        "sayt, telefon va Telegram ma'lumotlarini yig'adi. Siz hech narsa kiritmaysiz.",
        "ru": "Агент поиска сам находит компании в этих городах (раз в 7 дней) и собирает "
        "сайт, телефон и Telegram. Вам ничего вводить не нужно.",
        "en": "The Discovery agent finds businesses in these cities on its own (every 7 days) "
        "and collects website, phone and Telegram. You don't need to enter anything.",
    },
    "auto.provider": {"uz": "Manba", "ru": "Источник", "en": "Source"},
    "auto.provider.off": {
        "uz": "O'chirilgan (SEARCH_PROVIDER bo'sh)",
        "ru": "Выключено (SEARCH_PROVIDER пуст)",
        "en": "Off (SEARCH_PROVIDER is empty)",
    },
    "auto.found": {"uz": "topilgan", "ru": "найдено", "en": "found"},
    "auto.last_run": {"uz": "Oxirgi qidiruv", "ru": "Последний поиск", "en": "Last search"},
    "auto.never": {"uz": "hali bo'lmagan", "ru": "ещё не было", "en": "not yet"},
    "auto.run_now": {"uz": "Hozir qidirish", "ru": "Искать сейчас", "en": "Search now"},
    "auto.enable": {"uz": "Yoqish", "ru": "Включить", "en": "Enable"},
    "auto.disable": {"uz": "O'chirish", "ru": "Выключить", "en": "Disable"},
    "auto.disabled": {"uz": "o'chirilgan", "ru": "выключено", "en": "disabled"},
    "auto.add": {"uz": "Shahar qo'shish", "ru": "Добавить город", "en": "Add city"},
    "auto.categories": {"uz": "Sohalar", "ru": "Сферы", "en": "Categories"},
    "auto.queued": {
        "uz": "Navbatga qo'yildi: {n} ta qidiruv. Natija Boshqaruv sahifasida ko'rinadi.",
        "ru": "В очереди: {n} поисков. Результат появится на странице «Управление».",
        "en": "Queued: {n} searches. Progress shows on the Control page.",
    },
    "auto.runs": {"uz": "Oxirgi qidiruvlar", "ru": "Последние поиски", "en": "Recent searches"},
    "auto.cron_hint": {
        "uz": "Ishlashi uchun serverda cron sozlangan bo'lishi kerak "
        "(docs/deployment-cpanel.md §7).",
        "ru": "Для работы на сервере должен быть настроен cron (docs/deployment-cpanel.md §7).",
        "en": "Requires the server cron job (docs/deployment-cpanel.md §7).",
    },
    "auto.osm_attribution": {
        "uz": "Ma'lumotlar © OpenStreetMap hissadorlari (ODbL)",
        "ru": "Данные © участники OpenStreetMap (ODbL)",
        "en": "Data © OpenStreetMap contributors (ODbL)",
    },
    "cat.retail": {"uz": "Do'konlar", "ru": "Магазины", "en": "Retail"},
    "cat.food": {
        "uz": "Kafe va restoranlar",
        "ru": "Кафе и рестораны",
        "en": "Cafes & restaurants",
    },
    "cat.hospitality": {"uz": "Mehmonxonalar", "ru": "Гостиницы", "en": "Hotels"},
    "cat.health": {
        "uz": "Klinika va dorixonalar",
        "ru": "Клиники и аптеки",
        "en": "Clinics & pharmacies",
    },
    "cat.education": {"uz": "O'quv markazlari", "ru": "Учебные центры", "en": "Training centres"},
    "cat.services": {"uz": "Ofis va xizmatlar", "ru": "Офисы и услуги", "en": "Offices & services"},
    "cat.auto": {"uz": "Avto xizmatlar", "ru": "Авто сервис", "en": "Car services"},
    "cat.beauty": {"uz": "Go'zallik salonlari", "ru": "Салоны красоты", "en": "Beauty salons"},
    "cat.craft": {"uz": "Ustaxonalar", "ru": "Мастерские", "en": "Workshops"},
    # research & audit (M5)
    "audit.title": {"uz": "Sayt auditi", "ru": "Аудит сайта", "en": "Website audit"},
    "audit.score": {
        "uz": "Sayt holati: {score}/100",
        "ru": "Состояние сайта: {score}/100",
        "en": "Website health: {score}/100",
    },
    "audit.none": {
        "uz": "Hali tekshirilmagan.",
        "ru": "Ещё не проверен.",
        "en": "Not audited yet.",
    },
    "audit.error": {
        "uz": "Sayt ochilmadi ({cat}).",
        "ru": "Сайт не открылся ({cat}).",
        "en": "Site did not open ({cat}).",
    },
    "audit.findings": {"uz": "Topilmalar", "ru": "Находки", "en": "Findings"},
    "audit.fact": {"uz": "fakt", "ru": "факт", "en": "fact"},
    "audit.inference": {"uz": "taxmin", "ru": "предположение", "en": "inference"},
    "audit.measured": {"uz": "o'lchangan", "ru": "измерено", "en": "measured"},
    "check.https": {"uz": "HTTPS", "ru": "HTTPS", "en": "HTTPS"},
    "check.status": {"uz": "Javob kodi", "ru": "Код ответа", "en": "HTTP status"},
    "check.title": {"uz": "Sarlavha", "ru": "Заголовок", "en": "Title"},
    "check.meta_description": {
        "uz": "Tavsif (SEO)",
        "ru": "Описание (SEO)",
        "en": "Description (SEO)",
    },
    "check.mobile_viewport": {
        "uz": "Telefonga moslashgan",
        "ru": "Мобильная версия",
        "en": "Mobile-friendly",
    },
    "check.response_time": {"uz": "Tezlik", "ru": "Скорость", "en": "Response time"},
    "check.page_size": {"uz": "Sahifa hajmi", "ru": "Размер страницы", "en": "Page size"},
    "check.visible_contacts": {
        "uz": "Kontaktlar ko'rinadi",
        "ru": "Контакты видны",
        "en": "Visible contacts",
    },
    "check.telegram_link": {
        "uz": "Telegram havolasi",
        "ru": "Ссылка на Telegram",
        "en": "Telegram link",
    },
    "check.contact_form": {"uz": "Formalar soni", "ru": "Количество форм", "en": "Forms"},
    "check.image_alt_text": {
        "uz": "Rasm tavsiflari",
        "ru": "Alt у картинок",
        "en": "Image alt text",
    },
    "check.lang_attribute": {
        "uz": "Til belgisi",
        "ru": "Атрибут языка",
        "en": "Language attribute",
    },
    "check.copyright_year": {"uz": "Copyright yili", "ru": "Год копирайта", "en": "Copyright year"},
    "check.site_builder": {"uz": "Platforma", "ru": "Платформа", "en": "Platform"},
    "finding.no_website": {
        "uz": "Ochiq ma'lumotlarda bu biznesning sayti topilmadi.",
        "ru": "В открытых данных у бизнеса не найден сайт.",
        "en": "No website was found for this business in its public listing.",
    },
    "finding.website_unreachable": {
        "uz": "Ko'rsatilgan sayt ochilmadi.",
        "ru": "Указанный сайт не открывается.",
        "en": "The listed website could not be opened.",
    },
    "finding.no_https": {
        "uz": "Sayt HTTPS'siz ishlaydi.",
        "ru": "Сайт работает без HTTPS.",
        "en": "The website is served without HTTPS.",
    },
    "finding.http_error": {
        "uz": "Bosh sahifa xato kodi qaytardi.",
        "ru": "Главная страница вернула ошибку.",
        "en": "The homepage returned an error code.",
    },
    "finding.weak_seo_metadata": {
        "uz": "Bosh sahifada sarlavha yoki tavsif yo'q.",
        "ru": "На главной нет заголовка или описания.",
        "en": "The homepage lacks a title or meta description.",
    },
    "finding.not_mobile_friendly": {
        "uz": "Sayt telefonga moslashmagan (viewport yo'q).",
        "ru": "Сайт не адаптирован под телефон (нет viewport).",
        "en": "The homepage has no responsive (mobile) viewport tag.",
    },
    "finding.slow_response": {
        "uz": "Bosh sahifa sekin ochildi (bir o'lchov).",
        "ru": "Главная открылась медленно (одно измерение).",
        "en": "The homepage loaded slowly (one measurement).",
    },
    "finding.no_visible_contacts": {
        "uz": "Bosh sahifada telefon yoki email ko'rinmaydi.",
        "ru": "На главной не видно телефона или email.",
        "en": "No phone number or email is visible on the homepage.",
    },
    "finding.no_online_inquiry": {
        "uz": "Saytdan onlayn murojaat qilib bo'lmaydi (forma yoki Telegram yo'q).",
        "ru": "С сайта нельзя оставить заявку онлайн (нет формы или Telegram).",
        "en": "Visitors cannot send a request online (no form or Telegram link).",
    },
    "finding.possibly_outdated": {
        "uz": "Copyright yili eski — sayt yangilanmayotgan bo'lishi mumkin.",
        "ru": "Старый год копирайта — сайт, возможно, не обновляется.",
        "en": "Old copyright year — the site may not be maintained.",
    },
    "finding.audit_not_allowed": {
        "uz": "Sayt robots.txt orqali avtomatik tekshirishni taqiqlagan.",
        "ru": "Сайт запрещает автоматическую проверку в robots.txt.",
        "en": "The site's robots.txt disallows automated reading.",
    },
    # opportunity & scoring (M6)
    "nav.leads": {"uz": "Lidlar", "ru": "Лиды", "en": "Leads"},
    "leads.title": {"uz": "Lidlar", "ru": "Лиды", "en": "Leads"},
    "leads.empty": {
        "uz": "Hali lid yo'q — agentlar kompaniyalarni tekshirib baholagach "
        "shu yerda paydo bo'ladi.",
        "ru": "Лидов пока нет — они появятся после проверки и оценки компаний агентами.",
        "en": "No leads yet — they appear once agents have researched and scored companies.",
    },
    "leads.stage": {"uz": "Bosqich", "ru": "Этап", "en": "Stage"},
    "leads.score": {"uz": "Ball", "ru": "Балл", "en": "Score"},
    "leads.need": {"uz": "Ehtiyoj", "ru": "Потребность", "en": "Need"},
    "opp.title": {"uz": "Imkoniyatlar", "ru": "Возможности", "en": "Opportunities"},
    "opp.none": {
        "uz": "Hozircha imkoniyat topilmadi.",
        "ru": "Пока возможностей не найдено.",
        "en": "No opportunity found yet.",
    },
    "opp.because": {"uz": "sababi", "ru": "причина", "en": "because"},
    "score.title": {
        "uz": "Baho: {total}/100",
        "ru": "Оценка: {total}/100",
        "en": "Score: {total}/100",
    },
    "score.missing": {"uz": "Ma'lumot yo'q", "ru": "Нет данных", "en": "No data"},
    "score.weight": {"uz": "vazn", "ru": "вес", "en": "weight"},
    "score.version": {"uz": "hisoblangan", "ru": "рассчитано", "en": "computed"},
    "settings.scoring": {
        "uz": "Baholash sozlamalari",
        "ru": "Настройки оценки",
        "en": "Scoring settings",
    },
    "settings.threshold": {
        "uz": "Lid tayyor (QUALIFIED) chegarasi",
        "ru": "Порог квалификации лида",
        "en": "Qualification threshold",
    },
    "settings.saved": {
        "uz": "Saqlandi. Yangi baholar keyingi tekshiruvlarda qo'llanadi.",
        "ru": "Сохранено. Новые веса применятся при следующих оценках.",
        "en": "Saved. New weights apply to future evaluations.",
    },
    "settings.save": {"uz": "Saqlash", "ru": "Сохранить", "en": "Save"},
    "comp.service_fit": {
        "uz": "Xizmatga moslik",
        "ru": "Соответствие услугам",
        "en": "Service fit",
    },
    "comp.evidence_quality": {
        "uz": "Dalil sifati",
        "ru": "Качество данных",
        "en": "Evidence quality",
    },
    "comp.geography": {"uz": "Hudud", "ru": "География", "en": "Geography"},
    "comp.contactability": {
        "uz": "Bog'lanish imkoni",
        "ru": "Контактность",
        "en": "Contactability",
    },
    "comp.activity": {
        "uz": "Faollik belgilari",
        "ru": "Признаки активности",
        "en": "Activity signals",
    },
    "svc.business_website": {
        "uz": "Biznes sayt",
        "ru": "Сайт для бизнеса",
        "en": "Business website",
    },
    "svc.landing_page": {"uz": "Landing sahifa", "ru": "Лендинг", "en": "Landing page"},
    "svc.ecommerce": {"uz": "Internet do'kon", "ru": "Интернет-магазин", "en": "Online store"},
    "svc.telegram_bot": {"uz": "Telegram bot", "ru": "Telegram-бот", "en": "Telegram bot"},
    "svc.automation": {
        "uz": "Biznes avtomatlashtirish",
        "ru": "Автоматизация бизнеса",
        "en": "Business automation",
    },
    "svc.crm": {"uz": "CRM", "ru": "CRM", "en": "CRM"},
    "svc.ai_assistant": {"uz": "AI yordamchi", "ru": "AI-ассистент", "en": "AI assistant"},
    "svc.website_modernization": {
        "uz": "Saytni yangilash",
        "ru": "Обновление сайта",
        "en": "Website modernization",
    },
    "svc.maintenance": {
        "uz": "Saytga texnik xizmat",
        "ru": "Техподдержка сайта",
        "en": "Website maintenance",
    },
    "stage.CANDIDATE": {"uz": "Nomzod", "ru": "Кандидат", "en": "Candidate"},
    "stage.QUALIFIED": {"uz": "Tayyor", "ru": "Квалифицирован", "en": "Qualified"},
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
    # proposals & quality gate (M7)
    "nav.proposals": {"uz": "Takliflar", "ru": "Предложения", "en": "Proposals"},
    "proposals.title": {"uz": "Takliflar", "ru": "Предложения", "en": "Proposals"},
    "proposals.status": {"uz": "Holat", "ru": "Статус", "en": "Status"},
    "proposals.empty": {
        "uz": "Hali taklif yo'q — tayyor lidlar uchun agent o'zi tayyorlaydi.",
        "ru": "Предложений пока нет — агент готовит их для квалифицированных лидов.",
        "en": "No proposals yet — the agent drafts them for qualified leads.",
    },
    "proposals.no_price_note": {
        "uz": "Taklifda narx, muddat va kafolat yo'q — narxni mijoz buyurtmasidan keyin o'zingiz "
        "yuborasiz.",
        "ru": "В предложении нет цен, сроков и гарантий — цену вы отправляете сами после заказа.",
        "en": "Offers contain no price, deadline or guarantee — you send the price yourself "
        "after the order.",
    },
    "proposals.text": {"uz": "Taklif matni", "ru": "Текст предложения", "en": "Offer text"},
    "proposals.field_title": {"uz": "Sarlavha", "ru": "Заголовок", "en": "Title"},
    "proposals.approve": {"uz": "Tasdiqlayman", "ru": "Одобрить", "en": "Approve"},
    "proposals.reject": {"uz": "Rad etaman", "ru": "Отклонить", "en": "Reject"},
    "proposals.reason": {
        "uz": "Sabab (ixtiyoriy)",
        "ru": "Причина (необязательно)",
        "en": "Reason (optional)",
    },
    "proposals.reject_hint": {
        "uz": "Rad etilsa, bu kompaniyaga murojaat qilinmaydi (lid: DISQUALIFIED).",
        "ru": "После отклонения компании не пишем (лид: DISQUALIFIED).",
        "en": "Rejecting means this company will not be contacted (lead: DISQUALIFIED).",
    },
    "proposals.edit": {"uz": "Tahrirlash", "ru": "Редактировать", "en": "Edit"},
    "proposals.edit_hint": {
        "uz": "Saqlanganda yangi versiya yaratiladi va Quality Gate qayta tekshiradi.",
        "ru": "При сохранении создаётся новая версия и Quality Gate проверяет её снова.",
        "en": "Saving creates a new version that the Quality Gate checks again.",
    },
    "proposals.evidence": {"uz": "Dalillar", "ru": "Доказательства", "en": "Evidence"},
    "proposals.no_evidence": {
        "uz": "Dalil yo'q.",
        "ru": "Нет доказательств.",
        "en": "No evidence.",
    },
    "proposals.assumptions": {"uz": "Farazlar", "ru": "Допущения", "en": "Assumptions"},
    "proposals.questions": {
        "uz": "Mijozdan so'raladigan savollar",
        "ru": "Вопросы клиенту",
        "en": "Questions for the client",
    },
    "proposals.export": {
        "uz": "Markdown yuklab olish",
        "ru": "Скачать Markdown",
        "en": "Download Markdown",
    },
    "proposals.history": {"uz": "Tarix", "ru": "История", "en": "History"},
    "proposals.error": {"uz": "Bajarilmadi", "ru": "Не выполнено", "en": "Not done"},
    "proposals.done.approve": {
        "uz": "Tasdiqlandi. Yuborish outreach (M9) yoqilganda bo'ladi.",
        "ru": "Одобрено. Отправка — после включения рассылки (M9).",
        "en": "Approved. Sending happens once outreach (M9) is enabled.",
    },
    "proposals.done.reject": {"uz": "Rad etildi.", "ru": "Отклонено.", "en": "Rejected."},
    "proposals.done.edit": {
        "uz": "Yangi versiya saqlandi va tekshirildi.",
        "ru": "Новая версия сохранена и проверена.",
        "en": "New version saved and checked.",
    },
    "pstatus.DRAFT": {"uz": "Qoralama", "ru": "Черновик", "en": "Draft"},
    "pstatus.NEEDS_EDIT": {"uz": "Tahrir kerak", "ru": "Нужна правка", "en": "Needs edit"},
    "pstatus.AWAITING_APPROVAL": {
        "uz": "Tasdiq kutilmoqda",
        "ru": "Ждёт одобрения",
        "en": "Awaiting approval",
    },
    "pstatus.APPROVED": {"uz": "Tasdiqlangan", "ru": "Одобрено", "en": "Approved"},
    "pstatus.REJECTED": {"uz": "Rad etilgan", "ru": "Отклонено", "en": "Rejected"},
    "approval.PENDING": {"uz": "kutilmoqda", "ru": "ожидает", "en": "pending"},
    "approval.APPROVED": {"uz": "tasdiqlandi", "ru": "одобрено", "en": "approved"},
    "approval.REJECTED": {"uz": "rad etildi", "ru": "отклонено", "en": "rejected"},
    "approval.CANCELLED": {
        "uz": "bekor (yangi versiya)",
        "ru": "отменено (новая версия)",
        "en": "cancelled (new version)",
    },
    "gate.title": {
        "uz": "Sifat nazorati (Quality Gate)",
        "ru": "Контроль качества",
        "en": "Quality Gate",
    },
    "gate.approved": {"uz": "Toza", "ru": "Чисто", "en": "Clean"},
    "gate.needs_review": {"uz": "Ko'rib chiqing", "ru": "Проверьте", "en": "Needs review"},
    "gate.rejected": {"uz": "Rad etdi", "ru": "Отклонено", "en": "Rejected"},
    "gate.clean": {
        "uz": "Muammo topilmadi: narx, va'da, tasdiqlanmagan da'vo yo'q; AI ekanligi va rad "
        "etish yo'li yozilgan.",
        "ru": "Проблем нет: без цен, обещаний и неподтверждённых заявлений; есть AI-раскрытие и "
        "отказ.",
        "en": "No issues: no price, promise or unsupported claim; AI disclosure and opt-out "
        "present.",
    },
    "gate.pending": {
        "uz": "Tekshiruv navbatda.",
        "ru": "Проверка в очереди.",
        "en": "Check queued.",
    },
    "gate.issue.empty": {"uz": "Matn bo'sh", "ru": "Пустой текст", "en": "Empty text"},
    "gate.issue.price": {
        "uz": 'Narx, summa, chegirma yoki "bepul" bor',
        "ru": "Есть цена, сумма, скидка или «бесплатно»",
        "en": 'Contains a price, amount, discount or "free"',
    },
    "gate.issue.commitment": {
        "uz": "Va'da bor (kafolat, muddat, shartnoma, to'lov)",
        "ru": "Есть обязательство (гарантия, срок, договор, оплата)",
        "en": "Contains a commitment (guarantee, deadline, contract, payment)",
    },
    "gate.issue.unsupported_claim": {
        "uz": 'Tasdiqlanmagan da\'vo ("eng yaxshi", "100%", mijozlar haqida)',
        "ru": "Неподтверждённое заявление («лучший», «100%», о клиентах)",
        "en": 'Unsupported claim ("the best", "100%", about clients)',
    },
    "gate.issue.missing_disclosure": {
        "uz": "Mustafo AI ekanligi yozilmagan",
        "ru": "Нет раскрытия, что Мустафо — AI",
        "en": "Missing the AI disclosure (Mustafo)",
    },
    "gate.issue.missing_opt_out": {
        "uz": 'Rad etish yo\'li yozilmagan ("kerak emas")',
        "ru": "Нет способа отказаться («не пишите»)",
        "en": 'Missing the opt-out ("stop")',
    },
    "gate.issue.no_evidence": {
        "uz": "Dalilga asoslanmagan",
        "ru": "Нет доказательств",
        "en": "No evidence",
    },
    "gate.issue.language_mismatch": {
        "uz": "Til/yozuv mijoz tiliga mos emas",
        "ru": "Язык/алфавит не совпадает с языком клиента",
        "en": "Language/script does not match the client's",
    },
    "gate.issue.too_long": {"uz": "Juda uzun", "ru": "Слишком длинно", "en": "Too long"},
    "assume.public_data_only": {
        "uz": "Faqat ochiq ma'lumot (xarita, bosh sahifa) asosida; bitta o'lchov.",
        "ru": "Только по открытым данным (карты, главная страница); одно измерение.",
        "en": "Based only on public data (maps, homepage); one measurement.",
    },
    "assume.inferences_marked": {
        "uz": 'Ba\'zi kuzatuvlar taxmin — matnda "ehtimol" deb yozilgan.',
        "ru": "Часть наблюдений — предположения, в тексте помечены «возможно».",
        "en": "Some observations are inferences, phrased as possibilities.",
    },
    "question.goal": {
        "uz": "Asosiy maqsad nima: ko'proq mijoz, buyurtmani tezlashtirish yoki vaqtni tejash?",
        "ru": "Главная цель: больше клиентов, быстрее заказы или экономия времени?",
        "en": "Main goal: more customers, faster orders or saving time?",
    },
    "question.business_website": {
        "uz": "Saytda qaysi xizmat/mahsulotlar, nechta til va qanday aloqa usullari bo'lsin?",
        "ru": "Какие услуги/товары, языки и способы связи нужны на сайте?",
        "en": "Which services/products, languages and contact options should the site have?",
    },
    "question.landing_page": {
        "uz": "Sahifa qaysi bitta xizmatni taklif qilsin?",
        "ru": "Какую одну услугу должна продвигать страница?",
        "en": "Which single offer should the page promote?",
    },
    "question.ecommerce": {
        "uz": "Nechta mahsulot, to'lov va yetkazib berish qanday?",
        "ru": "Сколько товаров, как оплата и доставка?",
        "en": "How many products, and how are payment and delivery handled?",
    },
    "question.telegram_bot": {
        "uz": "Bot nima qilsin: buyurtma, savol-javob, katalog yoki yozilish?",
        "ru": "Что должен делать бот: заказы, ответы, каталог или запись?",
        "en": "What should the bot do: orders, Q&A, catalog or bookings?",
    },
    "question.automation": {
        "uz": "Qaysi takroriy ish ko'p vaqt oladi?",
        "ru": "Какая повторяющаяся работа отнимает больше всего времени?",
        "en": "Which repetitive task takes the most time?",
    },
    "question.crm": {
        "uz": "Hozir mijoz va buyurtmalar qayerda yuritiladi?",
        "ru": "Где сейчас ведутся клиенты и заказы?",
        "en": "Where are customers and orders tracked today?",
    },
    "question.ai_assistant": {
        "uz": "Mijozlar eng ko'p qanday savollar beradi?",
        "ru": "Какие вопросы клиенты задают чаще всего?",
        "en": "Which questions do customers ask most?",
    },
    "question.website_modernization": {
        "uz": "Hozirgi saytning nimasi yoqmaydi, nima qolishi kerak?",
        "ru": "Что не нравится в текущем сайте, что оставить?",
        "en": "What do you dislike about the current site, and what must stay?",
    },
    "question.maintenance": {
        "uz": "Saytni hozir kim yangilaydi va qanchalik tez-tez?",
        "ru": "Кто сейчас обновляет сайт и как часто?",
        "en": "Who updates the site now, and how often?",
    },
    "stats.awaiting": {"uz": "Tasdiq kutmoqda", "ru": "Ждут одобрения", "en": "Awaiting approval"},
    "stage.PROPOSAL_DRAFTED": {
        "uz": "Taklif yozildi",
        "ru": "Предложение готово",
        "en": "Proposal drafted",
    },
    "stage.AWAITING_APPROVAL": {
        "uz": "Tasdiq kutmoqda",
        "ru": "Ждёт одобрения",
        "en": "Awaiting approval",
    },
    "stage.APPROVED": {"uz": "Tasdiqlangan", "ru": "Одобрен", "en": "Approved"},
    "stage.DISQUALIFIED": {"uz": "Chiqarilgan", "ru": "Исключён", "en": "Disqualified"},
    "company.proposal": {"uz": "Taklif", "ru": "Предложение", "en": "Proposal"},
    # agent settings (M7c)
    "agentset.title": {
        "uz": "Agent sozlamalari",
        "ru": "Настройки агентов",
        "en": "Agent settings",
    },
    "agentset.intro": {
        "uz": "Har bir agent nima va qanday qilishini shu yerda o'zgartirasiz. Har o'zgarish "
        "versiyalanadi — xohlasangiz oldingisiga qaytarasiz.",
        "ru": "Здесь вы меняете, что и как делает каждый агент. Каждое изменение сохраняется "
        "версией — можно вернуть прежнюю.",
        "en": "Change what each agent does and how. Every change is versioned — you can restore "
        "an earlier one.",
    },
    "agentset.configure": {"uz": "Sozlash", "ru": "Настроить", "en": "Configure"},
    "agentset.defaults": {"uz": "standart", "ru": "по умолчанию", "en": "defaults"},
    "agentset.more": {"uz": "Boshqa sozlamalar", "ru": "Другие настройки", "en": "More settings"},
    "agentset.locked": {
        "uz": "O'zgartirib bo'lmaydigan qoidalar",
        "ru": "Неизменяемые правила",
        "en": "Rules that cannot be changed",
    },
    "agentset.saved": {"uz": "Saqlandi (v{v}).", "ru": "Сохранено (v{v}).", "en": "Saved (v{v})."},
    "agentset.not_saved": {
        "uz": "Saqlanmadi — quyidagilarni tuzating:",
        "ru": "Не сохранено — исправьте:",
        "en": "Not saved — please fix:",
    },
    "agentset.desc.orchestrator": {
        "uz": "Ish tartibi va navbat — faqat ko'rsatma (AI uchun).",
        "ru": "Порядок работы и очередь — только инструкции (для AI).",
        "en": "Workflow and queue — instructions only (for AI).",
    },
    "agentset.desc.discovery": {
        "uz": "Qaysi shahar va sohada qidirish, har qidiruvda nechta kompaniya.",
        "ru": "Где и в каких сферах искать, сколько компаний за поиск.",
        "en": "Where and in which industries to search, companies per search.",
    },
    "agentset.desc.research_audit": {
        "uz": "Bir ishga tushishda nechta kompaniyani tekshirish.",
        "ru": "Сколько компаний проверять за один запуск.",
        "en": "How many companies to check per run.",
    },
    "agentset.desc.opportunity_scoring": {
        "uz": 'Ball vaznlari, "tayyor lid" va "issiq lid" chegaralari.',
        "ru": "Веса баллов, пороги «готового» и «горячего» лида.",
        "en": "Score weights, qualified and hot lead thresholds.",
    },
    "agentset.desc.proposal_requirements": {
        "uz": "Qaysi xizmatlarni taklif qilish, nechta, va taklif matnlari.",
        "ru": "Какие услуги предлагать, сколько и тексты предложений.",
        "en": "Which services to offer, how many, and the offer texts.",
    },
    "agentset.desc.quality_gate": {
        "uz": "Qo'shimcha taqiqlangan va tekshiriladigan so'zlar.",
        "ru": "Дополнительные запрещённые и проверяемые слова.",
        "en": "Extra blocked and review words.",
    },
    "agentset.desc.conversation": {
        "uz": "Mustafo suhbati — sozlamalar M8 bilan; hozir ko'rsatma.",
        "ru": "Диалоги Мустафо — настройки с M8; сейчас инструкции.",
        "en": "Mustafo conversations — settings arrive with M8; instructions now.",
    },
    "agentset.results_per_search": {
        "uz": "Har qidiruvda ko'pi bilan nechta kompaniya (5–200)",
        "ru": "Максимум компаний за один поиск (5–200)",
        "en": "Max companies per search (5–200)",
    },
    "agentset.discovery_hint": {
        "uz": "Shahar, soha va qidirish oralig'i:",
        "ru": "Города, сферы и интервал поиска:",
        "en": "Cities, industries and interval:",
    },
    "agentset.companies_per_run": {
        "uz": "Bir ishga tushishda nechta kompaniya tekshirilsin (1–100)",
        "ru": "Сколько компаний проверять за запуск (1–100)",
        "en": "Companies to check per run (1–100)",
    },
    "agentset.hot_lead_threshold": {
        "uz": '"Issiq lid" chegarasi — Telegramga xabar (0–100)',
        "ru": "Порог «горячего» лида — уведомление в Telegram (0–100)",
        "en": "Hot lead threshold — Telegram alert (0–100)",
    },
    "agentset.enabled_services": {
        "uz": "Qaysi xizmatlarni taklif qilsin",
        "ru": "Какие услуги предлагать",
        "en": "Services to offer",
    },
    "agentset.max_services": {
        "uz": "Bitta taklifda nechta xizmat (1–5)",
        "ru": "Сколько услуг в одном предложении (1–5)",
        "en": "Services per offer (1–5)",
    },
    "agentset.min_strength": {
        "uz": "Ehtiyoj kuchi kamida (0.1–0.9) — past bo'lsa ko'proq taklif",
        "ru": "Минимальная сила потребности (0.1–0.9) — ниже = больше предложений",
        "en": "Minimum need strength (0.1–0.9) — lower = more offers",
    },
    "agentset.texts": {"uz": "Taklif matnlari", "ru": "Тексты предложения", "en": "Offer texts"},
    "agentset.texts_hint": {
        "uz": "Bo'sh qoldirilsa standart matn ishlatiladi. {company} — kompaniya nomi, {owner} — "
        "sizning ismingiz. Saqlashda Quality Gate tekshiradi: narx, kafolat, muddat bo'lsa "
        "saqlanmaydi. AI salomlashuvi, rad etish yo'li va imzo doim qo'shiladi.",
        "ru": "Пусто = стандартный текст. {company} — название компании, {owner} — ваше имя. При "
        "сохранении Quality Gate проверяет текст: с ценой, гарантией или сроком не сохранится. "
        "AI-раскрытие, отказ и подпись добавляются всегда.",
        "en": "Empty = built-in text. {company} = company name, {owner} = your name. The Quality "
        "Gate checks on save: prices, guarantees or deadlines are refused. AI disclosure, "
        "opt-out and signature are always added.",
    },
    "agentset.part.title": {"uz": "Sarlavha", "ru": "Заголовок", "en": "Title"},
    "agentset.part.greeting": {"uz": "Murojaat", "ru": "Обращение", "en": "Greeting"},
    "agentset.part.intro": {
        "uz": "Kirish (kuzatuvlardan oldin)",
        "ru": "Вступление (перед наблюдениями)",
        "en": "Intro (before observations)",
    },
    "agentset.part.services": {
        "uz": "Xizmatlar sarlavhasi",
        "ru": "Заголовок услуг",
        "en": "Services heading",
    },
    "agentset.part.next": {
        "uz": "Keyingi qadam (yakun)",
        "ru": "Следующий шаг (концовка)",
        "en": "Next step (closing)",
    },
    "agentset.extra_blocked": {
        "uz": "Taqiqlangan so'zlar (har qatorda bittadan) — bo'lsa taklif rad etiladi",
        "ru": "Запрещённые слова (по одному в строке) — предложение отклоняется",
        "en": "Blocked words (one per line) — the offer is rejected",
    },
    "agentset.extra_review": {
        "uz": "Tekshiriladigan so'zlar — bo'lsa \"ko'rib chiqing\" belgisi",
        "ru": "Слова для проверки — пометка «проверьте»",
        "en": 'Review words — marked "needs review"',
    },
    "agentset.words_hint": {
        "uz": "Bular standart qoidalarga qo'shiladi; standart qoidalarni o'chirib bo'lmaydi.",
        "ru": "Добавляются к встроенным правилам; встроенные отключить нельзя.",
        "en": "Added to the built-in rules; built-in rules cannot be removed.",
    },
    "agentset.later": {
        "uz": "Bu agentning ish sozlamalari o'z bosqichida qo'shiladi.",
        "ru": "Настройки этого агента появятся в его этапе.",
        "en": "This agent's settings arrive with its milestone.",
    },
    "agentset.instructions": {
        "uz": "Agentga ko'rsatma (oddiy so'z bilan)",
        "ru": "Инструкция агенту (своими словами)",
        "en": "Instructions for the agent (plain words)",
    },
    "agentset.instructions_placeholder": {
        "uz": "Masalan: restoranlarga avval Telegram bot taklif qil.",
        "ru": "Например: ресторанам сначала предлагай Telegram-бота.",
        "en": "E.g.: offer restaurants a Telegram bot first.",
    },
    "agentset.instructions_hint": {
        "uz": "AI kaliti qo'shilgach agentlar shu ko'rsatmaga amal qiladi. Qulflangan qoidalarga "
        "zid ko'rsatma bajarilmaydi.",
        "ru": "После добавления AI-ключа агенты будут следовать инструкции. Противоречащее "
        "закреплённым правилам не выполняется.",
        "en": "Agents follow this once an AI key is configured. Anything against the locked "
        "rules is ignored.",
    },
    "agentset.reset": {
        "uz": "Standartga qaytarish",
        "ru": "Сбросить по умолчанию",
        "en": "Reset to defaults",
    },
    "agentset.reset_confirm": {
        "uz": "Barcha sozlamalar standartga qaytsinmi?",
        "ru": "Сбросить все настройки агента?",
        "en": "Reset this agent to defaults?",
    },
    "agentset.history": {"uz": "Versiyalar", "ru": "Версии", "en": "Versions"},
    "agentset.restore": {"uz": "Shunga qaytarish", "ru": "Вернуть", "en": "Restore"},
    "agentset.no_history": {
        "uz": "Hali o'zgartirilmagan.",
        "ru": "Ещё не менялось.",
        "en": "Not changed yet.",
    },
    "rule.ai_disclosure": {
        "uz": "Mustafo har doim AI ekanini aytadi.",
        "ru": "Мустафо всегда сообщает, что он AI.",
        "en": "Mustafo always says it is an AI.",
    },
    "rule.no_prices": {
        "uz": "Mijozga narx, muddat, kafolat aytilmaydi — narxni o'zingiz yuborasiz.",
        "ru": "Клиенту не называются цены, сроки, гарантии — цену отправляете вы.",
        "en": "No prices, deadlines or guarantees to clients — you send the price.",
    },
    "rule.opt_out": {
        "uz": '"Kerak emas" degan kompaniyaga boshqa yozilmaydi.',
        "ru": "Тем, кто ответил «не пишите», больше не пишем.",
        "en": "Anyone who opts out is never contacted again.",
    },
    "rule.kill_switch": {
        "uz": "STOP tugmasi har doim ishlaydi.",
        "ru": "Кнопка STOP работает всегда.",
        "en": "The STOP button always works.",
    },
    "rule.lawful_sources": {
        "uz": "Faqat ochiq, qonuniy manbalar; spam va userbot yo'q.",
        "ru": "Только открытые законные источники; без спама и юзерботов.",
        "en": "Only open, lawful sources; no spam or userbots.",
    },
    "rule.owner_approval": {
        "uz": "Shartnoma, narx va to'lovni faqat siz kelishasiz.",
        "ru": "Договор, цену и оплату согласуете только вы.",
        "en": "Only you agree contracts, prices and payment.",
    },
    "gate.issue.owner_blocked_word": {
        "uz": "Sizning taqiqlangan so'zingiz bor",
        "ru": "Есть ваше запрещённое слово",
        "en": "Contains one of your blocked words",
    },
    "gate.issue.owner_review_word": {
        "uz": "Sizning tekshiriladigan so'zingiz bor",
        "ru": "Есть ваше слово для проверки",
        "en": "Contains one of your review words",
    },
    "nav.settings": {"uz": "Sozlamalar", "ru": "Настройки", "en": "Settings"},
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
