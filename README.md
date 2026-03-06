# Static-Video-Centre
[中文说明](README_CN.md)

This is a ‘front-end-centric’ media library project designed to run stably on low-performance devices (such as Amlogic boxes and small ARM hosts).

Core design:
- Purely static website (can be hosted directly via Nginx or any static server)
- No backend API
- No database
- No transcoding process
- Delivers a functional media browsing and playback experience with minimal backend overhead

The player utilises [**Video.js**](https://github.com/videojs/video.js); should loading fail, it will automatically fall back to the browser's native `<video>` element for playback. To use Video.js, please refer to [here](vendor/README.md).

## Feature Overview

- Wall Browsing (Poster Cards)
- Keyword Search (Title)
- Tag Filtering (`tags`)
- Shared Portal for Films and Series
- Series Season/Episode Switching (Player Page)
- Subtitle Support (`.srt` converted to WebVTT in frontend; also supports `.vtt`)
- Viewing Progress Tracking (`localStorage`)

## Project Structure

```text
.
├─ index.html                 # Media library homepage
├─ player.html                # Player page
├─ script.js                  # Frontend core logic
├─ style.css                  # Stylesheet
├─ library_tools.py           # Media library generation / update entry point (Python)
├─ tmdb_api.json              # TMDB API Key configuration
├─ requirements.txt           # Python dependencies
├─ media/
│  ├─ library.json            # Media index
│  ├─ movie.schema.json       # Movie metadata schema (JSON)
│  ├─ series.schema.json      # Series metadata schema (JSON)
│  ├─ <MovieFolder>/movie.json
│  └─ <SeriesFolder>/series.json
├─ tools/
│  ├─ scan_media.py           # Scan local media files
│  ├─ metadata_builder.py     # Build / update metadata (JSON)
│  └─ tmdb_client.py          # TMDB API client
└─ vendor/
     ├─ video.min.js
     └─ video-js.css
```

## Data Model (Core)

### 1) `media/library.json`

Maintain folder index only:

```json
{
	"movies": ["Titanic", "NCIS"]
}
```

> The project currently uses the `movies` array as a unified index (both films and series can be placed within this array; the frontend will subsequently determine whether to use `movie.json` or `series.json`).

### 2) Movies `media/<Folder>/movie.json`

```json
{
	"id": "Sample_Movie_A",
	"title": "Sample Movie A",
	"year": 2026,
	"description": "...",
	"duration": 5400,
	"tags": ["Sci-Fi"],
	"video": "Sample_Movie_A_2026.mp4",
	"poster": "poster.jpg",
	"subtitles": [
		{ "label": "English", "file": "Sample_Movie_A_en.srt" }
	]
}
```

### 3) Series `media/<Folder>/series.json`

```json
{
	"id": "Sample_Series_B",
	"type": "series",
	"title": "Sample Series B",
	"year": 2025,
	"description": "...",
	"poster": "poster.jpg",
	"tags": ["Sci-Fi"],
	"seasons": [
		{
			"season": 1,
			"title": "Season 1",
			"episodes": [
				{
					"episode": 1,
					"title": "Episode 1",
					"description": "...",
					"duration": 2700,
					"video": "S01/S01E01.mp4",
					"subtitles": [
						{ "label": "English", "file": "S01/S01E01_en.srt" }
					]
				}
			]
		}
	]
}
```

## Local Development and Launch

### 1) Python Dependencies

```bash
pip install -r requirements.txt
```

### 2) Configure the TMDB API Key

Create or modify the `tmdb_api.json` file:

```json
{
	"api_key": "YOUR_TMDB_API_KEY"
}
```

### 3) Build / Update Media metadata

```bash
python library_tools.py
```

### 4) Launch the static server

```bash
python -m http.server 8000
```

Open:
- `http://localhost:8000/index.html`

## Media File Placement Recommendations

- Movies:
    - `media/<MovieName>/movie.json`
    - `media/<MovieName>/<video-file>.mp4`
    - `media/<MovieName>/poster.jpg`
- Series:
    - `media/<SeriesName>/series.json`
    - `media/<SeriesName>/S01/S01E01.mp4` (Recommended naming convention: `SxxExx`)
    - `media/<SeriesName>/S01/S01E01_en.srt`

## Design Approach

This project deliberately avoids solutions with high backend costs:
- No real-time transcoding
- No database services introduced
- No reliance on persistent backend processes

Suitable scenarios:
- Home intranet media libraries
- Lightweight NAS/TV box environments
- Quick deployment of low-maintenance media indexing sites

## Known Limitations

- MKV playability depends on browser codec capabilities
- Playback progress stored locally in browser (does not synchronise across devices)
- Current workflow favours ‘local file structure + TMDB metadata’

---