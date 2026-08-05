#!/usr/bin/env python3
"""
Основонй скрипт для поиска и откликов на HH.ru за основу взят hh_auto_apply
Мои проекты github.com/vanuska
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright


ROOT_DIR = Path(__file__).resolve().parent
MY_DIR = ROOT_DIR / "my"
DEFAULT_CONFIG_PATH = MY_DIR / "config.yaml"
DEFAULT_STATE_DB = ROOT_DIR / "data" / "hh_auto_apply.sqlite3"
DEFAULT_COVER_LETTER_PROMPT_PATH = MY_DIR / "cover_letter_prompt.md"
DEFAULT_APPLICATION_QUESTIONS_FILE = MY_DIR / "application_questions.yaml"
HH_API_BASE = "https://api.hh.ru"
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
HH_API_TIMEOUT_SECONDS = 45
HH_API_RETRIES = 3

# Базовые ответы на вопросы работодателя (используются по умолчанию, если нет файла)
DEFAULT_APPLICATION_ANSWERS = [
    {
        "keywords": [
            "количество проектов", "сколько проектов", "общее количество",
            "за последние", "2-3 года", "проектов над которыми",
            "укажите общее количество", "укажите общее количество проектов"
        ],
        "answer": "Более 15 крупных и средних проектов"
    },
    {
        "keywords": [
            "предметные области", "области проектов", "над которыми работали",
            "работали последние", "перечислите предметные",
            "предметные области проектов", "перечислите предметные области проектов"
        ],
        "answer": "Управление IT-инфраструктурой, автоматизация бизнес-процессов, внедрение и сопровождение 1С и CRM систем, информационная безопасность, бюджетирование и тендеры, миграция IT-сервисов в ЦОД, управление командами до 45+ сотрудников"
    },
    {
        "keywords": [
            "от старта до завершения", "реализованы вами", "сколько из этих",
            "реализованы от старта", "реализованы Вами от старта",
            "старта до завершения", "реализованы вами от старта до завершения"
        ],
        "answer": "12 проектов реализовано от старта до завершения"
    },
    {
        "keywords": [
            "каскадным методом", "waterfall", "каскадный метод",
            "сколько waterfall", "реализованы каскадным",
            "реализованы каскадным методом"
        ],
        "answer": "8 проектов реализовано каскадным методом (waterfall)"
    },
    {
        "keywords": [
            "зарплат", "зп", "ожидания", "доход", "компенсац",
            "уровень заработной", "ежемесячных доход", "заработной платы",
            "желаемый уровень", "уточните желаемый уровень",
            "уточните желаемый уровень заработной платы"
        ],
        "answer": "от 270000 руб"
    },
    {
        "keywords": ["город", "откуда", "проживаете", "проживания"],
        "answer": "Москва"
    },
    {
        "keywords": [
            "бюджет проекта", "средний бюджет", "человеко-днях",
            "диапазон", "деньгах", "средний бюджет проекта",
            "какой был средний бюджет"
        ],
        "answer": "Бюджеты проектов варьировались от 5 до 50 миллионов рублей, средний бюджет составлял 15-20 миллионов рублей"
    },
    {
        "keywords": ["проект", "реализовали", "завершили", "сколько проектов"],
        "answer": "Более 15 проектов различной сложности и масштаба"
    },
    {
        "keywords": [
            "методология", "agile", "scrum", "kanban", "гибкая",
            "каскадная", "методология управления проектами"
        ],
        "answer": "Использовал как каскадную (waterfall), так и гибкие методологии (Agile, Scrum) в зависимости от требований проекта"
    },
    {
        "keywords": [
            "команда", "подчиненные", "сотрудники", "управление командой",
            "руководил", "количество подчиненных"
        ],
        "answer": "Управлял командами до 45+ сотрудников, включая системных администраторов, разработчиков и специалистов по информационной безопасности"
    }
]

DEFAULT_CITY = "Москва"
DEFAULT_SALARY = "от 270000 руб"

HR_ADAPTATION_RULES = """
Ты — профессиональный HR-консультант и эксперт по резюме. Твоя задача — адаптировать
подачу кандидата под конкретную вакансию в сопроводительном письме.

Общие принципы:
- Краткость: излагай информацию сжато, без воды.
- Конкретность: предпочитай измеримые достижения общим фразам.
- Релевантность: содержание должно соответствовать требованиям вакансии.
- Правдивость: не преувеличивай опыт и навыки.
- Деловой стиль: исключи юмор, сленг и восклицательные знаки.
- Не используй букву "е" с точками, длинные тире и типографские тире.

Алгоритм адаптации:
- Сопоставь желаемую роль кандидата с названием вакансии.
- Естественно встрой ключевые слова из вакансии, если они подтверждаются профилем.
- На первое место ставь релевантные обязанности, проекты и достижения.
- Не упоминай нерелевантный опыт, если он не помогает отклику.
- Используй цифры и результаты только если они есть в оригинальном профиле.

Не включай:
- Названия прошлых компаний кандидата.
- Семейное положение и возраст.
- Хобби, если они не связаны с работой.
- Очевидные навыки вроде MS Office или "уверенный пользователь ПК".
- Нерелевантный опыт.

Критически важный запрет галлюцинаций:
- Строго запрещено выдумывать факты, компании, должности, проекты или навыки.
- Строго запрещено добавлять образование, сертификаты или курсы, которых нет в профиле.
- Строго запрещено придумывать метрики и цифры.
- Используй только информацию из профиля кандидата и вакансии.
- Можно перефразировать и реструктурировать, но нельзя добавлять несуществующие данные.
- Нельзя использовать названия прошлых компаний кандидата в письме.
""".strip()


def send_telegram_notification(message: str, parse_mode: str = "HTML") -> None:
    """Отправляет сообщение в Telegram, если настроены переменные окружения."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                print("Telegram уведомление отправлено.")
            else:
                print(f"Telegram ответил с кодом {resp.status}")
    except Exception as e:
        print(f"Ошибка отправки в Telegram: {e}")


def test_openrouter_model(api_key: str, model: str) -> bool:
    """Быстро проверяет, работает ли модель на OpenRouter."""
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            timeout=10.0,
            default_headers={
                "HTTP-Referer": "https://github.com/vanuska/HH.ru-Job-Search-Apply-with-AI",
                "X-Title": "HH.ru-Job-Search-Apply-with-AI",
            }
        )
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Say 'ok'"}],
            max_tokens=20,
            temperature=0.0
        )
        return response.choices and len(response.choices[0].message.content.strip()) > 0
    except Exception as e:
        print(f"Ошибка проверки модели {model}: {e}")
        return False


