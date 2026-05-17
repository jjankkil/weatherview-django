@echo off
REM Startup script for debug configuration (CMD/DOS)
REM Sets default environment variables for local development

setlocal enabledelayedexpansion

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo Warning: Virtual environment not found at venv\Scripts\activate.bat
    echo Please create one with: python -m venv venv
)

REM Generate a random SECRET_KEY for debug if not set
if not defined WVD_SECRET_KEY (
    echo Generating temporary SECRET_KEY for debug...
    for /f "tokens=*" %%i in ('python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"') do set WVD_SECRET_KEY=%%i
    echo Generated temporary SECRET_KEY for debug: !WVD_SECRET_KEY!
)

REM Set debug mode
set WVD_DEBUG=True

REM Set allowed hosts for local development
set WVD_ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0

REM Set session cookie age (optional, defaults to 14 days)
set WVD_SESSION_COOKIE_AGE=1209600

REM Run the development server
python manage.py runserver 0.0.0.0:8000

endlocal
