#!/usr/bin/env python3
"""
Отдельный скрипт для проверки чатов HH.ru и отправки уведомлений в Telegram.
Не конфликтует с auto_apply.py, использует отдельный процесс.
"""

import argparse
import datetime as dt
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright


ROOT_DIR = Path(__file__).resolve().parent
MY_DIR = ROOT_DIR / "my"
DEFAULT_CONFIG_PATH = MY_DIR / "config.yaml"
DEFAULT_STATE_DB = ROOT_DIR / "data" / "hh_auto_apply.sqlite3"


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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_notifications (
            chat_id TEXT PRIMARY KEY,
            sent_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def session_file() -> Path:
    n8n_files_dir = os.getenv("N8N_FILES_DIR") or str(Path.home() / ".n8n-files")
    return Path(n8n_files_dir) / "hh_session.json"


def send_telegram_notification(message: str, parse_mode: str = "HTML") -> None:
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


def get_last_chat_check(conn: sqlite3.Connection) -> dt.datetime | None:
    row = conn.execute("SELECT value FROM chat_state WHERE key='last_chat_check'").fetchone()
    if row:
        try:
            return dt.datetime.fromisoformat(row[0])
        except:
            return None
    return None


def set_last_chat_check(conn: sqlite3.Connection, timestamp: dt.datetime):
    conn.execute(
        "INSERT OR REPLACE INTO chat_state (key, value) VALUES ('last_chat_check', ?)",
        (timestamp.isoformat(),)
    )
    conn.commit()


def check_chat_updates(config: dict[str, Any], conn: sqlite3.Connection | None = None) -> None:
    """Проверяет чат через парсинг страницы /chat и отправляет уведомления в Telegram."""
    state_path = session_file()
    if not state_path.exists():
        print("HH session not found, cannot check chat.")
        return

    close_conn = False
    if conn is None:
        state_db = Path(os.getenv("HH_STATE_DB") or DEFAULT_STATE_DB)
        if not state_db.is_absolute():
            state_db = ROOT_DIR / state_db
        conn = init_db(state_db)
        close_conn = True

    now = dt.datetime.now()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, slow_mo=100)
        context = browser.new_context(storage_state=str(state_path))
        page = context.new_page()

        try:
            print("Opening https://hh.ru/chat ...")
            page.goto("https://hh.ru/chat", wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_timeout(5000)
            
            try:
                page.wait_for_selector("[id^='chat-cell-'], [data-qa='chat-cell'], .chat-cell, [class*='chat-item'], .bloko-gap", timeout=10000)
                print("Элементы чата найдены.")
            except Exception as e:
                print(f"Не удалось дождаться элементов чата: {e}")
                html_content = page.content()
                debug_dir = ROOT_DIR / "data" / "debug"
                debug_dir.mkdir(parents=True, exist_ok=True)
                (debug_dir / "chat_page.html").write_text(html_content, encoding="utf-8")
                page.screenshot(path=debug_dir / "chat_debug.png")
                print(f"HTML и скриншот сохранены в {debug_dir}")
                return

            chat_cells = page.locator("[id^='chat-cell-']").all()
            if not chat_cells:
                print("Не найдено элементов чатов.")
                return

            new_messages = []
            for chat in chat_cells:
                try:
                    # 1. Ищем бейдж непрочитанных
                    badge = chat.locator("span.magritte-badge[data-qa='chatik-info-badges']").first
                    if badge.count() == 0:
                        badge = chat.locator(".magritte-badge, .badge, .bloko-badge, [class*='badge']").first
                    unread_count = 0
                    if badge.count() > 0:
                        try:
                            text = badge.inner_text().strip()
                            if text.isdigit():
                                unread_count = int(text)
                            else:
                                unread_count = 1
                        except:
                            unread_count = 1
                    else:
                        class_attr = chat.get_attribute("class") or ""
                        if "unread" in class_attr:
                            unread_count = 1

                    if unread_count == 0:
                        continue

                    # 2. Название вакансии
                    title_div = chat.locator("[data-qa='chat-cell-title']").first
                    if title_div.count() == 0:
                        title_div = chat.locator("[class*='title-']").first
                    vacancy_title = title_div.inner_text().strip() if title_div.count() > 0 else "Вакансия"

                    # 3. Название компании
                    subtitle_div = chat.locator("[data-qa='chat-cell-subtitle']").first
                    if subtitle_div.count() == 0:
                        subtitle_div = chat.locator("[class*='subtitle-']").first
                    company = subtitle_div.inner_text().strip() if subtitle_div.count() > 0 else "Неизвестная компания"

                    # 4. Превью последнего сообщения
                    preview_div = chat.locator("[class*='last-message-']").first
                    if preview_div.count() == 0:
                        preview_div = chat.locator("[data-qa='last-message']").first
                    if preview_div.count() == 0:
                        preview_div = chat.locator("[class*='message-']").first
                    preview = preview_div.inner_text().strip() if preview_div.count() > 0 else ""

                    # 5. Ссылка на чат
                    link_el = chat.locator("a[href*='/chat/']").first
                    link = link_el.get_attribute("href") if link_el.count() > 0 else ""
                    if link and not link.startswith("http"):
                        link = "https://hh.ru" + link

                    if not link:
                        chat_id = chat.get_attribute("id")
                        if chat_id and chat_id.startswith("chat-cell-"):
                            numeric_id = chat_id.replace("chat-cell-", "")
                            link = f"https://hh.ru/chat/{numeric_id}"

                    if link:
                        chat_id = link.split('/')[-1]
                    else:
                        chat_id = None

                    if not chat_id:
                        print("Не удалось определить chat_id, пропускаем.")
                        continue

                    # Проверяем, было ли уже отправлено уведомление об этом чате за последние 7 дней (10080 минут)
                    row = conn.execute(
                        "SELECT sent_at FROM chat_notifications WHERE chat_id = ? AND sent_at > datetime('now', '-7 days')",
                        (chat_id,)
                    ).fetchone()
                    if row:
                        print(f"Уведомление для чата {chat_id} уже отправлено недавно ({row[0]}), пропускаем.")
                        continue

                    new_messages.append({
                        "chat_id": chat_id,
                        "company": company,
                        "vacancy": vacancy_title,
                        "link": link,
                        "preview": preview[:200],
                        "count": unread_count,
                    })
                except Exception as e:
                    print(f"Ошибка при парсинге чата: {e}")

            if new_messages:
                msg_lines = ["📩 <b>Новые ответы в чате HH.ru:</b>", ""]
                for item in new_messages:
                    msg_lines.append(f"<b>{item['company']}</b> — {item['vacancy']}")
                    if item['link']:
                        msg_lines.append(f"<a href='{item['link']}'>Перейти к диалогу</a>")
                    msg_lines.append(f"Сообщений: {item['count']}")
                    if item['preview']:
                        msg_lines.append(f"Превью: {item['preview'][:100]}...")
                    msg_lines.append("")
                    # Записываем в БД
                    conn.execute(
                        "INSERT OR REPLACE INTO chat_notifications (chat_id, sent_at) VALUES (?, datetime('now'))",
                        (item['chat_id'],)
                    )
                    print(f"Записано уведомление для чата {item['chat_id']} в {dt.datetime.now()}")
                conn.commit()
                full_msg = "\n".join(msg_lines)
                send_telegram_notification(full_msg, parse_mode="HTML")
            else:
                print("Новых сообщений для уведомления нет.")
        except Exception as e:
            print(f"Ошибка при проверке чата: {e}")
            try:
                page.screenshot(path=ROOT_DIR / "data" / "debug" / "chat_debug.png")
                print("Скриншот сохранён в data/debug/chat_debug.png")
            except:
                pass
        finally:
            context.close()
            browser.close()

    # Очищаем старые записи (старше 7 дней)
    conn.execute("DELETE FROM chat_notifications WHERE sent_at < datetime('now', '-7 days')")
    conn.commit()
    set_last_chat_check(conn, now)
    if close_conn:
        conn.close()


def run_chat_schedule(config: dict[str, Any], args: argparse.Namespace) -> None:
    """Запускает периодическую проверку чата по расписанию (время или интервал)."""
    chat_config = get_nested(config, "chat_check", {})
    
    schedule = chat_config.get("schedule")
    interval_minutes = chat_config.get("interval_minutes")
    
    if schedule and isinstance(schedule, list) and len(schedule) > 0:
        run_times = [str(t) for t in schedule]
        print(f"Chat checker started. Run times: {', '.join(run_times)}")
        while True:
            now = dt.datetime.now()
            candidates = []
            for value in run_times:
                hour, minute = [int(part) for part in value.split(":", 1)]
                candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if candidate <= now:
                    candidate += dt.timedelta(days=1)
                candidates.append(candidate)
            next_run = min(candidates)
            sleep_for = max(1, int((next_run - now).total_seconds()))
            next_at = now + dt.timedelta(seconds=sleep_for)
            print(f"Next chat check at {next_at:%Y-%m-%d %H:%M:%S}")
            time.sleep(sleep_for)
            state_db = Path(os.getenv("HH_STATE_DB") or args.state_db or DEFAULT_STATE_DB)
            if not state_db.is_absolute():
                state_db = ROOT_DIR / state_db
            conn = init_db(state_db)
            try:
                check_chat_updates(config, conn)
            finally:
                conn.close()
    elif interval_minutes and isinstance(interval_minutes, (int, float)) and interval_minutes > 0:
        interval_seconds = int(interval_minutes * 60)
        print(f"Chat checker started. Interval: {interval_minutes} minutes.")
        while True:
            next_at = dt.datetime.now() + dt.timedelta(seconds=interval_seconds)
            print(f"Next chat check at {next_at:%Y-%m-%d %H:%M:%S}")
            time.sleep(interval_seconds)
            state_db = Path(os.getenv("HH_STATE_DB") or args.state_db or DEFAULT_STATE_DB)
            if not state_db.is_absolute():
                state_db = ROOT_DIR / state_db
            conn = init_db(state_db)
            try:
                check_chat_updates(config, conn)
            finally:
                conn.close()
    else:
        print("Chat checker started. Default interval: 30 minutes.")
        while True:
            next_at = dt.datetime.now() + dt.timedelta(minutes=30)
            print(f"Next chat check at {next_at:%Y-%m-%d %H:%M:%S}")
            time.sleep(30 * 60)
            state_db = Path(os.getenv("HH_STATE_DB") or args.state_db or DEFAULT_STATE_DB)
            if not state_db.is_absolute():
                state_db = ROOT_DIR / state_db
            conn = init_db(state_db)
            try:
                check_chat_updates(config, conn)
            finally:
                conn.close()


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="HH.ru chat checker")
    parser.add_argument("--config", default=os.getenv("HH_CONFIG_PATH") or str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--state-db", default=os.getenv("HH_STATE_DB") or str(DEFAULT_STATE_DB))
    parser.add_argument("--once", action="store_true", help="Run one chat check pass")
    parser.add_argument("--schedule", action="store_true", help="Run forever at chat_check.schedule or interval")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = ROOT_DIR / config_path
    config = load_yaml(config_path)

    if args.schedule:
        run_chat_schedule(config, args)
    else:
        state_db = Path(os.getenv("HH_STATE_DB") or args.state_db or DEFAULT_STATE_DB)
        if not state_db.is_absolute():
            state_db = ROOT_DIR / state_db
        conn = init_db(state_db)
        try:
            check_chat_updates(config, conn)
        finally:
            conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())