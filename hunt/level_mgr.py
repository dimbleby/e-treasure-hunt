from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from hunt.constants import HINTS_PER_LEVEL
from hunt.models import Hint, Level

if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile
    from django.http import HttpRequest


def upload_new_level(request: HttpRequest) -> str:
    failure_redirect = "/level-mgmt?success=False"

    if not request.user.has_perm("hunt.add_level"):
        return failure_redirect

    if not request.POST:
        return failure_redirect

    lvl_num = request.POST.get("lvl-num")
    if lvl_num is None:
        return failure_redirect

    failure_redirect = f"{failure_redirect}&next={lvl_num}"

    # Get the existing level, or create a new one.
    try:
        level = Level.objects.get(number=lvl_num)
    except Level.DoesNotExist:
        level = Level(number=lvl_num)

    def suffix(name: str) -> str:
        """Return normalized filename suffix."""
        return Path(name).suffix.lower()

    # Gather up the needed information.
    uploaded_files: list[UploadedFile[bytes]] = request.FILES.getlist(
        "files", default=[]
    )
    files = [(file.name, file) for file in uploaded_files if file.name is not None]
    about_file = next((file for name, file in files if suffix(name) == ".json"), None)
    blurb = next((file for name, file in files if suffix(name) == ".txt"), None)
    images = [
        (name, file)
        for name, file in files
        if suffix(name) in {".jpeg", ".jpg", ".png"}
    ]
    images.sort(key=lambda named_file: named_file[0].lower())

    # Level info and images are mandatory, we can manage without a description.
    if about_file is None or len(images) != HINTS_PER_LEVEL:
        return failure_redirect

    # Read level info, and read or default level description.
    about = json.load(about_file)
    lines = (
        [] if blurb is None else [line.decode("utf-8") for line in blurb.readlines()]
    )
    description = "".join(line for line in lines if line.strip())

    # Update the level.
    level.name = about.get("name")
    level.description = description
    level.latitude = about.get("latitude")
    level.longitude = about.get("longitude")
    level.tolerance = about.get("tolerance")
    level.full_clean()
    level.save()

    # Delete old hints.
    old_hints = level.hints.all()
    old_hints.delete()

    # Create new hints.
    for number, (name, file) in enumerate(images):
        hint = Hint(level=level, number=number)
        filename = f"{uuid4()}{suffix(name)}"
        hint.image.save(filename, file)

    return f"/level-mgmt?success=True&next={int(lvl_num) + 1}"
