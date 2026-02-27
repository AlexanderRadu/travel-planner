# Project: Waylines: a platform for author routes

[![Lint • Tests](https://gitlab.crja72.ru/django/2025/autumn/course/projects/team-2/badges/master/pipeline.svg?key_text=Lint%20%7C%20Tests&key_width=110)](https://gitlab.crja72.ru/django/2025/autumn/course/projects/team-2/pipelines)


## Development Mode Installation

### 1. Clone repository

```bash
git clone https://gitlab.crja72.ru/django/2025/autumn/course/projects/team-2.git
```

### 2. Create virtual environment

Linux/MacOS: 
```bash
python3 -m venv venv
```

Windows:
```bash
python -m venv venv
```  

### 3. Activate virtual environment

Linux/MacOS: 
```bash
source venv/bin/activate
```  
Windows:
 ```bash
venv\Scripts\activate
```  

### 4. Installing dependencies

For production: 
```bash
pip install -r requirements/prod.txt
```  
For testing:
 ```bash
pip install -r requirements/test.txt
```  
For development: 
```bash
pip install -r requirements/dev.txt
``` 


### 6. Apply database migrations

All following commands with python manage.py must be executed from the directory containing manage.py (in this case, waylines)  
```bash
cd waylines
```

#### Apply migrations to database

```bash
python manage.py migrate
```

#### Create a superuser (for access to the admin panel)

```bash
python manage.py createsuperuser
```

#### Collect static files (required for admin panel and styling)  

```bash
python manage.py collectstatic --noinput
```

#### Check migration status

```bash
python manage.py showmigrations
```

### 8. Running tests

```bash
python manage.py test
```

### 9. Run development server:

```bash
python manage.py runserver
```