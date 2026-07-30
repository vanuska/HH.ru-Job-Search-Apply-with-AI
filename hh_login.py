#!/usr/bin/env python3
"""
HH.ru авторизация - сохраняет сессию браузера
"""

import os
from playwright.sync_api import sync_playwright

# Загружаем .env вручную с правильной кодировкой
def load_env_manual():
    """Загружает .env файл с правильной кодировкой"""
    env_file = Path(__file__).resolve().parent / ".env"
    if env_file.exists():
        try:
            # Пробуем UTF-8
            content = env_file.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            try:
                # Пробуем Windows-1251
                content = env_file.read_text(encoding='cp1251')
            except UnicodeDecodeError:
                try:
                    # Пробуем с BOM
                    content = env_file.read_text(encoding='utf-8-sig')
                except:
                    print("Не удалось прочитать .env файл")
                    return
        
        # Парсим .env вручную
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith('#'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

# Исправленный путь
from pathlib import Path

N8N_FILES_DIR = os.getenv("N8N_FILES_DIR") or os.path.expanduser("~/.n8n-files")
SESSION_FILE = os.path.join(N8N_FILES_DIR, "hh_session.json")


def login():
    """Авторизация на HH.ru и сохранение сессии"""
    
    # Загружаем .env вручную
    load_env_manual()
    
    # Создаем директорию
    os.makedirs(N8N_FILES_DIR, exist_ok=True)
    
    print("\n" + "="*50)
    print("HH.RU АВТОРИЗАЦИЯ")
    print("="*50)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        # Открываем страницу логина
        page.goto("https://hh.ru/login")
        
        print("\nИнструкция:")
        print("1. В открывшемся браузере войдите в аккаунт HH.ru")
        print("2. Дождитесь загрузки личного кабинета")
        print("3. Вернитесь сюда и нажмите Enter")
        
        input("\nНажмите Enter когда залогинились...")
        
        # Сохраняем сессию
        context.storage_state(path=SESSION_FILE)
        print(f"\nСессия сохранена в {SESSION_FILE}")
        
        browser.close()


if __name__ == "__main__":
    login()
