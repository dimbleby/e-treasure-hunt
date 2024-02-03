#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import aiohttp
from pydantic import BaseModel, HttpUrl

SERVER = "http://localhost:8000"
USERNAME = "admin"
PASSWORD = "adminpasswordhere"  # noqa: S105


class Hint(BaseModel):
    number: int
    image: HttpUrl


class Level(BaseModel):
    number: int
    name: str
    description: str = ""
    latitude: str
    longitude: str
    tolerance: int
    hints: list[Hint] = []


class Page(BaseModel):
    next: HttpUrl | None = None
    results: list[Level] = []


async def download_hint(
    session: aiohttp.ClientSession,
    path: Path,
    level: Level,
    hint: Hint,
) -> None:
    async with session.get(hint.image.unicode_string()) as r:
        if not r.ok:
            print(f"Error downloading level {level.number} image {hint.number}")
            print(await r.text())

        r.raise_for_status()

        assert hint.image.path is not None
        suffix = Path(hint.image.path).suffix
        image_file = path / f"image{hint.number}{suffix}"

        with image_file.open("wb") as f:
            async for chunk, _end in r.content.iter_chunks():
                f.write(chunk)


def save_level(path: Path, level: Level) -> None:
    print(f"Saving level {level.number}")
    path.mkdir(parents=True, exist_ok=True)

    about = {
        "name": level.name,
        "latitude": level.latitude,
        "longitude": level.longitude,
        "tolerance": level.tolerance,
    }
    about_json = path / "about.json"
    with about_json.open("w") as f:
        json.dump(about, f, indent=2)

    if level.description:
        blurb_txt = path / "blurb.txt"
        blurb_txt.write_text(level.description)


async def main(path: Path) -> None:
    async with aiohttp.ClientSession() as session:
        next_page: HttpUrl | None = HttpUrl(f"{SERVER}/api/levels")

        while next_page is not None:
            async with session.get(
                next_page.unicode_string(), auth=aiohttp.BasicAuth(USERNAME, PASSWORD)
            ) as r:
                body = await r.text()
                if not r.ok:
                    print("Error downloading levels")
                    print(body)

                r.raise_for_status()

                page = Page.model_validate_json(body)

            hint_downloads = []
            for level in page.results:
                level_dir = path / f"level-{level.number:02d}"
                save_level(level_dir, level)
                for hint in level.hints:
                    hint_download = download_hint(session, level_dir, level, hint)
                    hint_downloads.append(hint_download)

            await asyncio.gather(*hint_downloads)

            next_page = page.next


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--target",
        type=Path,
        default=Path("download"),
        help="Directory in which to save levels",
    )
    args = parser.parse_args()

    asyncio.run(main(args.target))
