#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate

# Create superuser automatically (only if it doesn't exist)
python manage.py shell << EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('lasco, 'lascontenga32@gmail.com', '90515272Lasco.')
    print("Superuser created successfully")
else:
    print("Superuser already exists")
EOF