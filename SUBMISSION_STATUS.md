# Submission status

This package contains the source-code scaffold, detailed README, environment template and 17-request Postman collection.

**Important before submission:** the initial database migration is not pre-generated in this archive. After installing dependencies and configuring PostgreSQL, run `python manage.py makemigrations core` and commit the generated `core/migrations/0001_initial.py`. This first migration must include the custom UUID `core.User` model. Then run migrations against a clean database.

- [ ] Generate and commit initial migration.
- [ ] Run `python manage.py check`.
- [ ] Run `python manage.py migrate` against a clean PostgreSQL database.
- [ ] Run `python manage.py test` and resolve any environment-specific issues.
- [ ] Test every Postman request; replace variables with actual UUIDs.
- [ ] Record and link the 5–10 minute demo video in README.
- [ ] Confirm the exact 17 endpoint definitions against any endpoint table supplied separately by the instructor.
