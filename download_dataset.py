#!/usr/bin/env python3
"""Read a Google Sheets song table and turn supplied YouTube URLs into MP3s.

Expected columns: Song Title, Youtube Links 1, ..., Youtube Links 5.
Use only audio you own or are authorized to download and use.
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import Request, urlopen

try:
    import yt_dlp
except ImportError:
    print("Missing dependencies. Run: python -m pip install -r requirements.txt")
    sys.exit(1)

try:
    import static_ffmpeg
except ImportError:
    print("Missing dependencies. Run: python -m pip install -r requirements.txt")
    sys.exit(1)

try:
    from mutagen.easyid3 import EasyID3
except ImportError:
    print("Missing dependencies. Run: python -m pip install -r requirements.txt")
    sys.exit(1)

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.json"
LOCAL_CSV_FILE = BASE_DIR / "songs.csv"
OUTPUT_DIR = BASE_DIR / "dataset_mp3"
MANIFEST_FILE = BASE_DIR / "manifest.csv"
ID_REGISTRY_FILE = BASE_DIR / ".dataset_ids.json"

LINK_COLUMNS = [f"youtubelinks{i}" for i in range(1, 6)]
MANIFEST_FIELDS = [
    "id", "song_title", "youtube_title", "channel", "duration_seconds",
    "youtube_url", "source_row", "source_column", "file", "status",
]


def normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").strip().lower())


def safe_filename(value: str) -> str:
    """Remove characters that are unsafe or invalid in common file systems."""
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    value = value[:160].rstrip(" .")
    return value or "untitled_song"


def youtube_video_id(url: str) -> str | None:
    """Extract a YouTube video ID so tracking parameters do not create duplicates."""
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return None
    host = (parsed.hostname or "").lower()
    if host == "youtu.be":
        candidate = parsed.path.strip("/").split("/")[0]
    elif host == "youtube.com" or host.endswith(".youtube.com"):
        query = parse_qs(parsed.query)
        candidate = (query.get("v") or [""])[0]
        if not candidate:
            match = re.match(r"^/(?:shorts|embed|live)/([^/?]+)", parsed.path)
            candidate = match.group(1) if match else ""
    else:
        return None
    return candidate if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate or "") else None


def safe_youtube_url(url: str) -> bool:
    return youtube_video_id(url) is not None


def read_config() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"Missing config.json. Copy config.example.json to config.json "
            f"or create it using the README instructions."
        )
    with CONFIG_FILE.open("r", encoding="utf-8") as file:
        config = json.load(file)
    source = (config.get("source") or "google_sheet").strip().lower()
    if source not in {"google_sheet", "csv"}:
        raise ValueError('config.json "source" must be "google_sheet" or "csv"')
    config["source"] = source
    return config


def build_google_csv_url(sheet_url: str, worksheet_gid: str = "") -> str:
    """Convert a normal Google Sheets share URL into a CSV export URL."""
    parsed = urlparse(sheet_url.strip())
    if "docs.google.com" not in (parsed.hostname or ""):
        raise ValueError("google_sheet_url must be a Google Sheets URL")
    if "/export" in parsed.path and "format=csv" in parsed.query:
        return sheet_url

    match = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]+)", parsed.path)
    if not match:
        raise ValueError("Could not find the spreadsheet ID in google_sheet_url")
    sheet_id = match.group(1)

    query = parse_qs(parsed.query)
    gid = (worksheet_gid or "").strip()
    if not gid and query.get("gid"):
        gid = query["gid"][0]

    export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    if gid:
        export_url += f"&gid={quote(gid)}"
    return export_url


def fetch_google_sheet_csv(config: dict[str, Any]) -> str:
    sheet_url = (config.get("google_sheet_url") or "").strip()
    if not sheet_url:
        raise ValueError('Set "google_sheet_url" in config.json')
    export_url = build_google_csv_url(
        sheet_url,
        str(config.get("worksheet_gid") or ""),
    )
    request = Request(
        export_url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; DatasetCollector/1.0)"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            content = response.read()
    except HTTPError as exc:
        if exc.code in {401, 403}:
            raise RuntimeError(
                "Google Sheets denied access. Set General access to "
                "'Anyone with the link - Viewer', or publish the sheet to the web."
            ) from exc
        raise RuntimeError(f"Google Sheets returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach Google Sheets: {exc.reason}") from exc

    text = content.decode("utf-8-sig", errors="replace")
    if "<html" in text[:1000].lower() or "<!doctype html" in text[:1000].lower():
        raise RuntimeError(
            "Google returned a web page instead of CSV. Check that the sheet is "
            "shared as 'Anyone with the link - Viewer' and that worksheet_gid points "
            "to the tab containing the dataset."
        )
    return text


def rows_from_sheet_csv(text: str) -> list[dict[str, str]]:
    """Read rows by expected headers; blank link cells are ignored."""
    raw_rows = list(csv.reader(io.StringIO(text)))
    header_index = None
    header_values: list[str] = []
    normalized: list[str] = []

    # Detect the header row even if a title or blank row appears above the table.
    for index, values in enumerate(raw_rows[:50]):
        current = [normalize_header(value) for value in values]
        if "songtitle" in current and all(col in current for col in LINK_COLUMNS):
            header_index = index
            header_values = values
            normalized = current
            break

    if header_index is None:
        raise ValueError(
            "Could not find the required headers. The sheet must contain "
            "'Song Title' and 'Youtube Links 1' through 'Youtube Links 5'. "
            "No 'label' column is required."
        )

    title_index = normalized.index("songtitle")
    link_indexes = {column: normalized.index(column) for column in LINK_COLUMNS}
    output: list[dict[str, str]] = []
    seen_video_ids: set[str] = set()
    duplicate_count = 0

    for row_number, values in enumerate(raw_rows[header_index + 1:], start=header_index + 2):
        title = values[title_index].strip() if title_index < len(values) else ""
        if not title and not any(
            idx < len(values) and values[idx].strip()
            for idx in link_indexes.values()
        ):
            continue

        if not title:
            print(f"WARNING: Sheet row {row_number} has links but no Song Title; skipped.")
            continue

        for column in LINK_COLUMNS:
            idx = link_indexes[column]
            url = values[idx].strip() if idx < len(values) else ""
            if not url:
                continue
            video_id = youtube_video_id(url)
            if not video_id:
                print(
                    f"WARNING: Sheet row {row_number}, {column} is not a valid "
                    "YouTube video URL; skipped."
                )
                continue
            if video_id in seen_video_ids:
                duplicate_count += 1
                print(
                    f"WARNING: Duplicate video {video_id} at row {row_number}, "
                    f"{column}; skipped."
                )
                continue
            seen_video_ids.add(video_id)
            output.append({
                "song_title": title,
                "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
                "video_id": video_id,
                "source_row": str(row_number),
                "source_column": header_values[idx].strip() if idx < len(header_values) else column,
            })

    print(f"Duplicate video links skipped: {duplicate_count}")
    return output


def rows_from_local_csv() -> list[dict[str, str]]:
    if not LOCAL_CSV_FILE.exists():
        raise FileNotFoundError(f"Local CSV not found: {LOCAL_CSV_FILE}")
    with LOCAL_CSV_FILE.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames or not {"song_title", "youtube_url"}.issubset(reader.fieldnames):
            raise ValueError("songs.csv must contain: song_title,youtube_url")
        output = []
        seen_video_ids: set[str] = set()
        for row_number, row in enumerate(reader, start=2):
            title = (row.get("song_title") or "").strip()
            url = (row.get("youtube_url") or "").strip()
            if not title and not url:
                continue
            video_id = youtube_video_id(url)
            if not title or not video_id:
                print(f"WARNING: Invalid local CSV row {row_number}; skipped.")
                continue
            if video_id in seen_video_ids:
                print(f"WARNING: Duplicate video {video_id} at local CSV row {row_number}; skipped.")
                continue
            seen_video_ids.add(video_id)
            output.append({
                "song_title": title,
                "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
                "video_id": video_id,
                "source_row": str(row_number),
                "source_column": "youtube_url",
            })
        return output


def load_records(config: dict[str, Any]) -> list[dict[str, str]]:
    if config["source"] == "google_sheet":
        csv_text = fetch_google_sheet_csv(config)
        return rows_from_sheet_csv(csv_text)
    return rows_from_local_csv()


def load_id_registry() -> dict[str, str]:
    registry: dict[str, str] = {}
    if ID_REGISTRY_FILE.exists():
        try:
            data = json.loads(ID_REGISTRY_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                registry = {
                    str(video_id): str(dataset_id)
                    for video_id, dataset_id in data.items()
                    if str(dataset_id).isdigit()
                }
        except (OSError, json.JSONDecodeError):
            print("WARNING: Could not read .dataset_ids.json; starting a new ID registry.")

    # Help preserve IDs from an existing manifest when upgrading an older version.
    if not registry and MANIFEST_FILE.exists():
        try:
            with MANIFEST_FILE.open("r", newline="", encoding="utf-8-sig") as file:
                for row in csv.DictReader(file):
                    video_id = youtube_video_id(row.get("youtube_url", ""))
                    dataset_id = (row.get("id") or "").strip()
                    if video_id and dataset_id.isdigit():
                        registry[video_id] = dataset_id
        except OSError:
            pass
    return registry


def save_id_registry(registry: dict[str, str]) -> None:
    ID_REGISTRY_FILE.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def assign_stable_ids(records: list[dict[str, str]], registry: dict[str, str]) -> None:
    numeric_ids = [int(value) for value in registry.values() if value.isdigit()]
    next_id = max(numeric_ids, default=0) + 1
    for record in records:
        video_id = record["video_id"]
        if video_id not in registry:
            registry[video_id] = f"{next_id:04d}"
            next_id += 1
        record["id"] = registry[video_id]


def write_title_tag(mp3_path: Path, title: str) -> None:
    try:
        tags = EasyID3(str(mp3_path))
    except Exception:
        tags = EasyID3()
    tags["title"] = [title]
    tags.save(str(mp3_path))


def write_manifest(rows: list[dict[str, Any]]) -> None:
    with MANIFEST_FILE.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    # Install/download static ffmpeg + ffprobe in the Python environment.
    # This avoids requiring Homebrew, sudo, or administrator access.
    try:
        static_ffmpeg.add_paths()
        print("FFmpeg and ffprobe configured from the Python environment.")
    except Exception as exc:
        print(f"Could not prepare FFmpeg automatically: {exc}")
        print("Check server internet access, then run: python -m pip install -r requirements.txt")
        sys.exit(1)

    try:
        config = read_config()
        records = load_records(config)
    except Exception as exc:
        print(f"Could not load dataset source: {exc}")
        sys.exit(1)

    if not records:
        print("No valid song links were found in the selected source.")
        return

    registry = load_id_registry()
    assign_stable_ids(records, registry)
    save_id_registry(registry)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    download_options = {
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
    print(f"Source: {config['source']}")
    print(f"Unique YouTube recordings: {len(records)}")
    print(f"MP3 output folder: {OUTPUT_DIR}\n")

    for index, record in enumerate(records, start=1):
        dataset_id = record["id"]
        title = record["song_title"]
        url = record["youtube_url"]
        song_folder = safe_filename(title or "untitled_song")
        song_dir = OUTPUT_DIR / song_folder
        filename = f"{dataset_id} - {song_folder}.mp3"
        target = song_dir / filename
        song_dir.mkdir(parents=True, exist_ok=True)

        row: dict[str, Any] = {
            "id": dataset_id,
            "song_title": title,
            "youtube_title": "",
            "channel": "",
            "duration_seconds": "",
            "youtube_url": url,
            "source_row": record.get("source_row", ""),
            "source_column": record.get("source_column", ""),
            "file": str(target.relative_to(BASE_DIR)),
            "status": "error",
        }
        print(
            f"[{index}/{len(records)}] [{dataset_id}] {title} "
            f"({record.get('source_column', 'URL')})"
        )

        try:
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

            options = dict(download_options)
            options["outtmpl"] = str(song_dir / f"{Path(filename).stem}.%(ext)s")
            with yt_dlp.YoutubeDL(options) as ydl:
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
    print("Check the manifest and verify that recordings match the intended sources.")


if __name__ == "__main__":
    main()
