#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import aiohttp

if TYPE_CHECKING:
    from collections.abc import Iterable

HINTS_PER_LEVEL = 5

SERVER = "http://localhost:8000"
USERNAME = "admin"
PASSWORD = "adminpasswordhere"  # noqa: S105


CONTENT_TYPES = {
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
}


@dataclass
class Level:
    number: int
    path: Path


class Uploader:
    def __init__(self, session: aiohttp.ClientSession) -> None:
        self.session = session

    async def upload_level_without_hints(self, level: Level) -> None:
        """
        Upload a level, without creating any of its hints.

        :param level: The level to upload.
        """
        about = level.path / "about.json"
        with about.open(encoding="utf-8") as f:
            data = json.load(f)

        data["number"] = level.number

        # It's OK for there to be no blurb, but we report it in case that wasn't what
        # was intended.
        blurb = level.path / "blurb.txt"
        try:
            with blurb.open(encoding="utf-8") as f:
                data["description"] = f.read()
        except FileNotFoundError:
            print(f"No blurb at level {level.number}")
            data["description"] = ""

        url = f"{SERVER}/api/levels/{level.number}"
        auth = aiohttp.BasicAuth(USERNAME, PASSWORD)
        async with self.session.put(url, auth=auth, json=data) as r:
            if not r.ok:
                print(f"Error uploading level {level.number}")
                print(await r.text())

            r.raise_for_status()

    async def upload_hint(self, level: Level, hint: int, image: Path) -> None:
        """
        Upload a hint.

        :param level: The level that the hint belongs to.  The level must already exist.
        :param hint: The hint number.  Zero-indexed.
        :param image: The file containing the hint.
        """
        suffix = image.suffix
        content_type = CONTENT_TYPES.get(suffix.lower())
        if content_type is None:
            msg = f"unrecognized suffix: {suffix}"
            raise RuntimeError(msg)

        with image.open("rb") as f:
            url = f"{SERVER}/api/levels/{level.number}/hint"
            auth = aiohttp.BasicAuth(USERNAME, PASSWORD)
            data = aiohttp.FormData()
            data.add_field(
                "file",
                f,
                filename=image.name,
                content_type=content_type,
            )
            payload = {"number": hint}
            data.add_field(
                "data",
                json.dumps(payload),
                content_type="application/json",
            )
            async with self.session.post(url, auth=auth, data=data) as r:
                if not r.ok:
                    print(f"Error uploading level {level.number} hint {hint}")
                    print(await r.text())

                r.raise_for_status()

    async def upload_level(self, level: Level) -> None:
        """
        Upload a level from a directory, creating all of its hints.

        :param level: The level to upload.
        """
        print(f"Uploading level {level.number}")

        # Find the images.
        images = [
            file
            for file in level.path.iterdir()
            if file.suffix.lower() in CONTENT_TYPES
        ]

        # Should find exactly the right number - check the file extensions if not.
        if len(images) != HINTS_PER_LEVEL:
            msg = f"Found {len(images)} images in {level.path}"
            raise RuntimeError(msg)

        # Create the level.
        await self.upload_level_without_hints(level)

        # Upload the hints.
        images.sort(key=lambda x: x.name.lower())
        hint_uploads = [
            self.upload_hint(level, hint, image) for hint, image in enumerate(images)
        ]
        await asyncio.gather(*hint_uploads)

        print(f"Uploaded level {level.number}")

    async def upload_levels(self, levels: Iterable[Level]) -> None:
        # Tried making this more parallel, the server didn't like it...
        for level in levels:
            await self.upload_level(level)


async def main() -> None:
    # Uploads three levels, including the dummy levels 0 and 4.
    levels = [
        Level(0, Path("/directory/containing/dummy/level")),
        Level(1, Path("/directory/containing/level/one")),
        Level(2, Path("/directory/containing/level/two")),
        Level(3, Path("/directory/containing/level/three")),
        Level(4, Path("/directory/containing/dummy/level")),
    ]

    async with aiohttp.ClientSession() as session:
        uploader = Uploader(session)
        await uploader.upload_levels(levels)


if __name__ == "__main__":
    asyncio.run(main())
