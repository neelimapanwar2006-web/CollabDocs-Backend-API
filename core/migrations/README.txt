Generate the initial migration after installing requirements and configuring .env:

python manage.py makemigrations core
python manage.py migrate

Commit the generated 0001_initial.py file to GitHub. The custom UUID User model must be present in this first migration.
