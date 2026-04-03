# 🎓 SGU Schedule Bot

Telegram-бот для получения расписания занятий СГУ (Саратовский государственный университет).

## ✨ Возможности

| Кнопка | Описание |
|---|---|
| 📅 Моё расписание | Полное расписание вашей группы (из профиля) |
| 🔆 На сегодня | Только текущий день |
| 📚 Расписание группы | Поиск любой группы по факультету и форме обучения |
| 👨‍🏫 Преподаватель | Поиск по фамилии / ФИО |
| 🔔 Уведомления | Расписание в 08:00 (сегодня) и 22:00 (завтра) по местному времени |
| ⭐ Избранное | Быстрый доступ к сохранённым группам и преподавателям |
| 📋 История | Последние 10 поисков |
| 👤 Профиль | Факультет + группа сохраняются между запусками |
| 💡 Быстрый ввод | Напишите номер группы прямо в чат — бот найдёт её на вашем факультете |

## 📁 Структура

```
SheduleBot/
  bot.py              # точка входа
  config.py           # токен, часовой пояс, факультеты, константы
  database.py         # SQLite: профили, кэш, история, избранное, подписки
  fetcher.py          # HTTP-запросы + кэш расписаний
  parser.py           # парсинг HTML-таблиц СГУ
  keyboards.py        # все клавиатуры Telegram
  utils.py            # вспомогательные функции
  requirements.txt
  handlers/
    menu.py           # /start, помощь, история
    profile.py        # настройка профиля
    schedule.py       # расписание групп
    teacher.py        # поиск преподавателей
    favorites.py      # избранное
    notify.py         # подписка на уведомления
  data/
    sgu_bot.db        # SQLite (создаётся автоматически)
```

## 🚀 Установка и запуск

```bash
git clone https://github.com/MaximGaranin/SheduleBot.git
cd SheduleBot
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Вставьте токен и часовой пояс в `config.py`:
```python
BOT_TOKEN = "ВАШ_ТОКЕН"
TIMEZONE  = "Europe/Saratov"  # или Europe/Moscow, Asia/Yekaterinburg и т.д.
```

Запуск:
```bash
python bot.py
```

## 🛠️ Деплой через systemd

Создайте файл сервиса:
```bash
sudo nano /etc/systemd/system/sgubot.service
```

```ini
[Unit]
Description=SGU Schedule Telegram Bot
After=network.target

[Service]
Type=simple
User=w1ntry
WorkingDirectory=/home/w1ntry/SheduleBot
ExecStart=/home/w1ntry/SheduleBot/venv/bin/python bot.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable sgubot   # автозапуск при старте сервера
sudo systemctl start sgubot

# Полезные команды
sudo systemctl status sgubot   # статус
sudo journalctl -u sgubot -f   # лив-логи
sudo systemctl restart sgubot  # перезапуск
```

## 🗄️ Таблицы БД

| Таблица | Содержимое | TTL |
|---|---|---|
| `profiles` | Факультет, форма, группа пользователя | навсегда |
| `schedule_cache` | HTML страниц расписания | 1 час |
| `teacher_cache` | Результаты поиска преподавателей | 6 часов |
| `search_history` | История поиска пользователя | навсегда |
| `favorites` | Избранные группы и преподаватели | навсегда |
| `notify_subscriptions` | Подписки на уведомления | навсегда |

## 📦 Зависимости

- `python-telegram-bot[job-queue]` ≥ 21
- `httpx`
- `beautifulsoup4`
- `pytz`

> Python 3.10+ обязателен. Тестировалось на Python 3.14.
