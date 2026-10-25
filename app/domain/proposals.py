"""Value-focused offers without prices (CLAUDE.md §8.2 step 3, ADR-0008). Pure.

An offer is built only from recorded findings (observations) and the opportunities
derived from them. Facts are stated plainly; inferences are phrased as
possibilities. No price, amount, deadline, guarantee or testimonial is ever written —
the owner sends the price personally after the client's order is collected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.domain.persona import PERSONA, Language
from app.domain.scoring import Service

OWNER_NAME = "Bahrullo Nasrulloev"
MAX_SERVICES = 3
MIN_STRENGTH = 0.3


class ProposalStatus(str, Enum):
    DRAFT = "DRAFT"  # waiting for the Quality Gate
    NEEDS_EDIT = "NEEDS_EDIT"  # Quality Gate rejected it; the owner must edit
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"  # the owner decided not to contact this company


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"  # superseded by a newer version


@dataclass(frozen=True)
class Observation:
    key: str  # research finding key
    is_fact: bool


@dataclass(frozen=True)
class OfferInput:
    company_name: str
    language: Language
    observations: list[Observation]
    services: list[tuple[Service, float]]  # from opportunities, any order


@dataclass(frozen=True)
class OfferDraft:
    title: str
    body: str
    language: Language
    services: list[Service]
    observation_keys: list[str]
    # i18n keys for the owner (dashboard), never sent to the client.
    assumptions: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)


# --- texts -------------------------------------------------------------------

_OBSERVATIONS: dict[str, dict[Language, str]] = {
    "no_website": {
        Language.UZ: "Ochiq ro'yxatlarda kompaniyangiz sayti ko'rsatilmagan.",
        Language.RU: "В открытых справочниках у вашей компании не указан сайт.",
        Language.EN: "No website is listed for your business in public directories.",
    },
    "website_unreachable": {
        Language.UZ: "Ko'rsatilgan sayt hozir ochilmayapti.",
        Language.RU: "Указанный сайт сейчас не открывается.",
        Language.EN: "The listed website does not open at the moment.",
    },
    "http_error": {
        Language.UZ: "Saytning bosh sahifasi xatolik qaytarmoqda.",
        Language.RU: "Главная страница сайта возвращает ошибку.",
        Language.EN: "The homepage returns an error.",
    },
    "not_mobile_friendly": {
        Language.UZ: "Sayt telefon ekraniga moslashtirilmagan.",
        Language.RU: "Сайт не адаптирован для телефонов.",
        Language.EN: "The website is not adapted for phones.",
    },
    "no_https": {
        Language.UZ: "Sayt himoyalangan (HTTPS) ulanishsiz ochiladi.",
        Language.RU: "Сайт открывается без защищённого соединения (HTTPS).",
        Language.EN: "The website opens without a secure (HTTPS) connection.",
    },
    "slow_response": {
        Language.UZ: "Bosh sahifa sekin yuklandi.",
        Language.RU: "Главная страница загружалась медленно.",
        Language.EN: "The homepage loaded slowly.",
    },
    "weak_seo_metadata": {
        Language.UZ: "Bosh sahifada qidiruv tizimlari uchun sarlavha yoki tavsif yo'q.",
        Language.RU: "На главной странице нет заголовка или описания для поисковых систем.",
        Language.EN: "The homepage lacks a title or description for search engines.",
    },
    "no_visible_contacts": {
        Language.UZ: "Bosh sahifada telefon yoki email ko'rinmaydi.",
        Language.RU: "На главной странице не видно телефона или email.",
        Language.EN: "No phone or email is visible on the homepage.",
    },
    "no_online_inquiry": {
        Language.UZ: (
            "Ehtimol, mijozlar saytdan onlayn murojaat qoldira olmaydi "
            "(forma yoki Telegram havolasi topilmadi)."
        ),
        Language.RU: (
            "Похоже, клиенты не могут оставить заявку онлайн "
            "(не найдено формы или ссылки на Telegram)."
        ),
        Language.EN: (
            "It seems visitors cannot send a request online (no form or Telegram link found)."
        ),
    },
    "possibly_outdated": {
        Language.UZ: "Ehtimol, sayt anchadan beri yangilanmagan (sahifa pastidagi yil eski).",
        Language.RU: "Возможно, сайт давно не обновлялся (внизу страницы указан старый год).",
        Language.EN: (
            "The site may not have been updated for a while (the footer shows an old year)."
        ),
    },
}

_SERVICES: dict[Service, dict[Language, str]] = {
    Service.BUSINESS_WEBSITE: {
        Language.UZ: (
            "Biznes sayt — telefonda qulay va tez ochiladigan sayt, mijozlar sizni "
            "qidiruv va xaritalarda osonroq topadi."
        ),
        Language.RU: (
            "Сайт компании — быстрый и удобный на телефоне, чтобы клиентам было проще "
            "найти вас в поиске и на картах."
        ),
        Language.EN: (
            "Business website — fast and phone-friendly, so customers find you more "
            "easily in search and on maps."
        ),
    },
    Service.LANDING_PAGE: {
        Language.UZ: "Landing sahifa — bitta xizmat yoki taklifni aniq ko'rsatadigan sahifa.",
        Language.RU: "Лендинг — одна страница, которая понятно показывает ваше предложение.",
        Language.EN: "Landing page — one page that presents your offer clearly.",
    },
    Service.ECOMMERCE: {
        Language.UZ: "Internet do'kon — mahsulotlarni onlayn ko'rsatish va buyurtma qabul qilish.",
        Language.RU: "Интернет-магазин — показывать товары онлайн и принимать заказы.",
        Language.EN: "Online shop — show products online and accept orders.",
    },
    Service.TELEGRAM_BOT: {
        Language.UZ: (
            "Telegram bot — mijozlar savol va buyurtmalarini istalgan vaqtda yuboradi, "
            "siz esa hammasini bir joyda ko'rasiz."
        ),
        Language.RU: (
            "Telegram-бот — клиенты отправляют вопросы и заказы в любое время, а вы "
            "видите всё в одном месте."
        ),
        Language.EN: (
            "Telegram bot — customers send questions and orders at any time, and you "
            "see everything in one place."
        ),
    },
    Service.AUTOMATION: {
        Language.UZ: "Jarayonlarni avtomatlashtirish — takroriy qo'l ishlarini kamaytirish.",
        Language.RU: "Автоматизация процессов — меньше повторяющейся ручной работы.",
        Language.EN: "Process automation — less repetitive manual work.",
    },
    Service.CRM: {
        Language.UZ: "CRM — mijozlar va buyurtmalarni bir joyda yuritish.",
        Language.RU: "CRM — клиенты и заказы в одном месте.",
        Language.EN: "CRM — customers and orders in one place.",
    },
    Service.AI_ASSISTANT: {
        Language.UZ: "AI yordamchi — tez-tez beriladigan savollarga avtomatik javob.",
        Language.RU: "AI-ассистент — автоматические ответы на частые вопросы.",
        Language.EN: "AI assistant — automatic answers to frequent questions.",
    },
    Service.WEBSITE_MODERNIZATION: {
        Language.UZ: (
            "Saytni yangilash — telefonga moslashtirish, tezlashtirish, himoyalangan "
            "ulanish va zamonaviy ko'rinish."
        ),
        Language.RU: (
            "Обновление сайта — адаптация под телефоны, ускорение, защищённое "
            "соединение и современный вид."
        ),
        Language.EN: (
            "Website modernization — phone-friendly layout, faster loading, a secure "
            "connection and a modern look."
        ),
    },
    Service.MAINTENANCE: {
        Language.UZ: "Saytni qo'llab-quvvatlash — ishlashi va yangilanishini muntazam kuzatish.",
        Language.RU: "Поддержка сайта — регулярный контроль работы и обновлений.",
        Language.EN: "Website maintenance — regular checks that it works and stays up to date.",
    },
}

_FRAME: dict[Language, dict[str, str]] = {
    Language.UZ: {
        "title": "{company} uchun taklif",
        "greeting": "{company} jamoasiga,",
        "intro": (
            "{company} haqidagi ochiq ma'lumotlarni (onlayn xarita va sayt) ko'rib chiqdik "
            "va quyidagilarni ko'rdik:"
        ),
        "services": "Shu asosda sizga foyda berishi mumkin bo'lgan yechimlar:",
        "next": (
            "Narx va muddat sizning talablaringizga bog'liq. Qiziq bo'lsa, javob yozing — "
            "bir nechta savol beraman, so'ng ITcoDe.Uz rahbari {owner} sizga shaxsan "
            "taklif yuboradi."
        ),
    },
    Language.RU: {
        "title": "Предложение для {company}",
        "greeting": "Команде {company},",
        "intro": (
            "Мы посмотрели открытую информацию о {company} (онлайн-карты и сайт) "
            "и заметили следующее:"
        ),
        "services": "На этой основе вам могут быть полезны:",
        "next": (
            "Стоимость и сроки зависят от ваших требований. Если интересно, ответьте на это "
            "сообщение — я задам несколько вопросов, а затем руководитель ITcoDe.Uz "
            "{owner} лично пришлёт вам предложение."
        ),
    },
    Language.EN: {
        "title": "Proposal for {company}",
        "greeting": "Dear {company} team,",
        "intro": (
            "We looked at public information about {company} (online maps and website) "
            "and noticed the following:"
        ),
        "services": "Based on this, these could help your business:",
        "next": (
            "The exact scope and timing depend on your needs. If you are interested, "
            "reply to this message — I will ask a few questions, and then {owner}, the "
            "head of ITcoDe.Uz, will send you a personal proposal."
        ),
    },
}

# Cyrillic Uzbek offer texts arrive with M8 (client language detection); until
# then an offer for Uzbekistan is written in Latin script.
_TEMPLATE_LANGUAGE = {Language.UZ_CYRL: Language.UZ}


def template_language(language: Language) -> Language:
    return _TEMPLATE_LANGUAGE.get(language, language)


def pick_services(services: list[tuple[Service, float]]) -> list[Service]:
    ranked = sorted(services, key=lambda item: (-item[1], item[0].value))
    return [service for service, strength in ranked if strength >= MIN_STRENGTH][:MAX_SERVICES]


def build_offer(data: OfferInput) -> OfferDraft:
    lang = template_language(data.language)
    frame = _FRAME[lang]
    persona = PERSONA[lang]
    company = data.company_name.strip()
    observations = [o for o in data.observations if o.key in _OBSERVATIONS]
    # Facts first, then inferences; each key once.
    ordered = list(dict.fromkeys(o.key for o in sorted(observations, key=lambda o: not o.is_fact)))
    services = pick_services(data.services)

    lines = [persona.disclosure, "", frame["greeting"].format(company=company), ""]
    lines.append(frame["intro"].format(company=company))
    lines += [f"• {_OBSERVATIONS[key][lang]}" for key in ordered]
    lines += ["", frame["services"]]
    lines += [f"• {_SERVICES[service][lang]}" for service in services]
    lines += [
        "",
        frame["next"].format(owner=OWNER_NAME),
        "",
        persona.opt_out,
        "",
        persona.signature,
    ]

    assumptions = ["assume.public_data_only"]
    if any(not o.is_fact for o in observations):
        assumptions.append("assume.inferences_marked")
    questions = [f"question.{service.value}" for service in services] + ["question.goal"]
    return OfferDraft(
        title=frame["title"].format(company=company),
        body="\n".join(lines),
        language=lang,
        services=services,
        observation_keys=ordered,
        assumptions=assumptions,
        open_questions=questions,
    )
