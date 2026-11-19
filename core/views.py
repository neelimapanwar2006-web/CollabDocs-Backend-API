
from django.db import IntegrityError, transaction
from django.contrib.auth import get_user_model
from django.db.models import Count, Q

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import (
    Workspace,
    WorkspaceMember,
    Document,
    DocumentVersion,
    Comment,
    Tag,
    AuditLog,
)

from .serializers import (
    UserSerializer,
    WorkspaceSerializer,
    WorkspaceMemberSerializer,
    DocumentSerializer,
    DocumentVersionSerializer,
    CommentSerializer,
    TagSerializer,
    AuditLogSerializer,
)


User = get_user_model()


# ============================================================
# USER VIEWSET
# ============================================================

class UserViewSet(viewsets.ModelViewSet):

    queryset = User.objects.annotate(
        workspace_total=Count("workspace_memberships", distinct=True)
    ).order_by("id")

    serializer_class = UserSerializer

    filterset_fields = ["is_active"]
    search_fields = ["username", "email", "first_name", "last_name"]
    ordering_fields = ["username", "date_joined"]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()

        return Response(
            {"message": "User deleted successfully."},
            status=status.HTTP_200_OK
        )


# ============================================================
# WORKSPACE VIEWSET
# ============================================================

class WorkspaceViewSet(viewsets.ModelViewSet):

    queryset = Workspace.objects.select_related(
        "owner"
    ).annotate(
        member_total=Count("members", distinct=True)
    ).order_by("-created_at")

    serializer_class = WorkspaceSerializer

    filterset_fields = ["is_active", "owner"]
    search_fields = ["name", "description"]
    ordering_fields = ["created_at", "name"]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            # Workspace creation and owner membership
            # should be completed in one transaction.
            with transaction.atomic():
                self.perform_create(serializer)

        except IntegrityError:
            return Response(
                {
                    "message": (
                        "Workspace creation failed due to a data conflict."
                    )
                },
                status=status.HTTP_409_CONFLICT
            )

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )

    @action(
        detail=True,
        methods=["get", "post"],
        url_path="members"
    )
    def members(self, request, pk=None):

        workspace = self.get_object()

        # GET: Retrieve all members of this workspace.
        if request.method == "GET":

            members = WorkspaceMember.objects.filter(
                workspace=workspace
            ).select_related(
                "user",
                "workspace"
            )

            serializer = WorkspaceMemberSerializer(
                members,
                many=True
            )

            return Response(
                serializer.data,
                status=status.HTTP_200_OK
            )

        # POST: Add a new member to the workspace.
        payload = request.data.copy()
        payload["workspace"] = str(workspace.id)

        serializer = WorkspaceMemberSerializer(data=payload)

        if not serializer.is_valid():

            errors = serializer.errors

            # Handle duplicate workspace-user membership.
            duplicate = any(
                "unique set" in str(error).lower()
                or "already exists" in str(error).lower()
                for error in errors.get("non_field_errors", [])
            )

            if duplicate:
                return Response(
                    {
                        "message": (
                            "This user is already a member "
                            "of this workspace."
                        )
                    },
                    status=status.HTTP_409_CONFLICT
                )

            return Response(
                errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                serializer.save()

        except IntegrityError:
            return Response(
                {
                    "message": (
                        "This user is already a member "
                        "of this workspace."
                    )
                },
                status=status.HTTP_409_CONFLICT
            )

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )

    @action(
        detail=True,
        methods=["get"],
        url_path="stats"
    )
    def stats(self, request, pk=None):

        workspace = self.get_object()

        # Aggregate document and comment counts.
        stats = Document.objects.filter(
            workspace=workspace
        ).aggregate(
            document_count=Count("id", distinct=True),
            comment_count=Count("comments", distinct=True)
        )

        stats["member_count"] = workspace.members.count()

        return Response(
            {
                "workspace_id": str(workspace.id),
                **stats
            },
            status=status.HTTP_200_OK
        )


