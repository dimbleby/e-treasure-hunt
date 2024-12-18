from __future__ import annotations

import json
from typing import TYPE_CHECKING
from uuid import uuid4

from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from hunt.constants import HINTS_PER_LEVEL
from hunt.models import Hint, Level
from hunt.third_party.apimixin import AllowPUTAsCreateMixin

if TYPE_CHECKING:
    from rest_framework.request import Request


EXTENSIONS = {"image/jpeg": ".jpg", "image/png": ".png"}


class HintSerializer(serializers.ModelSerializer[Hint]):
    class Meta:
        model = Hint
        fields = ("number", "image")


class LevelSerializer(serializers.ModelSerializer[Level]):
    hints = HintSerializer(many=True, read_only=True)

    class Meta:
        model = Level
        fields = (
            "number",
            "name",
            "description",
            "latitude",
            "longitude",
            "tolerance",
            "hints",
        )


class LevelViewSet(AllowPUTAsCreateMixin[Level], viewsets.ModelViewSet[Level]):
    queryset = Level.objects.all().order_by("number")
    serializer_class = LevelSerializer
    http_method_names = (
        "delete",
        "get",
        "head",
        "patch",
        "post",
        "put",
    )

    @action(
        detail=True,
        methods=["post"],
        url_path="hint",
        parser_classes=[MultiPartParser],
    )
    def save_hint(self, request: Request, pk: str) -> Response:
        try:
            data = request.data["data"]
            details = json.loads(data)
            number = details["number"]
        except (KeyError, ValueError):
            return Response(
                "Hint number not provided", status=status.HTTP_400_BAD_REQUEST
            )

        if not isinstance(number, int):
            return Response(
                f"Hint '{number}' is not an integer", status=status.HTTP_400_BAD_REQUEST
            )

        if number >= HINTS_PER_LEVEL:
            return Response(
                f"Hint '{number}' is too high", status=status.HTTP_400_BAD_REQUEST
            )

        # Check that we have a file, and that it seems to be an image.
        try:
            upload = request.data["file"]
        except KeyError:
            return Response("No file attached", status=status.HTTP_400_BAD_REQUEST)

        extension = EXTENSIONS.get(upload.content_type)
        if extension is None:
            return Response(
                f"Bad content type: {upload.content_type}",
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get the level.
        try:
            level = Level.objects.get(number=pk)
        except Level.DoesNotExist:
            return Response(f"Level {pk} not found", status=status.HTTP_404_NOT_FOUND)

        # Update the old hint, if it exists, else create a new one.
        created = False
        try:
            hint = level.hints.get(number=number)
            if hint.image:
                hint.image.delete()
        except Hint.DoesNotExist:
            hint = Hint(level=level, number=number)
            created = True

        filename = f"{uuid4()}{extension}"
        hint.image.save(filename, upload.file)

        serializer = HintSerializer(hint, context={"request": request})
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(serializer.data, status=status_code)
