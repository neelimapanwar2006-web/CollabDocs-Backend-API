from django.contrib import admin
from django.contrib.auth import get_user_model
from .models import Workspace, WorkspaceMember, Document, DocumentVersion, Comment, Tag, AuditLog

admin.site.register(get_user_model())
admin.site.register([Workspace, WorkspaceMember, Document, DocumentVersion, Comment, Tag, AuditLog])
