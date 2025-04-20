#!/usr/bin/env python3
import hashlib
import sys

def generate_password_hash(password):
    """Генерирует SHA-256 хеш пароля"""
    return hashlib.sha256(password.encode()).hexdigest()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        password = sys.argv[1]
    else:
        password = input("Введите пароль для генерации хеша: ")
    
    password_hash = generate_password_hash(password)
    print("\nДобавьте следующую строку в файл .env:")
    print(f"ADMIN_PASSWORD_HASH={password_hash}")
    print("\nТеперь перезапустите бота.")
    print(f"SHA-256 хеш для пароля '{password}': {password_hash}") 