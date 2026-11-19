
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from rest_framework import serializers

from .models import (
    Workspace,
    WorkspaceMember,
    Document,
    DocumentVersion,
    Comment,
    Tag,
    AuditLog,
)


User = get_user_model()


# ============================================================
# USER SERIALIZER
# ============================================================

class UserSerializer(serializers.ModelSerializer):

    workspace_count = serializers.SerializerMethodField()

    class Meta:
        model = User

        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "password",
            "workspace_count",
        ]

        extra_kwargs = {
            "password": {
                "write_only": True,
                "required": False,
            }
        }

    def get_workspace_count(self, obj):
        # Use the queryset annotation to avoid an extra query.
        return getattr(
            obj,
            "workspace_total",
            obj.workspace_memberships.count()
        )

    def create(self, validated_data):

        password = validated_data.pop("password", None)

        user = User(**validated_data)

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save()

        return user

    def update(self, instance, validated_data):

        password = validated_data.pop("password", None)

        for key, value in validated_data.items():
            setattr(instance, key, value)

        if password:
            instance.set_password(password)

        instance.save()

        return instance


# ============================================================
# WORKSPACE MEMBER SERIALIZER
# ============================================================

class WorkspaceMemberSerializer(serializers.ModelSerializer):

    username = serializers.CharField(
        source="user.username",
        read_only=True
    )

    class Meta:
        model = WorkspaceMember

        fields = [
            "id",
            "workspace",
            "user",
            "username",
            "role",
            "joined_at",
        ]

        read_only_fields = [
            "id",
            "joined_at",
            "username",
        ]


# ============================================================
# WORKSPACE SERIALIZER
# ============================================================

class WorkspaceSerializer(serializers.ModelSerializer):

    owner_username = serializers.CharField(
        source="owner.username",
        read_only=True
    )

    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Workspace

        fields = [
            "id",
            "name",
            "description",
            "owner",
            "owner_username",
            "is_active",
            "member_count",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "owner_username",
            "member_count",
        ]

    def validate_name(self, value):

        if not value.strip():
            raise serializers.ValidationError(
                "Workspace name cannot be blank."
            )

        return value.strip()

    def get_member_count(self, obj):

        # Use the annotation from WorkspaceViewSet.
        return getattr(
            obj,
            "member_total",
            obj.members.count()
        )

    def create(self, validated_data):

        try:
            # Workspace and initial owner membership
            # must succeed or fail together.
            with transaction.atomic():

                workspace = Workspace.objects.create(
                    **validated_data
                )

                WorkspaceMember.objects.create(
                    workspace=workspace,
                    user=workspace.owner,
                    role=WorkspaceMember.Role.ADMIN,
                )

        except IntegrityError:
            raise serializers.ValidationError(
                {
                    "owner": (
                        "Workspace owner membership could not be created."
                    )
                }
            )

        return workspace


# ============================================================
# DOCUMENT VERSION SERIALIZER
# ============================================================

class DocumentVersionSerializer(serializers.ModelSerializer):

    changed_by_username = serializers.CharField(
        source="changed_by.username",
        read_only=True
    )

    class Meta:
        model = DocumentVersion

        fields = [
            "id",
            "document",
            "version_number",
            "title",
            "content",
            "changed_by",
            "changed_by_username",
            "created_at",
        ]


# ============================================================
# DOCUMENT SERIALIZER
# ============================================================

class DocumentSerializer(serializers.ModelSerializer):

    created_by_username = serializers.CharField(
        source="created_by.username",
        read_only=True
    )

    tags = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Tag.objects.all(),
        required=False
    )

    version_count = serializers.SerializerMethodField()

    class Meta:
        model = Document

        fields = [
            "id",
            "workspace",
            "title",
            "content",
            "status",
            "created_by",
            "created_by_username",
            "tags",
            "version_count",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "created_by_username",
            "version_count",
        ]

    def validate_title(self, value):

        if not value.strip():
            raise serializers.ValidationError(
                "Document title is required."
            )

        return value.strip()

    def validate(self, attrs):

        # During partial update, use existing instance values
        # for fields not included in the request.
        document_status = attrs.get(
            "status",
            getattr(
                self.instance,
                "status",
                Document.Status.DRAFT
            )
        )

        content = attrs.get(
            "content",
            getattr(self.instance, "content", "")
        )

        # Published documents must contain meaningful content.
        if (
            document_status == Document.Status.PUBLISHED
            and not content.strip()
        ):
            raise serializers.ValidationError(
                {
                    "content": (
                        "Published documents cannot have empty content."
                    )
                }
            )

        return attrs

    def get_version_count(self, obj):

        # Use the annotation from DocumentViewSet.
        return getattr(
            obj,
            "version_total",
            obj.versions.count()
        )

    def create(self, validated_data):

        tags = validated_data.pop("tags", [])

        with transaction.atomic():

            # Document post_save signal can create the initial version
            # and audit log within this transaction.
            document = Document.objects.create(
                **validated_data
            )

            if tags:
                document.tags.set(tags)

        return document

    def update(self, instance, validated_data):

        tags = validated_data.pop("tags", None)

        with transaction.atomic():

            for key, value in validated_data.items():
                setattr(instance, key, value)

            # Saving the document triggers its post_save signal.
            instance.save()

            # Update tags only when tags are included in the request.
            if tags is not None:
                instance.tags.set(tags)

        return instance


# ============================================================
# COMMENT SERIALIZER
# ============================================================

class CommentSerializer(serializers.ModelSerializer):

    author_username = serializers.CharField(
        source="author.username",
        read_only=True
    )

    reply_count = serializers.SerializerMethodField()

    class Meta:
        model = Comment

        fields = [
            "id",
            "document",
            "author",
            "author_username",
            "body",
            "parent",
            "reply_count",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "author_username",
            "reply_count",
        ]

    def validate(self, attrs):

        parent = attrs.get("parent")

        document = attrs.get(
            "document",
            getattr(self.instance, "document", None)
        )

        # A reply must belong to the same document as its parent.
        if parent and document and parent.document_id != document.id:
            raise serializers.ValidationError(
                {
                    "parent": (
                        "A reply must belong to the same document "
                        "as its parent."
                    )
                }
            )

        return attrs

    def get_reply_count(self, obj):

        return obj.replies.count()


# ============================================================
# TAG SERIALIZER
# ============================================================

class TagSerializer(serializers.ModelSerializer):

    document_count = serializers.SerializerMethodField()

    class Meta:
        model = Tag

        fields = [
            "id",
            "name",
            "color",
            "document_count",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "document_count",
            "created_at",
        ]

    def get_document_count(self, obj):

        # Use the annotation from TagViewSet.
        return getattr(
            obj,
            "document_total",
            obj.documents.count()
        )


# ============================================================
# AUDIT LOG SERIALIZER
# ============================================================

class AuditLogSerializer(serializers.ModelSerializer):

    actor_username = serializers.CharField(
        source="actor.username",
        read_only=True
    )

    class Meta:
        model = AuditLog

        fields = [
            "id",
            "actor",
            "actor_username",
            "action",
            "model_name",
            "object_id",
            "details",
            "created_at",
        ]
