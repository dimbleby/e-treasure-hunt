"""Tests for the REST API."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from hunt.models import Hint, Level

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.contrib.auth.models import User


@pytest.fixture
def api_client() -> APIClient:
    """DRF test client."""
    return APIClient()


@pytest.fixture
def staff_api_client(api_client: APIClient, staff_user: User) -> APIClient:
    """DRF test client logged in as staff."""
    api_client.force_authenticate(user=staff_user)
    return api_client


@pytest.fixture
def regular_api_client(api_client: APIClient, user: User) -> APIClient:
    """DRF test client logged in as regular user."""
    api_client.force_authenticate(user=user)
    return api_client


class TestLevelAPI:
    """Tests for Level API endpoints."""

    def test_list_levels_requires_staff(self, regular_api_client: APIClient) -> None:
        """Regular users cannot list levels."""
        response = regular_api_client.get("/api/levels")
        assert response.status_code == 403

    def test_list_levels_as_staff(
        self, staff_api_client: APIClient, create_level: Callable[..., Level]
    ) -> None:
        """Staff can list levels."""
        create_level(number=1)
        create_level(number=2, name="Level 2")

        response = staff_api_client.get("/api/levels")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2

    def test_get_level_detail(self, staff_api_client: APIClient, level: Level) -> None:
        """Staff can get level details."""
        response = staff_api_client.get(f"/api/levels/{level.number}")
        assert response.status_code == 200
        data = response.json()
        assert data["number"] == level.number
        assert data["name"] == level.name

    def test_create_level(self, staff_api_client: APIClient) -> None:
        """Staff can create a new level."""
        response = staff_api_client.post(
            "/api/levels",
            {
                "number": 1,
                "name": "New Level",
                "description": "Test description",
                "latitude": "51.50722",
                "longitude": "-0.12750",
                "tolerance": 50,
            },
            format="json",
        )
        assert response.status_code == 201
        assert Level.objects.filter(number=1).exists()

    def test_update_level(self, staff_api_client: APIClient, level: Level) -> None:
        """Staff can update an existing level."""
        response = staff_api_client.patch(
            f"/api/levels/{level.number}",
            {"name": "Updated Name"},
            format="json",
        )
        assert response.status_code == 200
        level.refresh_from_db()
        assert level.name == "Updated Name"

    def test_delete_level(self, staff_api_client: APIClient, level: Level) -> None:
        """Staff can delete a level."""
        response = staff_api_client.delete(f"/api/levels/{level.number}")
        assert response.status_code == 204
        assert not Level.objects.filter(number=level.number).exists()

    def test_put_creates_level_if_not_exists(self, staff_api_client: APIClient) -> None:
        """PUT should create a level if it doesn't exist."""
        response = staff_api_client.put(
            "/api/levels/99",
            {
                "number": 99,
                "name": "New Level",
                "description": "Test",
                "latitude": "51.50722",
                "longitude": "-0.12750",
                "tolerance": 50,
            },
            format="json",
        )
        assert response.status_code == 201
        assert Level.objects.filter(number=99).exists()


class TestHintAPI:
    """Tests for Hint API endpoint."""

    def test_upload_hint_without_data(
        self, staff_api_client: APIClient, level: Level
    ) -> None:
        """Uploading hint without data should fail."""
        response = staff_api_client.post(
            f"/api/levels/{level.number}/hint",
            {},
            format="multipart",
        )
        assert response.status_code == 400

    def test_upload_hint_without_file(
        self, staff_api_client: APIClient, level: Level
    ) -> None:
        """Uploading hint without file should fail."""
        response = staff_api_client.post(
            f"/api/levels/{level.number}/hint",
            {"data": json.dumps({"number": 0})},
            format="multipart",
        )
        assert response.status_code == 400

    def test_upload_hint_invalid_number(
        self, staff_api_client: APIClient, level: Level
    ) -> None:
        """Uploading hint with invalid number should fail."""
        image = SimpleUploadedFile("test.jpg", b"fake image", content_type="image/jpeg")
        response = staff_api_client.post(
            f"/api/levels/{level.number}/hint",
            {"data": json.dumps({"number": "abc"}), "file": image},
            format="multipart",
        )
        assert response.status_code == 400

    def test_upload_hint_number_too_high(
        self, staff_api_client: APIClient, level: Level
    ) -> None:
        """Uploading hint with number >= HINTS_PER_LEVEL should fail."""
        image = SimpleUploadedFile("test.jpg", b"fake image", content_type="image/jpeg")
        response = staff_api_client.post(
            f"/api/levels/{level.number}/hint",
            {"data": json.dumps({"number": 10}), "file": image},
            format="multipart",
        )
        assert response.status_code == 400

    def test_upload_hint_bad_content_type(
        self, staff_api_client: APIClient, level: Level
    ) -> None:
        """Uploading hint with bad content type should fail."""
        file = SimpleUploadedFile(
            "test.txt", b"not an image", content_type="text/plain"
        )
        response = staff_api_client.post(
            f"/api/levels/{level.number}/hint",
            {"data": json.dumps({"number": 0}), "file": file},
            format="multipart",
        )
        assert response.status_code == 400

    def test_upload_hint_nonexistent_level(self, staff_api_client: APIClient) -> None:
        """Uploading hint to nonexistent level should fail."""
        image = SimpleUploadedFile("test.jpg", b"fake image", content_type="image/jpeg")
        response = staff_api_client.post(
            "/api/levels/999/hint",
            {"data": json.dumps({"number": 0}), "file": image},
            format="multipart",
        )
        assert response.status_code == 404

    def test_upload_hint_success(
        self, staff_api_client: APIClient, level: Level
    ) -> None:
        """Successfully uploading a hint."""
        image = SimpleUploadedFile("test.jpg", b"fake image", content_type="image/jpeg")
        response = staff_api_client.post(
            f"/api/levels/{level.number}/hint",
            {"data": json.dumps({"number": 0}), "file": image},
            format="multipart",
        )
        assert response.status_code == 201
        assert level.hints.filter(number=0).exists()

    def test_upload_hint_replaces_existing(
        self, staff_api_client: APIClient, level: Level
    ) -> None:
        """Uploading hint with existing number should replace it."""
        # Create initial hint
        hint = Hint(level=level, number=0)
        hint.image.save("old.jpg", ContentFile(b"old image"))

        # Upload replacement
        image = SimpleUploadedFile("new.jpg", b"new image", content_type="image/jpeg")
        response = staff_api_client.post(
            f"/api/levels/{level.number}/hint",
            {"data": json.dumps({"number": 0}), "file": image},
            format="multipart",
        )
        assert response.status_code == 200  # 200 for update, not 201
        assert level.hints.filter(number=0).count() == 1