def test_model_with_sample_letter(llm: LlmConfig, model: str, profile: str) -> tuple[bool, str]:
    """
    Тестирует модель на реальном примере письма.
    Возвращает (успешно_ли, текст_ответа)
    """
    try:
        from openai import OpenAI

        test_profile = profile[:500] if len(profile) > 500 else profile

        system_prompt = """
Ты пишешь сопроводительные письма для hh.ru от лица кандидата.
Стиль: русский язык, профессионально, уверенно, без штампов.
Ответ должен быть 2-3 предложения.
"""
        user_prompt = f"""
Профиль кандидата:
{test_profile}

Вакансия:
Название: Тестовая вакансия IT-руководителя
Компания: Тестовая компания

Напиши короткое сопроводительное письмо (2-3 предложения) на русском языке.
"""

        client = OpenAI(
            api_key=llm.api_key,
            base_url=llm.base_url or "https://openrouter.ai/api/v1",
            timeout=15.0,
            default_headers={
                "HTTP-Referer": "https://github.com/vanuska/HH.ru-Job-Search-Apply-with-AI",
                "X-Title": "HH.ru-Job-Search-Apply-with-AI",
            }
        )
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=200,
        )
        raw_text = (response.choices[0].message.content or "").strip()
        if raw_text:
            return True, raw_text
        else:
            return False, "Пустой ответ"
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "rate-limited" in error_msg:
            return False, "Ограничение запросов (429)"
        else:
            return False, f"Ошибка: {e}"


def interactive_model_selection(llm: LlmConfig, profile: str) -> str:
    """
    Интерактивный выбор модели: тестирует модели и спрашивает пользователя.
    Список моделей загружается из переменной окружения OPENROUTER_MODELS (если есть)
    или используется встроенный список по умолчанию.
    """
    env_models_str = os.getenv("OPENROUTER_MODELS", "")
    env_models = [m.strip() for m in env_models_str.split(",") if m.strip()] if env_models_str else []

    default_models = [
        "openrouter/free",
        "cohere/north-mini-code:free",
        "google/gemma-4-26b-a4b-it:free",
        "google/gemma-4-31b-it:free",
        "nvidia/nemotron-3-nano-30b-a3b:free",
        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
        "nvidia/nemotron-3-ultra-550b-a55b:free",
        "nvidia/nemotron-3.5-content-safety:free",
        "nvidia/nemotron-nano-12b-v2-vl:free",
        "nvidia/nemotron-nano-9b-v2:free",
        "openai/gpt-oss-20b:free",
        "poolside/laguna-m.1:free",
        "poolside/laguna-xs-2.1:free",
        "tencent/hy3:free",
        "openrouter/auto",
        "openrouter/auto-beta",
    ]

    models_to_try = env_models if env_models else default_models

    if llm.model != "auto" and llm.model not in models_to_try:
        models_to_try.insert(0, llm.model)

    seen = set()
    unique_models = []
    for model in models_to_try:
        if model not in seen:
            seen.add(model)
            unique_models.append(model)

    print("\n" + "="*70)
    print("ИНТЕРАКТИВНЫЙ ВЫБОР МОДЕЛИ")
    print("="*70)
    print(f"Всего моделей для тестирования: {len(unique_models)}")

    for idx, model in enumerate(unique_models, 1):
        print(f"\n[{idx}/{len(unique_models)}] Тестируем модель: {model}")
        print("-" * 50)

        print("  Генерация тестового письма...")
        success, response_text = test_model_with_sample_letter(llm, model, profile)

        if not success:
            print(f"  Модель не работает: {response_text}")
            continue

        print("  Модель сгенерировала ответ:")
        print("-" * 50)
        print(response_text)
        print("-" * 50)

        while True:
            user_input = input(f"\n  Устраивает ли вас эта модель? (Y/N): ").strip().upper()
            if user_input in ['Y', 'N', 'ДА', 'НЕТ']:
                break
            print("  Введите Y (Да) или N (Нет)")

        if user_input in ['Y', 'ДА']:
            print(f"\n  Модель {model} выбрана!")
            return model
        else:
            print(f"  Пропускаем модель {model}, пробуем следующую...")

    print("\n  Все модели отклонены. Используем openrouter/free.")
    return "openrouter/free"


class HtmlTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)

    def text(self) -> str:
        return normalize_space(" ".join(self.parts))


@dataclass(frozen=True)
class Vacancy:
    id: str
    title: str
    employer: str
    url: str
    apply_url: str
    description: str
    has_test: bool
    response_letter_required: bool
    query: str
    schedule_id: str
    schedule_name: str


@dataclass(frozen=True)
class LlmConfig:
    provider: str
    model: str
    api_key: str
    base_url: str | None = None


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_letter_text(value: str) -> str:
    replacements = {
        "ё": "е",
        "Ё": "Е",
        "—": "-",
        "–": "-",
        "−": "-",
        "‑": "-",
    }
    for source, replacement in replacements.items():
        value = value.replace(source, replacement)
    return normalize_space(value)


def clean_letter_response(text: str) -> str:
    """
    Очищает ответ от лишних пояснений и проверяет наличие русского языка.
    Если после очистки нет русских букв – возвращает пустую строку.
    """
    if not text:
        return ""

    if not re.search(r'[А-Яа-я]', text):
        return ""

    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r'^(We need|The user|Let\'s|I need|Here is|I will|We\'ll|Okay,|So,|First,|Now,|Sure,|Alright,|The candidate|The company|The vacancy)', stripped, re.IGNORECASE):
            continue
        cleaned_lines.append(stripped)

    if not cleaned_lines:
        return ""

    result = ' '.join(cleaned_lines).strip()
    if not re.search(r'[А-Яа-я]', result):
        return ""

    return result


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config must contain a YAML object: {path}")
    return data


def get_nested(config: dict[str, Any], path: str, default: Any) -> Any:
    current: Any = config
    for key in path.split("."):
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def hh_user_agent() -> str:
    return os.getenv("HH_USER_AGENT") or DEFAULT_USER_AGENT


def strip_html(value: str) -> str:
    parser = HtmlTextExtractor()
    parser.feed(html.unescape(value or ""))
    return parser.text()


def build_title_query(query: str, title_only: bool) -> str:
    return query.strip()


def vacancy_rules(config: dict[str, Any]) -> dict[str, Any]:
    return get_nested(config, "vacancies", {})


def vacancy_keywords(config: dict[str, Any]) -> list[str]:
    rules = vacancy_rules(config)
    if "keywords" in rules:
        return [str(value).strip() for value in rules.get("keywords") or [] if str(value).strip()]
    search_config = get_nested(config, "search", {})
    return [str(value).strip() for value in search_config.get("queries") or [] if str(value).strip()]


def vacancy_stop_words(config: dict[str, Any]) -> list[str]:
    rules = vacancy_rules(config)
    if "stop_words" in rules:
        return [str(value).strip() for value in rules.get("stop_words") or [] if str(value).strip()]
    filters = get_nested(config, "filters", {})
    return [str(value).strip() for value in filters.get("exclude_title_keywords") or [] if str(value).strip()]


def required_title_words_any(config: dict[str, Any]) -> list[str]:
    rules = vacancy_rules(config)
    return [str(value).strip() for value in rules.get("required_title_words_any") or [] if str(value).strip()]


def remote_only_enabled(config: dict[str, Any]) -> bool:
    rules = vacancy_rules(config)
    return bool(rules.get("remote_only", False))


def skip_already_applied_enabled(config: dict[str, Any]) -> bool:
    rules = vacancy_rules(config)
    return bool(rules.get("skip_already_applied", True))


def page_has_existing_response(page: Page) -> bool:
    response_markers = [
        "text=Вы откликнулись",
        "text=Отклик отправлен",
        "text=Резюме доставлено",
        "text=Вы уже откликнулись",
        "text=Ваш отклик отправлен",
        "text=Отклик успешно отправлен",
    ]
    for marker in response_markers:
        try:
            if page.locator(marker).count() > 0:
                return True
        except Exception:
            continue
    return False


