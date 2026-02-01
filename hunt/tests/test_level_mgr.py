"""Tests for level management (upload) functionality."""

from __future__ import annotations

import io
import json
from typing import TYPE_CHECKING

import pytest
from django.contrib.auth.models import Permission, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory

from hunt.level_mgr import upload_new_level
from hunt.models import Hint, Level

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.fixture
def user_with_add_level_perm(user: User) -> User:
    """Create a user with permission to add levels."""
    perm = Permission.objects.get(codename="add_level")
    user.user_permissions.add(perm)
    user.save()
    # Refetch to clear permission cache
    return User.objects.get(pk=user.pk)


class TestUploadNewLevel:
    """Tests for upload_new_level function."""

    def test_upload_without_permission(self, user: User) -> None:
        """Upload should fail without add_level permission."""
        factory = RequestFactory()
        request = factory.post("/add-level", {"lvl-num": "1"})
        request.user = user

        result = upload_new_level(request)
        assert result == "/level-mgmt?success=False"

    def test_upload_without_post_data(self, user_with_add_level_perm: User) -> None:
        """Upload should fail without POST data."""
        factory = RequestFactory()
        request = factory.get("/add-level")
        request.user = user_with_add_level_perm

        result = upload_new_level(request)
        assert result == "/level-mgmt?success=False"

    def test_upload_without_level_number(self, user_with_add_level_perm: User) -> None:
        """Upload should fail without level number."""
        factory = RequestFactory()
        request = factory.post("/add-level", {})
        request.user = user_with_add_level_perm

        result = upload_new_level(request)
        assert result == "/level-mgmt?success=False"

    def test_upload_without_json_file(self, user_with_add_level_perm: User) -> None:
        """Upload should fail without JSON config file."""
        factory = RequestFactory()
        # Create 5 image files but no JSON
        files = [
            SimpleUploadedFile(f"hint{i}.jpg", b"fake image", content_type="image/jpeg")
            for i in range(5)
        ]
        request = factory.post("/add-level", {"lvl-num": "1", "files": files})
        request.user = user_with_add_level_perm

        result = upload_new_level(request)
        assert result == "/level-mgmt?success=False&next=1"

    def test_upload_without_enough_images(self, user_with_add_level_perm: User) -> None:
        """Upload should fail without exactly 5 images."""
        factory = RequestFactory()
        about = json.dumps(
            {
                "name": "Test Level",
                "latitude": "51.50722",
                "longitude": "-0.12750",
                "tolerance": 50,
            }
        )
        json_file = SimpleUploadedFile(
            "about.json", about.encode(), content_type="application/json"
        )
        # Only 3 images instead of 5
        images = [
            SimpleUploadedFile(f"hint{i}.jpg", b"fake image", content_type="image/jpeg")
            for i in range(3)
        ]
        request = factory.post(
            "/add-level", {"lvl-num": "1", "files": [json_file, *images]}
        )
        request.user = user_with_add_level_perm

        result = upload_new_level(request)
        assert result == "/level-mgmt?success=False&next=1"

    @pytest.mark.django_db
    def test_upload_success_new_level(self, user_with_add_level_perm: User) -> None:
        """Successfully upload a new level."""
        factory = RequestFactory()
        about = json.dumps(
            {
                "name": "Test Level",
                "latitude": "51.50722",
                "longitude": "-0.12750",
                "tolerance": 50,
            }
        )
        json_file = SimpleUploadedFile(
            "about.json", about.encode(), content_type="application/json"
        )
        images = [
            SimpleUploadedFile(f"hint{i}.jpg", b"fake image", content_type="image/jpeg")
            for i in range(5)
        ]
        request = factory.post(
            "/add-level", {"lvl-num": "1", "files": [json_file, *images]}
        )
        request.user = user_with_add_level_perm

        result = upload_new_level(request)

        assert result == "/level-mgmt?success=True&next=2"
        assert Level.objects.filter(number=1).exists()
        level = Level.objects.get(number=1)
        assert level.name == "Test Level"
        assert level.hints.count() == 5

    @pytest.mark.django_db
    def test_upload_success_with_description(
        self, user_with_add_level_perm: User
    ) -> None:
        """Successfully upload a level with description file."""
        factory = RequestFactory()
        about = json.dumps(
            {
                "name": "Test Level",
                "latitude": "51.50722",
                "longitude": "-0.12750",
                "tolerance": 50,
            }
        )
        json_file = SimpleUploadedFile(
            "about.json", about.encode(), content_type="application/json"
        )
        description = SimpleUploadedFile(
            "description.txt",
            b"This is a test description.\nWith multiple lines.",
            content_type="text/plain",
        )
        images = [
            SimpleUploadedFile(f"hint{i}.jpg", b"fake image", content_type="image/jpeg")
            for i in range(5)
        ]
        request = factory.post(
            "/add-level",
            {"lvl-num": "1", "files": [json_file, description, *images]},
        )
        request.user = user_with_add_level_perm

        result = upload_new_level(request)

        assert result == "/level-mgmt?success=True&next=2"
        level = Level.objects.get(number=1)
        assert "test description" in level.description

    @pytest.mark.django_db
    def test_upload_replaces_existing_level(
        self,
        user_with_add_level_perm: User,
        create_level: Callable[..., Level],
    ) -> None:
        """Uploading to existing level should replace it."""
        # Create existing level with hints
        existing = create_level(number=1, name="Old Level")
        for i in range(5):
            hint = Hint(level=existing, number=i)
            hint.image.save(f"old{i}.jpg", io.BytesIO(b"old"))

        factory = RequestFactory()
        about = json.dumps(
            {
                "name": "New Level",
                "latitude": "52.00000",
                "longitude": "-0.20000",
                "tolerance": 100,
            }
        )
        json_file = SimpleUploadedFile(
            "about.json", about.encode(), content_type="application/json"
        )
        images = [
            SimpleUploadedFile(f"new{i}.png", b"new image", content_type="image/png")
            for i in range(5)
        ]
        request = factory.post(
            "/add-level", {"lvl-num": "1", "files": [json_file, *images]}
        )
        request.user = user_with_add_level_perm

        result = upload_new_level(request)

        assert result == "/level-mgmt?success=True&next=2"
        level = Level.objects.get(number=1)
        assert level.name == "New Level"
        assert level.hints.count() == 5
