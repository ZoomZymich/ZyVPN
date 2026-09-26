# 🛡️ ZyVPN - Universal VPN Client for Windows

Современный, универсальный и лёгкий VPN-клиент для Windows с поддержкой **абсолютно всех современных протоколов**, включая новейший **XHTTP over TCP** и режим автоматической маршрутизации (обход сайтов РФ и локальной сети).

![ZyVPN Architecture](https://img.shields.io/badge/Architecture-Dual--Core-indigo?style=for-the-badge)
![Supported Protocols](https://img.shields.io/badge/Protocols-VLESS%20%7C%20XHTTP%20%7C%20VMess%20%7C%20Trojan%20%7C%20Hysteria2%20%7C%20TUIC%20%7C%20SS-emerald?style=for-the-badge)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%2F%2011-blue?style=for-the-badge)

---

## ✨ Ключевые возможности

- 🚀 **100% покрытие всех протоколов и транспортов:**
  - **VLESS:** XTLS Reality, Vision, TLS, direct TCP, WebSocket, gRPC, HTTPUpgrade.
  - **⚡ XHTTP (SplitHTTP):** новейший транспорт поверх **чистого TCP, TLS и Reality** (режимы `auto`, `packet-up`, `stream-up`, `stream-one`) для гарантированного обхода современных блокировок и ТСПУ/DPI.
  - **VMess:** TCP, WebSocket, gRPC, HTTPUpgrade, mKCP.
  - **Trojan:** TCP, WebSocket, gRPC.
  - **Shadowsocks:** SIP002, Shadowsocks 2022 (AEAD).
  - **Hysteria 2:** ультрабыстрый UDP-протокол для нестабильных каналов.
  - **TUIC v5:** протокол на базе QUIC с высокой скоростью установления соединения.
  - **WireGuard.**
- 📦 **Приём любых подписок (All-in-One):**
  - Подписки Base64 (любые наборы `vless://`, `vmess://`, `trojan://`, `ss://`, `hy2://`, `tuic://`).
  - Подписки **Clash / Clash.Meta / Mihomo YAML** (автоматический парсинг секции `proxies`).
  - Одиночные ссылки и ключи из буфера обмена.
  - Автоматическое обновление подписок в один клик.
- 🇷🇺 **Режим авто-маршрутизации (Smart Bypass):**
  - Российские ресурсы (`.ru`, `.рф`, `.su`, Госуслуги, Банки, Яндекс, VK, Ozon, Кинопоиск) и локальная сеть (LAN) открываются напрямую на скорости вашего провайдера.
  - Заблокированные сайты, зарубежные сервисы и YouTube прозрачно направляются через VPN.
  - Возможность переключения в режим "Global" (100% трафика через VPN).
- 🔌 **Режимы работы в Windows:**
  - **Системный прокси (System Proxy):** мгновенное включение без повышенных прав.
  - **TUN Режим (Wintun):** виртуальный адаптер для полного перехвата всего системного трафика (игры, Discord, системные службы).
- ⚡ **Встроенный замер задержки (Ping):**
  - Высокоточный многопоточный TCP Handshake замер пинга для всех серверов списка.
- 🎨 **Современный интерфейс:**
  - Тёмная тема в стиле Glassmorphism, анимированная кнопка подключения, быстрый поиск и фильтрация узлов.

---

## 🏗️ Архитектура

ZyVPN использует модульную архитектуру **Dual-Engine (Двойное ядро)**:
1. **Xray-core (v26+)**: эталонное ядро для работы с **VLESS (Reality / Vision)** и **XHTTP over TCP/TLS**, VMess, Trojan, Shadowsocks.
2. **Sing-box core (v1.14+)**: ядро для работы с **Hysteria 2**, **TUIC v5** и системным виртуальным сетевым адаптером **TUN (`wintun.dll`)**.

---

## 🚀 Быстрый запуск

### Вариант 1. Запуск через 1 клик
Просто дважды кликните по файлу:
```cmd
ZyVPN.bat
```

### Вариант 2. Запуск из консоли
1. Установите зависимости (если запускаете впервые):
   ```bash
   pip install -r requirements.txt
   ```
2. Запустите приложение:
   ```bash
   python run.py
   ```

---

## 🛠️ Загрузка и обновление бинарных ядер

Для автоматической загрузки самых свежих ядер `Xray-core`, `Sing-box` и драйвера `wintun.dll` выполните:
```bash
python scripts/download_binaries.py
```

---

## 📁 Структура проекта

```
ZyVPN/
  ├── bin/                 # Бинарные файлы ядер (Xray, Sing-box, Wintun)
  ├── data/                # База данных подписок и настройки
  ├── scripts/             # Служебные скрипты загрузки и тестов
  ├── zyvpn/
  │   ├── models.py        # Модели данных узлов и подписок
  │   ├── parser.py        # Универсальный парсер подписок (XHTTP, Clash, Base64)
  │   ├── generator.py     # Генератор конфигураций ядер и маршрутизации
  │   ├── core.py          # Контроллер процессов и логирования
  │   ├── sysproxy.py      # Управление системным прокси Windows (WinINet API)
  │   ├── ping.py          # Модуль замера пинга
  │   ├── storage.py       # Менеджер хранения данных
  │   ├── api.py           # API бэкенда для фронтенда
  │   └── ui/              # Графический интерфейс (HTML / CSS / JS)
  ├── run.py               # Точка входа в приложение
  ├── ZyVPN.bat            # Лаунчер запуска
  └── requirements.txt     # Зависимости Python
```

---

## ⚖️ Лицензия
MIT License.
