#!/usr/bin/env python3
"""
Скрипт для очистки базы данных hh_auto_apply.sqlite3
Создает бэкап перед очисткой.
Также позволяет просматривать записи детально.
"""

import sqlite3
import shutil
from pathlib import Path
from datetime import datetime


def show_detailed_records(conn):
    """Показывает все записи в детальном формате"""
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT vacancy_id, title, employer, status, reason, url, query, 
               substr(letter, 1, 200) as letter_preview, updated_at 
        FROM vacancy_runs 
        ORDER BY updated_at DESC
    """)
    rows = cursor.fetchall()
    
    if not rows:
        print("\nЗаписей нет")
        return
    
    print("\n" + "="*80)
    print("ДЕТАЛЬНЫЙ ПРОСМОТР ЗАПИСЕЙ")
    print("="*80)
    
    for idx, row in enumerate(rows, 1):
        vacancy_id, title, employer, status, reason, url, query, letter_preview, updated_at = row
        
        print(f"\n{'-'*80}")
        print(f"ЗАПИСЬ #{idx}")
        print(f"{'-'*80}")
        print(f"  ID вакансии:    {vacancy_id}")
        print(f"  Название:       {title}")
        print(f"  Работодатель:   {employer}")
        print(f"  Статус:         {status}")
        if reason:
            print(f"  Причина:        {reason}")
        print(f"  URL:            {url}")
        print(f"  Поисковый запрос: {query}")
        print(f"  Дата:           {updated_at[:19]}")
        if letter_preview:
            print(f"  Письмо (первые 200 символов):")
            print(f"     {letter_preview}...")
        print(f"{'-'*80}")


def show_stats(conn):
    """Показывает статистику базы данных"""
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM vacancy_runs")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT status, COUNT(*) FROM vacancy_runs GROUP BY status")
    stats = cursor.fetchall()
    
    print("\n" + "="*50)
    print("СТАТИСТИКА БАЗЫ ДАННЫХ")
    print("="*50)
    print(f"Всего записей: {total}")
    print("\nПо статусам:")
    for status, count in stats:
        print(f"  - {status}: {count}")
    print("="*50)
    
    return total


def clean_database():
    """Очищает таблицу vacancy_runs в базе данных"""
    
    db_path = Path("data/hh_auto_apply.sqlite3")
    backup_dir = Path("data/backups")
    
    if not db_path.exists():
        print(f"База данных не найдена: {db_path}")
        return False
    
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"hh_auto_apply_{timestamp}.sqlite3"
    
    print(f"\nСоздание бэкапа: {backup_path}")
    shutil.copy2(db_path, backup_path)
    print(f"Бэкап создан: {backup_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Получаем количество записей ДО очистки
        cursor.execute("SELECT COUNT(*) FROM vacancy_runs")
        total_before = cursor.fetchone()[0]
        
        show_stats(conn)
        
        print("\nВНИМАНИЕ: Это действие удалит все записи из базы данных!")
        confirm = input("Продолжить очистку? (Y/N): ").strip().upper()
        
        if confirm not in ['Y', 'ДА']:
            print("\nОчистка отменена.")
            conn.close()
            return False
        
        # Очищаем таблицу
        cursor.execute("DELETE FROM vacancy_runs")
        conn.commit()
        
        # Получаем количество записей ПОСЛЕ очистки
        cursor.execute("SELECT COUNT(*) FROM vacancy_runs")
        total_after = cursor.fetchone()[0]
        
        conn.close()
        
        print(f"\nБаза данных очищена! Удалено записей: {total_before - total_after}")
        print(f"Записей после очистки: {total_after}")
        return True
        
    except sqlite3.Error as e:
        print(f"Ошибка при очистке базы данных: {e}")
        return False


def view_records():
    """Просмотр записей без очистки"""
    db_path = Path("data/hh_auto_apply.sqlite3")
    
    if not db_path.exists():
        print(f"База данных не найдена: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        
        show_stats(conn)
        
        show_detail = input("\nПоказать детальный список записей? (Y/N): ").strip().upper()
        if show_detail in ['Y', 'ДА']:
            show_detailed_records(conn)
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Ошибка: {e}")


def main():
    """Главная функция"""
    print("\n" + "="*50)
    print("УПРАВЛЕНИЕ БАЗОЙ ДАННЫХ")
    print("="*50)
    
    print("\nВыберите действие:")
    print("1. Просмотр записей (без удаления)")
    print("2. Очистка базы данных (с созданием бэкапа)")
    print("3. Выход")
    
    choice = input("\nВыберите (1-3): ").strip()
    
    if choice == "1":
        view_records()
    elif choice == "2":
        clean_database()
    else:
        print("\nДо свидания!")

if __name__ == "__main__":
    main()
