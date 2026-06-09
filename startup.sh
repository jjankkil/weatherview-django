#!/bin/bash

# Startup script for debug configuration (Bash/Linux/WSL)
# Sets default environment variables for local development

set -e

# Activate virtual environment if it exists
if [ -f "venv/bin/activate" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
else
    echo "Warning: Virtual environment not found at venv/bin/activate"
    echo "Please create one with: python -m venv venv"
fi

# Generate a random SECRET_KEY for debug if not set
if [ -z "$WVD_SECRET_KEY" ]; then
    echo "Generating temporary SECRET_KEY for debug..."
    export WVD_SECRET_KEY=$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
    echo "Generated temporary SECRET_KEY for debug: $WVD_SECRET_KEY"
fi

# Set debug mode
export WVD_DEBUG=True

# Set allowed hosts for local development
export WVD_ALLOWED_HOSTS="localhost,127.0.0.1,0.0.0.0"

# Set session cookie age (optional, defaults to 14 days)
export WVD_SESSION_COOKIE_AGE=1209600

# Load secrets from .env if present
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

# Run the development server
python manage.py runserver 0.0.0.0:8000
