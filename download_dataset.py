#!/usr/bin/env python3
"""Convert explicitly supplied YouTube URLs to numbered MP3 dataset files.

Use only audio you own or are authorized to download and use. This script does
not search YouTube; it processes the exact URLs entered in songs.csv.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    import yt_dlp
except ImportError:
    print("Missing dependencies. Run: python -m pip install -r requirements.txt")
    sys.exit(1)

try:
    from mutagen.easyid3 import EasyID3
except ImportError:
    print("Missing dependencies. Run: python -m pip install -r requirements.txt")
    sys.exit(1)

BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "songs.csv"
OUTPUT_DIR = BASE_DIR / "dataset_mp3"
MANIFEST_FILE = BASE_DIR / "manifest.csv"

INPUT_FIELDS = ["song_title", "youtube_url"]
MANIFEST_FIELDS = [
    "id",
    "song_title",
    "youtube_title",
    "channel",
    "duration_seconds",
    "youtube_url",
    "file",
    "status",
]


def safe_filename(value: str) -> str:
    """Remove characters that are unsafe or invalid in common file systems."""
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    value = value[:160].rstrip(" .")
    return value or "untitled_song"


def is_youtube_url(url: str) -> bool:
    try:
        host = (urlparse(url.strip()).hostname or "").lower()
    except ValueError:
        return False
    return (
        host == "youtu.be"
        or host == "youtube.com"
        or host.endswith(".youtube.com")
    )


def load_songs() -> list[dict[str, str]]:
    if not INPUT_FILE.exists():
        with INPUT_FILE.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=INPUT_FIELDS)
            writer.writeheader()
            writer.writerow({
                "song_title": "Example Song",
                "youtube_url": "https://www.youtube.com/watch?v=REPLACE_WITH_VIDEO_ID",
            })
        print(f"Created template: {INPUT_FILE}")
        print("Edit songs.csv with your song titles and exact YouTube URLs, then run again.")
        return []

    with INPUT_FILE.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames or not set(INPUT_FIELDS).issubset(reader.fieldnames):
            raise ValueError("songs.csv must contain: song_title,youtube_url")

        songs: list[dict[str, str]] = []
        for raw in reader:
            title = (raw.get("song_title") or "").strip()
            url = (raw.get("youtube_url") or "").strip()
            if not title and not url:
                continue
            songs.append({"song_title": title, "youtube_url": url})
    return songs


def write_title_tag(mp3_path: Path, title: str) -> None:
    try:
        tags = EasyID3(str(mp3_path))
    except Exception:
        tags = EasyID3()
    tags["title"] = [title]
    tags.save(str(mp3_path))


def write_manifest(rows: list[dict[str, Any]]) -> None:
    """Write one manifest row per CSV entry, without duplicating old runs."""
    with MANIFEST_FILE.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    try:
        songs = load_songs()
    except Exception as exc:
        print(f"Could not read songs.csv: {exc}")
        sys.exit(1)

    if not songs:
        print("No songs to process. Add rows to songs.csv and run again.")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    options = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "ignoreerrors": False,
        "nooverwrites": True,
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "0",
        }],
    }
    info_options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
    }

    results: list[dict[str, Any]] = []
    print(f"Rows to process: {len(songs)}")
    print(f"MP3 output folder: {OUTPUT_DIR}\n")

    for index, song in enumerate(songs, start=1):
        dataset_id = f"{index:04d}"
        title = song["song_title"]
        url = song["youtube_url"]
        song_folder = safe_filename(title or "untitled_song")
        song_dir = OUTPUT_DIR / song_folder
        filename = f"{dataset_id} - {song_folder}.mp3"
        target = song_dir / filename

        row: dict[str, Any] = {
            "id": dataset_id,
            "song_title": title,
            "youtube_title": "",
            "channel": "",
            "duration_seconds": "",
            "youtube_url": url,
            "file": str(target.relative_to(BASE_DIR)),
            "status": "error",
        }
        print(f"[{index}/{len(songs)}] [{dataset_id}] {title or '(missing title)'}")

        try:
            if not title:
                raise ValueError("song_title is required")
            if not url or not is_youtube_url(url):
                raise ValueError("youtube_url must be a valid YouTube or youtu.be URL")

            # Store each song title in its own directory.
            song_dir.mkdir(parents=True, exist_ok=True)

            # Existing numbered file is preserved rather than downloaded again.
            if target.exists():
                row["status"] = "already_exists"
                print(f"  Already exists: {target.relative_to(OUTPUT_DIR)}")
                try:
                    with yt_dlp.YoutubeDL(info_options) as ydl:
                        info = ydl.extract_info(url, download=False)
                    if info:
                        row.update({
                            "youtube_title": info.get("title", ""),
                            "channel": info.get("channel") or info.get("uploader") or "",
                            "duration_seconds": info.get("duration") or "",
                        })
                except Exception:
                    pass
                results.append(row)
                print()
                continue

            with yt_dlp.YoutubeDL(info_options) as ydl:
                info = ydl.extract_info(url, download=False)
            if not info:
                raise RuntimeError("Could not read video metadata from this URL")

            row.update({
                "youtube_title": info.get("title", ""),
                "channel": info.get("channel") or info.get("uploader") or "",
                "duration_seconds": info.get("duration") or "",
            })

            download_options = dict(options)
            download_options["outtmpl"] = str(
                song_dir / f"{Path(filename).stem}.%(ext)s"
            )
            with yt_dlp.YoutubeDL(download_options) as ydl:
                ydl.download([url])

            if target.exists():
                write_title_tag(target, title)
                row["status"] = "downloaded"
                print(f"  Saved: {target.relative_to(OUTPUT_DIR)}")
            else:
                row["status"] = "error_output_missing"
                print("  ERROR: MP3 output was not created. Check FFmpeg and yt-dlp.")

        except Exception as exc:
            row["status"] = f"error: {str(exc)[:180]}"
            print(f"  ERROR: {exc}")

        results.append(row)
        print()

    write_manifest(results)
    downloaded = sum(item["status"] == "downloaded" for item in results)
    existing = sum(item["status"] == "already_exists" for item in results)
    errors = sum(item["status"].startswith("error") for item in results)
    print("Finished.")
    print(f"New MP3s:        {downloaded}")
    print(f"Already existed: {existing}")
    print(f"Errors:          {errors}")
    print(f"Audio folder:    {OUTPUT_DIR}")
    print(f"Manifest:        {MANIFEST_FILE}")
    print("Review manifest.csv and verify each recording matches the intended source.")


if __name__ == "__main__":
    main()
