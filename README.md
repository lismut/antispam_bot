# Telegram Anti-Spam Bot

Бот для групповых чатов Telegram: автоматически находит спам, удаляет сообщения и блокирует отправителей.

## Возможности

- Эвристический детектор спама (ключевые слова, ссылки, CAPS, emoji, пересылки, массовые @упоминания)
- Удаление спам-сообщений
- Бан пользователя, отправившего спам
- Whitelist чатов (опционально)
- Настраиваемый порог чувствительности
- Запуск как systemd-сервис на Ubuntu

## Быстрый старт (локально)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Отредактируйте .env — вставьте TELEGRAM_BOT_TOKEN
python bot.py
```

---

## Развёртывание на Ubuntu (VPS)

Ниже пошаговая инструкция для чистой Ubuntu 22.04 / 24.04.

### 1. Создайте бота в Telegram

1. Откройте [@BotFather](https://t.me/BotFather) в Telegram.
2. Отправьте `/newbot`.
3. Задайте имя и username (должен заканчиваться на `bot`, например `MySpamGuardBot`).
4. Скопируйте **HTTP API Token** — он понадобится для `.env`.

> **Важно:** отключите режим «Privacy» у бота, если хотите, чтобы он видел все сообщения в группе:
> - BotFather → `/mybots` → ваш бот → **Bot Settings** → **Group Privacy** → **Turn off**

Без этого бот будет получать только команды и сообщения с упоминанием `@YourBot`.

### 2. Подключитесь к серверу

```bash
ssh user@YOUR_SERVER_IP
```

### 3. Установите зависимости системы

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
```

### 4. Создайте пользователя для бота

```bash
sudo useradd --system --home-dir /opt/telegram-spam-bot --create-home spam-bot
```

### 5. Скопируйте проект на сервер

**Вариант A — через git:**

```bash
sudo -u spam-bot git clone YOUR_REPO_URL /opt/telegram-spam-bot
```

**Вариант B — через scp с локальной машины:**

```bash
scp -r ./ user@YOUR_SERVER_IP:/tmp/telegram-spam-bot
ssh user@YOUR_SERVER_IP
sudo mv /tmp/telegram-spam-bot /opt/telegram-spam-bot
sudo chown -R spam-bot:spam-bot /opt/telegram-spam-bot
```

### 6. Настройте виртуальное окружение

```bash
sudo -u spam-bot bash -c '
  cd /opt/telegram-spam-bot
  python3 -m venv venv
  source venv/bin/activate
  pip install --upgrade pip
  pip install -r requirements.txt
'
```

### 7. Создайте файл конфигурации

```bash
sudo -u spam-bot cp /opt/telegram-spam-bot/.env.example /opt/telegram-spam-bot/.env
sudo -u spam-bot nano /opt/telegram-spam-bot/.env
```

Пример `.env`:

```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
ALLOWED_CHAT_IDS=-1001234567890
SPAM_THRESHOLD=50
LOG_LEVEL=INFO
```

| Переменная | Описание |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Токен от BotFather (обязательно) |
| `ALLOWED_CHAT_IDS` | ID чатов через запятую. Пусто = все группы, где бот админ |
| `SPAM_THRESHOLD` | Порог 0–100. Выше = меньше ложных срабатываний, ниже = строже |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

### 8. Проверьте запуск вручную

```bash
sudo -u spam-bot bash -c '
  cd /opt/telegram-spam-bot
  source venv/bin/activate
  python bot.py
'
```

Если в логах `Бот запущен` — всё работает. Остановите через `Ctrl+C`.

### 9. Настройте автозапуск (systemd)

```bash
sudo cp /opt/telegram-spam-bot/spam-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable spam-bot
sudo systemctl start spam-bot
sudo systemctl status spam-bot
```

Полезные команды:

```bash
sudo systemctl restart spam-bot   # перезапуск
sudo journalctl -u spam-bot -f      # логи в реальном времени
sudo journalctl -u spam-bot -n 100  # последние 100 строк
```

---

## Подключение бота к чату

### 1. Добавьте бота в группу

1. Откройте нужную группу в Telegram.
2. **Управление группой** → **Добавить участника** → найдите вашего бота.

### 2. Назначьте бота администратором

**Управление группой** → **Администраторы** → **Добавить администратора** → выберите бота.

Обязательные права:

| Право | Зачем |
|---|---|
| **Удаление сообщений** | Удалять спам |
| **Блокировка участников** | Банить спамеров |

Остальные права можно отключить.

### 3. Узнайте ID чата

Отправьте в группе команду:

```
/chatid
```

Бот ответит, например: `Chat ID: -1001234567890`

Добавьте этот ID в `.env` → `ALLOWED_CHAT_IDS`, если хотите ограничить работу только этой группой:

```bash
sudo nano /opt/telegram-spam-bot/.env
sudo systemctl restart spam-bot
```

### 4. Проверьте статус

```
/status
```

Бот покажет, есть ли права администратора и проходит ли чат whitelist.

---

## Как работает детектор

Каждому сообщению начисляются баллы:

| Сигнал | Баллы |
|---|---|
| Спам-ключевые слова (крипта, казино, «заработок» и т.д.) | +25 |
| Наличие ссылок | +20 |
| Сокращённые URL (bit.ly, clck.ru…) | +15 |
| Избыток CAPS | +15 |
| Много emoji (5+) | +10 |
| Пересланное сообщение | +15 |
| Новый участник + ссылка | +20 |
| Повторяющиеся символы (!!!!!) | +10 |
| 3+ упоминания @user | +20 |

Если сумма ≥ `SPAM_THRESHOLD` (по умолчанию 50) — сообщение удаляется, пользователь блокируется.

Список ключевых слов можно расширить в файле `spam_detector.py` → `SPAM_KEYWORDS`.

---

## Настройка чувствительности

| `SPAM_THRESHOLD` | Поведение |
|---|---|
| 30–40 | Агрессивный фильтр, больше ложных срабатываний |
| 50 | Баланс (рекомендуется для старта) |
| 60–70 | Мягче, пропускает пограничные сообщения |

После изменения `.env` перезапустите сервис:

```bash
sudo systemctl restart spam-bot
```

---

## Структура проекта

```
.
├── bot.py              # Основной код бота
├── spam_detector.py    # Логика детекции спама
├── config.py           # Загрузка настроек из .env
├── requirements.txt    # Python-зависимости
├── .env.example        # Пример конфигурации
├── spam-bot.service    # Unit-файл systemd
└── README.md           # Эта инструкция
```

---

## Ограничения и рекомендации

- Бот **не блокирует** сообщения от администраторов и создателя чата.
- Эвристики не заменяют ML-модель — для сложных кейсов дополняйте `SPAM_KEYWORDS`.
- Telegram API не позволяет боту читать сообщения в группе, если включён **Group Privacy** — обязательно отключите его в BotFather.
- Для очень активных чатов следите за логами: `sudo journalctl -u spam-bot -f`.

---

## Устранение неполадок

| Проблема | Решение |
|---|---|
| Бот не реагирует на сообщения | Отключите Group Privacy в BotFather |
| «Права администратора: ❌» | Назначьте бота админом с нужными правами |
| Бот не удаляет сообщения | Проверьте право «Удаление сообщений» |
| Бот не банит | Проверьте право «Блокировка участников» |
| Слишком много ложных срабатываний | Поднимите `SPAM_THRESHOLD` до 60–70 |
| Пропускает спам | Понизьте порог или добавьте слова в `SPAM_KEYWORDS` |
