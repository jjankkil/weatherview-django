# Startup script for debug configuration (PowerShell)
# Sets default environment variables for local development

# Activate virtual environment if it exists
if (Test-Path ".venv\Scripts\Activate.ps1") {
    Write-Host "Activating virtual environment..."
    & ".venv\Scripts\Activate.ps1"
} else {
    Write-Host "Warning: Virtual environment not found at .venv\Scripts\Activate.ps1" -ForegroundColor Yellow
    Write-Host "Please create one with: python -m venv .venv" -ForegroundColor Yellow
}

# Generate a random SECRET_KEY for debug if not set
if (-not $env:WVD_SECRET_KEY) {
    Write-Host "Generating temporary SECRET_KEY for debug..."
    $env:WVD_SECRET_KEY = python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
    Write-Host "Generated temporary SECRET_KEY for debug: $($env:WVD_SECRET_KEY)"
}

# Set debug mode
$env:WVD_DEBUG = "True"

# Set allowed hosts for local development
$env:WVD_ALLOWED_HOSTS = "localhost,127.0.0.1,0.0.0.0"

# Set session cookie age (optional, defaults to 14 days)
$env:WVD_SESSION_COOKIE_AGE = "1209600"

# Load secrets from .env if present
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), 'Process')
        }
    }
}

# Run the development server
python manage.py runserver 0.0.0.0:8000
