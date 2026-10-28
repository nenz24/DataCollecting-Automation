# Data Collecting Automation — Google Sheets to MP3

Read a song table from Google Sheets, flatten up to five YouTube links per song, and create a locally organized MP3 dataset.

## Expected Google Sheets columns

The table must contain these column headers (spelling can differ in capitalization/spaces):

- \`Song Title\`
- \`Youtube Links 1\`
- \`Youtube Links 2\`
- \`Youtube Links 3\`
- \`Youtube Links 4\`
- \`Youtube Links 5\`

No \`label\` column is required or used. Extra columns are ignored. Blank URL cells are skipped. Each filled YouTube link becomes one recording, and repeated video IDs are deduplicated even when the URL has different tracking parameters.

## Google Sheets access

The script reads a CSV export of the sheet, so the spreadsheet must be viewable without an interactive login. In Google Sheets, use **Share → General access → Anyone with the link → Viewer**. If the sheet cannot be shared that way, publish the relevant tab to the web or use local CSV mode.

The source is configured in \`config.json\`:

\`\`\`json
{
  "source": "google_sheet",
  "google_sheet_url": "https://docs.google.com/spreadsheets/d/YOUR_SPREADSHEET_ID/edit",
  "worksheet_gid": ""
}
\`\`\`

- \`google_sheet_url\`: your spreadsheet sharing URL.
- \`worksheet_gid\`: optional tab ID (the number after \`gid=\` in the sheet URL). Leave empty to export the first/default tab. Set it if the data table lives on another tab.

If you prefer to read a local \`songs.csv\` with columns \`song_title,youtube_url\`, set \`"source": "csv"\` in \`config.json\`.

## Setup

Install FFmpeg on macOS:

\`\`\`bash
brew install ffmpeg
\`\`\`

Set up Python dependencies:

\`\`\`bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
\`\`\`

## Run

\`\`\`bash
python download_dataset.py
\`\`\`

The script reads the sheet on every run, so you can append songs or paste new YouTube links into the spreadsheet and rerun the command. It does not perform a song search.

## Output structure

Each song title gets its own folder. Every filename keeps both a globally unique numeric ID and the song title:

\`\`\`text
dataset_mp3/
├── Raja Semesta/
│   ├── 0002 - Raja Semesta.mp3
│   └── 0003 - Raja Semesta.mp3
└── Ha.. Hallelujah/
    ├── 0005 - Ha.. Hallelujah.mp3
    └── 0006 - Ha.. Hallelujah.mp3

manifest.csv
.dataset_ids.json
\`\`\`

- \`manifest.csv\` records the dataset ID, song title, YouTube title, channel, duration, source URL, source row/column, saved file path, and status.
- \`.dataset_ids.json\` stores a persistent mapping from YouTube video ID to dataset ID, so adding rows or links later does not renumber existing recordings. It is local and ignored by Git. Back up this file along with the dataset if you need to preserve IDs across computers.
- \`dataset_mp3/\` and \`manifest.csv\` are local output, not pushed into GitHub.

Only download audio that you own or are authorized to download and use. Check applicable platform terms and rights before downloading.
