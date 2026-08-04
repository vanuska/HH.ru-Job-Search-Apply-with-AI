#!/usr/bin/env python3
"""
Скрипт для управления базой данных hh_auto_apply.sqlite3
Поддерживает:
- Работу с таблицей vacancy_runs (отклики)
- Работу с таблицей chat_notifications (уведомления о чатах)
- Фильтрацию, сортировку, просмотр полных данных, удаление записей
- Создание бэкапа и полную очистку
"""

import sqlite3
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import sys


DB_PATH = Path("data/hh_auto_apply.sqlite3")
BACKUP_DIR = Path("data/backups")


def ensure_db():
    if not DB_PATH.exists():
        print(f"База данных не найдена: {DB_PATH}")
        return False
    return True


def connect_db():
    return sqlite3.connect(DB_PATH)


def show_stats_vacancy(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM vacancy_runs")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT status, COUNT(*) FROM vacancy_runs GROUP BY status")
    stats = cursor.fetchall()
    cursor.execute("SELECT MIN(updated_at), MAX(updated_at) FROM vacancy_runs")
    min_date, max_date = cursor.fetchone()

    print("\n" + "="*60)
    print("СТАТИСТИКА ОТКЛИКОВ (vacancy_runs)")
    print("="*60)
    print(f"Всего записей: {total}")
    if min_date:
        print(f"Период: с {min_date[:10]} по {max_date[:10]}")
    print("\nПо статусам:")
    for status, count in stats:
        print(f"  - {status}: {count}")
    print("="*60)
    return total


def show_stats_chat(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM chat_notifications")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT MIN(sent_at), MAX(sent_at) FROM chat_notifications")
    min_date, max_date = cursor.fetchone()
    cursor.execute("SELECT SUM(last_unread_count) FROM chat_notifications")
    sum_unread = cursor.fetchone()[0] or 0

    print("\n" + "="*60)
    print("СТАТИСТИКА УВЕДОМЛЕНИЙ О ЧАТАХ (chat_notifications)")
    print("="*60)
    print(f"Всего записей: {total}")
    if min_date:
        print(f"Период: с {min_date[:10]} по {max_date[:10]}")
    print(f"Суммарное количество непрочитанных: {sum_unread}")
    print("="*60)
    return total


def filter_and_display_vacancy(conn, filters=None, sort_by=None, order='DESC'):
    cursor = conn.cursor()
    query = "SELECT vacancy_id, title, employer, status, reason, url, substr(letter, 1, 200) as letter_preview, updated_at FROM vacancy_runs WHERE 1=1"
    params = []
    
    if filters:
        if filters.get('status'):
            statuses = [s.strip() for s in filters['status'].split(',')]
            placeholders = ','.join(['?'] * len(statuses))
            query += f" AND status IN ({placeholders})"
            params.extend(statuses)
        if filters.get('company'):
            query += " AND employer LIKE ?"
            params.append(f"%{filters['company']}%")
        if filters.get('title'):
            query += " AND title LIKE ?"
            params.append(f"%{filters['title']}%")
        if filters.get('date_from'):
            query += " AND updated_at >= ?"
            params.append(filters['date_from'])
        if filters.get('date_to'):
            query += " AND updated_at <= ?"
            params.append(filters['date_to'] + " 23:59:59")
    
    if sort_by:
        allowed_sort = ['updated_at', 'status', 'title', 'employer']
        if sort_by in allowed_sort:
            query += f" ORDER BY {sort_by} {order}"
        else:
            query += " ORDER BY updated_at DESC"
    else:
        query += " ORDER BY updated_at DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    if not rows:
        print("\nЗаписей по указанным критериям нет.")
        return []
    
    print(f"\nНайдено записей: {len(rows)}")
    print("-"*80)
    for idx, row in enumerate(rows, 1):
        vacancy_id, title, employer, status, reason, url, letter_preview, updated_at = row
        print(f"{idx:3}. {updated_at[:16]} | {status:8} | {employer[:20]:20} | {title[:30]:30}")
        if reason:
            print(f"     Причина: {reason}")
        if letter_preview:
            print(f"     Письмо: {letter_preview}...")
        print("-"*80)
    
    return rows