def keyword_match(value: str, keywords: list[str]) -> str | None:
    low_value = value.lower()
    for keyword in keywords:
        if keyword and keyword.lower() in low_value:
            return keyword
    return None


def vacancy_passes_filters(
    config: dict[str, Any],
    title: str,
    employer: str,
    description: str,
    schedule_id: str,
    has_test: bool,
) -> bool:
    filters = get_nested(config, "filters", {})
    if remote_only_enabled(config) and schedule_id != "remote":
        return False
    if required_title_words_any(config) and keyword_match(title, required_title_words_any(config)) is None:
        return False
    if keyword_match(title, vacancy_stop_words(config)):
        return False
    if keyword_match(employer, filters.get("exclude_company_keywords") or []):
        return False
    if keyword_match(description, filters.get("exclude_description_keywords") or []):
        return False
    if bool(filters.get("skip_has_test", True)) and has_test:
        return False
    return True


def search_vacancies_browser(
    page: Page,
    config: dict[str, Any],
    conn: sqlite3.Connection | None = None,
) -> list[Vacancy]:
    search_config = get_nested(config, "search", {})
    queries = vacancy_keywords(config)
    if not queries:
        raise ValueError("Config vacancies.keywords is empty")

    results: list[Vacancy] = []
    seen_ids: set[str] = set()
    title_only = bool(search_config.get("title_only", True))
    max_pages = int(search_config.get("max_pages", 1))
    per_page = int(search_config.get("per_page", 20))

    for query in queries:
        for page_num in range(max_pages):
            params = {
                "text": query,
                "area": search_config.get("area", 113),
                "items_on_page": per_page,
                "page": page_num,
            }
            if title_only:
                params["search_field"] = "name"
            if remote_only_enabled(config):
                params["schedule"] = "remote"

            url = "https://hh.ru/search/vacancy?" + urllib.parse.urlencode(params)
            try:
                page.goto(url, wait_until="commit", timeout=90_000)
                page.wait_for_load_state("domcontentloaded", timeout=20_000)
            except PlaywrightTimeoutError:
                print(f"Browser search page load timeout, trying to parse current page: {url}")
            page.wait_for_timeout(2000)

            if "captcha" in page.title().lower() or page.locator("text=Капча").count() > 0:
                raise RuntimeError("hh.ru captcha appeared during browser search")

            cards = page.locator("[data-qa='vacancy-serp__vacancy']").all()
            if not cards:
                cards = page.locator("[data-qa='serp-item']").all()

            candidates: list[tuple[str, str, str, str]] = []
            for card in cards:
                try:
                    title_el = card.locator("[data-qa='serp-item__title']").first
                    if title_el.count() == 0:
                        continue
                    title = normalize_space(title_el.inner_text())
                    vacancy_url = str(title_el.get_attribute("href") or "")
                    vacancy_id = extract_vacancy_id(vacancy_url)
                    if not vacancy_id or vacancy_id in seen_ids:
                        continue
                    seen_ids.add(vacancy_id)

                    employer_el = card.locator("[data-qa='vacancy-serp__vacancy-employer']").first
                    employer = normalize_space(employer_el.inner_text()) if employer_el.count() > 0 else "Компания"
                    candidates.append((vacancy_id, title, employer, vacancy_url))
                except Exception:
                    continue

            for vacancy_id, title, employer, vacancy_url in candidates:
                description, already_responded = get_vacancy_description_browser(page, vacancy_url)
                if already_responded:
                    print(f"Skipping already responded vacancy: {title}")
                    if conn is not None:
                        record_result(
                            conn,
                            Vacancy(
                                id=vacancy_id,
                                title=title,
                                employer=employer or "Компания",
                                url=vacancy_url,
                                apply_url=vacancy_url,
                                description=description,
                                has_test=False,
                                response_letter_required=False,
                                query=query,
                                schedule_id="remote" if remote_only_enabled(config) else "",
                                schedule_name="Удаленная работа" if remote_only_enabled(config) else "",
                            ),
                            "skipped",
                            "Already responded on hh.ru",
                            "",
                        )
                    continue
                schedule_id = "remote" if remote_only_enabled(config) else ""
                schedule_name = "Удаленная работа" if remote_only_enabled(config) else ""
                if not vacancy_passes_filters(
                    config,
                    title=title,
                    employer=employer,
                    description=description,
                    schedule_id=schedule_id,
                    has_test=False,
                ):
                    continue
                results.append(
                    Vacancy(
                        id=vacancy_id,
                        title=title,
                        employer=employer or "Компания",
                        url=vacancy_url,
                        apply_url=vacancy_url,
                        description=description,
                        has_test=False,
                        response_letter_required=False,
                        query=query,
                        schedule_id=schedule_id,
                        schedule_name=schedule_name,
                    )
                )

    return results


def extract_vacancy_id(url: str) -> str:
    match = re.search(r"/vacancy/(\d+)", url)
    if match:
        return match.group(1)
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query)
    for key in ("vacancyId", "vacancy_id", "id"):
        if query.get(key):
            return str(query[key][0])
    return ""


def get_vacancy_description_browser(page: Page, url: str) -> tuple[str, bool]:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_timeout(1000)
        already_responded = page_has_existing_response(page)
        page.wait_for_selector("[data-qa='vacancy-description']", timeout=10_000)
        desc_el = page.locator("[data-qa='vacancy-description']").first
        description = normalize_space(desc_el.inner_text()) if desc_el.count() > 0 else ""
        return description, already_responded
    except Exception:
        return "", False


