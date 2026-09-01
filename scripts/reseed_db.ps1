$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (Test-Path ".venv\Scripts\Activate.ps1") {
    & ".venv\Scripts\Activate.ps1"
}

Write-Host "[1/5] flask --app wsgi.py db upgrade"
flask --app wsgi.py db upgrade

Write-Host "[2/5] python scripts/seed_flama_template.py"
python scripts/seed_flama_template.py

Write-Host "[3/5] flask --app wsgi.py user-role-seed"
flask --app wsgi.py user-role-seed

Write-Host "[4/5] flask --app wsgi.py taxonomy-seed"
flask --app wsgi.py taxonomy-seed

Write-Host "[5/5] flask --app wsgi.py vocab-seed --path static/seed_data --replace-lessons"
flask --app wsgi.py vocab-seed --path "static/seed_data" --replace-lessons

Write-Host "Done reseed DB."
