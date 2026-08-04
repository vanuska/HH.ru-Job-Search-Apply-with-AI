#!/usr/bin/env python3
"""
Тест генерации сопроводительного письма сгенерированного выбраной LLM
"""

import sys
import os
from pathlib import Path
sys.path.insert(0, '.')

# Загружаем .env вручную
def load_env_manual():
    """Загружает .env файл вручную"""
    env_file = Path(__file__).resolve().parent / ".env"
    if not env_file.exists():
        return
    
    # Пробуем разные кодировки
    content = None
    for encoding in ['utf-8', 'cp1251', 'utf-8-sig', 'latin-1']:
        try:
            content = env_file.read_text(encoding=encoding)
            break
        except:
            continue
    
    if content is None:
        print("Не удалось прочитать .env файл")
        return
    
    # Парсим .env
    for line in content.splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            if '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

# Загружаем переменные окружения
load_env_manual()

# Импортируем функции из auto_apply
from auto_apply import (
    load_profile,
    load_llm_config,
    generate_cover_letter,
    Vacancy,
    load_yaml,
    ROOT_DIR,
    DEFAULT_CONFIG_PATH
)


def test_letter():
    """Тестирует генерацию письма"""
    
    print("="*60)
    print("ТЕСТ ГЕНЕРАЦИИ ПИСЬМА")
    print("="*60)
    
    # Загружаем профиль
    print("\n1. Загрузка профиля...")
    try:
        profile = load_profile()
        print(f"Профиль загружен: {len(profile)} символов")
    except Exception as e:
        print(f"Ошибка загрузки профиля: {e}")
        return
    
    # Загружаем LLM конфиг
    print("\n2. Загрузка LLM...")
    try:
        llm = load_llm_config()
        print(f"LLM: {llm.provider} ({llm.model})")
    except Exception as e:
        print(f"Ошибка загрузки LLM: {e}")
        return
    
    # Создаем тестовую вакансию
    print("\n3. Создание тестовой вакансии...")
    vacancy = Vacancy(
        id='test_123',
        title='Руководитель IT-департамента',
        employer='Тестовая компания',
        url='https://hh.ru/vacancy/test',
        apply_url='https://hh.ru/vacancy/test',
        description='Управление IT-инфраструктурой, руководство командой, бюджетирование.',
        has_test=False,
        response_letter_required=False,
        query='Руководитель ИТ',
        schedule_id='remote',
        schedule_name='Удаленная работа'
    )
    print("Тестовая вакансия создана")
    
    # Загружаем конфиг
    print("\n4. Загрузка конфига...")
    try:
        config_path = Path(os.getenv("HH_CONFIG_PATH") or DEFAULT_CONFIG_PATH)
        if not config_path.is_absolute():
            config_path = ROOT_DIR / config_path
        config = load_yaml(config_path)
        print("Конфиг загружен")
    except Exception as e:
        print(f"Ошибка загрузки конфига: {e}")
        return
    
    # Генерируем письмо
    print("\n5. Генерация письма...")
    try:
        letter = generate_cover_letter(llm, profile, vacancy, config)
        print("\n" + "="*60)
        print("СОГЕНЕРИРОВАННОЕ ПИСЬМО:")
        print("="*60)
        print(letter)
        print("="*60)
        print(f"\nДлина: {len(letter)} символов")
        print("Тест пройден успешно!")
    except Exception as e:
        print(f"Ошибка генерации письма: {e}")


if __name__ == "__main__":
    test_letter()