def init_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS vacancy_runs (
            vacancy_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            reason TEXT,
            title TEXT NOT NULL,
            employer TEXT NOT NULL,
            url TEXT NOT NULL,
            query TEXT NOT NULL,
            letter TEXT,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def already_processed(conn: sqlite3.Connection, vacancy_id: str, include_dry_run: bool) -> bool:
    statuses = ["success", "skipped"]
    if include_dry_run:
        statuses.append("dry_run")
    placeholders = ",".join("?" for _ in statuses)
    row = conn.execute(
        f"SELECT 1 FROM vacancy_runs WHERE vacancy_id = ? AND status IN ({placeholders})",
        (vacancy_id, *statuses),
    ).fetchone()
    return row is not None


def record_result(
    conn: sqlite3.Connection,
    vacancy: Vacancy,
    status: str,
    reason: str,
    letter: str,
) -> None:
    conn.execute(
        """
        INSERT INTO vacancy_runs (
            vacancy_id, status, reason, title, employer, url, query, letter, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(vacancy_id) DO UPDATE SET
            status = excluded.status,
            reason = excluded.reason,
            title = excluded.title,
            employer = excluded.employer,
            url = excluded.url,
            query = excluded.query,
            letter = excluded.letter,
            updated_at = excluded.updated_at
        """,
        (
            vacancy.id,
            status,
            reason,
            vacancy.title,
            vacancy.employer,
            vacancy.url,
            vacancy.query,
            letter,
            dt.datetime.now(dt.timezone.utc).isoformat(),
        ),
    )
    conn.commit()


def read_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("Install pypdf or create my/profile.md with your profile text") from exc

    reader = PdfReader(str(path))
    chunks: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            chunks.append(text)
    return normalize_space("\n".join(chunks))


def load_profile() -> str:
    """Загружает профиль из my/profile.md или PDF."""
    print("📂 Загрузка профиля...")
    profile_md = MY_DIR / "profile.md"
    if profile_md.exists():
        content = profile_md.read_text(encoding="utf-8").strip()
        print(f"   ✅ Профиль загружен из my/profile.md ({len(content)} символов)")
        return content

    pdf_paths = sorted(MY_DIR.glob("*.pdf"))
    if not pdf_paths:
        raise RuntimeError("No profile found. Add my/profile.md or a readable PDF resume to my/")
    print(f"   📄 Найдено PDF: {', '.join(p.name for p in pdf_paths)}")
    chunks: list[str] = []
    for path in pdf_paths:
        text = read_pdf_text(path)
        if text:
            chunks.append(f"Источник: {path.name}\n{text}")
            print(f"   📄 Извлечено из {path.name}: {len(text)} символов")

    profile = "\n\n".join(chunks).strip()
    if not profile:
        raise RuntimeError("No profile found. Add my/profile.md or a readable PDF resume to my/")
    print(f"   ✅ Итоговый профиль: {len(profile)} символов")
    return profile


def load_cover_letter_prompt_template(config: dict[str, Any]) -> str:
    letter_config = get_nested(config, "letter", {})
    prompt_path = Path(letter_config.get("prompt_path") or DEFAULT_COVER_LETTER_PROMPT_PATH)
    if not prompt_path.is_absolute():
        prompt_path = ROOT_DIR / prompt_path
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8").strip()
    return default_cover_letter_prompt_template()


def default_cover_letter_prompt_template() -> str:
    return """
Ты пишешь сопроводительные письма для hh.ru от лица кандидата.

Главная цель: письмо должно выглядеть как короткое осмысленное сообщение живого senior/lead-разработчика, а не как универсальный шаблон.

Стиль:
- русский язык;
- спокойно, уверенно, профессионально;
- без восторга, продажности, канцелярита и HR-штампов;
- без фраз "меня заинтересовала вакансия", "буду рад", "рассмотрите мою кандидатуру", "внести вклад", "с большим интересом";
- без восклицательных знаков;
- не пересказывай резюме целиком.

Логика письма:
1. Начни с короткого приветствия.
2. Сразу назови 1-2 точки совпадения между вакансией и опытом кандидата.
3. Добавь конкретный релевантный опыт или результат из профиля.
4. Заверши спокойным предложением обсудить задачи команды.
""".strip()


def build_cover_letter_prompt(
    profile: str,
    vacancy: Vacancy,
    config: dict[str, Any],
) -> tuple[str, str, int]:
    letter_config = get_nested(config, "letter", {})
    max_chars = int(letter_config.get("max_chars", 1200))
    portfolio_url = str(letter_config.get("portfolio_url") or "").strip()
    extra_instructions = str(letter_config.get("extra_instructions") or "").strip()

    system = f"{load_cover_letter_prompt_template(config)}\n\n{HR_ADAPTATION_RULES}".strip()

    user = (
        "Профиль кандидата:\n"
        f"{profile[:6000]}\n\n"
        "Вакансия:\n"
        f"Название: {vacancy.title}\n"
        f"Компания: {vacancy.employer}\n"
        f"Описание: {vacancy.description[:4000]}\n\n"
        "Требования к письму:\n"
        "- 3-5 предложений.\n"
        f"- Максимум {max_chars} символов.\n"
        "- Не начинай с 'Меня заинтересовала вакансия'.\n"
        "- Не пиши общими словами 'имею большой опыт', если можно назвать стек, домен или задачу.\n"
        "- Упомяни только 1-2 наиболее релевантных факта из профиля.\n"
        "- Если нечего сопоставить, напиши нейтрально и не притягивай опыт.\n\n"
        "Верни только текст письма, без заголовков и пояснений.\n"
    )

    if portfolio_url:
        user += f"- Можно аккуратно добавить ссылку на портфолио: {portfolio_url}\n"
    if extra_instructions:
        user += f"\nДополнительные инструкции:\n{extra_instructions}\n"

    return system, user, max_chars


def load_llm_config() -> LlmConfig:
    provider = (os.getenv("LLM_PROVIDER") or "openai").strip().lower()
    if provider == "none":
        return LlmConfig(provider=provider, model="none", api_key="")
    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY") or ""
        model = os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
        return LlmConfig(provider=provider, model=model, api_key=api_key)
    elif provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY") or ""
        model = os.getenv("ANTHROPIC_MODEL") or "claude-sonnet-4-6"
        return LlmConfig(provider=provider, model=model, api_key=api_key)
    elif provider == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY") or ""
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY is missing for LLM_PROVIDER=openrouter")

        model = os.getenv("OPENROUTER_MODEL")
        base_url = "https://openrouter.ai/api/v1"

        if not model or model == "auto":
            print("Будет запущен интерактивный выбор модели")
            return LlmConfig(provider=provider, model="auto", api_key=api_key, base_url=base_url)
        else:
            print(f"Используем модель: {model}")
            if test_openrouter_model(api_key, model):
                print("Модель работает")
            else:
                print(f"Модель {model} не отвечает, будет запущен интерактивный выбор...")
                return LlmConfig(provider=provider, model="auto", api_key=api_key, base_url=base_url)

        return LlmConfig(provider=provider, model=model, api_key=api_key, base_url=base_url)
    else:
        raise RuntimeError(f"LLM_PROVIDER must be 'openai', 'anthropic', 'openrouter', or 'none'. Got: {provider}")


def generate_cover_letter(
    llm: LlmConfig,
    profile: str,
    vacancy: Vacancy,
    config: dict[str, Any],
) -> str:
    if llm.provider == "none":
        return normalize_letter_text(generate_fallback_letter(vacancy))

    system, user, max_chars = build_cover_letter_prompt(profile, vacancy, config)

    if llm.provider == "openai":
        letter = generate_openai_letter(llm, system, user)
    elif llm.provider == "anthropic":
        letter = generate_anthropic_letter(llm, system, user)
    elif llm.provider == "openrouter":
        letter = generate_openrouter_letter(llm, system, user, vacancy)
    else:
        raise RuntimeError(f"Unsupported LLM provider: {llm.provider}")

    if not letter or not re.search(r'[А-Яа-я]', letter):
        print("Warning: generated letter contains no Russian or is empty, using fallback.")
        letter = generate_fallback_letter(vacancy)

    return normalize_letter_text(letter)[:max_chars].strip()


def generate_fallback_letter(vacancy: Vacancy) -> str:
    title_lower = vacancy.title.lower()
    desc_lower = vacancy.description.lower() if vacancy.description else ""

    combined_text = f"{title_lower} {desc_lower}"

    keywords_map = {
        "management": {
            "words": ["руковод", "lead", "manager", "директор", "начальник", "управлен", "team leader", "head of", "cio", "cto"],
            "phrases": [
                "Руководил командами до 45+ сотрудников, включая системных администраторов, разработчиков и специалистов по информационной безопасности,",
                "проводил оптимизацию персонала. В 2026 закончил ВШЭ по направлению Бизнес-аналитика. Занимаюсь разработкой ПО с открытым кодом.",
                "Осуществлял бюджетирование, проведение тендеров (44-ФЗ, 223-ФЗ) и финансовое прогнозирование.",
                "Обеспечил сокращение издержек за счет внедрения AI, технологий Искусственного Интеллекта на 15-23%.",
                "Разрабатывал стратегию развития IT-отделов и оптимизировал затраты на как на оборудование, так и на ФОТ от 25 до 80%."
            ]
        },
        "infrastructure": {
            "words": ["инфраструктур", "сервер", "сеть", "администр", "виртуализац", "vmware", "hyper-v", "схд", "цод", "backup", "восстановлен"],
            "phrases": [
                "Управлял IT-инфраструктурой: виртуализация (VMware, Hyper-V), СХД, резервное копирование, администрирование сетевого оборудования Cisco, HP, Fortinet.",
                "Осуществлял перевод и сопровождение всех IT/ИБ сервисов в ЦОД iXcellerate.",
                "Внедрял системы мониторинга (SolarWinds, Zabbix) и управления инцидентами."
            ]
        },
        "security": {
            "words": ["безопасн", "security", "защит", "фз-152", "152-фз", "iso 27001", "dlp", "антивирус", "угроз", "уязвим", "пентест"],
            "phrases": [
                "Обеспечивал соответствие требованиям 152-ФЗ и международным стандартам ISO/IEC 27001:2022, ISO 9001:2015, ISO 45001:2018.",
                "Внедрял и администрировал системы информационной безопасности: KES, KUMA, Acunetix, PT NAD, McAfee, WatchGuard.",
                "Имею сертификат внутреннего аудитора по стандартам ISO и опыт проведения аудитов."
            ]
        },
        "automation": {
            "words": ["автоматизац", "бизнес-процесс", "1с", "crm", "битрикс", "мегаплан", "sap", "erp", "workflow", "интеграц"],
            "phrases": [
                "Реализовал полный цикл автоматизации бизнес-процессов (воронка продаж, закупки, договоры, Help Desk, логистика) на базе 1С, CRM Битрикс24 и Мегаплан.",
                "Внедрял интеграции с внешними провайдерами: телефония UIS, Почта, Диадок.",
                "Имею опыт внедрения SAP (модули FI, CO, MM, SD) и управления проектами по автоматизации."
            ]
        },
        "support": {
            "words": ["поддержк", "help desk", "service desk", "пользовател", "заявк", "sla", "инцидент"],
            "phrases": [
                "Организовал и контролировал работу службы поддержки 24/7, сократил время обработки заявок с 48 до 8 часов.",
                "Внедрял системы Service Desk (SysAid, SharePoint), управлял SLA и проводил обучение пользователей.",
                "Обеспечивал 1-ю и 2-ю линии поддержки для приложений 1С и SAP."
            ]
        }
    }

    selected_phrases = []
    for category, data in keywords_map.items():
        if any(keyword in combined_text for keyword in data["words"]):
            selected_phrases.extend(data["phrases"])

    if not selected_phrases:
        selected_phrases = [
            "Имею 18-летний опыт управления IT-инфраструктурой, информационной безопасностью и автоматизацией бизнес-процессов.",
            "Руководил командами до 45+ сотрудников, проводил бюджетирование и тендеры, сокращение издержек.",
            "Внедрял стандарты ISO 27001, ISO 9001 и обеспечивал соответствие 152-ФЗ.",
            "В 2026 закончил ВШЭ по направлению Бизнес-аналитика. Занимаюсь разработкой ПО с открытым кодом."
        ]

    max_phrases = 5
    if len(selected_phrases) > max_phrases:
        selected_phrases = selected_phrases[:max_phrases]

    greeting = "Здравствуйте."
    intro = f"Вижу неплохое совпадение вашей вакансии {vacancy.title} с моим профессиональным опытом:"

    body = " ".join(selected_phrases)

    closing = "Готов, в любое удобное Вам время, обсудить взаимовыгодное сотрудничество."

    full_letter = f"{greeting} {intro} {body} {closing}"
    full_letter = re.sub(r"\s+", " ", full_letter).strip()

    return full_letter


def generate_openai_letter(llm: LlmConfig, system: str, user: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=llm.api_key)
    response = client.chat.completions.create(
        model=llm.model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.7,
        max_tokens=450,
    )
    return (response.choices[0].message.content or "").strip()


def generate_anthropic_letter(llm: LlmConfig, system: str, user: str) -> str:
    from anthropic import Anthropic

    client = Anthropic(api_key=llm.api_key)
    response = client.messages.create(
        model=llm.model,
        system=system,
        messages=[{"role": "user", "content": user}],
        max_tokens=450,
        temperature=0.7,
    )
    chunks: list[str] = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            chunks.append(getattr(block, "text", ""))
    return "".join(chunks).strip()


def generate_openrouter_letter(llm: LlmConfig, system: str, user: str, vacancy: Vacancy) -> str:
    from openai import OpenAI

    client = OpenAI(
        api_key=llm.api_key,
        base_url=llm.base_url or "https://openrouter.ai/api/v1",
    )
    try:
        response = client.chat.completions.create(
            model=llm.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.7,
            max_tokens=600,
            extra_headers={
                "HTTP-Referer": "https://github.com/vanuska/HH.ru-Job-Search-Apply-with-AI",
                "X-Title": "HH.ru-Job-Search-Apply-with-AI",
            },
        )
        raw_text = (response.choices[0].message.content or "").strip()
        print(f"Raw letter length: {len(raw_text)}")
        cleaned = clean_letter_response(raw_text)
        if cleaned:
            return cleaned
        else:
            print("Warning: cleaned letter is empty, using raw text or fallback")
            if raw_text and re.search(r'[А-Яа-я]', raw_text):
                return raw_text[:1200]
            else:
                return generate_fallback_letter(vacancy)
    except Exception as e:
        print(f"OpenRouter generation error: {e}")
        return generate_fallback_letter(vacancy)


def locator_context_text(locator) -> str:
    try:
        return normalize_space(
            locator.evaluate(
                """element => {
                    let node = element;
                    const parts = [];
                    for (let i = 0; i < 5 && node; i += 1) {
                        if (node.innerText) parts.push(node.innerText);
                        node = node.parentElement;
                    }
                    return parts.join(' ');
                }"""
            )
        )
    except Exception:
        return ""


def locator_value(locator) -> str:
    try:
        value = locator.input_value(timeout=500)
        return value or ""
    except Exception:
        return ""


def visible_textareas(page: Page):
    result = []
    textareas = page.locator("textarea")
    for index in range(textareas.count()):
        textarea = textareas.nth(index)
        try:
            if textarea.is_visible(timeout=500):
                result.append(textarea)
        except Exception:
            continue
    return result


def find_cover_letter_textarea(page: Page):
    textareas = visible_textareas(page)
    for textarea in textareas:
        context = locator_context_text(textarea).lower()
        try:
            placeholder = (textarea.get_attribute("placeholder") or "").lower()
        except Exception:
            placeholder = ""
        combined = f"{context} {placeholder}"
        if "сопровод" in combined or "письм" in combined:
            return textarea
    if len(textareas) == 1:
        context = locator_context_text(textareas[0]).lower()
        if not any(word in context for word in ("город", "зарплат", "зп", "ожидания", "доход")):
            return textareas[0]
    return None


def load_application_questions(config: dict[str, Any]) -> list[dict[str, Any]]:
    questions_file_path = config.get("application_questions_file")
    if questions_file_path:
        path = Path(questions_file_path)
        if not path.is_absolute():
            path = ROOT_DIR / path
    else:
        path = DEFAULT_APPLICATION_QUESTIONS_FILE

    if path.exists():
        try:
            import yaml
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "answers" in data:
                return data["answers"]
            else:
                print(f"Неверный формат файла {path}, используется стандартный список.")
                return DEFAULT_APPLICATION_ANSWERS
        except Exception as e:
            print(f"Ошибка загрузки файла вопросов {path}: {e}")
            return DEFAULT_APPLICATION_ANSWERS
    else:
        try:
            import yaml
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                yaml.dump(DEFAULT_APPLICATION_ANSWERS, f, allow_unicode=True, default_flow_style=False)
            print(f"Создан файл вопросов: {path}")
        except Exception as e:
            print(f"Не удалось создать файл вопросов: {e}")
        return DEFAULT_APPLICATION_ANSWERS


def configured_question_answers(config: dict[str, Any]) -> list[dict[str, Any]]:
    return load_application_questions(config)


def answer_for_question(question_text: str, config: dict[str, Any]) -> str:
    normalized = question_text.lower()
    for item in configured_question_answers(config):
        keywords = [str(keyword).lower() for keyword in item.get("keywords") or []]
        if keywords and any(keyword in normalized for keyword in keywords):
            return str(item.get("answer") or "").strip()
    return ""


def get_question_text_from_field(field) -> str:
    try:
        parent = field.locator("xpath=ancestor::*[@data-qa='task-body']").first
        if parent.count() > 0:
            question_el = parent.locator("[data-qa='task-question']").first
            if question_el.count() > 0:
                return normalize_space(question_el.inner_text())
        question_el = field.locator("xpath=ancestor::*[@data-qa='task-question']").first
        if question_el.count() > 0:
            return normalize_space(question_el.inner_text())
    except Exception:
        pass
    return ""


def generate_answers_for_questions(
    llm: LlmConfig,
    questions: list[str],
    vacancy: Vacancy,
    profile: str,
    config: dict[str, Any],
) -> dict[str, str]:
    if not questions:
        return {}

    system_prompt = """
Ты — помощник кандидата на hh.ru. Твоя задача — дать краткие, конкретные и правдивые ответы на вопросы работодателя, используя только информацию из профиля кандидата.

Правила:
- Отвечай строго на русском языке.
- Каждый ответ — одно предложение или короткая фраза (не более 200 символов).
- Не выдумывай факты, не добавляй информацию, которой нет в профиле.
- Если в профиле нет ответа на вопрос, напиши просто "Не указано".
- Не используй общие фразы, такие как "имею опыт", если можно указать конкретные цифры или факты.
- Ответы должны быть полезными для работодателя, но без лишних деталей.
"""
    user_prompt = f"""
Профиль кандидата:
{profile[:4000]}

Вакансия:
Название: {vacancy.title}
Компания: {vacancy.employer}
Описание: {vacancy.description[:2000]}

Вопросы работодателя (ответь на каждый):
{chr(10).join(f"{i+1}. {q}" for i, q in enumerate(questions))}

Формат ответа (только ответы, без пояснений):
1. ответ
2. ответ
...
"""

    try:
        if llm.provider == "openrouter":
            from openai import OpenAI
            client = OpenAI(
                api_key=llm.api_key,
                base_url=llm.base_url or "https://openrouter.ai/api/v1",
                timeout=30.0,
                default_headers={
                    "HTTP-Referer": "https://github.com/vanuska/HH.ru-Job-Search-Apply-with-AI",
                    "X-Title": "HH.ru-Job-Search-Apply-with-AI",
                }
            )
            response = client.chat.completions.create(
                model=llm.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=len(questions) * 200,
            )
            raw = response.choices[0].message.content or ""
        elif llm.provider == "openai":
            from openai import OpenAI
            client = OpenAI(api_key=llm.api_key)
            response = client.chat.completions.create(
                model=llm.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=len(questions) * 200,
            )
            raw = response.choices[0].message.content or ""
        elif llm.provider == "anthropic":
            from anthropic import Anthropic
            client = Anthropic(api_key=llm.api_key)
            response = client.messages.create(
                model=llm.model,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                max_tokens=len(questions) * 200,
                temperature=0.3,
            )
            raw = "".join(block.text for block in response.content if hasattr(block, "text"))
        else:
            return {}

        lines = raw.strip().splitlines()
        results = {}
        current_question = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
            match = re.match(r'^(\d+)\.\s*(.*)', line)
            if match:
                idx = int(match.group(1))
                if 1 <= idx <= len(questions):
                    answer = match.group(2).strip()
                    if answer:
                        results[questions[idx-1]] = answer
            else:
                if current_question and current_question not in results:
                    results[current_question] = line
        if len(results) < len(questions):
            remaining = [q for q in questions if q not in results]
            for q in remaining:
                pattern = re.escape(q) + r'\s*[:–-]?\s*(.*?)(?=\n\s*\d+\.|$)'
                match = re.search(pattern, raw, re.DOTALL | re.IGNORECASE)
                if match:
                    ans = match.group(1).strip()
                    if ans and len(ans) < 300:
                        results[q] = ans
        return results

    except Exception as e:
        print(f"Ошибка при генерации AI-ответов на вопросы: {e}")
        return {}


def fill_application_questions(
    page: Page,
    config: dict[str, Any],
    llm: LlmConfig | None = None,
    vacancy: Vacancy | None = None,
    profile: str | None = None,
) -> list[str]:
    filled: list[str] = []
    fields = []

    for selector in ["textarea", "input[type='text']", "input:not([type])"]:
        locators = page.locator(selector)
        for index in range(locators.count()):
            field = locators.nth(index)
            try:
                if field.is_visible(timeout=500) and field.is_enabled(timeout=500):
                    fields.append(field)
            except Exception:
                continue

    static_answers = {}
    ai_questions = []
    field_map = {}

    for field in fields:
        if locator_value(field).strip():
            continue

        question_text = get_question_text_from_field(field)
        if not question_text:
            question_text = locator_context_text(field)

        if not question_text:
            continue

        answer = answer_for_question(question_text, config)
        if answer:
            field.fill(answer)
            filled.append(f"стат: {question_text[:50]}... -> {answer[:50]}...")
        else:
            ai_questions.append(question_text)
            field_map[question_text] = field

    ai_config = get_nested(config, "application_questions", {})
    use_ai = bool(ai_config.get("use_ai_fallback", False))
    max_ai = int(ai_config.get("max_ai_questions_per_run", 5))

    if use_ai and ai_questions and llm and vacancy and profile:
        if len(ai_questions) <= max_ai:
            print(f"Генерация AI-ответов для {len(ai_questions)} вопросов...")
            ai_answers = generate_answers_for_questions(llm, ai_questions, vacancy, profile, config)
            for question, answer in ai_answers.items():
                if answer and question in field_map:
                    field = field_map[question]
                    try:
                        field.fill(answer)
                        filled.append(f"AI: {question[:50]}... -> {answer[:50]}...")
                    except Exception:
                        pass
        else:
            print(f"Слишком много вопросов для AI ({len(ai_questions)}), превышает лимит {max_ai}. Оставлены пустыми.")

    return filled


def click_first(page: Page, selectors: list[str], timeout_ms: int = 1500) -> bool:
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            if locator.count() > 0 and locator.is_visible(timeout=timeout_ms):
                locator.click()
                return True
        except Exception:
            continue
    return False


def click_first_enabled_button(page: Page, button_texts: list[str], timeout_ms: int = 1500) -> bool:
    for text in button_texts:
        buttons = page.locator(f"button:has-text('{text}')")
        try:
            count = buttons.count()
        except Exception:
            continue
        for index in range(count - 1, -1, -1):
            button = buttons.nth(index)
            try:
                if button.is_visible(timeout=timeout_ms) and button.is_enabled(timeout=timeout_ms):
                    button.click()
                    return True
            except Exception:
                continue
    return False


def save_apply_debug(page: Page, vacancy_id: str) -> str:
    debug_dir = ROOT_DIR / "data" / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    base = debug_dir / f"apply-{vacancy_id}-{stamp}"
    try:
        page.screenshot(path=str(base.with_suffix(".png")), full_page=True)
    except Exception:
        pass
    try:
        base.with_suffix(".html").write_text(page.content(), encoding="utf-8")
    except Exception:
        pass
    return str(base)


def apply_to_vacancy(
    page: Page,
    vacancy: Vacancy,
    letter: str,
    config: dict[str, Any],
    llm: LlmConfig | None = None,
    profile: str | None = None,
) -> tuple[str, str]:
    if not letter or not re.search(r'[А-Яа-я]', letter):
        print("Letter is empty or has no Russian, generating fallback in apply_to_vacancy...")
        letter = generate_fallback_letter(vacancy)
        if not letter or not re.search(r'[А-Яа-я]', letter):
            return "error", "No valid letter generated"

    target_url = vacancy.url or vacancy.apply_url
    if not target_url:
        return "error", "No apply URL"

    page.goto(target_url, wait_until="domcontentloaded", timeout=30_000)
    page.wait_for_timeout(1500)

    if page_has_existing_response(page):
        return "skipped", "Already responded"

    clicked_initial = click_first(
        page,
        [
            "[data-qa='vacancy-response-link-top']",
            "[data-qa='vacancy-response-link-bottom']",
            "a:has-text('Откликнуться')",
            "button:has-text('Откликнуться')",
        ],
        timeout_ms=3000,
    )
    if not clicked_initial:
        return "error", "Initial response button not found"

    page.wait_for_timeout(2500)
    if page_has_existing_response(page):
        return "success", "Response sent"

    cover_letter_area = find_cover_letter_textarea(page)
    if cover_letter_area is None:
        click_first(
            page,
            [
                "a:has-text('Написать сопроводительное')",
                "button:has-text('Написать сопроводительное')",
                "a:has-text('Добавить сопроводительное')",
                "button:has-text('Добавить сопроводительное')",
                "button:has-text('С сопроводительным')",
                "text=С сопроводительным",
                "[data-qa='vacancy-response-actions-dropdown']",
            ],
        )
        page.wait_for_timeout(1500)
        cover_letter_area = find_cover_letter_textarea(page)

    if cover_letter_area is not None:
        cover_letter_area.fill(letter)
        page.wait_for_timeout(500)

    filled_questions = fill_application_questions(page, config, llm, vacancy, profile)
    for filled in filled_questions:
        print(f"Filled application question: {filled}")

    submit_attempts = 0
    while submit_attempts < 3:
        clicked = click_first(
            page,
            [
                "button[data-qa='vacancy-response-submit-popup']",
                "button[data-qa='vacancy-response-submit']",
                "button:has-text('Отправить')",
                "button:has-text('Отправить отклик')",
                "button[type='submit']",
            ],
            timeout_ms=2500,
        )
        if not clicked:
            clicked = click_first_enabled_button(page, ["Откликнуться", "Отправить"], timeout_ms=2500)
        if not clicked:
            submit_attempts += 1
            time.sleep(1)
            continue

        for _ in range(15):
            page.wait_for_timeout(1000)
            if page_has_existing_response(page):
                return "success", "Response sent"
        submit_attempts += 1
        print(f"Submit clicked but no confirmation yet, attempt {submit_attempts}/3")

    debug_base = save_apply_debug(page, vacancy.id)
    return "error", f"Submit clicked but hh.ru did not confirm response; debug saved: {debug_base}"


def session_file() -> Path:
    n8n_files_dir = os.getenv("N8N_FILES_DIR") or str(Path.home() / ".n8n-files")
    return Path(n8n_files_dir) / "hh_session.json"


def search_vacancies(
    config: dict[str, Any],
    conn: sqlite3.Connection | None = None,
    headless: bool = False,
) -> list[Vacancy]:
    state_path = session_file()
    if not state_path.exists():
        raise RuntimeError(f"HH session not found: {state_path}. Run python3 hh_login.py")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=250)
        context = browser.new_context(storage_state=str(state_path))
        page = context.new_page()
        try:
            return search_vacancies_browser(page, config, conn)
        finally:
            context.close()
            browser.close()


