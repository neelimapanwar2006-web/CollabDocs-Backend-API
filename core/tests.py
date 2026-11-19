from django.contrib.auth import get_user_model
User = get_user_model()
from django.test import TestCase
from django.db import transaction
from .models import Workspace, WorkspaceMember, Document, DocumentVersion, AuditLog


class CollabDocsModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="test-password-123")

    def test_workspace_owner_becomes_admin_via_serializer(self):
        from .serializers import WorkspaceSerializer
        serializer = WorkspaceSerializer(data={"name": "Engineering", "owner": self.user.id})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        workspace = serializer.save()
        self.assertTrue(WorkspaceMember.objects.filter(
            workspace=workspace, user=self.user, role=WorkspaceMember.Role.ADMIN
        ).exists())

    def test_document_save_creates_version_and_audit_log(self):
        document = Document.objects.create(
            workspace=self._workspace(), title="First", content="Initial", created_by=self.user
        )
        self.assertEqual(document.versions.count(), 1)
        self.assertTrue(AuditLog.objects.filter(object_id=str(document.id), action="created").exists())
        document.title = "Second"
        document.save()
        self.assertEqual(document.versions.count(), 2)
        self.assertTrue(AuditLog.objects.filter(object_id=str(document.id), action="updated").exists())

    def _workspace(self):
        return Workspace.objects.create(name="Test", owner=self.user)
