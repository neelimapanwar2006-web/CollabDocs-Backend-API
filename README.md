# CollabDocs – Backend API

A Django REST Framework backend for a collaborative document platform. It supports users, workspaces, workspace membership and roles, documents, immutable document version snapshots, threaded comments, tags, and audit logs.

> **Submission note:** This repository is a backend-only project. Postman is the API client; no frontend is included.

## 1. Features mapped to the brief

- UUID primary keys on all application-owned models.
- A custom `AbstractUser` model (`core.User`) uses a UUID primary key.
- Workspace owner is added as an `admin` member in the same `transaction.atomic()` block as workspace creation.
- `WorkspaceMember` has a database `UniqueConstraint` on `(workspace, user)`.
- `Workspace.is_active` defaults to `True`.
- `WorkspaceMember.Role` and `Document.Status` use `TextChoices`.
- Documents are versioned on every save. The post-save signal creates the next version using `Document.versions.count() + 1`.
- Document saves, version snapshots, and audit entries execute in the serializer's atomic transaction.
- Comments support threaded replies through a self-referential nullable foreign key.
- Tags and documents have a many-to-many relationship.
- Request logging middleware prints method, path, response status and duration in milliseconds.
- Querysets use `select_related`, `prefetch_related`, `Q`, `Count`, `aggregate`, `values`, and ID `__in` filtering where appropriate.
- Serializers use `SerializerMethodField` and custom validation.

## 2. Data model

| Model | Purpose |
|---|---|
| User | Django built-in user model for account details |
| Workspace | Collaboration space and owner |
| WorkspaceMember | User membership and role |
| Document | Workspace document and tags |
| DocumentVersion | Snapshot created on each document save |
| Comment | Document comment and threaded reply |
| Tag | Reusable document label |
| AuditLog | Records important model actions |

All eight models, including the custom `core.User` model, use UUID primary keys. `AUTH_USER_MODEL` is configured before initial migrations. Always generate the first migration before running `migrate`.

## 3. Setup

### Requirements
- Python 3.10+
- PostgreSQL 14+ (PostgreSQL 17 is also suitable)
- Git
- Postman

### Windows PowerShell

```powershell
git clone <YOUR_PUBLIC_GITHUB_REPOSITORY_URL>
cd CollabDocs_Submission

python -m venv venv
.\venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt

Copy-Item .env.example .env
```

Edit `.env` with your local PostgreSQL database name, username and password. Create the database first:

```sql
CREATE DATABASE collabdocs;
```

Then run:

```powershell
python manage.py makemigrations core
python manage.py migrate
python manage.py check
python manage.py createsuperuser
python manage.py runserver
```

API base URL: `http://127.0.0.1:8000/api/`

For a quick local smoke test without PostgreSQL, set `DB_ENGINE=sqlite` in `.env`. The final submission demonstration should use PostgreSQL if required by the evaluator.

## 4. API endpoint catalogue

The router exposes CRUD routes for users, workspaces, documents, comments and tags, plus custom actions and read-only audit logs.

| # | Method | Endpoint | Purpose |
|---:|---|---|---|
| 1 | GET | `/api/users/` | List users; supports search and active filter |
| 2 | POST | `/api/users/` | Create user |
| 3 | GET | `/api/users/{id}/` | Retrieve user |
| 4 | PUT/PATCH | `/api/users/{id}/` | Update user |
| 5 | DELETE | `/api/users/{id}/` | Delete user |
| 6 | GET | `/api/workspaces/` | List workspaces |
| 7 | POST | `/api/workspaces/` | Create workspace and owner admin membership atomically |
| 8 | GET | `/api/workspaces/{id}/` | Retrieve workspace |
| 9 | GET | `/api/workspaces/{id}/stats/` | Workspace document/comment/member counts |
| 10 | GET/POST | `/api/workspaces/{id}/members/` | List/add members; duplicate returns 409 |
| 11 | GET/POST | `/api/documents/` | List/create documents |
| 12 | GET/PUT/PATCH/DELETE | `/api/documents/{id}/` | Document detail and updates |
| 13 | GET | `/api/documents/{id}/versions/` | List document version snapshots |
| 14 | GET | `/api/documents/summary/` | Document counts grouped by status |
| 15 | GET/POST | `/api/comments/` | List/create comments and replies |
| 16 | GET/POST | `/api/tags/` | List/create tags |
| 17 | GET | `/api/audit-logs/` | List audit events |

Additional router routes include tag detail/update/delete and `/api/tags/{id}/documents/`. The exact list above groups method variants as endpoint operations for the project checklist.