def filter_and_display_chat(conn, filters=None, sort_by=None, order='DESC'):
    """Выводит записи из chat_notifications с фильтрацией и сортировкой, включая company, vacancy_title, preview, last_unread_count."""
    cursor = conn.cursor()
    query = "SELECT chat_id, sent_at, company, vacancy_title, preview, last_unread_count FROM chat_notifications WHERE 1=1"
    params = []
    
    if filters:
        if filters.get('chat_id'):
            query += " AND chat_id LIKE ?"
            params.append(f"%{filters['chat_id']}%")
        if filters.get('company'):
            query += " AND company LIKE ?"
            params.append(f"%{filters['company']}%")
        if filters.get('vacancy'):
            query += " AND vacancy_title LIKE ?"
            params.append(f"%{filters['vacancy']}%")
        if filters.get('min_unread'):
            query += " AND last_unread_count >= ?"
            params.append(int(filters['min_unread']))
        if filters.get('date_from'):
            query += " AND sent_at >= ?"
            params.append(filters['date_from'])
        if filters.get('date_to'):
            query += " AND sent_at <= ?"
            params.append(filters['date_to'] + " 23:59:59")
    
    if sort_by:
        allowed_sort = ['sent_at', 'chat_id', 'company', 'vacancy_title', 'last_unread_count']
        if sort_by in allowed_sort:
            query += f" ORDER BY {sort_by} {order}"
        else:
            query += " ORDER BY sent_at DESC"
    else:
        query += " ORDER BY sent_at DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    if not rows:
        print("\nЗаписей по указанным критериям нет.")
        return []
    
    print(f"\nНайдено записей: {len(rows)}")
    print("-"*80)
    for idx, row in enumerate(rows, 1):
        chat_id, sent_at, company, vacancy, preview, unread = row
        print(f"{idx:3}. {sent_at[:16]} | unread:{unread:2} | {company[:20] if company else '':20} | {vacancy[:30] if vacancy else '':30}")
        if preview:
            print(f"     Превью: {preview[:100]}...")
        print("-"*80)
    
    return rows


def view_full_letter(conn, vacancy_id):
    cursor = conn.cursor()
    cursor.execute("SELECT letter FROM vacancy_runs WHERE vacancy_id = ?", (vacancy_id,))
    row = cursor.fetchone()
    if row and row[0]:
        print("\n" + "="*60)
        print(f"ПОЛНЫЙ ТЕКСТ ПИСЬМА (vacancy_id: {vacancy_id})")
        print("="*60)
        print(row[0])
        print("="*60)
    else:
        print("Письмо не найдено или пусто.")


def delete_vacancy_record(conn, vacancy_id):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vacancy_runs WHERE vacancy_id = ?", (vacancy_id,))
    conn.commit()
    print(f"Запись {vacancy_id} удалена.")


def delete_chat_record(conn, chat_id):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chat_notifications WHERE chat_id = ?", (chat_id,))
    conn.commit()
    print(f"Запись для чата {chat_id} удалена.")


def clear_all_chat_notifications(conn):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chat_notifications")
    conn.commit()
    print("Таблица chat_notifications очищена.")


