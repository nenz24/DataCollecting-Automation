# Data Collecting Automation — YouTube Audio Dataset

A small Python utility for organizing YouTube audio recordings into a consistently named MP3 dataset.

## Features

- Reads the exact YouTube links supplied by you in `songs.csv`; it does not search for songs.
- Uses one CSV row per recording, so the same song can have multiple recordings.
- Creates one folder per song title.
- Assigns a sequential numeric dataset ID globally across all songs (for example, `0001`, `0002`).
- Keeps both the ID and song title in the filename, e.g. `dataset_mp3/Raja Semesta/0002 - Raja Semesta.mp3`.
- Uses your supplied song title for the MP3 title tag.
- Writes `manifest.csv` with the dataset ID, supplied title, YouTube title, channel, duration, URL, output path, and processing status.
- Skips output files that already exist.

> Only download audio that you own or are authorized to download and use. Check applicable platform terms and rights before downloading.

## Requirements

- macOS (instructions below use Homebrew)
- Python 3.10+
- FFmpeg

## Setup

Install FFmpeg:

```bash
brew install ffmpeg
```

From the repository directory, create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Add your songs

Edit `songs.csv` using Numbers, Excel, or a text editor. The file has two columns:

```csv
song_title,youtube_url
Goodness of God,https://www.youtube.com/watch?v=VIDEO_ID_1
Goodness of God,https://www.youtube.com/watch?v=VIDEO_ID_2
Build My Life,https://youtu.be/VIDEO_ID_3
```

- One row represents one recording.
- Multiple rows may use the same `song_title`; each row receives its own globally unique numeric ID.
- Paste the exact YouTube URL in `youtube_url`.
- Replace the example URLs before running the script.
- IDs are generated from row order, starting at `0001`. Keep the existing row order and append new rows at the bottom so the IDs of already-downloaded recordings do not change.

## Run

```bash
python download_dataset.py
```

The script creates a separate folder per song title and keeps both ID and title in each filename:

```text
dataset_mp3/
├── Raja Semesta/
│   ├── 0002 - Raja Semesta.mp3
│   ├── 0003 - Raja Semesta.mp3
│   └── 0004 - Raja Semesta.mp3
└── Ha.. Hallelujah/
    ├── 0005 - Ha.. Hallelujah.mp3
    └── 0006 - Ha.. Hallelujah.mp3

manifest.csv
```

IDs are global across the dataset and do not reset within each song folder. The `manifest.csv` records the corresponding folder and MP3 path for each CSV row.

If you previously downloaded MP3s using the old flat-folder layout, the updated script does not move existing files automatically. The new version writes into song-specific subfolders. Move/backup your older files if you need them, or re-run the script to create the new folder structure.

## Notes

The first YouTube search result is **not** selected automatically: the URL is taken exactly from your CSV. Check the manifest and listen to the recordings to ensure that each recording matches the intended source.
