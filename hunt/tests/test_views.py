"""Tests for hunt views."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.core.files.base import ContentFile
from django.test import Client
from django.urls import reverse

from hunt.models import AppSetting, Hint

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.contrib.auth.models import User

    from hunt.models import Level


@pytest.fixture
def client() -> Client:
    """Django test client."""
    return Client()


@pytest.fixture
def logged_in_client(client: Client, user: User) -> Client:
    """Django test client logged in as a regular user."""
    client.force_login(user)
    return client


@pytest.fixture
def staff_client(client: Client, staff_user: User) -> Client:
    """Django test client logged in as staff."""
    client.force_login(staff_user)
    return client


class TestGoHome:
    """Tests for go_home view."""

    def test_go_home_redirects_to_login(self, client: Client) -> None:
        """Unauthenticated users should be redirected to login."""
        response = client.get(reverse("go-home"))
        assert response.status_code == 302
        assert "/accounts/login/" in response.url  # type: ignore[attr-defined]

    def test_go_home_player_redirects_to_home(self, logged_in_client: Client) -> None:
        """Regular users should be redirected to /home."""
        response = logged_in_client.get(reverse("go-home"))
        assert response.status_code == 302
        assert response.url == "/home"  # type: ignore[attr-defined]

    def test_go_home_staff_redirects_to_mgmt(self, staff_client: Client) -> None:
        """Staff users should be redirected to /mgmt."""
        response = staff_client.get(reverse("go-home"))
        assert response.status_code == 302
        assert response.url == "/mgmt"  # type: ignore[attr-defined]


@pytest.mark.django_db
class TestHome:
    """Tests for home view."""

    def test_home_requires_login(self, client: Client) -> None:
        """Home page requires authentication."""
        response = client.get(reverse("home"))
        assert response.status_code == 302
        assert "/accounts/login/" in response.url  # type: ignore[attr-defined]

    def test_home_renders_welcome(self, logged_in_client: Client, level: Level) -> None:
        """Home page should render welcome template."""
        _ = level  # Fixture creates level in database
        response = logged_in_client.get(reverse("home"))
        assert response.status_code == 200


@pytest.mark.django_db
class TestSearch:
    """Tests for search view."""

    def test_search_requires_login(self, client: Client) -> None:
        """Search page requires authentication."""
        response = client.get(reverse("search"))
        assert response.status_code == 302

    def test_search_renders_search_template(self, logged_in_client: Client) -> None:
        """Search page should render search template."""
        response = logged_in_client.get(reverse("search"))
        assert response.status_code == 200


class TestDoSearch:
    """Tests for do_search view."""

    def test_do_search_redirects_to_search_without_params(
        self, logged_in_client: Client
    ) -> None:
        """do_search should redirect to search without coordinates."""
        response = logged_in_client.get(reverse("do-search"))
        assert response.status_code == 302
        assert response.url == "/search"  # type: ignore[attr-defined]


@pytest.mark.django_db
class TestNothing:
    """Tests for nothing view."""

    def test_nothing_requires_login(self, client: Client) -> None:
        """Nothing page requires authentication."""
        response = client.get(reverse("nothing-here"))
        assert response.status_code == 302

    def test_nothing_renders(self, logged_in_client: Client) -> None:
        """Nothing page should render."""
        response = logged_in_client.get(reverse("nothing-here"))
        assert response.status_code == 200


@pytest.mark.django_db
class TestOops:
    """Tests for oops view."""

    def test_oops_requires_login(self, client: Client) -> None:
        """Oops page requires authentication."""
        response = client.get(reverse("oops"))
        assert response.status_code == 302

    def test_oops_renders(self, logged_in_client: Client) -> None:
        """Oops page should render."""
        response = logged_in_client.get(reverse("oops"))
        assert response.status_code == 200


@pytest.mark.django_db
class TestLevels:
    """Tests for levels list view."""

    def test_levels_requires_login(self, client: Client) -> None:
        """Levels page requires authentication."""
        response = client.get(reverse("levels"))
        assert response.status_code == 302

    def test_levels_renders(self, logged_in_client: Client, level: Level) -> None:
        """Levels page should render."""
        _ = level  # Fixture creates level in database
        response = logged_in_client.get(reverse("levels"))
        assert response.status_code == 200


@pytest.mark.django_db
class TestLevel:
    """Tests for level view."""

    def test_level_requires_login(self, client: Client) -> None:
        """Level page requires authentication."""
        response = client.get(reverse("level", args=[1]))
        assert response.status_code == 302

    def test_level_renders_for_current_level(
        self,
        logged_in_client: Client,
        create_level: Callable[..., Level],
    ) -> None:
        """Level page should render for current level."""
        # Create level 0 (previous), level 1 (current), level 2 for hint prep
        create_level(number=0, name="Level 0")
        level = create_level(number=1)
        create_level(number=2)

        # Add hints to level 1
        for i in range(5):
            hint = Hint(level=level, number=i)
            hint.image.save(f"hint_{i}.jpg", ContentFile(b"fake"))

        response = logged_in_client.get(reverse("level", args=[1]))
        assert response.status_code == 200

    def test_level_oops_for_future_level(
        self,
        logged_in_client: Client,
        level: Level,
    ) -> None:
        """Level page should show oops for future levels."""
        _ = level  # Fixture creates level in database
        # User is at level 1, try to access level 5
        response = logged_in_client.get(reverse("level", args=[5]))
        assert response.status_code == 200


@pytest.mark.django_db
class TestMgmt:
    """Tests for management views."""

    def test_mgmt_requires_staff(self, logged_in_client: Client) -> None:
        """Management page requires staff status."""
        response = logged_in_client.get(reverse("mgmt"))
        assert response.status_code == 302

    def test_mgmt_renders_for_staff(self, staff_client: Client) -> None:
        """Management page should render for staff."""
        response = staff_client.get(reverse("mgmt"))
        assert response.status_code == 200

    def test_level_mgmt_requires_staff(self, logged_in_client: Client) -> None:
        """Level management page requires staff status."""
        response = logged_in_client.get(reverse("level-mgmt"))
        assert response.status_code == 302

    def test_level_mgmt_renders_for_staff(self, staff_client: Client) -> None:
        """Level management page should render for staff."""
        response = staff_client.get(reverse("level-mgmt"))
        assert response.status_code == 200


class TestHuntEvents:
    """Tests for hunt events download."""

    def test_events_requires_staff(self, logged_in_client: Client) -> None:
        """Events download requires staff status."""
        response = logged_in_client.get(reverse("events"))
        assert response.status_code == 302

    def test_events_returns_csv(self, staff_client: Client) -> None:
        """Events should return a CSV file."""
        response = staff_client.get(reverse("events"))
        assert response.status_code == 200
        assert response["Content-Type"] == "text/csv"


@pytest.mark.django_db
class TestMaps:
    """Tests for map views."""

    def test_map_requires_login(self, client: Client) -> None:
        """Map page requires authentication."""
        response = client.get(reverse("map"))
        assert response.status_code == 302

    def test_alt_map_requires_login(self, client: Client) -> None:
        """Alt map page requires authentication."""
        response = client.get(reverse("alt-map"))
        assert response.status_code == 302

    def test_default_map_uses_alt_when_configured(
        self, logged_in_client: Client
    ) -> None:
        """Default map should use alt map when configured."""
        AppSetting.objects.create(active=True, use_alternative_map=True)

        response = logged_in_client.get(reverse("map"))
        assert response.status_code == 200

    def test_default_map_uses_alt_without_api_key(
        self,
        logged_in_client: Client,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Default map should use alt map when no Google API key."""
        monkeypatch.delenv("GM_API_KEY", raising=False)

        response = logged_in_client.get(reverse("map"))
        assert response.status_code == 200

    def test_default_map_uses_google_with_api_key(
        self,
        logged_in_client: Client,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Default map should use Google map when API key is set."""
        monkeypatch.setenv("GM_API_KEY", "test-api-key")

        response = logged_in_client.get(reverse("map"))
        assert response.status_code == 200

    def test_alt_map_renders(self, logged_in_client: Client) -> None:
        """Alt map should render."""
        response = logged_in_client.get(reverse("alt-map"))
        assert response.status_code == 200


@pytest.mark.django_db
class TestHint:
    """Tests for hint request view."""

    def test_hint_requires_login(self, client: Client) -> None:
        """Hint request requires authentication."""
        response = client.get(reverse("hint"))
        assert response.status_code == 302

    def test_hint_redirects(self, logged_in_client: Client) -> None:
        """Hint view should redirect."""
        response = logged_in_client.get(reverse("hint"))
        assert response.status_code == 302
