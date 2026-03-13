# Waylines: Travel Planner


**Waylines** — это платформа для создания, поиска и планирования авторских туристических маршрутов. 

## 🛠 Стек технологий
- **Backend:** Python, Django
- **Frontend:** HTML5, CSS3, JavaScript
- **Инфраструктура:** Docker, Docker Compose
- **Управление зависимостями:** pip (requirements), npm (package.json)

---

## 🚀 Установка и запуск в режиме разработки (Локально)

### 1. Клонирование репозитория
```bash
git clone https://github.com/AlexanderRadu/travel-planner.git
cd travel-planner
```

### 2. Настройка окружения
Скопируйте шаблон переменных окружения и при необходимости измените их:
```bash
cp template.env .env
```

### 3. Создание и активация виртуального окружения

**Linux / MacOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

### 4. Установка зависимостей
Проект поддерживает несколько профилей зависимостей. Выберите нужный:

- Для разработки: `pip install -r requirements/dev.txt`
- Для тестирования: `pip install -r requirements/test.txt`
- Для продакшена: `pip install -r requirements/prod.txt`

*(Также может потребоваться установка JS-зависимостей, если используется фронтенд-сборка: `npm install`)*

### 5. Подготовка базы данных
Все команды `manage.py` выполняются из директории `src`.

```bash
cd src

# Применение миграций к базе данных
python manage.py migrate

# Сбор статичных файлов (для корректного отображения админ-панели)
python manage.py collectstatic --noinput

# (Опционально) Проверка статуса миграций
python manage.py showmigrations
```

### 6. Создание суперпользователя
Для доступа к панели администратора необходимо создать аккаунт суперпользователя:
```bash
python manage.py createsuperuser
```

### 7. Запуск локального сервера разработки
```bash
python manage.py runserver
```
После этого проект будет доступен по адресу: `http://127.0.0.1:8000/`

---

## Запуск через Docker


1. Убедитесь, что у вас установлен Docker и Docker Compose.
2. Создайте файл `.env` на основе `template.env`.
3. Запустите контейнеры:
   ```bash
   docker-compose up --build
   ```
4. Для выполнения миграций внутри контейнера используйте:
   ```bash
   docker-compose exec web python manage.py migrate
   ```

---

## Запуск тестов

Для проверки работоспособности проекта используйте команду:
```bash
cd src
python manage.py test
```