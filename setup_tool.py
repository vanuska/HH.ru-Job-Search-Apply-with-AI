#!/usr/bin/env python3
"""
Инструмент для настройки и управления hh-auto-apply
"""

import os
import sys
import shutil
import subprocess
import platform
import re
import time
import signal
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent
MODULES_DIR = ROOT_DIR / "modules"
EXAMPLES_DIR = ROOT_DIR / "examples"
MY_DIR = ROOT_DIR / "my"
DATA_DIR = ROOT_DIR / "data"

CORE_SCRIPTS = [
    "auto_apply.py",
    "hh_login.py",
    "check_models.py",
    "clean_db.py",
    "test_letter.py",
    "requirements.txt",
]
CONFIG_EXAMPLE = "config.example.yaml"

PID_FILE = DATA_DIR / "auto_apply.pid"
LOG_FILE = DATA_DIR / "auto_apply_schedule.log"


class SetupTool:
    """Инструмент для настройки проекта"""

    def __init__(self):
        self.root_dir = ROOT_DIR
        self.is_linux = platform.system() == "Linux"
        self.has_gui = self._check_gui()
        self._ensure_directories()
        self._copy_missing_files()

    def _check_gui(self):
        """Проверяет наличие графического интерфейса"""
        if not self.is_linux:
            return True
        if os.environ.get("DISPLAY"):
            return True
        try:
            subprocess.run(["xdpyinfo"], capture_output=True, check=True)
            return True
        except:
            return False

    def _ensure_directories(self):
        for d in [MY_DIR, DATA_DIR]:
            d.mkdir(exist_ok=True, parents=True)
            print(f"Проверена/создана директория: {d}")

    def _copy_missing_files(self):
        for fname in CORE_SCRIPTS:
            src = MODULES_DIR / fname
            dst = self.root_dir / fname
            if src.exists() and not dst.exists():
                shutil.copy2(src, dst)
                print(f"Скопирован {fname} из modules в корень")
        src = EXAMPLES_DIR / CONFIG_EXAMPLE
        dst = self.root_dir / CONFIG_EXAMPLE
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)
            print(f"Скопирован {CONFIG_EXAMPLE} из examples в корень")

    def show_menu(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        print("=" * 70)
        print("HH-AUTO-APPLY SETUP TOOL")
        print("=" * 70)
        print()
        print("Доступные шаги:")
        print()
        print("  1. Начальная установка (первый раз)")
        print("  2. Настройка Telegram бота для уведомлений (один раз)")
        print("  3. Авторизация на HH.ru с сохранением сессии (один раз)")
        print("  4. Выбор и настройка LLM (env)")
        print("  5. Выбор доступных LLM")
        print("  6. Импорт резюме для AI Cover Letter")
        print("  7. Настройка промта для AI CL")
        print("  8. Тест генерации AI CL")
        print("  9. Запуск || Поиск работы")
        print(" 10. Работа с базой данных (отклики, ошибки)")
        print(" 11. Выход")
        print()
        print("-" * 70)
        print("Рекомендуется выполнять шаги по порядку")
        print("=" * 70)
        self._check_files_status()
        print(f"\nОС: {'Linux' if self.is_linux else 'Windows/Mac'}")
        print(f"Графический интерфейс: {'Есть' if self.has_gui else 'Отсутствует (сервер)'}")
        if self.is_linux and not self.has_gui:
            print("Будет использован xvfb-run для видимого режима браузера")
        print()

    def _check_files_status(self):
        files_status = [
            (".env", "[ENV]"),
            ("my/profile.md", "[PROF]"),
            ("my/config.yaml", "[CONF]"),
            ("my/cover_letter_prompt.md", "[PROMPT]"),
            ("data/hh_auto_apply.sqlite3", "[DB]"),
        ]
        print("\nСтатус файлов:")
        for path, label in files_status:
            full = self.root_dir / path
            status = "OK" if full.exists() else "MISSING"
            print(f"  {label} {path}: {status}")
        print()

    def run_step(self, step_number: int):
        steps = {
            1: self._step_install_deps,
            2: self._step_setup_telegram,
            3: self._step_hh_login,
            4: self._step_setup_env,
            5: self._step_check_models,
            6: self._step_create_profile,
            7: self._step_setup_prompt,
            8: self._step_test_letter,
            9: self._step_run_apply,
            10: self._step_clean_db,
            11: self._exit,
        }
        if step_number in steps:
            try:
                steps[step_number]()
                input("\nНажмите Enter для продолжения...")
            except Exception as e:
                print(f"\nОшибка при выполнении шага {step_number}: {e}")
                input("\nНажмите Enter для продолжения...")
        else:
            print("Неверный номер шага")
            input("\nНажмите Enter для продолжения...")

    # ---------- ШАГ 1: Начальная установка ----------
    def _step_install_deps(self):
        print("\n" + "=" * 60)
        print("ШАГ 1: НАЧАЛЬНАЯ УСТАНОВКА (ПЕРВЫЙ РАЗ)")
        print("=" * 60)

        if self.is_linux:
            print("\nОбнаружена система Linux. Установка системных зависимостей...")
            self._install_system_deps()

        req_file = self.root_dir / "requirements.txt"
        if not req_file.exists():
            print("Файл requirements.txt не найден в корне. Проверьте modules.")
            return

        print("\nУстановка Python-зависимостей из requirements.txt...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", str(req_file)],
                check=True,
            )
            print("Python-зависимости установлены")
        except subprocess.CalledProcessError as e:
            print(f"Ошибка установки Python-пакетов: {e}")
            return

        print("\nУстановка браузеров Playwright...")
        try:
            subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                check=True,
            )
            print("Playwright браузеры установлены")
        except subprocess.CalledProcessError as e:
            print(f"Ошибка установки Playwright: {e}")

        if self.is_linux:
            print("\nУстановка системных зависимостей для Playwright...")
            try:
                subprocess.run(
                    [sys.executable, "-m", "playwright", "install-deps", "chromium"],
                    check=True,
                )
                print("Системные зависимости Playwright установлены")
            except subprocess.CalledProcessError as e:
                print(f"Ошибка установки зависимостей Playwright: {e}")
                self._install_playwright_deps_manual()

        if self.is_linux and not self.has_gui:
            print("\nОбнаружена система Linux без графического интерфейса.")
            self._ensure_xvfb()

        print("\nНачальная установка завершена!")

    def _install_system_deps(self):
        deps = [
            "libnspr4", "libnss3", "libx11-6", "libx11-xcb1", "libxcb1",
            "libxcomposite1", "libxcursor1", "libxdamage1", "libxext6",
            "libxfixes3", "libxi6", "libxrandr2", "libxrender1", "libxss1",
            "libxtst6", "libgbm1", "libasound2", "libpango-1.0-0", "libcairo2",
            "libatk1.0-0", "libatk-bridge2.0-0", "libgtk-3-0", "libdrm2",
            "libxshmfence1", "fonts-liberation", "libappindicator3-1",
            "libnss3-tools", "xdg-utils",
        ]
        print("Установка системных пакетов (может потребоваться sudo):")
        try:
            subprocess.run(["sudo", "apt", "update"], check=True)
            subprocess.run(
                ["sudo", "apt", "install", "-y"] + deps,
                check=True,
            )
            print("Системные пакеты установлены")
        except subprocess.CalledProcessError as e:
            print(f"Ошибка установки системных пакетов: {e}")

    def _install_playwright_deps_manual(self):
        try:
            subprocess.run(
                ["sudo", "apt", "install", "-y",
                 "libnspr4", "libnss3", "libx11-6", "libx11-xcb1",
                 "libxcb1", "libxcomposite1", "libxcursor1", "libxdamage1",
                 "libxext6", "libxfixes3", "libxi6", "libxrandr2",
                 "libxrender1", "libxss1", "libxtst6", "libgbm1",
                 "libasound2", "libpango-1.0-0", "libcairo2", "libatk1.0-0",
                 "libatk-bridge2.0-0", "libgtk-3-0", "libdrm2", "libxshmfence1"],
                check=True,
            )
            print("Системные зависимости установлены вручную")
        except subprocess.CalledProcessError as e:
            print(f"Ошибка ручной установки: {e}")

    def _ensure_xvfb(self):
        try:
            subprocess.run(["which", "xvfb-run"], capture_output=True, check=True)
            print("xvfb-run уже установлен")
            return
        except:
            pass
        print("Установка xvfb для виртуального дисплея...")
        try:
            subprocess.run(["sudo", "apt", "update"], check=True)
            subprocess.run(["sudo", "apt", "install", "-y", "xvfb"], check=True)
            print("xvfb успешно установлен")
        except subprocess.CalledProcessError as e:
            print(f"Не удалось установить xvfb: {e}")

    # ---------- ШАГ 2: Настройка Telegram бота ----------
    def _step_setup_telegram(self):
        print("\n" + "=" * 60)
        print("ШАГ 2: НАСТРОЙКА TELEGRAM БОТА ДЛЯ УВЕДОМЛЕНИЙ (ОДИН РАЗ)")
        print("=" * 60)

        env_file = self.root_dir / ".env"
        existing_vars = {}
        if env_file.exists():
            content = env_file.read_text(encoding='utf-8')
            for line in content.splitlines():
                if '=' in line and not line.startswith('#'):
                    key, val = line.split('=', 1)
                    existing_vars[key.strip()] = val.strip()

        current_token = existing_vars.get("TELEGRAM_BOT_TOKEN", "")
        current_chat = existing_vars.get("TELEGRAM_CHAT_ID", "")

        if current_token:
            print(f"\nТекущий TELEGRAM_BOT_TOKEN: {current_token}")
        if current_chat:
            print(f"Текущий TELEGRAM_CHAT_ID: {current_chat}")

        token = input("\nВведите токен бота (или Enter, чтобы пропустить): ").strip()
        if token:
            chat_id = input("Введите ваш chat_id: ").strip()
            if chat_id:
                self._update_env_var("TELEGRAM_BOT_TOKEN", token)
                self._update_env_var("TELEGRAM_CHAT_ID", chat_id)
                print("Настройки сохранены.")
                if self._send_test_telegram(token, chat_id):
                    print("Тестовое сообщение успешно отправлено!")
                else:
                    print("Не удалось отправить тестовое сообщение. Проверьте токен и chat_id.")
            else:
                print("Chat_id не введён, настройка отменена.")
        else:
            print("Настройка отменена.")

    def _send_test_telegram(self, token: str, chat_id: str) -> bool:
        """Отправляет тестовое сообщение в Telegram."""
        try:
            import urllib.request
            import json
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = json.dumps({"chat_id": chat_id, "text": "✅ Тестовое сообщение от hh-auto-apply setup tool"})
            req = urllib.request.Request(url, data=data.encode('utf-8'), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status == 200
        except Exception as e:
            print(f"Ошибка отправки: {e}")
            return False

    # ---------- ШАГ 3: Авторизация на HH.ru ----------
    def _step_hh_login(self):
        print("\n" + "=" * 60)
        print("ШАГ 3: АВТОРИЗАЦИЯ НА HH.RU С СОХРАНЕНИЕМ СЕССИИ (ОДИН РАЗ)")
        print("=" * 60)
        self._run_script("hh_login.py")

    # ---------- ШАГ 4: Выбор и настройка LLM (env) ----------
    def _step_setup_env(self):
        print("\n" + "=" * 60)
        print("ШАГ 4: ВЫБОР И НАСТРОЙКА LLM (ENV)")
        print("=" * 60)

        env_file = self.root_dir / ".env"

        # Загружаем существующие переменные, если файл есть
        existing_vars = {}
        if env_file.exists():
            content = env_file.read_text(encoding='utf-8')
            for line in content.splitlines():
                if '=' in line and not line.startswith('#'):
                    key, val = line.split('=', 1)
                    existing_vars[key.strip()] = val.strip()

        print("\nТекущие настройки .env (если есть):")
        for key in ["LLM_PROVIDER", "OPENROUTER_API_KEY", "OPENROUTER_MODEL",
                    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "TELEGRAM_BOT_TOKEN",
                    "TELEGRAM_CHAT_ID"]:
            val = existing_vars.get(key, "(не задано)")
            print(f"  {key}: {val}")

        print("\nБудут сохранены все существующие переменные, обновятся только те, что вы укажете.")
        print("Оставьте поле пустым, чтобы не менять значение.")

        # HH_USER_AGENT закомментирован
        # email = input("\nВведите ваш email для HH_USER_AGENT: ").strip()
        # if not email:
        #     email = "your-email@example.com"
        #     print(f"Используем заглушку: {email}")

        print("\nВыбор LLM провайдера:")
        print("1. OpenRouter (рекомендуется, бесплатные модели)")
        print("2. OpenAI (платные модели)")
        print("3. Anthropic (платные модели)")
        print("4. Пропустить (буду использовать позже)")
        print("5. Использовать текущий провайдер без изменений")

        current_provider = existing_vars.get("LLM_PROVIDER", "")
        default_choice = "5" if current_provider else "1"
        provider_choice = input(f"Выберите (1-5, Enter={default_choice}): ").strip()
        if not provider_choice:
            provider_choice = default_choice

        # Загружаем существующий .env в словарь для обновления
        env_data = existing_vars.copy()

        if provider_choice == "1":
            env_data["LLM_PROVIDER"] = "openrouter"
            api_key = input("Введите ваш OpenRouter API ключ (или Enter для пропуска): ").strip()
            if api_key:
                env_data["OPENROUTER_API_KEY"] = api_key
            elif "OPENROUTER_API_KEY" not in env_data:
                env_data["OPENROUTER_API_KEY"] = "none"

            print("\nВыбор модели OpenRouter:")
            print("1. auto (автоматический выбор, рекомендуется)")
            print("2. openrouter/free (бесплатная)")
            print("3. openai/gpt-4o-mini")
            print("4. anthropic/claude-3.5-sonnet")
            print("5. Своя модель")
            print("6. Оставить текущую")
            model_choice = input("Выберите (1-6): ").strip()
            if model_choice == "1":
                env_data["OPENROUTER_MODEL"] = "auto"
            elif model_choice == "2":
                env_data["OPENROUTER_MODEL"] = "openrouter/free"
            elif model_choice == "3":
                env_data["OPENROUTER_MODEL"] = "openai/gpt-4o-mini"
            elif model_choice == "4":
                env_data["OPENROUTER_MODEL"] = "anthropic/claude-3.5-sonnet"
            elif model_choice == "5":
                custom = input("Введите название модели: ").strip()
                if custom:
                    env_data["OPENROUTER_MODEL"] = custom
            elif model_choice == "6":
                pass  # оставляем как есть
            else:
                env_data["OPENROUTER_MODEL"] = "auto"
            print(f"Выбрана модель: {env_data.get('OPENROUTER_MODEL', 'не указана')}")

        elif provider_choice == "2":
            env_data["LLM_PROVIDER"] = "openai"
            api_key = input("Введите ваш OpenAI API ключ (или Enter для пропуска): ").strip()
            if api_key:
                env_data["OPENAI_API_KEY"] = api_key
            elif "OPENAI_API_KEY" not in env_data:
                env_data["OPENAI_API_KEY"] = "none"
            env_data["OPENAI_MODEL"] = "gpt-4o-mini"

        elif provider_choice == "3":
            env_data["LLM_PROVIDER"] = "anthropic"
            api_key = input("Введите ваш Anthropic API ключ (или Enter для пропуска): ").strip()
            if api_key:
                env_data["ANTHROPIC_API_KEY"] = api_key
            elif "ANTHROPIC_API_KEY" not in env_data:
                env_data["ANTHROPIC_API_KEY"] = "none"
            env_data["ANTHROPIC_MODEL"] = "claude-sonnet-4-6"

        elif provider_choice == "4":
            if "LLM_PROVIDER" not in env_data:
                env_data["LLM_PROVIDER"] = "none"
                env_data["OPENROUTER_API_KEY"] = "none"
                env_data["OPENROUTER_MODEL"] = "none"
            print("Настройка AI-модели пропущена")

        elif provider_choice == "5":
            print("Провайдер оставлен без изменений")

        else:
            print("Неверный выбор. Используем OpenRouter с auto")
            env_data["LLM_PROVIDER"] = "openrouter"
            if "OPENROUTER_API_KEY" not in env_data:
                env_data["OPENROUTER_API_KEY"] = "none"
            env_data["OPENROUTER_MODEL"] = "auto"

        # Пути к файлам — оставляем существующие или добавляем по умолчанию
        if "N8N_FILES_DIR" not in env_data:
            env_data["N8N_FILES_DIR"] = ""
        if "HH_CONFIG_PATH" not in env_data:
            env_data["HH_CONFIG_PATH"] = "my/config.yaml"
        if "HH_STATE_DB" not in env_data:
            env_data["HH_STATE_DB"] = "data/hh_auto_apply.sqlite3"

        # HH_USER_AGENT закомментирован — не добавляем
        # if "HH_USER_AGENT" not in env_data:
        #     env_data["HH_USER_AGENT"] = f"hh-auto-apply/1.0 ({email})"

        # Сохраняем .env с сохранением всех переменных
        try:
            lines = []
            for key, value in env_data.items():
                lines.append(f"{key}={value}")
            env_file.write_text("\n".join(lines), encoding="utf-8")
            print(".env файл обновлён с сохранением всех переменных")
        except Exception as e:
            print(f"Ошибка записи: {e}")

    # ---------- ШАГ 5: Выбор доступных LLM ----------
    def _step_check_models(self):
        print("\n" + "=" * 60)
        print("ШАГ 5: ВЫБОР ДОСТУПНЫХ LLM")
        print("=" * 60)

        load_dotenv()
        provider = os.getenv("LLM_PROVIDER", "").lower()

        # Если провайдер не OpenRouter – выполняем стандартный скрипт
        if provider != "openrouter":
            print("Провайдер не OpenRouter. Запуск стандартной проверки...")
            self._run_script("check_models.py")
            return

        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key or api_key == "none":
            print("OPENROUTER_API_KEY не задан. Запуск стандартной проверки...")
            self._run_script("check_models.py")
            return

        print("Получение списка моделей OpenRouter...")
        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1"
            )
            models_response = client.models.list()
            model_ids = [m.id for m in models_response.data if m.id]
        except Exception as e:
            print(f"Ошибка получения списка моделей OpenRouter: {e}")
            print("Запуск стандартной проверки...")
            self._run_script("check_models.py")
            return

        if not model_ids:
            print("Список моделей пуст. Запуск стандартной проверки...")
            self._run_script("check_models.py")
            return

        # Определение бесплатных моделей
        KNOWN_FREE_MODELS = {
            "openrouter/free",
            "openrouter/auto",
            "openrouter/auto-beta",
            "google/gemini-2.0-flash-exp:free",
            "cohere/north-mini-code:free",
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
            "google/gemma-4-26b-a4b-it:free",
            "google/gemma-4-31b-it:free",
            "meta-llama/llama-3.2-3b-instruct:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "nousresearch/hermes-3-llama-3.1-405b:free",
            "sao10k/l3-lunaris-8b:free",
            "openai/gpt-4o-2024-08-06:free",
            "meta-llama/llama-3.1-70b-instruct:free",
            "meta-llama/llama-3.1-8b-instruct:free",
            "mistralai/mistral-nemo:free",
            "openai/gpt-4o-mini:free",
            "openai/gpt-4o-mini-2024-07-18:free",
            "google/gemma-2-27b-it:free",
        }

        models_info = []
        for model_id in model_ids:
            is_free = (":free" in model_id) or (model_id in KNOWN_FREE_MODELS)
            price_display = "free" if is_free else "платная/неизвестно"
            models_info.append({
                'id': model_id,
                'is_free': is_free,
                'price_display': price_display
            })

        print(f"\nДоступные модели OpenRouter (всего {len(models_info)}):")
        for idx, info in enumerate(models_info, 1):
            print(f"  {idx}. {info['id']} ({info['price_display']})")

        print("\nВы можете сохранить модели в .env для использования в auto_apply.")
        print("Команды:")
        print("  'free'  - сохранить все модели, помеченные как бесплатные")
        print("  'all'   - сохранить все модели (включая платные)")
        print("  номера  - сохранить только выбранные модели (через запятую, например 1,3,5)")
        print("  Enter   - пропустить сохранение")
        choice = input("\nВаш выбор: ").strip()

        if not choice:
            print("Сохранение моделей пропущено.")
            return

        selected_models = []
        if choice.lower() == "free":
            selected_models = [info['id'] for info in models_info if info['is_free']]
            print(f"Выбраны все бесплатные модели ({len(selected_models)} шт.)")
        elif choice.lower() == "all":
            selected_models = [info['id'] for info in models_info]
            print(f"Выбраны все модели ({len(selected_models)} шт.)")
        else:
            parts = [p.strip() for p in choice.split(",") if p.strip()]
            for part in parts:
                try:
                    idx = int(part) - 1
                    if 0 <= idx < len(models_info):
                        selected_models.append(models_info[idx]['id'])
                    else:
                        print(f"Номер {part} вне диапазона, пропускаем.")
                except ValueError:
                    print(f"Некорректный ввод '{part}', пропускаем.")

        if not selected_models:
            print("Не выбрано ни одной модели.")
            return

        # Сохраняем список выбранных моделей
        self._update_env_var("OPENROUTER_MODELS", ",".join(selected_models))

        if len(selected_models) == 1:
            self._update_env_var("OPENROUTER_MODEL", selected_models[0])
            print(f"Установлена модель по умолчанию: {selected_models[0]}")
        else:
            current_model = os.getenv("OPENROUTER_MODEL")
            if current_model and current_model != "auto":
                set_auto = input("Выбрано несколько моделей. Хотите установить OPENROUTER_MODEL='auto' для интерактивного выбора? (Y/N): ").strip().upper()
                if set_auto in ["Y", "ДА"]:
                    self._update_env_var("OPENROUTER_MODEL", "auto")
                    print("OPENROUTER_MODEL установлен в 'auto'.")
                else:
                    print("OPENROUTER_MODEL оставлен без изменений.")
            else:
                self._update_env_var("OPENROUTER_MODEL", "auto")
                print("OPENROUTER_MODEL установлен в 'auto' для интерактивного выбора.")

        print(f"Сохранено {len(selected_models)} моделей в переменную OPENROUTER_MODELS.")
        if len(selected_models) <= 5:
            print("Выбранные модели:", ", ".join(selected_models))
        else:
            print(f"Выбрано {len(selected_models)} моделей.")
        print("Теперь auto_apply может использовать эти модели.")

    # ---------- ШАГ 6: Импорт резюме ----------
    def _step_create_profile(self):
        print("\n" + "=" * 60)
        print("ШАГ 6: ИМПОРТ РЕЗЮМЕ ДЛЯ AI COVER LETTER")
        print("=" * 60)

        profile_file = MY_DIR / "profile.md"

        if profile_file.exists():
            overwrite = input("profile.md уже существует. Перезаписать? (Y/N): ").strip().upper()
            if overwrite not in ["Y", "ДА"]:
                print("Используем существующий profile.md")
                return

        print("\nВыберите способ создания профиля:")
        print("1. Вручную (ввод в консоли)")
        print("2. Извлечь из PDF файла")
        print("3. Извлечь из DOC/DOCX файла")
        print("4. Извлечь из TXT файла")
        print("5. Сгенерировать с помощью LLM (требуется API ключ)")

        choice = input("Выберите способ (1-5): ").strip()

        if choice == "1":
            self._create_manual_profile()
        elif choice == "2":
            self._extract_from_pdf_with_dialog()
        elif choice == "3":
            self._extract_from_docx_with_dialog()
        elif choice == "4":
            self._extract_from_txt_with_dialog()
        elif choice == "5":
            self._generate_with_llm()
        else:
            print("Неверный выбор. Создаём вручную.")
            self._create_manual_profile()

    def _create_manual_profile(self):
        print("\nВведите данные о себе (затем Ctrl+D для сохранения):")
        print("Пример формата:")
        print("# Имя Фамилия")
        print("Email: example@mail.ru")
        print("Telegram: @username")
        print("## Опыт работы")
        print("Компания, должность, период...")
        print("## Ключевые навыки")
        print("- Навык 1")
        print("- Навык 2")
        print("\nНачинайте ввод:")

        lines = []
        try:
            while True:
                line = input()
                lines.append(line)
        except EOFError:
            pass

        if lines and any(l.strip() for l in lines):
            content = "\n".join(lines)
            (MY_DIR / "profile.md").write_text(content, encoding="utf-8")
            print(f"Профиль сохранён в my/profile.md ({len(content)} символов)")
        else:
            print("Пустой ввод, профиль не создан")

    def _extract_from_pdf_with_dialog(self):
        print("\n" + "=" * 60)
        print("ИЗВЛЕЧЕНИЕ ИЗ PDF")
        print("=" * 60)

        pdf_files = list(MY_DIR.glob("*.pdf"))

        print("\nОткуда взять PDF файл?")
        print("1. Из папки my/ (уже скопированы)")
        print("2. Указать путь к файлу вручную")
        print("3. Скопировать из домашней папки")

        source_choice = input("Выберите (1-3): ").strip()
        pdf_path = None

        if source_choice == "1":
            if not pdf_files:
                print("В папке my/ нет PDF файлов.")
                print("Скопируйте PDF в папку my/ и попробуйте снова")
                return

            print("\nНайденные PDF файлы:")
            for i, f in enumerate(pdf_files, 1):
                size = f.stat().st_size / 1024
                print(f"  {i}. {f.name} ({size:.1f} КБ)")

            choice = input("Выберите номер файла (или Enter для первого): ").strip()

            try:
                if choice:
                    idx = int(choice) - 1
                    pdf_path = pdf_files[idx] if 0 <= idx < len(pdf_files) else pdf_files[0]
                else:
                    pdf_path = pdf_files[0]
            except (ValueError, IndexError):
                pdf_path = pdf_files[0]

        elif source_choice == "2":
            file_path = input("Введите полный путь к PDF файлу: ").strip()
            if not file_path:
                print("Путь не указан")
                return

            pdf_path = Path(file_path)
            if not pdf_path.exists():
                print(f"Файл не найден: {pdf_path}")
                return

            import shutil
            dest = MY_DIR / pdf_path.name
            shutil.copy2(pdf_path, dest)
            print(f"Файл скопирован в {dest}")
            pdf_path = dest

        elif source_choice == "3":
            home = Path.home()
            print(f"\nПоиск PDF в домашней папке: {home}")

            home_pdfs = list(home.glob("*.pdf"))

            if not home_pdfs:
                print("PDF файлы не найдены в домашней папке")
                return

            print("\nНайденные PDF в домашней папке:")
            for i, f in enumerate(home_pdfs[:10], 1):
                size = f.stat().st_size / 1024
                print(f"  {i}. {f.name} ({size:.1f} КБ)")

            if len(home_pdfs) > 10:
                print(f"  ... и еще {len(home_pdfs) - 10} файлов")

            choice = input("Выберите номер файла: ").strip()

            try:
                idx = int(choice) - 1
                pdf_path = home_pdfs[idx] if 0 <= idx < len(home_pdfs) else None
                if not pdf_path:
                    print("Неверный выбор")
                    return
            except ValueError:
                print("Неверный ввод")
                return

            import shutil
            dest = MY_DIR / pdf_path.name
            shutil.copy2(pdf_path, dest)
            print(f"Файл скопирован в {dest}")
            pdf_path = dest

        else:
            print("Неверный выбор")
            return

        if pdf_path and pdf_path.exists():
            self._extract_pdf_text(pdf_path)

    def _extract_pdf_text(self, pdf_path: Path):
        try:
            from pypdf import PdfReader
        except ImportError:
            print("pypdf не установлен. Установите: pip install pypdf")
            return

        print(f"\nИзвлечение текста из: {pdf_path.name}")

        try:
            reader = PdfReader(str(pdf_path))
            text_parts = []

            for page_num, page in enumerate(reader.pages, 1):
                text = page.extract_text() or ""
                if text.strip():
                    text_parts.append(f"--- Страница {page_num} ---\n{text}")
                    print(f"  Страница {page_num}: {len(text)} символов")

            if not text_parts:
                print("Не удалось извлечь текст из PDF")
                return

            content = "\n\n".join(text_parts)

            profile_file = MY_DIR / "profile.md"
            profile_file.write_text(content, encoding="utf-8")

            print(f"\nПрофиль создан из {pdf_path.name}")
            print(f"Размер: {len(content)} символов")
            print(f"Сохранен: {profile_file}")

        except Exception as e:
            print(f"Ошибка при извлечении из PDF: {e}")

    def _extract_from_docx_with_dialog(self):
        print("\n" + "=" * 60)
        print("ИЗВЛЕЧЕНИЕ ИЗ DOC/DOCX")
        print("=" * 60)

        doc_files = list(MY_DIR.glob("*.docx")) + list(MY_DIR.glob("*.doc"))

        print("\nОткуда взять DOC/DOCX файл?")
        print("1. Из папки my/ (уже скопированы)")
        print("2. Указать путь к файлу вручную")
        print("3. Скопировать из домашней папки")

        source_choice = input("Выберите (1-3): ").strip()
        doc_path = None

        if source_choice == "1":
            if not doc_files:
                print("В папке my/ нет DOC/DOCX файлов")
                return

            print("\nНайденные DOC/DOCX файлы:")
            for i, f in enumerate(doc_files, 1):
                size = f.stat().st_size / 1024
                print(f"  {i}. {f.name} ({size:.1f} КБ)")

            choice = input("Выберите номер файла (или Enter для первого): ").strip()

            try:
                if choice:
                    idx = int(choice) - 1
                    doc_path = doc_files[idx] if 0 <= idx < len(doc_files) else doc_files[0]
                else:
                    doc_path = doc_files[0]
            except (ValueError, IndexError):
                doc_path = doc_files[0]

        elif source_choice == "2":
            file_path = input("Введите полный путь к DOC/DOCX файлу: ").strip()
            if not file_path:
                print("Путь не указан")
                return

            doc_path = Path(file_path)
            if not doc_path.exists():
                print(f"Файл не найден: {doc_path}")
                return

            import shutil
            dest = MY_DIR / doc_path.name
            shutil.copy2(doc_path, dest)
            print(f"Файл скопирован в {dest}")
            doc_path = dest

        elif source_choice == "3":
            home = Path.home()
            print(f"\nПоиск DOC/DOCX в домашней папке: {home}")

            home_docs = list(home.glob("*.docx")) + list(home.glob("*.doc"))

            if not home_docs:
                print("DOC/DOCX файлы не найдены в домашней папке")
                return

            print("\nНайденные DOC/DOCX в домашней папке:")
            for i, f in enumerate(home_docs[:10], 1):
                size = f.stat().st_size / 1024
                print(f"  {i}. {f.name} ({size:.1f} КБ)")

            choice = input("Выберите номер файла: ").strip()

            try:
                idx = int(choice) - 1
                doc_path = home_docs[idx] if 0 <= idx < len(home_docs) else None
                if not doc_path:
                    print("Неверный выбор")
                    return
            except ValueError:
                print("Неверный ввод")
                return

            import shutil
            dest = MY_DIR / doc_path.name
            shutil.copy2(doc_path, dest)
            print(f"Файл скопирован в {dest}")
            doc_path = dest

        else:
            print("Неверный выбор")
            return

        if doc_path and doc_path.exists():
            self._extract_docx_text(doc_path)

    def _extract_docx_text(self, doc_path: Path):
        if doc_path.suffix.lower() == '.doc':
            print(f"\nФайл {doc_path.name} имеет старый формат .doc")
            print("Рекомендации:")
            print("  1. Откройте файл в Microsoft Word и сохраните как .docx")
            print("  2. Или сохраните как .txt и используйте способ 4")
            return

        try:
            import docx
        except ImportError:
            print("python-docx не установлен. Установите: pip install python-docx")
            return

        print(f"\nИзвлечение текста из: {doc_path.name}")

        try:
            doc = docx.Document(str(doc_path))
            text_parts = [p.text for p in doc.paragraphs if p.text.strip()]

            if not text_parts:
                print("Не удалось извлечь текст (пустой результат)")
                return

            content = "\n\n".join(text_parts)

            profile_file = MY_DIR / "profile.md"
            profile_file.write_text(content, encoding="utf-8")

            print(f"\nПрофиль создан из {doc_path.name}")
            print(f"Размер: {len(content)} символов")
            print(f"Сохранен: {profile_file}")

        except Exception as e:
            print(f"Не удалось открыть файл: {e}")

    def _extract_from_txt_with_dialog(self):
        print("\n" + "=" * 60)
        print("ИЗВЛЕЧЕНИЕ ИЗ TXT")
        print("=" * 60)

        txt_files = list(MY_DIR.glob("*.txt"))

        print("\nОткуда взять TXT файл?")
        print("1. Из папки my/ (уже скопированы)")
        print("2. Указать путь к файлу вручную")
        print("3. Скопировать из домашней папки")

        source_choice = input("Выберите (1-3): ").strip()
        txt_path = None

        if source_choice == "1":
            if not txt_files:
                print("В папке my/ нет TXT файлов")
                return

            print("\nНайденные TXT файлы:")
            for i, f in enumerate(txt_files, 1):
                size = f.stat().st_size / 1024
                print(f"  {i}. {f.name} ({size:.1f} КБ)")

            choice = input("Выберите номер файла (или Enter для первого): ").strip()

            try:
                if choice:
                    idx = int(choice) - 1
                    txt_path = txt_files[idx] if 0 <= idx < len(txt_files) else txt_files[0]
                else:
                    txt_path = txt_files[0]
            except (ValueError, IndexError):
                txt_path = txt_files[0]

        elif source_choice == "2":
            file_path = input("Введите полный путь к TXT файлу: ").strip()
            if not file_path:
                print("Путь не указан")
                return

            txt_path = Path(file_path)
            if not txt_path.exists():
                print(f"Файл не найден: {txt_path}")
                return

            import shutil
            dest = MY_DIR / txt_path.name
            shutil.copy2(txt_path, dest)
            print(f"Файл скопирован в {dest}")
            txt_path = dest

        elif source_choice == "3":
            home = Path.home()
            print(f"\nПоиск TXT в домашней папке: {home}")

            home_txts = list(home.glob("*.txt"))

            if not home_txts:
                print("TXT файлы не найдены в домашней папке")
                return

            print("\nНайденные TXT в домашней папке:")
            for i, f in enumerate(home_txts[:10], 1):
                size = f.stat().st_size / 1024
                print(f"  {i}. {f.name} ({size:.1f} КБ)")

            choice = input("Выберите номер файла: ").strip()

            try:
                idx = int(choice) - 1
                txt_path = home_txts[idx] if 0 <= idx < len(home_txts) else None
                if not txt_path:
                    print("Неверный выбор")
                    return
            except ValueError:
                print("Неверный ввод")
                return

            import shutil
            dest = MY_DIR / txt_path.name
            shutil.copy2(txt_path, dest)
            print(f"Файл скопирован в {dest}")
            txt_path = dest

        else:
            print("Неверный выбор")
            return

        if txt_path and txt_path.exists():
            try:
                content = txt_path.read_text(encoding="utf-8", errors="ignore")

                if content.strip():
                    profile_file = MY_DIR / "profile.md"
                    profile_file.write_text(content, encoding="utf-8")

                    print(f"\nПрофиль создан из {txt_path.name}")
                    print(f"Размер: {len(content)} символов")
                    print(f"Сохранен: {profile_file}")
                else:
                    print("Файл пуст")

            except Exception as e:
                print(f"Ошибка при чтении файла: {e}")

    def _generate_with_llm(self):
        print("\n" + "=" * 60)
        print("ГЕНЕРАЦИЯ ПРОФИЛЯ С ПОМОЩЬЮ LLM")
        print("=" * 60)

        try:
            from dotenv import load_dotenv
            load_dotenv()
            provider = os.getenv("LLM_PROVIDER", "openrouter")
            model = os.getenv("OPENROUTER_MODEL", "openrouter/free")
            if model == "auto":
                model = "openrouter/free"
            print(f"Провайдер: {provider}")
            print(f"Модель: {model}")
            print()
        except:
            pass

        print("Введите информацию о себе в формате:")
        print("- Имя и контактные данные")
        print("- Ключевые навыки")
        print("- Опыт работы (компании, должности, обязанности)")
        print("- Образование")
        print("- Сертификаты")
        print("(Затем нажмите Ctrl+D для завершения ввода)")

        lines = []
        try:
            while True:
                line = input()
                lines.append(line)
        except EOFError:
            pass

        if not lines or not any(line.strip() for line in lines):
            print("Данные не введены")
            return

        raw_data = "\n".join(lines)

        try:
            from dotenv import load_dotenv
            load_dotenv()

            provider = os.getenv("LLM_PROVIDER", "openrouter")

            if provider == "openrouter":
                formatted = self._format_with_openrouter(raw_data)
            elif provider == "openai":
                formatted = self._format_with_openai(raw_data)
            elif provider == "anthropic":
                formatted = self._format_with_anthropic(raw_data)
            else:
                print(f"Неизвестный провайдер: {provider}")
                formatted = raw_data

            if formatted:
                (MY_DIR / "profile.md").write_text(formatted, encoding="utf-8")
                print("\nПрофиль сгенерирован с помощью LLM")
                print(f"Размер: {len(formatted)} символов")
            else:
                print("Используем сырые данные")
                (MY_DIR / "profile.md").write_text(raw_data, encoding="utf-8")

        except Exception as e:
            print(f"Ошибка при генерации профиля: {e}")
            print("Сохраняем сырые данные")
            (MY_DIR / "profile.md").write_text(raw_data, encoding="utf-8")

    def _format_with_openrouter(self, raw_data: str) -> str:
        try:
            from openai import OpenAI
            import os

            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key or api_key == "none":
                print("OPENROUTER_API_KEY не найден или равен none")
                print("Пожалуйста, укажите API ключ в файле .env")
                return ""

            model = os.getenv("OPENROUTER_MODEL", "openrouter/free")
            if model == "auto":
                model = "openrouter/free"
                print(f"Используем модель по умолчанию: {model}")
            else:
                print(f"Используем модель из .env: {model}")

            client = OpenAI(
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1"
            )

            prompt = f"""
Преобразуй следующие данные в структурированный профиль для hh.ru.
Используй формат markdown с разделами:
# Имя
Email, Telegram, LinkedIn, Телефон

## Желаемая роль
...

## Ключевые навыки
...

## Опыт работы
...

## Образование
...

Данные:
{raw_data}
"""

            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
                temperature=0.3
            )

            return response.choices[0].message.content or ""

        except Exception as e:
            print(f"Ошибка OpenRouter: {e}")
            return ""

    def _format_with_openai(self, raw_data: str) -> str:
        print("Функция временно не реализована")
        return ""

    def _format_with_anthropic(self, raw_data: str) -> str:
        print("Функция временно не реализована")
        return ""

    # ---------- ШАГ 7: Настройка промта ----------
    def _step_setup_prompt(self):
        print("\n" + "=" * 60)
        print("ШАГ 7: НАСТРОЙКА ПРОМТА ДЛЯ AI CL")
        print("=" * 60)
        prompt_file = MY_DIR / "cover_letter_prompt.md"
        if prompt_file.exists():
            overwrite = input("Файл уже существует. Перезаписать? (Y/N): ").strip().upper()
            if overwrite not in ["Y", "ДА"]:
                print("Используем существующий")
                return
        template = """# ВАЖНО: ОТВЕЧАЙ ТОЛЬКО НА РУССКОМ ЯЗЫКЕ
# ВЕРНИ ТОЛЬКО ГОТОВОЕ ПИСЬМО, 3-5 ПРЕДЛОЖЕНИЙ

Ты пишешь сопроводительные письма для hh.ru от лица кандидата.

Стиль: профессионально, спокойно, без штампов.
Без фраз "меня заинтересовала", "буду рад", "рассмотрите".
Без восклицательных знаков.

Логика письма:
1. Приветствие
2. 1-2 точки совпадения с вакансией
3. Конкретный опыт из профиля
4. Предложение обсудить задачи

Не пересказывай резюме целиком.
Не используй названия прошлых компаний.
"""
        prompt_file.write_text(template, encoding="utf-8")
        print("cover_letter_prompt.md создан")

    # ---------- ШАГ 8: Тест генерации AI CL ----------
    def _step_test_letter(self):
        print("\n" + "=" * 60)
        print("ШАГ 8: ТЕСТ ГЕНЕРАЦИИ AI CL")
        print("=" * 60)
        self._run_script("test_letter.py")

    # ---------- ШАГ 9: Запуск поиска работы ----------
    def _step_run_apply(self):
        print("\n" + "=" * 60)
        print("ШАГ 9: ЗАПУСК || ПОИСК РАБОТЫ")
        print("=" * 60)

        if self._is_schedule_running():
            print("\nОбнаружен запущенный процесс auto_apply.py (PID из файла).")
            choice = input("Остановить его и запустить новый? (Y/N): ").strip().upper()
            if choice in ["Y", "ДА"]:
                self._stop_schedule_process()
                if PID_FILE.exists():
                    PID_FILE.unlink()
                print("Процесс остановлен.")
            else:
                print("Продолжаем с существующим процессом.")
                input("Нажмите Enter для возврата в меню...")
                return

        config_file = MY_DIR / "config.yaml"
        if config_file.exists():
            try:
                import yaml
                with open(config_file, 'r', encoding='utf-8') as f:
                    cfg = yaml.safe_load(f) or {}
                current_limit = cfg.get("limits", {}).get("max_applications_per_run", 5)
                raw_schedule = cfg.get("schedule", {}).get("run_times", ["09:30", "18:30"])
                current_schedule = [str(t) for t in raw_schedule]
            except Exception as e:
                print(f"Ошибка чтения конфига: {e}")
                current_limit = 5
                current_schedule = ["09:30", "18:30"]
        else:
            current_limit = 5
            current_schedule = ["09:30", "18:30"]

        print("\nТекущие настройки:")
        print(f"  - Лимит откликов за запуск: {current_limit}")
        schedule_str = ", ".join(current_schedule)
        print(f"  - Расписание: {schedule_str}")

        print("\nХотите изменить параметры перед запуском?")
        change = input("Изменить лимит и расписание? (Y/N, Enter=N): ").strip().upper()
        updated = False
        if change in ["Y", "ДА"]:
            new_limit = input(f"Количество откликов за запуск (Enter для {current_limit}): ").strip()
            if new_limit:
                try:
                    new_limit_int = int(new_limit)
                    import yaml
                    with open(config_file, 'r', encoding='utf-8') as f:
                        cfg = yaml.safe_load(f) or {}
                    if "limits" not in cfg:
                        cfg["limits"] = {}
                    cfg["limits"]["max_applications_per_run"] = new_limit_int
                    self._save_yaml_preserve_format(config_file, cfg)
                    current_limit = new_limit_int
                    updated = True
                    print(f"Лимит обновлён: {current_limit}")
                except ValueError:
                    print("Неверное число, лимит не изменён")
            else:
                print("Лимит оставлен без изменений")

            new_schedule = input(f"Новое расписание (через запятую, Enter для {schedule_str}): ").strip()
            if new_schedule:
                new_times = [str(t.strip()) for t in new_schedule.split(",") if t.strip()]
                if new_times:
                    import yaml
                    with open(config_file, 'r', encoding='utf-8') as f:
                        cfg = yaml.safe_load(f) or {}
                    if "schedule" not in cfg:
                        cfg["schedule"] = {}
                    cfg["schedule"]["run_times"] = new_times
                    self._save_yaml_preserve_format(config_file, cfg)
                    current_schedule = new_times
                    updated = True
                    print(f"Расписание обновлено: {', '.join(current_schedule)}")
                else:
                    print("Пустое расписание, оставлено текущее")
            else:
                print("Расписание оставлено без изменений")

        if not updated:
            print("Параметры не изменены")

        print("\nВыберите режим запуска:")
        print("1. Dry-run (только поиск и генерация, без отправки)")
        print("2. Prod-run (отклики, браузер видимый)")
        print("3. Prod-run (отклики, браузер в фоне)")
        print("4. Prod-run (расписание, отклики, браузер видимый)")
        print("5. Prod-run (расписание, отклики, браузер в фоне)")
        print("-" * 50)
        print(f"Текущий лимит: {current_limit}")
        print(f"Текущее расписание: {', '.join(current_schedule)}")
        print()

        mode = input("Выберите режим (1-5): ").strip()

        # Работа с моделью
        env_path = self.root_dir / ".env"
        current_model = None
        if env_path.exists():
            content = env_path.read_text(encoding='utf-8')
            match = re.search(r'^OPENROUTER_MODEL=(.*)$', content, re.MULTILINE)
            if match:
                current_model = match.group(1).strip()

        is_schedule = mode in ["4", "5"]

        if is_schedule:
            print("\nДля запуска по расписанию необходимо выбрать модель, которая будет использоваться постоянно.")
            print("Сейчас будет выполнена проверка доступных моделей через OpenRouter.")
            print("После проверки вы сможете выбрать модель, и она будет записана в .env.")

            env_content = env_path.read_text(encoding='utf-8') if env_path.exists() else ""
            api_key_match = re.search(r'^OPENROUTER_API_KEY=(.*)$', env_content, re.MULTILINE)
            api_key = api_key_match.group(1).strip() if api_key_match else None
            if not api_key or api_key == "none":
                print("\nОШИБКА: в .env не указан OPENROUTER_API_KEY или он равен 'none'.")
                print("Пожалуйста, сначала укажите API ключ в .env (например, через шаг 4).")
                input("Нажмите Enter для продолжения...")
                return

            print("\nЗапуск check_models.py для отображения доступных моделей...")
            self._run_script("check_models.py")
            print("\nТеперь выберите модель, которую хотите использовать для расписания.")
            print("Введите название модели (например, openrouter/free, openai/gpt-4o-mini, anthropic/claude-3.5-sonnet и т.д.)")
            print("Если оставить пустым, будет использована openrouter/free.")
            chosen_model = input("Название модели: ").strip()
            if not chosen_model:
                chosen_model = "openrouter/free"
                print(f"Выбрана модель по умолчанию: {chosen_model}")

            self._update_env_var("OPENROUTER_MODEL", chosen_model)
            print(f"Модель {chosen_model} записана в .env как OPENROUTER_MODEL.")
            extra_env = {"HH_AUTO_APPLY_NON_INTERACTIVE": "1"}
        else:
            if current_model and current_model not in ["auto", "none"]:
                print(f"\nВНИМАНИЕ: в .env указана конкретная модель: {current_model}")
                print("Для режимов без расписания (1-3) рекомендуется использовать 'auto'")
                print("(тогда при каждом запуске будет предлагаться интерактивный выбор модели).")
                switch = input("Хотите переключить на 'auto'? (Y/N, Enter=N): ").strip().upper()
                if switch in ["Y", "ДА"]:
                    self._update_env_var("OPENROUTER_MODEL", "auto")
                    print("Модель переключена на auto.")
                else:
                    print(f"Оставлена модель {current_model}.")
            extra_env = {}

        # Формирование аргументов
        args = []
        use_xvfb = False

        if mode == "1":
            args = ["--once"]
            print("\nЗапуск в режиме DRY-RUN (без отправки)")
        elif mode == "2":
            args = ["--once", "--apply"]
            print("\nЗапуск PROD-RUN (отклики, браузер видимый)")
        elif mode == "3":
            args = ["--once", "--apply", "--headless"]
            print("\nЗапуск PROD-RUN (отклики, браузер в фоне)")
        elif mode == "4":
            args = ["--schedule", "--apply"]
            print("\nЗапуск ПО РАСПИСАНИЮ (отклики, браузер видимый)")
        elif mode == "5":
            args = ["--schedule", "--apply", "--headless"]
            print("\nЗапуск ПО РАСПИСАНИЮ (отклики, браузер в фоне)")
        else:
            print("Неверный выбор. Запуск в dry-run режиме.")
            args = ["--once"]

        # Настройка xvfb
        if self.is_linux and not self.has_gui:
            if mode in ["2", "4"]:
                xvfb_choice = input("Использовать xvfb-run? (Y/N, Enter=Y): ").strip().upper()
                if xvfb_choice != "N":
                    use_xvfb = True
                    if "--headless" in args:
                        args.remove("--headless")
                    print("Будет использован xvfb-run")
                else:
                    if "--headless" not in args:
                        args.append("--headless")
                    print("Добавлен флаг --headless (браузер будет невидимым)")

        # Передаём также Telegram-переменные, если они заданы
        if env_path.exists():
            env_content = env_path.read_text(encoding='utf-8')
            tg_token = re.search(r'^TELEGRAM_BOT_TOKEN=(.*)$', env_content, re.MULTILINE)
            tg_chat = re.search(r'^TELEGRAM_CHAT_ID=(.*)$', env_content, re.MULTILINE)
            if tg_token and tg_token.group(1).strip() and tg_chat and tg_chat.group(1).strip():
                extra_env["TELEGRAM_BOT_TOKEN"] = tg_token.group(1).strip()
                extra_env["TELEGRAM_CHAT_ID"] = tg_chat.group(1).strip()

        # Запуск
        if is_schedule:
            background = input("Запустить процесс в фоновом режиме? (Y/N, Enter=Y): ").strip().upper()
            if background != "N":
                self._run_script_detached("auto_apply.py", args, use_xvfb=use_xvfb, extra_env=extra_env)
                print("\nПроцесс auto_apply.py запущен в фоновом режиме.")
                print(f"Лог-файл: {LOG_FILE}")
                print(f"PID сохранён в {PID_FILE}. Для остановки процесса удалите этот файл или выполните kill <PID>.")
                input("Нажмите Enter для возврата в меню...")
                return
            else:
                self._run_script("auto_apply.py", args, use_xvfb=use_xvfb, extra_env=extra_env)
        else:
            self._run_script("auto_apply.py", args, use_xvfb=use_xvfb, extra_env=extra_env)

    # ---------- ШАГ 10: Работа с базой данных ----------
    def _step_clean_db(self):
        print("\n" + "=" * 60)
        print("ШАГ 10: РАБОТА С БАЗОЙ ДАННЫХ (ОТКЛИКИ, ОШИБКИ)")
        print("=" * 60)
        self._run_script("clean_db.py")

    # ---------- ШАГ 11: Выход ----------
    def _exit(self):
        print("\nДо свидания!")
        sys.exit(0)

    # ---------- ВСПОМОГАТЕЛЬНЫЕ ДЛЯ УПРАВЛЕНИЯ ПРОЦЕССОМ ----------
    def _is_schedule_running(self) -> bool:
        if not PID_FILE.exists():
            return False
        try:
            pid = int(PID_FILE.read_text().strip())
            if sys.platform == "win32":
                result = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True)
                return str(pid) in result.stdout
            else:
                os.kill(pid, 0)
                return True
        except (ValueError, ProcessLookupError, OSError):
            return False

    def _stop_schedule_process(self):
        if not PID_FILE.exists():
            print("PID-файл не найден.")
            return
        try:
            pid = int(PID_FILE.read_text().strip())
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], check=True)
            else:
                os.kill(pid, signal.SIGTERM)
                time.sleep(2)
                try:
                    os.kill(pid, 0)
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            PID_FILE.unlink(missing_ok=True)
            print(f"Процесс с PID {pid} остановлен.")
        except Exception as e:
            print(f"Ошибка при остановке процесса: {e}")

    def _run_script_detached(self, script_name: str, args: List[str] = None,
                             use_xvfb: bool = False, extra_env: Dict[str, str] = None):
        script_path = self.root_dir / script_name
        if not script_path.exists():
            print(f"Скрипт {script_name} не найден в корне.")
            return

        cmd = []
        if use_xvfb:
            try:
                subprocess.run(["which", "xvfb-run"], capture_output=True, check=True)
                cmd = ["xvfb-run", "-a", sys.executable, str(script_path)]
            except:
                print("xvfb-run не найден. Запуск без xvfb.")
                cmd = [sys.executable, str(script_path)]
        else:
            cmd = [sys.executable, str(script_path)]

        if args:
            cmd.extend(args)

        env = os.environ.copy()
        if extra_env:
            env.update(extra_env)

        log_fd = open(LOG_FILE, "a", encoding="utf-8")
        log_fd.write(f"\n\n--- Запуск {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        log_fd.flush()

        try:
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
                proc = subprocess.Popen(
                    cmd,
                    stdout=log_fd,
                    stderr=subprocess.STDOUT,
                    env=env,
                    creationflags=creationflags,
                    text=False
                )
            else:
                proc = subprocess.Popen(
                    cmd,
                    stdout=log_fd,
                    stderr=subprocess.STDOUT,
                    env=env,
                    start_new_session=True,
                    text=False
                )
            PID_FILE.write_text(str(proc.pid))
            print(f"Процесс запущен с PID {proc.pid}")
        except Exception as e:
            print(f"Ошибка запуска в фоне: {e}")
            log_fd.close()
            return
        log_fd.close()

    # ---------- БЕЗОПАСНОЕ ОБНОВЛЕНИЕ .ENV ----------
    def _update_env_var(self, key: str, value: str):
        """Обновляет или добавляет переменную в .env, сохраняя все остальные строки."""
        env_path = self.root_dir / ".env"
        if not env_path.exists():
            env_path.write_text(f"{key}={value}\n", encoding='utf-8')
            return

        lines = env_path.read_text(encoding='utf-8').splitlines(keepends=False)
        found = False
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={value}"
                found = True
                break
        if not found:
            lines.append(f"{key}={value}")
        env_path.write_text("\n".join(lines) + "\n", encoding='utf-8')

    # ---------- ОБЫЧНЫЙ ЗАПУСК ----------
    def _run_script(self, script_name: str, args: List[str] = None,
                    use_xvfb: bool = False, extra_env: Dict[str, str] = None):
        script_path = self.root_dir / script_name
        if not script_path.exists():
            print(f"Скрипт {script_name} не найден в корне.")
            return

        cmd = []
        if use_xvfb:
            try:
                subprocess.run(["which", "xvfb-run"], capture_output=True, check=True)
                cmd = ["xvfb-run", "-a", sys.executable, str(script_path)]
            except:
                print("xvfb-run не найден. Запуск без xvfb.")
                cmd = [sys.executable, str(script_path)]
        else:
            cmd = [sys.executable, str(script_path)]

        if args:
            cmd.extend(args)

        print(f"\nЗапуск: {' '.join(cmd)}")
        print("-" * 60)

        env = os.environ.copy()
        if extra_env:
            env.update(extra_env)

        try:
            subprocess.run(cmd, env=env, check=True)
            print("-" * 60)
            print(f"{script_name} выполнен успешно")
        except subprocess.CalledProcessError as e:
            print(f"Ошибка при выполнении {script_name}: {e}")
        except KeyboardInterrupt:
            print("\nПрервано пользователем")

    # ---------- СОХРАНЕНИЕ YAML ----------
    def _save_yaml_preserve_format(self, file_path: Path, data: Dict[str, Any]):
        try:
            from ruamel.yaml import YAML
            from ruamel.yaml.scalarstring import SingleQuotedScalarString
        except ImportError:
            print("Модуль ruamel.yaml не найден. Устанавливаю...")
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", "ruamel.yaml"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                print("Установка ruamel.yaml выполнена успешно.")
                from ruamel.yaml import YAML
                from ruamel.yaml.scalarstring import SingleQuotedScalarString
            except Exception as e:
                print(f"Не удалось установить ruamel.yaml: {e}")
                print("Будет использован стандартный yaml (без кавычек).")
                import yaml
                with open(file_path, 'w', encoding='utf-8') as f:
                    yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
                print("Конфиг сохранён (стандартный YAML).")
                return

        yaml_ruamel = YAML()
        yaml_ruamel.preserve_quotes = True
        yaml_ruamel.indent(mapping=2, sequence=4, offset=2)

        if "schedule" in data and "run_times" in data["schedule"]:
            times = data["schedule"]["run_times"]
            if isinstance(times, list):
                data["schedule"]["run_times"] = [
                    SingleQuotedScalarString(str(t)) for t in times
                ]

        with open(file_path, 'w', encoding='utf-8') as f:
            yaml_ruamel.dump(data, f)

        print("Конфиг сохранён с кавычками для времени (ruamel.yaml)")


def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("=" * 70)
    print("HH-AUTO-APPLY SETUP TOOL")
    print("=" * 70)
    print("\nИнструмент для настройки проекта")
    print("Все шаги можно выполнять последовательно или выборочно\n")
    tool = SetupTool()
    while True:
        tool.show_menu()
        try:
            choice = input("\nВыберите шаг (1-11): ").strip()
            if not choice:
                continue
            step = int(choice)
            if 1 <= step <= 11:
                tool.run_step(step)
            else:
                print("Введите число от 1 до 11")
                input("Нажмите Enter...")
        except ValueError:
            print("Введите число")
            input("Нажмите Enter...")
        except KeyboardInterrupt:
            print("\nДо свидания!")
            sys.exit(0)


if __name__ == "__main__":
    main()