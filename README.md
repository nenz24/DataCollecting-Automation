# Data Collecting Automation — Google Sheets to MP3

Read a song table from Google Sheets, expand up to five YouTube links per song, and create a locally organized MP3 dataset.

## Expected Google Sheets columns

The table must contain these headers (capitalization and spaces do not matter):

- `Song Title`
- `Youtube Links 1`
- `Youtube Links 2`
- `Youtube Links 3`
- `Youtube Links 4`
- `Youtube Links 5`

Extra columns are ignored. Blank URL cells are skipped. Each populated YouTube URL becomes one recording. Duplicate video IDs are skipped even if their URLs differ only by tracking parameters.

## Google Sheets access

The script reads a CSV export of the spreadsheet, so it must be viewable without an interactive login. In Google Sheets, select **Share → General access → Anyone with the link → Viewer**. Alternatively, publish the relevant worksheet to the web.

The source is configured in `config.json`:

```json
{
  "source": "google_sheet",
  "google_sheet_url": "https://docs.google.com/spreadsheets/d/YOUR_SPREADSHEET_ID/edit",
  "worksheet_gid": ""
}
```

- `google_sheet_url`: the spreadsheet sharing URL.
- `worksheet_gid`: optional numeric tab ID (the number after `gid=` in the worksheet URL). Leave it empty to export the first/default tab. Set it if the table is in another tab.

If you prefer a local CSV, set `"source": "csv"` in `config.json` and use `songs.csv` with `song_title,youtube_url` headers.

## Setup

Install FFmpeg on macOS:

```bash
brew install ffmpeg
```

Create a virtual environment and install Python dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Run

```bash
python download_dataset.py
```

The script reads the spreadsheet on each run, so add new songs or paste additional YouTube URLs into the sheet and run it again. It does not search for songs.

## Output structure

Each song title receives its own folder. Every filename contains both the globally unique numeric ID and the song title:

```text
dataset_mp3/
├── Raja Semesta/
│   ├── 0002 - Raja Semesta.mp3
│   └── 0003 - Raja Semesta.mp3
└── Ha.. Hallelujah/
    ├── 0005 - Ha.. Hallelujah.mp3
    └── 0006 - Ha.. Hallelujah.mp3

manifest.csv
.dataset_ids.json
```

- `manifest.csv` records the ID, song title, YouTube title, channel, duration, source URL, source row and column, saved path, and processing status.
- `.dataset_ids.json` stores the persistent mapping from YouTube video ID to dataset ID, so adding links later does not renumber existing recordings. It is local and ignored by Git. Back it up with your dataset if you need to preserve IDs on another computer.
- `dataset_mp3/` and `manifest.csv` are local output and are not uploaded to GitHub.

If you previously downloaded MP3s using an older flat-folder layout, the script does not move those files automatically. Back them up or move them manually if you want to preserve them in the new layout.

> Only download audio that you own or are authorized to download and use. Check applicable platform terms and rights before downloading.