def seconds_until_next_run(run_times: list[str]) -> int:
    now = dt.datetime.now()
    candidates: list[dt.datetime] = []
    for value in run_times:
        hour, minute = [int(part) for part in value.split(":", 1)]
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            candidate += dt.timedelta(days=1)
        candidates.append(candidate)
    next_run = min(candidates)
    return max(1, int((next_run - now).total_seconds()))


def run_once(config: dict[str, Any], args: argparse.Namespace) -> None:
    print("\n🚀 ЗАПУСК ОДНОКРАТНОГО ПОИСКА И ОТКЛИКОВ")
    print("=" * 60)

    state_db = Path(os.getenv("HH_STATE_DB") or args.state_db or DEFAULT_STATE_DB)
    if not state_db.is_absolute():
        state_db = ROOT_DIR / state_db
    conn = init_db(state_db)

    print("📂 Шаг 1: Загрузка профиля...")
    profile = load_profile()

    print("🤖 Шаг 2: Инициализация LLM...")
    llm = load_llm_config()

    if llm.model == "auto":
        print("🔄 Запуск интерактивного выбора модели...")
        selected_model = interactive_model_selection(llm, profile)
        llm = LlmConfig(
            provider=llm.provider,
            model=selected_model,
            api_key=llm.api_key,
            base_url=llm.base_url
        )
        print(f"✅ Финальная модель: {selected_model}")
    elif llm.provider == "openrouter":
        print(f"🔍 Проверяем модель {llm.model}...")
        if not test_openrouter_model(llm.api_key, llm.model):
            print(f"⚠️ Модель {llm.model} не работает, запускаем интерактивный выбор...")
            selected_model = interactive_model_selection(llm, profile)
            llm = LlmConfig(
                provider=llm.provider,
                model=selected_model,
                api_key=llm.api_key,
                base_url=llm.base_url
            )
            print(f"✅ Финальная модель: {selected_model}")

    print(f"✅ LLM provider: {llm.provider} ({llm.model})")

    print("\n🔍 Шаг 3: Поиск вакансий...")
    print("   (браузер может открыться и закрыться, это нормально)")
    vacancies = search_vacancies(config, conn, headless=bool(args.headless))
    print(f"   ✅ Найдено вакансий: {len(vacancies)}")

    if not vacancies:
        print("⚠️ Нет новых вакансий, подходящих под фильтры.")
        conn.close()
        return

    limits = get_nested(config, "limits", {})
    max_per_run = int(args.max_applications or limits.get("max_applications_per_run", 5))
    delay = int(limits.get("delay_between_applications_seconds", 12))

    print(f"\n📊 Лимит откликов за запуск: {max_per_run}")
    print(f"⏱️ Задержка между откликами: {delay} сек")
    print(f"💾 База данных: {state_db}")
    print(f"🔄 Режим: {'ОТПРАВКА ОТКЛИКОВ' if args.apply else 'СИМУЛЯЦИЯ (DRY-RUN)'}")

    sent_or_planned = 0
    browser_context = None
    playwright = None
    browser = None
    page = None

    applied_details = []

    try:
        if args.apply:
            print("\n🌐 Инициализация браузера для отправки откликов...")
            state_path = session_file()
            if not state_path.exists():
                raise RuntimeError(f"HH session not found: {state_path}. Run python3 hh_login.py")
            playwright = sync_playwright().start()
            browser = playwright.chromium.launch(headless=bool(args.headless), slow_mo=250)
            browser_context = browser.new_context(storage_state=str(state_path))
            page = browser_context.new_page()
            print("   ✅ Браузер запущен")

        for idx, vacancy in enumerate(vacancies, 1):
            if sent_or_planned >= max_per_run:
                print(f"\n⏹️ Достигнут лимит откликов ({max_per_run}), остановка.")
                break
            if skip_already_applied_enabled(config) and already_processed(
                conn,
                vacancy.id,
                include_dry_run=not args.apply,
            ):
                print(f"⏭️ Пропускаем уже обработанную вакансию #{idx}: {vacancy.title}")
                continue

            print(f"\n📌 Обработка вакансии {idx}/{len(vacancies)}")
            print(f"   🏢 {vacancy.employer} — {vacancy.title}")
            print(f"   🔗 {vacancy.url}")

            print("   ✍️ Генерация письма...")
            letter = generate_cover_letter(llm, profile, vacancy, config)
            if not letter or not re.search(r'[А-Яа-я]', letter):
                error_msg = "Letter generation failed (empty or no Russian)"
                print(f"   ❌ Ошибка: {error_msg}")
                record_result(conn, vacancy, "error", error_msg, "")
                continue

            print(f"   📝 Письмо ({len(letter)} символов):")
            print(f"      {letter[:200]}...")

            if args.apply:
                print("   📤 Отправка отклика...")
                assert page is not None
                status, reason = apply_to_vacancy(page, vacancy, letter, config, llm, profile)
                record_result(conn, vacancy, status, reason, letter)
                print(f"   ✅ Результат: {status} ({reason})")
                if status == "success":
                    applied_details.append({
                        "title": vacancy.title,
                        "employer": vacancy.employer,
                        "url": vacancy.url,
                    })
                if status == "error":
                    print(f"   🔍 Отладка сохранена в data/debug/")
                time.sleep(delay)
            else:
                record_result(conn, vacancy, "dry_run", "Generated letter only", letter)
                print("   🔄 Симуляция (dry-run)")

            sent_or_planned += 1

    finally:
        if browser_context is not None:
            browser_context.close()
        if browser is not None:
            browser.close()
        if playwright is not None:
            playwright.stop()
        conn.close()

    total_found = len(vacancies)

    # Подсчёт статистики в зависимости от режима
    if args.apply:
        # Реальный режим: отдельно успешные и ошибки
        applied_count = len(applied_details)
        error_count = sent_or_planned - applied_count  # все неудачные попытки (включая ошибки отправки)
        dry_run_count = 0
    else:
        # Dry-run режим: все обработанные – симуляции
        dry_run_count = sent_or_planned
        applied_count = 0
        error_count = 0

    print("\n" + "=" * 60)
    print("📊 ИТОГИ ЗАПУСКА")
    print("=" * 60)
    print(f"Найдено вакансий:           {total_found}")
    print(f"Обработано:                 {sent_or_planned}")
    if args.apply:
        print(f"Отправлено откликов:       {applied_count}")
        print(f"Ошибок:                    {error_count}")
    else:
        print(f"Симуляций (dry-run):       {dry_run_count}")
    print("=" * 60)

    # Формируем сообщение для Telegram
    if vacancies:
        msg_lines = [
            "✅ <b>Поиск завершён.</b>",
            f"Найдено вакансий: {total_found}",
        ]
        if args.apply:
            msg_lines.append(f"Отправлено откликов: {applied_count}")
            msg_lines.append(f"Ошибок: {error_count}")
        else:
            msg_lines.append(f"Симуляций (dry-run): {dry_run_count}")
        msg_lines.append(f"Лимит: {max_per_run}")
        msg_lines.append(f"Время: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        if applied_details:
            msg_lines.append("")
            msg_lines.append("<b>📋 Список отправленных откликов:</b>")
            max_display = 10
            display_list = applied_details[:max_display]
            for idx, item in enumerate(display_list, 1):
                link = item["url"]
                title = item["title"]
                employer = item["employer"]
                msg_lines.append(f"{idx}. <a href='{link}'>{title}</a> — {employer}")
            if len(applied_details) > max_display:
                msg_lines.append(f"... и ещё {len(applied_details) - max_display} откликов")
        else:
            if args.apply:
                msg_lines.append("")
                msg_lines.append("⚠️ Откликов не отправлено (все попытки завершились ошибкой).")
            else:
                msg_lines.append("")
                msg_lines.append("⚠️ Откликов не отправлено (режим симуляции).")

        full_msg = "\n".join(msg_lines)
        send_telegram_notification(full_msg, parse_mode="HTML")
    else:
        send_telegram_notification("⚠️ Поиск не нашёл новых вакансий.", parse_mode="HTML")


def run_schedule(config: dict[str, Any], args: argparse.Namespace) -> None:
    run_times = get_nested(config, "schedule.run_times", ["09:30", "18:30"])
    if not isinstance(run_times, list) or not run_times:
        raise ValueError("schedule.run_times must be a non-empty list")

    print(f"Scheduler started. Run times: {', '.join(run_times)}")
    while True:
        sleep_for = seconds_until_next_run([str(value) for value in run_times])
        next_at = dt.datetime.now() + dt.timedelta(seconds=sleep_for)
        print(f"Next run at {next_at:%Y-%m-%d %H:%M:%S}")
        time.sleep(sleep_for)
        run_once(config, args)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HH.ru auto apply helper")
    parser.add_argument("--config", default=os.getenv("HH_CONFIG_PATH") or str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--state-db", default=os.getenv("HH_STATE_DB") or str(DEFAULT_STATE_DB))
    parser.add_argument("--once", action="store_true", help="Run one search/apply pass")
    parser.add_argument("--schedule", action="store_true", help="Run forever at schedule.run_times")
    parser.add_argument("--apply", action="store_true", help="Actually send responses. Default is dry-run.")
    parser.add_argument("--headless", action="store_true", help="Run browser headless in --apply mode")
    parser.add_argument("--max-applications", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    # Принудительно устанавливаем UTF-8 для Windows-консоли,
    # чтобы корректно отображались эмодзи и русские буквы.
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except AttributeError:
            # Для старых версий Python (до 3.7)
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    load_dotenv()
    args = parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = ROOT_DIR / config_path
    config = load_yaml(config_path)

    if not args.once and not args.schedule:
        args.once = True

    if args.schedule:
        run_schedule(config, args)
    else:
        run_once(config, args)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
