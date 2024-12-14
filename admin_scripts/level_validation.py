#!/usr/bin/env python3

"""
Client-side validator for levels.

Some of these checks just make sure that the hunt website won't reject the upload
(without having to actually attempt such an upload).

Other checks are for admin-y things like:
- Tolerances that are suspiciously tight
- README.md files (which are supposed to contain a detailed explanation of the
  structure of the level for the GM's use)
  being smaller than blurb.txt files (which are supposed to be a hunter-consumable
  précis of the level answer/concept once they've solved it)

The checking for the names of the images is stricter than the server requires.
The server will consider the images in alphabetical order, so (say) 1-image.jpg,
2-image.jpg, ... is just a valid a scheme as clue.png, hint1.png, etc.
However, this strict checking does serve to remind the admin to make sure that the
level setter has not come up with their own novel image-naming scheme that wouldn't
work once the server considers the images alphabetically.
"""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path
from typing import TextIO

CONTENT_TYPES = {
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
}


def unzip_all() -> None:
    for file_ in Path(ALL_LEVELS_DIR).iterdir():
        if file_.suffix != ".zip":
            continue

        folder_path = ALL_LEVELS_DIR / file_.stem
        if folder_path.exists():
            continue

        with zipfile.ZipFile(file_) as zip_ref:
            zip_ref.extractall(folder_path)


def validate_format() -> None:
    count = 0
    for dir_path in Path(ALL_LEVELS_DIR).iterdir():
        if not dir_path.is_dir():
            continue

        if "DUMMY" in dir_path.name:
            continue

        count += 1
        if (dir_path / "about.json").exists():
            # Check json for values
            with (dir_path / "about.json").open() as f:
                check_json(f, dir_path.name)
        else:
            print("No json in", dir_path)

        readme_path: Path | None = None
        for possible_readme_filename in (
            "readme.md",
            "README.md",
            "README.txt",
            "readme.txt",
        ):
            possible_readme_path = dir_path / possible_readme_filename
            if possible_readme_path.exists():
                readme_path = possible_readme_path
                # Assume only one readme exists
                break

        if readme_path is None:
            print("No readme in", dir_path)

        if not (dir_path / "blurb.txt").exists():
            print("No blurb in", dir_path)

        # Check readme is bigger than blurb
        if (dir_path / "blurb.txt").exists() and readme_path is not None:
            blurb_size = (dir_path / "blurb.txt").stat().st_size
            readme_size = readme_path.stat().st_size
            if blurb_size > readme_size:
                print("Blurb is bigger than readme for", dir_path)

        images = [
            file_
            for file_ in dir_path.iterdir()
            if file_.suffix.lower() in CONTENT_TYPES
        ]

        # Should find exactly the right number - check the file extensions if not.
        if len(images) != 5:
            print(f"Found {len(images)} images in {dir_path}")
        else:
            images.sort(key=lambda x: x.name.lower())
            if not images[0].name.startswith("clue"):
                print("No clue in", dir_path)

            # Check the images aren't too big or bad things will happen to the
            # upload. We don't want a repeat of the Wawrinka incident.
            for i, image in enumerate(images):
                image_size = image.stat().st_size
                if image_size > 3 * 1000 * 1000:  # ~3 MB
                    print(
                        "Image",
                        image,
                        "is too big in",
                        dir_path,
                        "size = ",
                        f"{image_size:,}",
                    )

                if not image.name.startswith("hint"):
                    print("No hint", i, "in", dir_path)

    print("Analyzed", count, "levels")


def check_coord(coord: str, coord_name: str, filename: str) -> None:
    lat = float(coord)
    if not lat:
        print("No", coord_name, "for level", filename)
    elif lat == 0.0:
        print("  warning: 0", coord_name, "for level", filename)

    numbers_and_dp_only = re.sub(r"[^0-9.]", "", coord)
    a, b = numbers_and_dp_only.split(".") if "." in coord else (coord, "")
    if len(b) > 5:
        print("More than 5 dp for", coord_name, "for level", filename, ":", coord)
    if len(a) + len(b) > 7:
        print("More than 7 digits for", coord_name, "for level", filename, ":", coord)


def check_json(f: TextIO, filename: str) -> None:
    json_data = json.load(f)
    if not len(json_data["name"]) > 0:
        print("No name for level", filename)

    check_coord(json_data["latitude"], "lat", filename)
    check_coord(json_data["longitude"], "long", filename)

    tol = int(json_data["tolerance"])
    if not tol:
        print("No tolerance for level", filename)
    elif tol < 1:
        print("0 tolerance for level", filename)
    elif tol < 20:
        print("Too-low-resolution tolerance of", tol, "for level", filename)
    elif tol <= 50:
        print("  warning: Small tolerance of", tol, "for level", filename)


if __name__ == "__main__":
    argparser = argparse.ArgumentParser()
    argparser.add_argument(
        "input_directory",
        help="Path to a directory containing the (possibly zipped) "
        "levels to be examined",
    )
    args = argparser.parse_args()
    ALL_LEVELS_DIR = Path(args.input_directory)
    assert ALL_LEVELS_DIR.exists()
    assert ALL_LEVELS_DIR.is_dir()

    unzip_all()
    validate_format()