# ============================================================
# DOCUMENT VIEWSET
# ============================================================

class DocumentViewSet(viewsets.ModelViewSet):

    queryset = Document.objects.select_related(
        "workspace",
        "created_by"
    ).prefetch_related(
        "tags"
    ).annotate(
        comment_total=Count("comments", distinct=True),
        version_total=Count("versions", distinct=True)
    ).order_by("-updated_at")

    serializer_class = DocumentSerializer

    filterset_fields = ["workspace", "status", "created_by"]
    search_fields = ["title", "content"]
    ordering_fields = ["created_at", "updated_at", "title"]

    def get_queryset(self):

        queryset = super().get_queryset()

        # Q object: search in title OR content.
        search = self.request.query_params.get("q")

        if search:
            queryset = queryset.filter(
                Q(title__icontains=search)
                | Q(content__icontains=search)
            )

        # Filter documents created on or after a date.
        created_after = self.request.query_params.get("created_after")

        if created_after:
            queryset = queryset.filter(
                created_at__date__gte=created_after
            )

        # Filter documents created on or before a date.
        created_before = self.request.query_params.get("created_before")

        if created_before:
            queryset = queryset.filter(
                created_at__date__lte=created_before
            )

        # Filter using comma-separated document UUIDs.
        ids = self.request.query_params.get("ids")

        if ids:
            id_list = [
                value.strip()
                for value in ids.split(",")
                if value.strip()
            ]

            queryset = queryset.filter(id__in=id_list)

        return queryset

    def create(self, request, *args, **kwargs):

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            # Document save and its related signal operations
            # should participate in the same transaction.
            with transaction.atomic():
                serializer.save()

        except IntegrityError:
            return Response(
                {
                    "message": (
                        "Document could not be saved "
                        "because of a data conflict."
                    )
                },
                status=status.HTTP_409_CONFLICT
            )

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )

    @action(
        detail=True,
        methods=["get"],
        url_path="versions"
    )
    def versions(self, request, pk=None):

        document = self.get_object()

        versions = document.versions.select_related(
            "changed_by"
        ).all()

        serializer = DocumentVersionSerializer(
            versions,
            many=True
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="summary"
    )
    def summary(self, request):

        summary = Document.objects.values(
            "status"
        ).annotate(
            total=Count("id")
        ).order_by("status")

        return Response(
            {
                "summary": list(summary),
                "total_documents": Document.objects.count()
            },
            status=status.HTTP_200_OK
        )


# ============================================================
# COMMENT VIEWSET
# ============================================================

class CommentViewSet(viewsets.ModelViewSet):

    queryset = Comment.objects.select_related(
        "author",
        "document",
        "parent"
    ).prefetch_related(
        "replies"
    ).order_by("-created_at")

    serializer_class = CommentSerializer

    filterset_fields = ["document", "author", "parent"]
    search_fields = ["body"]
    ordering_fields = ["created_at"]

    def create(self, request, *args, **kwargs):

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        serializer.save()

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )


# ============================================================
# TAG VIEWSET
# ============================================================

class TagViewSet(viewsets.ModelViewSet):

    queryset = Tag.objects.annotate(
        document_total=Count("documents", distinct=True)
    ).order_by("name")

    serializer_class = TagSerializer

    search_fields = ["name"]
    ordering_fields = ["name"]

    @action(
        detail=True,
        methods=["get"],
        url_path="documents"
    )
    def documents(self, request, pk=None):

        tag = self.get_object()

        documents = tag.documents.select_related(
            "workspace",
            "created_by"
        ).prefetch_related(
            "tags"
        )

        serializer = DocumentSerializer(
            documents,
            many=True
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )


# ============================================================
# AUDIT LOG VIEWSET
# ============================================================

class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):

    queryset = AuditLog.objects.select_related(
        "actor"
    ).all()

    serializer_class = AuditLogSerializer

    filterset_fields = ["actor", "action", "model_name"]
    search_fields = ["object_id", "model_name", "action"]
    ordering_fields = ["created_at"]
