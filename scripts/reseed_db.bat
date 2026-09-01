@echo off
setlocal

:: Get project root (parent directory of the script)
cd /d "%~dp0\.."

:: Activate virtual environment if it exists
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
)

echo [1/5] flask --app wsgi.py db upgrade
flask --app wsgi.py db upgrade
if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%

echo [2/5] python scripts/seed_flama_template.py
python scripts/seed_flama_template.py
if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%

echo [3/5] flask --app wsgi.py user-role-seed
flask --app wsgi.py user-role-seed
if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%

echo [4/5] flask --app wsgi.py taxonomy-seed
flask --app wsgi.py taxonomy-seed
if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%

echo [5/5] flask --app wsgi.py vocab-seed --path "static/seed_data" --replace-lessons
flask --app wsgi.py vocab-seed --path "static/seed_data" --replace-lessons
if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%

echo Done reseed DB.
