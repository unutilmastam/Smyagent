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
        "uz": "Mustafo javoblari: avtomatik yoki sizning tasdig'ingiz bilan, aloqa ma'lumoti.",
        "ru": "Ответы Мустафо: автоматически или с вашим одобрением, контакт для связи.",
        "en": "Mustafo replies: automatic or with your approval, handoff contact.",
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
    # outreach (M9)
    "out.title": {"uz": "Yuborish", "ru": "Рассылка", "en": "Outreach"},
    "out.saved": {"uz": "Bajarildi.", "ru": "Готово.", "en": "Done."},
    "out.sending_off": {
        "uz": "Yuborish o'chiq (OUTBOUND_SENDING_ENABLED=false): xatlar navbatda turadi, hech "
        "narsa jo'natilmaydi.",
        "ru": "Отправка выключена (OUTBOUND_SENDING_ENABLED=false): письма ждут в очереди, "
        "ничего не уходит.",
        "en": "Sending is off (OUTBOUND_SENDING_ENABLED=false): emails wait in the queue, "
        "nothing goes out.",
    },
    "out.email_off": {
        "uz": "Email sozlanmagan (SMTP_HOST, SMTP_FROM) — takliflar Telegram yoki telefon "
        "vazifasi bo'ladi.",
        "ru": "Email не настроен (SMTP_HOST, SMTP_FROM) — предложения станут задачами "
        "Telegram/телефон.",
        "en": "Email is not configured (SMTP_HOST, SMTP_FROM) — offers become Telegram/phone "
        "tasks.",
    },
    "out.paused": {"uz": "Email to'xtatilgan", "ru": "Email приостановлен", "en": "Email paused"},
    "out.resume": {"uz": "Emailni qayta yoqish", "ru": "Возобновить email", "en": "Resume email"},
    "out.resume_confirm": {
        "uz": "Sababni tekshirdingizmi? Email qayta yoqilsinmi?",
        "ru": "Причина проверена? Возобновить email?",
        "en": "Checked the reason? Resume email?",
    },
    "out.email_today": {
        "uz": "Bugun email / limit",
        "ru": "Email сегодня / лимит",
        "en": "Emails today / cap",
    },
    "out.telegram_today": {
        "uz": "Bugun Telegram / limit",
        "ru": "Telegram сегодня / лимит",
        "en": "Telegram today / cap",
    },
    "out.bounces": {
        "uz": "Qaytgan xatlar (30 kun)",
        "ru": "Возвраты (30 дней)",
        "en": "Bounces (30 days)",
    },
    "out.telegram_tasks": {
        "uz": "Telegram — bir bosishda yuboring",
        "ru": "Telegram — отправка в одно касание",
        "en": "Telegram — one-tap send",
    },
    "out.telegram_hint": {
        "uz": "Tugma matnni nusxalaydi va kompaniya chatini ochadi — o'z akkauntingizdan joylab "
        'yuborasiz, so\'ng "Yubordim" ni bosing.',
        "ru": "Кнопка копирует текст и открывает чат компании — вставьте и отправьте со своего "
        "аккаунта, затем нажмите «Отправил».",
        "en": "The button copies the text and opens the company chat — paste and send from your "
        'account, then tap "Sent".',
    },
    "out.copy_open": {
        "uz": "Nusxalash va ochish",
        "ru": "Скопировать и открыть",
        "en": "Copy and open",
    },
    "out.copied": {"uz": "Matn nusxalandi", "ru": "Текст скопирован", "en": "Text copied"},
    "out.sent_it": {"uz": "Yubordim", "ru": "Отправил", "en": "Sent"},
    "out.called": {"uz": "Qo'ng'iroq qildim", "ru": "Позвонил", "en": "Called"},
    "out.skip": {"uz": "O'tkazib yuborish", "ru": "Пропустить", "en": "Skip"},
    "out.phone_tasks": {
        "uz": "Telefon — o'zingiz qo'ng'iroq qiling",
        "ru": "Телефон — позвоните сами",
        "en": "Phone — call yourself",
    },
    "out.emails": {"uz": "Emaillar", "ru": "Письма", "en": "Emails"},
    "out.none": {"uz": "Hozircha yo'q.", "ru": "Пока нет.", "en": "None yet."},
    "out.done_list": {"uz": "Siz yuborganlar", "ru": "Отправлено вами", "en": "Sent by you"},
    "out.replied": {"uz": "javob keldi", "ru": "ответили", "en": "replied"},
    "out.mark_replied": {"uz": "Javob keldi", "ru": "Ответили", "en": "They replied"},
    "out.kind.first": {"uz": "birinchi", "ru": "первое", "en": "first"},
    "out.kind.follow_up": {"uz": "eslatma", "ru": "напоминание", "en": "follow-up"},
    "ostatus.QUEUED": {"uz": "navbatda", "ru": "в очереди", "en": "queued"},
    "ostatus.SENDING": {"uz": "yuborilmoqda", "ru": "отправляется", "en": "sending"},
    "ostatus.SENT": {"uz": "yuborildi", "ru": "отправлено", "en": "sent"},
    "ostatus.UNKNOWN": {
        "uz": "noma'lum — pochtani tekshiring",
        "ru": "неизвестно — проверьте почту",
        "en": "unknown — check mailbox",
    },
    "ostatus.FAILED": {"uz": "xato", "ru": "ошибка", "en": "failed"},
    "ostatus.BOUNCED": {"uz": "qaytdi", "ru": "возврат", "en": "bounced"},
    "ostatus.BLOCKED": {"uz": "to'xtatildi", "ru": "заблокировано", "en": "blocked"},
    "ostatus.TASK": {"uz": "vazifa", "ru": "задача", "en": "task"},
    "ostatus.DONE": {"uz": "bajarildi", "ru": "выполнено", "en": "done"},
    "ostatus.SKIPPED": {"uz": "o'tkazildi", "ru": "пропущено", "en": "skipped"},
    "agentset.email_auto_approve": {
        "uz": "Toza takliflarni (Quality Gate: toza) mening tasdig'imsiz email qilish",
        "ru": "Отправлять чистые предложения (Quality Gate: чисто) по email без моего одобрения",
        "en": "Email clean offers (Quality Gate: clean) without my approval",
    },
    "agentset.email_auto_hint": {
        "uz": '"Ko\'rib chiqing" belgili takliflar baribir sizga keladi. Har xatda rad etish '
        "havolasi bo'ladi; qaytish 5% dan oshsa yoki shikoyat kelsa email o'zi to'xtaydi.",
        "ru": "Предложения «проверьте» всё равно приходят к вам. В каждом письме ссылка отписки; "
        "при возвратах >5% или жалобе email останавливается сам.",
        "en": '"Needs review" offers still come to you. Every email has an unsubscribe link; '
        "bounces >5% or a complaint pause email automatically.",
    },
    "agentset.email_daily_cap": {
        "uz": "Kuniga ko'pi bilan email",
        "ru": "Максимум писем в день",
        "en": "Max emails per day",
    },
    "agentset.email_warmup_start": {
        "uz": "Birinchi kun nechta (qizdirish)",
        "ru": "Первый день (прогрев)",
        "en": "First day (warm-up)",
    },
    "agentset.email_warmup_step": {
        "uz": "Har kuni qo'shiladi",
        "ru": "Прибавка в день",
        "en": "Added per day",
    },
    "agentset.email_min_gap_minutes": {
        "uz": "Xatlar orasida kamida (daqiqa)",
        "ru": "Минимум между письмами (мин)",
        "en": "Minimum gap between emails (min)",
    },
    "agentset.follow_up_days": {
        "uz": "Eslatma necha kundan keyin (bir marta)",
        "ru": "Напоминание через (дней, один раз)",
        "en": "Follow-up after (days, once)",
    },
    "agentset.telegram_daily_cap": {
        "uz": "Kuniga ko'pi bilan Telegram",
        "ru": "Максимум Telegram в день",
        "en": "Max Telegram per day",
    },
    "unsub.title": {"uz": "Xat olishni to'xtatish", "ru": "Отписка", "en": "Unsubscribe"},
    "unsub.ask": {
        "uz": "ITcoDe.Uz dan boshqa xat olishni xohlamaysizmi? Tugmani bosing.",
        "ru": "Не хотите больше получать письма от ITcoDe.Uz? Нажмите кнопку.",
        "en": "Don't want emails from ITcoDe.Uz any more? Press the button.",
    },
    "unsub.button": {"uz": "Boshqa yozmang", "ru": "Больше не писать", "en": "Stop emailing me"},
    "unsub.done": {
        "uz": "Tayyor. Sizga boshqa xat yuborilmaydi.",
        "ru": "Готово. Мы больше не будем вам писать.",
        "en": "Done. You will not receive further emails from us.",
    },
    "unsub.invalid": {"uz": "Havola noto'g'ri.", "ru": "Неверная ссылка.", "en": "Invalid link."},
    # conversations & orders (M8)
    "nav.conversations": {"uz": "Suhbatlar", "ru": "Диалоги", "en": "Chats"},
    "conv.title": {
        "uz": "Mijozlar bilan suhbatlar",
        "ru": "Диалоги с клиентами",
        "en": "Client conversations",
    },
    "conv.intro": {
        "uz": "Mijozlar Mustafo botiga o'zlari yozadi. Mustafo AI ekanini aytadi, buyurtmani "
        "so'rab oladi va sizga topshiradi.",
        "ru": "Клиенты сами пишут боту Мустафо. Он сообщает, что он AI, собирает заказ и "
        "передаёт его вам.",
        "en": "Clients write to the Mustafo bot themselves. It says it is an AI, collects the "
        "order and hands it to you.",
    },
    "conv.empty": {
        "uz": "Hali suhbat yo'q. Bot havolasini saytingiz, Instagram va vizitkaga qo'ying.",
        "ru": "Диалогов пока нет. Разместите ссылку на бота на сайте, в Instagram и на визитке.",
        "en": "No conversations yet. Put the bot link on your site, Instagram and business card.",
    },
    "conv.drafts": {
        "uz": "{n} javob tasdiq kutmoqda",
        "ru": "{n} ответ ждёт одобрения",
        "en": "{n} reply awaiting approval",
    },
    "conv.messages": {"uz": "Xabarlar", "ru": "Сообщения", "en": "Messages"},
    "conv.disclosed": {"uz": "AI ekanligi aytilgan", "ru": "AI раскрыт", "en": "AI disclosed"},
    "conv.opted_out": {
        "uz": "Mijoz rad etdi — unga boshqa hech narsa yuborilmaydi.",
        "ru": "Клиент отказался — ему больше ничего не отправляется.",
        "en": "The client opted out — nothing will be sent to them again.",
    },
    "conv.send": {"uz": "Yuborish", "ru": "Отправить", "en": "Send"},
    "conv.discard": {"uz": "Bekor qilish", "ru": "Отменить", "en": "Discard"},
    "conv.owner_reply": {"uz": "O'zingiz yozing", "ru": "Написать самому", "en": "Write yourself"},
    "conv.owner_reply_hint": {
        "uz": "Siz yozganda Mustafo jim turadi (suhbat sizga o'tadi). Narxni faqat siz yozasiz.",
        "ru": "Когда пишете вы, Мустафо молчит (диалог переходит к вам). Цену называете только вы.",
        "en": "When you write, Mustafo stays silent (you take over). Only you state prices.",
    },
    "conv.resume": {
        "uz": "Mustafo davom etsin",
        "ru": "Мустафо продолжает",
        "en": "Let Mustafo continue",
    },
    "conv.done.send": {
        "uz": "Yuborish navbatiga qo'yildi.",
        "ru": "Поставлено в очередь на отправку.",
        "en": "Queued for sending.",
    },
    "conv.done.discard": {"uz": "Bekor qilindi.", "ru": "Отменено.", "en": "Discarded."},
    "conv.done.reply": {
        "uz": "Xabaringiz yuborish navbatida.",
        "ru": "Ваше сообщение в очереди.",
        "en": "Your message is queued.",
    },
    "conv.done.resume": {
        "uz": "Mustafo yana javob beradi.",
        "ru": "Мустафо снова отвечает.",
        "en": "Mustafo replies again.",
    },
    "conv.done.accepted": {
        "uz": "Buyurtma qabul qilindi (WON).",
        "ru": "Заказ принят (WON).",
        "en": "Order accepted (WON).",
    },
    "conv.done.question": {
        "uz": "Suhbat sizga o'tdi.",
        "ru": "Диалог передан вам.",
        "en": "You took over the chat.",
    },
    "conv.done.rejected": {
        "uz": "Buyurtma rad etildi (LOST).",
        "ru": "Заказ отклонён (LOST).",
        "en": "Order declined (LOST).",
    },
    "cstate.OPEN": {"uz": "Ochiq", "ru": "Открыт", "en": "Open"},
    "cstate.BRIEF": {"uz": "Buyurtma so'ralmoqda", "ru": "Сбор заказа", "en": "Collecting order"},
    "cstate.AWAITING_CONFIRMATION": {
        "uz": "Mijoz tasdig'i kutilmoqda",
        "ru": "Ждём подтверждения",
        "en": "Awaiting client confirmation",
    },
    "cstate.ORDER_CONFIRMED": {
        "uz": "✅ Buyurtma tasdiqlandi",
        "ru": "✅ Заказ подтверждён",
        "en": "✅ Order confirmed",
    },
    "cstate.HANDOFF": {"uz": "Siz gaplashyapsiz", "ru": "Ведёте вы", "en": "You are handling"},
    "cstate.OPTED_OUT": {"uz": "Rad etgan", "ru": "Отказался", "en": "Opted out"},
    "bstatus.COLLECTING": {"uz": "to'ldirilmoqda", "ru": "заполняется", "en": "collecting"},
    "bstatus.AWAITING_CONFIRMATION": {
        "uz": "tasdiq kutilmoqda",
        "ru": "ждёт подтверждения",
        "en": "awaiting confirmation",
    },
    "bstatus.CONFIRMED": {
        "uz": "mijoz tasdiqladi",
        "ru": "клиент подтвердил",
        "en": "client confirmed",
    },
    "bstatus.CANCELLED": {"uz": "bekor", "ru": "отменён", "en": "cancelled"},
    "mstatus.RECEIVED": {"uz": "mijozdan", "ru": "от клиента", "en": "from client"},
    "mstatus.DRAFT": {"uz": "tasdiq kutmoqda", "ru": "ждёт одобрения", "en": "awaiting approval"},
    "mstatus.APPROVED": {"uz": "navbatda", "ru": "в очереди", "en": "queued"},
    "mstatus.SENT": {"uz": "yuborildi", "ru": "отправлено", "en": "sent"},
    "mstatus.REJECTED": {"uz": "bekor qilindi", "ru": "отменено", "en": "discarded"},
    "mstatus.BLOCKED": {"uz": "to'xtatildi", "ru": "заблокировано", "en": "blocked"},
    "intent.opt_out": {"uz": "rad etish", "ru": "отказ", "en": "opt-out"},
    "intent.human_request": {"uz": "odam so'radi", "ru": "просит человека", "en": "wants a human"},
    "intent.bot_question": {"uz": "botmisan?", "ru": "ты бот?", "en": "are you a bot?"},
    "intent.price_request": {"uz": "narx so'radi", "ru": "спросил цену", "en": "asked price"},
    "intent.interest": {"uz": "qiziqish", "ru": "интерес", "en": "interest"},
    "intent.confirm": {"uz": "tasdiq", "ru": "подтверждение", "en": "confirm"},
    "intent.deny": {"uz": "yo'q", "ru": "нет", "en": "no"},
    "intent.greeting": {"uz": "salom", "ru": "приветствие", "en": "greeting"},
    "intent.spam": {"uz": "spam", "ru": "спам", "en": "spam"},
    "intent.other": {"uz": "boshqa", "ru": "другое", "en": "other"},
    "order.title": {"uz": "Buyurtma", "ru": "Заказ", "en": "Order"},
    "order.service": {"uz": "Nima kerak", "ru": "Что нужно", "en": "What"},
    "order.goal": {"uz": "Maqsad", "ru": "Цель", "en": "Goal"},
    "order.features": {"uz": "Imkoniyatlar", "ru": "Функции", "en": "Features"},
    "order.examples": {"uz": "Namunalar", "ru": "Примеры", "en": "Examples"},
    "order.content": {"uz": "Materiallar", "ru": "Материалы", "en": "Materials"},
    "order.deadline": {"uz": "Istalgan muddat", "ru": "Желаемый срок", "en": "Preferred timing"},
    "order.contact": {"uz": "Aloqa", "ru": "Контакт", "en": "Contact"},
    "order.notes": {"uz": "Tuzatishlar", "ru": "Исправления", "en": "Corrections"},
    "order.budget": {
        "uz": "Budjet (mijoz so'zi, faqat siz uchun)",
        "ru": "Бюджет (слова клиента, только для вас)",
        "en": "Budget (client's words, owner only)",
    },
    "order.confirmed_at": {
        "uz": "Mijoz tasdiqladi",
        "ru": "Клиент подтвердил",
        "en": "Client confirmed",
    },
    "order.decision": {"uz": "Qaroringiz", "ru": "Ваше решение", "en": "Your decision"},
    "order.decision.accepted": {"uz": "qabul qilindi", "ru": "принят", "en": "accepted"},
    "order.decision.question": {"uz": "savol berildi", "ru": "есть вопросы", "en": "questions"},
    "order.decision.rejected": {"uz": "rad etildi", "ru": "отклонён", "en": "declined"},
    "order.spec": {
        "uz": "Loyiha spetsifikatsiyasi (Markdown)",
        "ru": "ТЗ проекта (Markdown)",
        "en": "Project spec (Markdown)",
    },
    "order.accept": {"uz": "✅ Qabul qilaman", "ru": "✅ Принимаю", "en": "✅ Accept"},
    "order.question": {"uz": "❓ Savol beraman", "ru": "❓ Есть вопросы", "en": "❓ Ask questions"},
    "order.reject": {"uz": "❌ Rad etaman", "ru": "❌ Отклоняю", "en": "❌ Decline"},
    "home.new_orders": {
        "uz": "Yangi buyurtma: {n}",
        "ru": "Новых заказов: {n}",
        "en": "New orders: {n}",
    },
    "agentset.reply_mode": {
        "uz": "Mustafo qanday javob bersin",
        "ru": "Как отвечает Мустафо",
        "en": "How Mustafo replies",
    },
    "agentset.reply_mode.approve_all": {
        "uz": "Har bir javobni men tasdiqlayman (standart)",
        "ru": "Каждый ответ одобряю я (по умолчанию)",
        "en": "I approve every reply (default)",
    },
    "agentset.reply_mode.auto_safe": {
        "uz": "Xavfsiz javoblar darhol ketsin (narx/va'da bo'lsa — menga keladi)",
        "ru": "Безопасные ответы сразу (с ценой/обещанием — ко мне)",
        "en": "Safe replies go at once (anything with price/promise comes to me)",
    },
    "agentset.reply_mode_hint": {
        "uz": "Avtomatik rejimda ham OUTBOUND_SENDING_ENABLED=true va STOP o'chiq bo'lishi "
        "kerak. Rad etish, AI ekanligi va narxsizlik har doim saqlanadi.",
        "ru": "Даже в авто-режиме нужен OUTBOUND_SENDING_ENABLED=true и выключенный STOP. Отказ, "
        "AI-раскрытие и «без цен» действуют всегда.",
        "en": "Auto mode still needs OUTBOUND_SENDING_ENABLED=true and STOP off. Opt-out, AI "
        "disclosure and no prices always apply.",
    },
    "agentset.owner_contact": {
        "uz": "Mijoz \"odam\" so'rasa ko'rsatiladigan aloqa",
        "ru": "Контакт для клиента, если он просит человека",
        "en": "Contact shown when a client asks for a human",
    },
    "jobs.title": {
        "uz": "Vazifalar",
        "ru": "Задачи",
        "en": "Jobs",
    },
    "jobs.status": {
        "uz": "Holat",
        "ru": "Статус",
        "en": "Status",
    },
    "jobs.agent": {
        "uz": "Agent",
        "ru": "Агент",
        "en": "Agent",
    },
    "jobs.filter": {
        "uz": "Ko'rsatish",
        "ru": "Показать",
        "en": "Show",
    },
    "jobs.attempts": {
        "uz": "Urinish",
        "ru": "Попытки",
        "en": "Attempts",
    },
    "jobs.empty": {
        "uz": "Bu yerda hozircha vazifa yo'q.",
        "ru": "Задач пока нет.",
        "en": "No jobs here yet.",
    },
    "jobs.pages": {
        "uz": "Sahifalar",
        "ru": "Страницы",
        "en": "Pages",
    },
    "jobs.prev": {
        "uz": "Oldingi",
        "ru": "Назад",
        "en": "Previous",
    },
    "jobs.next": {
        "uz": "Keyingi",
        "ru": "Далее",
        "en": "Next",
    },
    "jobs.created": {
        "uz": "Yaratilgan",
        "ru": "Создана",
        "en": "Created",
    },
    "jobs.run_after": {
        "uz": "Bajarish vaqti",
        "ru": "Запуск после",
        "en": "Run after",
    },
    "jobs.finished": {
        "uz": "Tugagan",
        "ru": "Завершена",
        "en": "Finished",
    },
    "jobs.worker": {
        "uz": "Ishchi",
        "ru": "Исполнитель",
        "en": "Worker",
    },
    "jobs.error": {
        "uz": "Xato",
        "ru": "Ошибка",
        "en": "Error",
    },
    "jobs.input": {
        "uz": "Kirish ma'lumoti",
        "ru": "Входные данные",
        "en": "Input",
    },
    "jobs.runs": {
        "uz": "Ishga tushirishlar",
        "ru": "Запуски",
        "en": "Runs",
    },
    "jobs.no_runs": {
        "uz": "Hali ishga tushmagan.",
        "ru": "Ещё не запускалась.",
        "en": "Not run yet.",
    },
    "jobs.retry": {
        "uz": "Qayta urinish",
        "ru": "Повторить",
        "en": "Retry",
    },
    "jobs.cancel": {
        "uz": "Bekor qilish",
        "ru": "Отменить",
        "en": "Cancel",
    },
    "jobs.cancel.confirm": {
        "uz": "Vazifani bekor qilasizmi?",
        "ru": "Отменить задачу?",
        "en": "Cancel this job?",
    },
    "jobs.done.retry": {
        "uz": "Vazifa navbatga qaytarildi — keyingi cron'da bajariladi.",
        "ru": "Задача снова в очереди — выполнится при следующем cron.",
        "en": "Job re-queued — it runs at the next cron.",
    },
    "jobs.done.cancel": {
        "uz": "Vazifa bekor qilindi.",
        "ru": "Задача отменена.",
        "en": "Job cancelled.",
    },
    "jobs.open": {
        "uz": "Vazifalar va xatolar",
        "ru": "Задачи и ошибки",
        "en": "Jobs and errors",
    },
    "jstatus.QUEUED": {
        "uz": "navbatda",
        "ru": "в очереди",
        "en": "queued",
    },
    "jstatus.RUNNING": {
        "uz": "bajarilmoqda",
        "ru": "выполняется",
        "en": "running",
    },
    "jstatus.SUCCEEDED": {
        "uz": "bajarildi",
        "ru": "выполнена",
        "en": "succeeded",
    },
    "jstatus.FAILED": {
        "uz": "xato",
        "ru": "ошибка",
        "en": "failed",
    },
    "jstatus.CANCELLED": {
        "uz": "bekor qilingan",
        "ru": "отменена",
        "en": "cancelled",
    },
    "jstatus.BUDGET_DEFERRED": {
        "uz": "byudjet kutilmoqda",
        "ru": "ждёт бюджета",
        "en": "budget deferred",
    },
    "cron.never": {
        "uz": "Fon ishlari (cron) hali bir marta ham ishga tushmagan. cPanel → Cron Jobs'da "
        "runner qatorini qo'shing (docs/deploy-first-time-uz.md, 8-qadam).",
        "ru": "Фоновые задачи (cron) ещё ни разу не запускались. Добавьте строку runner в "
        "cPanel → Cron Jobs.",
        "en": "Background jobs (cron) have never run. Add the runner line in cPanel → Cron Jobs.",
    },
    "cron.late": {
        "uz": "Fon ishlari {m} daqiqadan beri ishlamayapti! cPanel → Cron Jobs va "
        "~/smyagent_data/runner.log ni tekshiring.",
        "ru": "Фоновые задачи не запускались {m} мин! Проверьте cPanel → Cron Jobs и "
        "~/smyagent_data/runner.log.",
        "en": "Background jobs have not run for {m} min! Check cPanel → Cron Jobs and "
        "~/smyagent_data/runner.log.",
    },
    "cron.ok": {
        "uz": "Cron ishlayapti: oxirgi marta {m} daqiqa oldin",
        "ru": "Cron работает: последний запуск {m} мин назад",
        "en": "Cron is running: last run {m} min ago",
    },
    "cron.last": {
        "uz": "✓ {ok} · ✗ {bad}",
        "ru": "✓ {ok} · ✗ {bad}",
        "en": "✓ {ok} · ✗ {bad}",
    },
    "cron.crashed": {
        "uz": "runner xato bilan to'xtagan",
        "ru": "runner завершился с ошибкой",
        "en": "the runner crashed",
    },
    "office.title": {
        "uz": "Virtual ofis",
        "ru": "Виртуальный офис",
        "en": "Virtual office",
    },
    "office.tab.office": {
        "uz": "🏢 Ofis",
        "ru": "🏢 Офис",
        "en": "🏢 Office",
    },
    "office.tab.graph": {
        "uz": "◉ Grafik",
        "ru": "◉ Граф",
        "en": "◉ Graph",
    },
    "office.open": {
        "uz": "🏢 Virtual ofis — agentlarni ko'rish",
        "ru": "🏢 Виртуальный офис — агенты",
        "en": "🏢 Virtual office — see the agents",
    },
    "office.hint": {
        "uz": "Xodimni bosing — uning ishi va boshqaruv tugmalari ochiladi. Barmoq bilan suring "
        "— butun bino ko'rinadi.",
        "ru": "Нажмите на сотрудника — откроются его работа и кнопки. Листайте пальцем, чтобы "
        "увидеть всё здание.",
        "en": "Tap an employee to see their work and controls. Swipe to see the whole building.",
    },
    "office.canvas_label": {
        "uz": "Virtual ofis: 7 agent stollarda, oshxona, hojatxona, direktor xonasi, majlis "
        "xonasi va pochta",
        "ru": "Виртуальный офис: 7 агентов, кухня, туалет, кабинет директора, переговорная и почта",
        "en": "Virtual office: 7 agents at desks, kitchen, restroom, director's room, meeting "
        "room and mail desk",
    },
    "office.staff": {
        "uz": "Xodimlar",
        "ru": "Сотрудники",
        "en": "Employees",
    },
    "office.today": {
        "uz": "Bugun",
        "ru": "Сегодня",
        "en": "Today",
    },
    "office.loading": {
        "uz": "Yuklanmoqda…",
        "ru": "Загрузка…",
        "en": "Loading…",
    },
    "office.offline": {
        "uz": "Aloqa yo'q — oxirgi holat ko'rsatilmoqda",
        "ru": "Нет связи — показано последнее состояние",
        "en": "Offline — showing the last state",
    },
    "office.real_note": {
        "uz": "Har bir harakat bazadagi haqiqiy ish holatidan olinadi.",
        "ru": "Каждое движение — из реального состояния в базе.",
        "en": "Every movement comes from the real state in the database.",
    },
    "office.close": {
        "uz": "Yopish",
        "ru": "Закрыть",
        "en": "Close",
    },
    "office.done": {
        "uz": "bajarildi",
        "ru": "выполнено",
        "en": "done",
    },
    "office.failed": {
        "uz": "xato",
        "ru": "ошибок",
        "en": "failed",
    },
    "office.queued": {
        "uz": "navbatda",
        "ru": "в очереди",
        "en": "queued",
    },
    "office.cost": {
        "uz": "AI xarajati",
        "ru": "Расходы AI",
        "en": "AI cost",
    },
    "office.view_job": {
        "uz": "Vazifani ko'rish",
        "ru": "Открыть задачу",
        "en": "Open the job",
    },
    "office.settings": {
        "uz": "Sozlamalar",
        "ru": "Настройки",
        "en": "Settings",
    },
    "office.retry_at": {
        "uz": "qayta: {t}",
        "ru": "повтор: {t}",
        "en": "retry: {t}",
    },
    "office.director": {
        "uz": "Siz (direktor)",
        "ru": "Вы (директор)",
        "en": "You (director)",
    },
    "office.resume.confirm": {
        "uz": "Barcha agentlarni yana ishga tushirasizmi?",
        "ru": "Снова запустить всех агентов?",
        "en": "Start all agents again?",
    },
    "office.stopped_banner": {
        "uz": "FAVQULODDA TO'XTATILGAN",
        "ru": "ЭКСТРЕННО ОСТАНОВЛЕНО",
        "en": "EMERGENCY STOPPED",
    },
    "office.new_order": {
        "uz": "✅ Yangi buyurtma — {t}",
        "ru": "✅ Новый заказ — {t}",
        "en": "✅ New order — {t}",
    },
    "office.cron_late": {
        "uz": "Cron ishlamayapti — agentlar yangi ish olmaydi",
        "ru": "Cron не работает — агенты не берут работу",
        "en": "Cron is not running — agents take no new work",
    },
    "office.room.open": {
        "uz": "ISH ZALI",
        "ru": "ОПЕНСПЕЙС",
        "en": "OPEN SPACE",
    },
    "office.room.dir": {
        "uz": "DIREKTOR XONASI",
        "ru": "КАБИНЕТ ДИРЕКТОРА",
        "en": "DIRECTOR",
    },
    "office.room.kitchen": {
        "uz": "OSHXONA",
        "ru": "КУХНЯ",
        "en": "KITCHEN",
    },
    "office.room.wc": {
        "uz": "HOJATXONA",
        "ru": "ТУАЛЕТ",
        "en": "RESTROOM",
    },
    "office.room.meet": {
        "uz": "MAJLIS XONASI",
        "ru": "ПЕРЕГОВОРНАЯ",
        "en": "MEETING ROOM",
    },
    "office.room.mail": {
        "uz": "POCHTA",
        "ru": "ПОЧТА",
        "en": "MAIL",
    },
    "office.funnel": {
        "uz": "Bugun: {a} topildi → {b} tahlil → {c} taklif → {d} email → {e} buyurtma",
        "ru": "Сегодня: {a} найдено → {b} анализ → {c} предлож. → {d} email → {e} заказ",
        "en": "Today: {a} found → {b} analysed → {c} offers → {d} emails → {e} orders",
    },
    "office.mode.work": {
        "uz": "ishlayapti",
        "ru": "работает",
        "en": "working",
    },
    "office.mode.idle": {
        "uz": "bo'sh — kofe",
        "ru": "свободен — кофе",
        "en": "idle — coffee",
    },
    "office.mode.queued": {
        "uz": "navbat — keyingi cron",
        "ru": "очередь — следующий cron",
        "en": "queued — next cron",
    },
    "office.mode.wait": {
        "uz": "kutyapti",
        "ru": "ждёт",
        "en": "waiting",
    },
    "office.mode.pause": {
        "uz": "pauza",
        "ru": "пауза",
        "en": "paused",
    },
    "office.mode.stop": {
        "uz": "to'xtatilgan",
        "ru": "остановлен",
        "en": "stopped",
    },
    "office.mode.error": {
        "uz": "xato",
        "ru": "ошибка",
        "en": "error",
    },
    "office.mode.stalled": {
        "uz": "javob bermayapti",
        "ru": "не отвечает",
        "en": "not responding",
    },
    "office.wait.rate_limit": {
        "uz": "so'rov limiti",
        "ru": "лимит запросов",
        "en": "rate limit",
    },
    "office.wait.backoff": {
        "uz": "vaqtinchalik xato, qayta uriniladi",
        "ru": "временная ошибка, повтор",
        "en": "temporary error, will retry",
    },
    "office.wait.budget": {
        "uz": "AI byudjeti tugadi",
        "ru": "бюджет AI исчерпан",
        "en": "AI budget used up",
    },
    "office.wait.deferred": {
        "uz": "kunlik limit / oraliq",
        "ru": "дневной лимит / интервал",
        "en": "daily cap / spacing",
    },
    "office.role.orchestrator": {
        "uz": "Boshqaruvchi — ishlarni navbatga qo'yadi",
        "ru": "Распределяет работу",
        "en": "Schedules the work",
    },
    "office.role.discovery": {
        "uz": "Qidiruvchi — yangi kompaniyalarni topadi",
        "ru": "Находит новые компании",
        "en": "Finds new companies",
    },
    "office.role.research_audit": {
        "uz": "Tahlilchi — saytlarni tekshiradi",
        "ru": "Проверяет сайты",
        "en": "Checks websites",
    },
    "office.role.opportunity_scoring": {
        "uz": "Baholovchi — imkoniyatga ball qo'yadi",
        "ru": "Оценивает возможности",
        "en": "Scores opportunities",
    },
    "office.role.proposal_requirements": {
        "uz": "Taklifchi — narxsiz taklif yozadi",
        "ru": "Пишет предложения без цен",
        "en": "Writes offers without prices",
    },
    "office.role.quality_gate": {
        "uz": "Nazoratchi — matnlarni tekshiradi",
        "ru": "Проверяет тексты",
        "en": "Checks the texts",
    },
    "office.role.conversation": {
        "uz": "Mustafo — mijozlar bilan gaplashadi (AI)",
        "ru": "Мустафо — общается с клиентами (AI)",
        "en": "Mustafo — talks to clients (AI)",
    },
    "an.title": {
        "uz": "Analitika",
        "ru": "Аналитика",
        "en": "Analytics",
    },
    "an.period": {
        "uz": "Davr",
        "ru": "Период",
        "en": "Period",
    },
    "an.days.1": {
        "uz": "Bugun",
        "ru": "Сегодня",
        "en": "Today",
    },
    "an.days.7": {
        "uz": "7 kun",
        "ru": "7 дней",
        "en": "7 days",
    },
    "an.days.30": {
        "uz": "30 kun",
        "ru": "30 дней",
        "en": "30 days",
    },
    "an.days.0": {
        "uz": "Hammasi",
        "ru": "Всё время",
        "en": "All time",
    },
    "an.budget": {
        "uz": "AI byudjeti",
        "ru": "Бюджет AI",
        "en": "AI budget",
    },
    "an.budget.month": {
        "uz": "Shu oy",
        "ru": "Этот месяц",
        "en": "This month",
    },
    "an.budget.day": {
        "uz": "Bugun",
        "ru": "Сегодня",
        "en": "Today",
    },
    "an.budget.used.month": {
        "uz": "Oylik AI byudjeti tugadi — AI ishlari keyingi oyga qoldirildi.",
        "ru": "Месячный бюджет AI исчерпан — AI-задачи отложены до следующего месяца.",
        "en": "Monthly AI budget used up — AI work waits for next month.",
    },
    "an.budget.used.day": {
        "uz": "Bugungi AI byudjeti tugadi — AI ishlari ertaga davom etadi.",
        "ru": "Дневной бюджет AI исчерпан — AI-задачи продолжатся завтра.",
        "en": "Today's AI budget used up — AI work continues tomorrow.",
    },
    "an.budget.hint": {
        "uz": "Chegara .env da: MONTHLY_AI_BUDGET_USD (kunlik = oylik ÷ kunlar). 80% da botga "
        "xabar keladi.",
        "ru": "Лимит в .env: MONTHLY_AI_BUDGET_USD (дневной = месячный ÷ дни). При 80% придёт "
        "сообщение в бот.",
        "en": "Limit in .env: MONTHLY_AI_BUDGET_USD (daily = monthly ÷ days). The bot warns at "
        "80%.",
    },
    "an.funnel": {
        "uz": "Voronka",
        "ru": "Воронка",
        "en": "Funnel",
    },
    "an.step.found": {
        "uz": "Kompaniya topildi",
        "ru": "Найдено компаний",
        "en": "Companies found",
    },
    "an.step.researched": {
        "uz": "Tahlil qilindi",
        "ru": "Проанализировано",
        "en": "Researched",
    },
    "an.step.qualified": {
        "uz": "Mos lid",
        "ru": "Подходящий лид",
        "en": "Qualified lead",
    },
    "an.step.proposals": {
        "uz": "Taklif tayyorlandi",
        "ru": "Предложение готово",
        "en": "Offer drafted",
    },
    "an.step.approved": {
        "uz": "Taklif tasdiqlandi",
        "ru": "Предложение одобрено",
        "en": "Offer approved",
    },
    "an.step.contacted": {
        "uz": "Murojaat qilindi",
        "ru": "Связались",
        "en": "Contacted",
    },
    "an.step.replied": {
        "uz": "Javob berdi",
        "ru": "Ответили",
        "en": "Replied",
    },
    "an.step.replied_all": {
        "uz": "Javob bergan + o'zi yozgan",
        "ru": "Ответили + написали сами",
        "en": "Replied + wrote first",
    },
    "an.step.orders": {
        "uz": "Buyurtma tasdiqlandi",
        "ru": "Заказ подтверждён",
        "en": "Order confirmed",
    },
    "an.step.won": {
        "uz": "Yutildi (WON)",
        "ru": "Выиграно (WON)",
        "en": "Won",
    },
    "an.of": {
        "uz": "dan",
        "ru": "от",
        "en": "of",
    },
    "an.inbound": {
        "uz": "Botga o'zi yozgan mijozlar: {n}",
        "ru": "Клиенты, написавшие в бот сами: {n}",
        "en": "Clients who wrote to the bot first: {n}",
    },
    "an.how": {
        "uz": "Qanday hisoblanadi?",
        "ru": "Как считается?",
        "en": "How is this counted?",
    },
    "an.definition": {
        "uz": "Har bir qator — davr ichida shu bosqichga yetgan alohida kompaniya/lidlar soni "
        "(audit jurnalidan, hozirgi holatdan emas). Foiz — shu davrdagi oldingi bosqichga "
        "nisbat; qisqa davrda 100% dan oshishi mumkin. Buyurtma foizi javob berganlar va "
        "botga o'zi yozganlar yig'indisiga nisbatan.",
        "ru": "Каждая строка — число разных компаний/лидов, достигших этапа в периоде (из "
        "журнала, не из текущего состояния). Процент — к предыдущему этапу того же "
        "периода; на коротком периоде может быть больше 100%. Процент заказов — от суммы "
        "ответивших и написавших сами.",
        "en": "Each row counts distinct companies/leads that reached the step within the period "
        "(from the audit trail, not current state). The rate is relative to the previous "
        "step in the same period and can exceed 100% for short periods. The order rate is "
        "relative to replies plus clients who wrote first.",
    },
    "an.outreach": {
        "uz": "Murojaatlar",
        "ru": "Рассылка",
        "en": "Outreach",
    },
    "an.out.sent": {
        "uz": "Email yuborildi",
        "ru": "Отправлено email",
        "en": "Emails sent",
    },
    "an.out.telegram": {
        "uz": "Telegram (siz yubordingiz)",
        "ru": "Telegram (отправили вы)",
        "en": "Telegram (sent by you)",
    },
    "an.out.replies": {
        "uz": "Javoblar",
        "ru": "Ответы",
        "en": "Replies",
    },
    "an.out.bounced": {
        "uz": "Qaytgan email",
        "ru": "Возвраты email",
        "en": "Bounced",
    },
    "an.agents": {
        "uz": "Agentlar ishi",
        "ru": "Работа агентов",
        "en": "Agent work",
    },
    "an.cost": {
        "uz": "AI xarajati (davr)",
        "ru": "Расходы AI (период)",
        "en": "AI cost (period)",
    },
    "an.cost.models": {
        "uz": "Model bo'yicha",
        "ru": "По моделям",
        "en": "By model",
    },
    "an.cost.none": {
        "uz": "Bu davrda AI ishlatilmadi.",
        "ru": "В этом периоде AI не использовался.",
        "en": "No AI used in this period.",
    },
    "an.searches": {
        "uz": "Qidiruv so'rovlari: {n}",
        "ru": "Поисковых запросов: {n}",
        "en": "Search requests: {n}",
    },
    "totp.title": {
        "uz": "Ikki bosqichli kirish (2FA)",
        "ru": "Двухфакторный вход (2FA)",
        "en": "Two-factor login (2FA)",
    },
    "totp.intro": {
        "uz": "Parolga qo'shimcha: kirishda telefoningizdagi ilova (Google yoki Microsoft "
        "Authenticator) ko'rsatgan 6 xonali kod so'raladi.",
        "ru": "В дополнение к паролю при входе нужен 6-значный код из приложения на телефоне "
        "(Google или Microsoft Authenticator).",
        "en": "In addition to the password, logging in asks for the 6-digit code from the app "
        "on your phone (Google or Microsoft Authenticator).",
    },
    "totp.off": {
        "uz": "2FA o'chiq. Dashboard internetda ochiq — yoqish tavsiya etiladi.",
        "ru": "2FA выключена. Панель открыта в интернете — рекомендуем включить.",
        "en": "2FA is off. The dashboard is on the internet — turning it on is recommended.",
    },
    "totp.on": {
        "uz": "2FA yoqilgan",
        "ru": "2FA включена",
        "en": "2FA is on",
    },
    "totp.enable": {
        "uz": "2FA ni yoqish",
        "ru": "Включить 2FA",
        "en": "Turn on 2FA",
    },
    "totp.setup.title": {
        "uz": "Ilovaga ulash",
        "ru": "Подключение приложения",
        "en": "Connect the app",
    },
    "totp.setup.step1": {
        "uz": "Telefonga Google Authenticator yoki Microsoft Authenticator o'rnating.",
        "ru": "Установите на телефон Google Authenticator или Microsoft Authenticator.",
        "en": "Install Google Authenticator or Microsoft Authenticator on your phone.",
    },
    "totp.setup.step2": {
        "uz": "Ilovada «+» → «QR kodni skanerlash» va quyidagi kodni skanerlang (kod shu "
        "telefonda bo'lsa — pastdagi kalitni qo'lda kiriting yoki havolani bosing).",
        "ru": "В приложении «+» → «Сканировать QR-код» и отсканируйте код ниже (если код на "
        "этом же телефоне — введите ключ вручную или нажмите ссылку).",
        "en": "In the app tap «+» → «Scan a QR code» and scan the code below (if it is on this "
        "same phone, type the key by hand or tap the link).",
    },
    "totp.setup.qr_alt": {
        "uz": "2FA uchun QR kod",
        "ru": "QR-код для 2FA",
        "en": "QR code for 2FA",
    },
    "totp.setup.manual": {
        "uz": "Qo'lda kiritish uchun kalit (hisob nomi: SMY Agent):",
        "ru": "Ключ для ручного ввода (аккаунт: SMY Agent):",
        "en": "Key for manual entry (account: SMY Agent):",
    },
    "totp.setup.link": {
        "uz": "Shu telefonda:",
        "ru": "На этом телефоне:",
        "en": "On this phone:",
    },
    "totp.setup.open_app": {
        "uz": "ilovada ochish",
        "ru": "открыть в приложении",
        "en": "open in the app",
    },
    "totp.setup.step3": {
        "uz": "Ilova ko'rsatgan 6 xonali kod",
        "ru": "6-значный код из приложения",
        "en": "The 6-digit code shown in the app",
    },
    "totp.setup.confirm": {
        "uz": "Tasdiqlash va yoqish",
        "ru": "Подтвердить и включить",
        "en": "Confirm and turn on",
    },
    "totp.setup.cancel": {
        "uz": "Bekor qilish",
        "ru": "Отмена",
        "en": "Cancel",
    },
    "totp.code": {
        "uz": "Ilovadagi kod yoki zaxira kod",
        "ru": "Код из приложения или резервный код",
        "en": "App code or recovery code",
    },
    "totp.code.app": {
        "uz": "Ilovadagi 6 xonali kod",
        "ru": "6-значный код из приложения",
        "en": "6-digit app code",
    },
    "totp.codes.title": {
        "uz": "10 ta zaxira kod",
        "ru": "10 резервных кодов",
        "en": "10 recovery codes",
    },
    "totp.codes.warn": {
        "uz": "Bu kodlar faqat HOZIR ko'rsatiladi. Telefon yo'qolsa, har biri bir marta kirish "
        "uchun ishlaydi.",
        "ru": "Коды показываются только СЕЙЧАС. Если потеряете телефон, каждый работает для "
        "одного входа.",
        "en": "These codes are shown only NOW. If you lose your phone, each one works for one "
        "login.",
    },
    "totp.codes.copy": {
        "uz": "Nusxa olish",
        "ru": "Скопировать",
        "en": "Copy",
    },
    "totp.codes.copied": {
        "uz": "Nusxa olindi",
        "ru": "Скопировано",
        "en": "Copied",
    },
    "totp.codes.where": {
        "uz": "Telefondan boshqa joyda saqlang: qog'ozga yozing yoki parol menejeriga qo'ying "
        "(chatga yubormang).",
        "ru": "Храните не в телефоне: запишите на бумаге или в менеджере паролей (не "
        "отправляйте в чат).",
        "en": "Keep them off the phone: on paper or in a password manager (never in a chat).",
    },
    "totp.codes.new": {
        "uz": "Yangi zaxira kodlar",
        "ru": "Новые резервные коды",
        "en": "New recovery codes",
    },
    "totp.remaining": {
        "uz": "Ishlatilmagan zaxira kodlar: {n}",
        "ru": "Неиспользованных резервных кодов: {n}",
        "en": "Unused recovery codes: {n}",
    },
    "totp.remaining.low": {
        "uz": "Zaxira kodlar kam qoldi — yangilarini oling.",
        "ru": "Резервных кодов мало — создайте новые.",
        "en": "Few recovery codes left — create new ones.",
    },
    "totp.disable": {
        "uz": "2FA ni o'chirish",
        "ru": "Выключить 2FA",
        "en": "Turn off 2FA",
    },
    "totp.disable.confirm": {
        "uz": "2FA ni o'chirasizmi? Kirish faqat parol bilan bo'ladi.",
        "ru": "Выключить 2FA? Вход будет только по паролю.",
        "en": "Turn off 2FA? Login will need only the password.",
    },
    "totp.done.disabled": {
        "uz": "2FA o'chirildi.",
        "ru": "2FA выключена.",
        "en": "2FA turned off.",
    },
    "totp.lost": {
        "uz": "Telefon ham, zaxira kodlar ham yo'qolsa — cPanel Terminal'da:",
        "ru": "Если потеряны и телефон, и коды — в cPanel Terminal:",
        "en": "Lost both the phone and the codes? In cPanel Terminal:",
    },
    "totp.error.code": {
        "uz": "Kod noto'g'ri yoki eskirgan. Ilovadagi yangi kodni kiriting.",
        "ru": "Неверный или устаревший код. Введите новый код из приложения.",
        "en": "Wrong or expired code. Enter the current code from the app.",
    },
    "totp.error.password": {
        "uz": "Parol noto'g'ri.",
        "ru": "Неверный пароль.",
        "en": "Wrong password.",
    },
    "totp.login.title": {
        "uz": "Tasdiqlash kodi",
        "ru": "Код подтверждения",
        "en": "Verification code",
    },
    "totp.login.hint": {
        "uz": "Authenticator ilovasidagi 6 xonali kodni kiriting.",
        "ru": "Введите 6-значный код из приложения Authenticator.",
        "en": "Enter the 6-digit code from your Authenticator app.",
    },
    "totp.login.recovery": {
        "uz": "Telefon yo'qmi? Zaxira kodlardan birini kiriting (masalan abcde-fghjk).",
        "ru": "Нет телефона? Введите один из резервных кодов (например abcde-fghjk).",
        "en": "No phone? Enter one of your recovery codes (e.g. abcde-fghjk).",
    },
    "totp.login.back": {
        "uz": "Boshqa akkaunt bilan kirish",
        "ru": "Войти под другим аккаунтом",
        "en": "Log in with another account",
    },
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
