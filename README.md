# Data Collecting Automation — YouTube Audio Dataset

A small Python utility for organizing YouTube audio recordings into a consistently named MP3 dataset.

## Features

- Reads the exact YouTube links supplied by you in `songs.csv`; it does not search for songs.
- Uses one CSV row per recording, so the same song can have multiple recordings.
- Assigns a sequential numeric dataset ID based on row order (for example, `0001`, `0002`).
- Saves audio as MP3 and uses your supplied song title for the MP3 title tag.
- Writes `manifest.csv` with the dataset ID, supplied title, YouTube title, channel, duration, URL, output filename, and processing status.
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
- Multiple rows may use the same `song_title`; each row receives its own numeric ID.
- Paste the exact YouTube URL in `youtube_url`.
- Replace the example URLs before running the script.
- IDs are generated from row order, starting at `0001`. Keep row order stable after downloading; adding, removing, or reordering rows may change IDs.

## Run

```bash
python download_dataset.py
```

The script creates:

- `dataset_mp3/` — numbered MP3 files such as `0001 - Goodness of God.mp3`
- `manifest.csv` — a metadata/status record for the current CSV rows

If a numbered MP3 already exists, the script skips downloading that row. If you change the URL but keep the same row order and title, remove or rename the old MP3 before running again.

## Notes

The first YouTube result is **not** selected automatically: the URL is taken exactly from your CSV. Check the manifest and listen to the recordings to ensure that each recording matches your dataset needs.