### Useful filters
- Documents: `?workspace=<uuid>&status=draft&created_after=2026-01-01&created_before=2026-12-31`
- Documents OR search: `?q=design` searches title **or** content.
- Documents ID filter: `?ids=<uuid1>,<uuid2>`
- Users: `?is_active=true&search=alex`
- Workspaces: `?is_active=true&search=engineering`
- Comments: `?document=<uuid>&author=<user_id>`
- Audit logs: `?action=created&model_name=Document`

## 5. Sample request bodies

### Create user – POST `/api/users/`
```json
{
  "username": "alex",
  "email": "alex@example.com",
  "password": "StrongPass123!",
  "first_name": "Alex",
  "last_name": "Morgan"
}
```

### Create workspace – POST `/api/workspaces/`
```json
{
  "name": "Product Team",
  "description": "Shared product planning workspace",
  "owner": 1
}
```

### Add workspace member – POST `/api/workspaces/{id}/members/`
```json
{
  "user": 2,
  "role": "editor"
}
```

### Create document – POST `/api/documents/`
```json
{
  "workspace": "REPLACE-WITH-WORKSPACE-UUID",
  "title": "Project plan",
  "content": "Milestones and responsibilities",
  "status": "draft",
  "created_by": 1,
  "tags": []
}
```

### Update document – PATCH `/api/documents/{id}/`
```json
{
  "title": "Project plan – revised",
  "content": "Updated milestones and owners"
}
```

### Create comment – POST `/api/comments/`
```json
{
  "document": "REPLACE-WITH-DOCUMENT-UUID",
  "author": 1,
  "body": "Please review this section.",
  "parent": null
}
```

### Create tag – POST `/api/tags/`
```json
{
  "name": "python",
  "color": "#3776AB"
}
```

## 6. Transactions, versioning and audit trail

1. Workspace serializer wraps workspace insertion and initial admin membership insertion in one `transaction.atomic()` block.
2. Document serializer wraps document creation/update and tag changes in one atomic block.
3. The `post_save` signal is registered by `CoreConfig.ready()`.
4. The signal creates a `DocumentVersion` with `version_number = instance.versions.count() + 1` and writes an `AuditLog` event.
5. A failure raised inside the transaction rolls back the document write, version and audit record together.

### Demonstrating rollback
For a controlled demonstration, use Django shell or a temporary test:

```python
from django.db import transaction
from django.contrib.auth.models import User
from core.models import Workspace, Document

user = User.objects.first()
workspace = Workspace.objects.first()
try:
    with transaction.atomic():
        doc = Document.objects.create(
            workspace=workspace,
            title="Rollback demonstration",
            content="This row must not remain",
            created_by=user,
        )
        raise RuntimeError("Intentional failure to demonstrate rollback")
except RuntimeError:
    pass

# The document, version and signal-generated audit row are all rolled back.
```

## 7. Middleware demonstration

Start the server and make any Postman request. The terminal prints a line similar to:

```text
GET /api/documents/ status=200 duration_ms=8.42
```

## 8. Run tests

```powershell
python manage.py test
```

The included tests cover workspace owner membership and document version/audit creation. Extend these with APIClient tests for every route before final evaluation.

## 9. Postman

Import `postman_collection.json` from the repository root. Set the collection variable `base_url` to `http://127.0.0.1:8000/api`. Replace example IDs with UUIDs and user IDs returned by your own API.

## 10. Demo video checklist (5–10 minutes)

1. Show the running server and PostgreSQL configuration (do not reveal `.env` secrets).
2. Create a user and workspace; show owner membership with `admin` role.
3. Create a document and update it; show two version records.
4. Show the corresponding AuditLog entries.
5. Add a comment, threaded reply and tag.
6. Show workspace stats or document summary aggregation.
7. Show middleware request logs in the terminal.
8. Run the rollback example and prove the created row was not persisted.
9. Add the Loom/Google Drive demo URL here before submission.

**Demo video:** `ADD_YOUR_LOOM_OR_GOOGLE_DRIVE_LINK_HERE`

## 11. GitHub submission checklist

- [ ] Public GitHub repository
- [ ] `.env.example` committed; real `.env` excluded
- [ ] Pinned `requirements.txt`
- [ ] All migrations committed
- [ ] README setup instructions completed
- [ ] Postman collection committed at repository root
- [ ] PostgreSQL migration tested from a clean database
- [ ] All required API requests tested in Postman
- [ ] Demo video uploaded and linked above
