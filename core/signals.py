
"""
Document lifecycle audit signal.

Whenever a Document is created or updated:
1. Create a new DocumentVersion.
2. Create an AuditLog entry.
3. Keep both operations inside a database transaction.

When called through DocumentSerializer, these operations also participate
in the serializer's transaction.atomic() block.
"""

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Document, DocumentVersion, AuditLog


@receiver(post_save, sender=Document)
def record_document_change(sender, instance, created, **kwargs):

    # Django's created argument identifies whether this is a new document.
    action = "created" if created else "updated"

    # Keep version creation and audit logging together.
    with transaction.atomic():

        # Calculate the next version number for this document.
        next_number = instance.versions.count() + 1

        # Save a snapshot of the document.
        DocumentVersion.objects.create(
            document=instance,
            version_number=next_number,
            title=instance.title,
            content=instance.content,
            changed_by=instance.created_by,
        )

        # Record the document lifecycle event.
        AuditLog.objects.create(
            actor=instance.created_by,
            action=action,
            model_name="Document",
            object_id=str(instance.pk),
            details={
                "title": instance.title
            },
        )