def interactive_menu():
    if not ensure_db():
        return
    
    conn = connect_db()
    try:
        while True:
            print("\n" + "="*60)
            print("УПРАВЛЕНИЕ БАЗОЙ ДАННЫХ")
            print("="*60)
            
            show_stats_vacancy(conn)
            show_stats_chat(conn)
            
            print("\nДоступные действия:")
            print("  1. Работа с откликами (vacancy_runs)")
            print("  2. Работа с уведомлениями о чатах (chat_notifications)")
            print("  3. Создать бэкап и полностью очистить БД (все таблицы)")
            print("  4. Выйти")
            
            choice = input("\nВыберите действие (1-4): ").strip()
            
            if choice == '1':
                while True:
                    print("\n--- ОТКЛИКИ (vacancy_runs) ---")
                    print("  1. Вывести записи (с фильтрацией)")
                    print("  2. Просмотреть полное письмо по ID вакансии")
                    print("  3. Удалить запись по ID вакансии")
                    print("  4. Назад")
                    sub = input("Выберите (1-4): ").strip()
                    
                    if sub == '1':
                        print("\n--- Фильтры (оставьте пустым для пропуска) ---")
                        status = input("Статус (success/skipped/error/dry_run, можно через запятую): ").strip()
                        company = input("Компания (часть названия): ").strip()
                        title = input("Вакансия (часть названия): ").strip()
                        date_from = input("Дата с (ГГГГ-ММ-ДД): ").strip()
                        date_to = input("Дата по (ГГГГ-ММ-ДД): ").strip()
                        
                        filters = {}
                        if status:
                            filters['status'] = status
                        if company:
                            filters['company'] = company
                        if title:
                            filters['title'] = title
                        if date_from:
                            filters['date_from'] = date_from
                        if date_to:
                            filters['date_to'] = date_to
                        
                        print("\n--- Сортировка ---")
                        print("Поля: updated_at, status, title, employer")
                        sort_by = input("Сортировать по (Enter = updated_at): ").strip() or 'updated_at'
                        order = input("Порядок (ASC/DESC, Enter = DESC): ").strip().upper() or 'DESC'
                        
                        rows = filter_and_display_vacancy(conn, filters, sort_by, order)
                        
                        if rows:
                            view_choice = input("\nХотите посмотреть полное письмо для какой-либо записи? (Y/N): ").strip().upper()
                            if view_choice in ['Y', 'ДА']:
                                idx = input("Введите номер записи из списка: ").strip()
                                try:
                                    idx = int(idx) - 1
                                    if 0 <= idx < len(rows):
                                        vacancy_id = rows[idx][0]
                                        view_full_letter(conn, vacancy_id)
                                    else:
                                        print("Неверный номер.")
                                except ValueError:
                                    print("Некорректный ввод.")
                    
                    elif sub == '2':
                        vacancy_id = input("Введите ID вакансии: ").strip()
                        view_full_letter(conn, vacancy_id)
                    
                    elif sub == '3':
                        vacancy_id = input("Введите ID вакансии для удаления: ").strip()
                        confirm = input(f"Удалить запись {vacancy_id}? (Y/N): ").strip().upper()
                        if confirm in ['Y', 'ДА']:
                            delete_vacancy_record(conn, vacancy_id)
                    
                    elif sub == '4':
                        break
                    else:
                        print("Неверный выбор.")
            
            elif choice == '2':
                while True:
                    print("\n--- УВЕДОМЛЕНИЯ О ЧАТАХ (chat_notifications) ---")
                    print("  1. Вывести записи (с фильтрацией)")
                    print("  2. Удалить запись по chat_id")
                    print("  3. Очистить все записи чатов")
                    print("  4. Назад")
                    sub = input("Выберите (1-4): ").strip()
                    
                    if sub == '1':
                        print("\n--- Фильтры (оставьте пустым для пропуска) ---")
                        chat_id_filter = input("ID чата (часть): ").strip()
                        company_filter = input("Компания (часть названия): ").strip()
                        vacancy_filter = input("Вакансия (часть названия): ").strip()
                        min_unread = input("Минимальное количество непрочитанных: ").strip()
                        date_from = input("Дата с (ГГГГ-ММ-ДД): ").strip()
                        date_to = input("Дата по (ГГГГ-ММ-ДД): ").strip()
                        
                        filters = {}
                        if chat_id_filter:
                            filters['chat_id'] = chat_id_filter
                        if company_filter:
                            filters['company'] = company_filter
                        if vacancy_filter:
                            filters['vacancy'] = vacancy_filter
                        if min_unread and min_unread.isdigit():
                            filters['min_unread'] = min_unread
                        if date_from:
                            filters['date_from'] = date_from
                        if date_to:
                            filters['date_to'] = date_to
                        
                        print("\n--- Сортировка ---")
                        print("Поля: sent_at, chat_id, company, vacancy_title, last_unread_count")
                        sort_by = input("Сортировать по (Enter = sent_at): ").strip() or 'sent_at'
                        order = input("Порядок (ASC/DESC, Enter = DESC): ").strip().upper() or 'DESC'
                        
                        filter_and_display_chat(conn, filters, sort_by, order)
                    
                    elif sub == '2':
                        chat_id = input("Введите chat_id для удаления: ").strip()
                        confirm = input(f"Удалить запись для чата {chat_id}? (Y/N): ").strip().upper()
                        if confirm in ['Y', 'ДА']:
                            delete_chat_record(conn, chat_id)
                    
                    elif sub == '3':
                        confirm = input("Очистить все записи о чатах? (Y/N): ").strip().upper()
                        if confirm in ['Y', 'ДА']:
                            clear_all_chat_notifications(conn)
                    
                    elif sub == '4':
                        break
                    else:
                        print("Неверный выбор.")
            
            elif choice == '3':
                confirm = input("\nВНИМАНИЕ! Это удалит все записи из БД (обе таблицы). Создать бэкап и очистить? (Y/N): ").strip().upper()
                if confirm in ['Y', 'ДА']:
                    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_path = BACKUP_DIR / f"hh_auto_apply_{timestamp}.sqlite3"
                    shutil.copy2(DB_PATH, backup_path)
                    print(f"Бэкап создан: {backup_path}")
                    
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM vacancy_runs")
                    cursor.execute("DELETE FROM chat_notifications")
                    conn.commit()
                    print("База данных очищена.")
            
            elif choice == '4':
                break
            else:
                print("Неверный выбор.")
    
    finally:
        conn.close()


def main():
    interactive_menu()


if __name__ == "__main__":
    main()
