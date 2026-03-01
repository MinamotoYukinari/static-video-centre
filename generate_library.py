import os
import re
import json
from pathlib import Path
from difflib import SequenceMatcher

import requests


TMDB_API_KEY = "[Your TMDB API]"  # Set your TMDB API key here or via the TMDB_API_KEY environment variable
TMDB_BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"
MEDIA_DIR = Path("./media")
CONFIDENCE_THRESHOLD = 0.35
TMDB_LANGUAGE = str(os.getenv("TMDB_LANGUAGE", "zh-TW")).strip() or "zh-TW"
CACHE_FILE = MEDIA_DIR / ".tmdb_cache.json"
REQUEST_TIMEOUT = 20

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".m4v", ".webm"}
SUBTITLE_EXTENSIONS = {".srt", ".vtt", ".ass"}
POSTER_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

SEASON_FOLDER_PATTERNS = [
    re.compile(r"(?i)^(?:s|season)[\s._-]*(\d{1,2})$"),
    re.compile(r"第\s*(\d{1,2})\s*季"),
]

EPISODE_PATTERNS = [
    re.compile(r"(?i)\bs(\d{1,2})[\s._-]*e(\d{1,3})\b"),
    re.compile(r"(?i)\b(\d{1,2})x(\d{1,3})\b"),
    re.compile(r"(?i)\bep(?:isode)?[\s._-]*(\d{1,3})\b"),
    re.compile(r"第\s*(\d{1,3})\s*[集话話]"),
]

LANG_HINTS = {
    "zh": ["zh", "zho", "chi", "chs", "cht", "cn", "tc", "sc", "chinese", "中文", "繁中", "简中"],
    "en": ["en", "eng", "english", "英文"],
    "ja": ["ja", "jpn", "jp", "japanese", "日文", "日本語"],
}


def log_ok(message):
    print(f"[OK] {message}")


def log_warning(message):
    print(f"[WARNING] {message}")


def log_error(message):
    print(f"[ERROR] {message}")


def read_json(path_obj, default_value=None):
    if not path_obj.exists():
        return default_value
    try:
        return json.loads(path_obj.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Failed to parse JSON: {path_obj} ({exc})")


def write_json(path_obj, payload):
    content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    path_obj.write_text(content, encoding="utf-8")


def write_json_atomic(path_obj, payload):
    temp_path = path_obj.with_name(f".{path_obj.name}.tmp")
    content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(path_obj)


def list_media_folders():
    if not MEDIA_DIR.exists() or not MEDIA_DIR.is_dir():
        raise RuntimeError(f"Media directory not found: {MEDIA_DIR}")

    folders = []
    for entry in sorted(MEDIA_DIR.iterdir(), key=lambda p: p.name.lower()):
        if not entry.is_dir():
            continue
        if entry.name.startswith("."):
            continue
        folders.append(entry)
    return folders


def detect_contract_type(folder_path):
    series_path = folder_path / "series.json"
    movie_path = folder_path / "movie.json"
    if series_path.exists():
        return "series", series_path
    if movie_path.exists():
        return "movie", movie_path
    return None, None


def refresh_library_json():
    folders = list_media_folders()
    entries = []
    for folder in folders:
        media_type, _ = detect_contract_type(folder)
        if media_type:
            entries.append(folder.name)

    payload = {"movies": sorted(entries, key=lambda x: x.lower())}
    write_json_atomic(MEDIA_DIR / "library.json", payload)
    log_ok("library.json refreshed")


def choose_folder():
    folders = list_media_folders()
    if not folders:
        log_warning("No media folders found.")
        return None

    print("\nAvailable folders:")
    for idx, folder in enumerate(folders, start=1):
        print(f"{idx}. {folder.name}")

    selected = input("Select folder index: ").strip()
    if not selected.isdigit():
        log_error("Invalid folder selection.")
        return None

    index = int(selected)
    if index < 1 or index > len(folders):
        log_error("Folder index out of range.")
        return None

    return folders[index - 1]


def normalize_for_similarity(text):
    text = text.lower()
    text = re.sub(r"[._\-\[\]\(\)]", " ", text)
    text = re.sub(r"[^\w\u4e00-\u9fff\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def similarity(a, b):
    return SequenceMatcher(None, normalize_for_similarity(a), normalize_for_similarity(b)).ratio()


def detect_year_from_date(date_str):
    if not date_str or not isinstance(date_str, str):
        return None
    match = re.match(r"^(\d{4})", date_str)
    return int(match.group(1)) if match else None


def language_from_name(filename):
    lower_name = filename.lower()
    for lang, hints in LANG_HINTS.items():
        for hint in hints:
            if hint in lower_name:
                return lang
    return "und"


def label_from_lang(lang):
    if lang == "zh":
        return "Chinese"
    if lang == "en":
        return "English"
    if lang == "ja":
        return "Japanese"
    return "Unknown"


def load_cache():
    if not CACHE_FILE.exists():
        return {"responses": {}}

    data = read_json(CACHE_FILE, default_value={"responses": {}})
    if not isinstance(data, dict):
        raise RuntimeError("Invalid cache file format.")

    responses = data.get("responses")
    if not isinstance(responses, dict):
        raise RuntimeError("Invalid cache file format: responses must be object.")

    return data


def save_cache(cache):
    if not isinstance(cache, dict):
        raise RuntimeError("Cache must be dict.")
    if "responses" not in cache or not isinstance(cache["responses"], dict):
        raise RuntimeError("Cache missing responses object.")
    write_json_atomic(CACHE_FILE, cache)


def cached_request(cache, endpoint, params):
    if not TMDB_API_KEY:
        raise RuntimeError("TMDB_API_KEY is not set.")

    query = dict(params or {})
    query["api_key"] = TMDB_API_KEY
    query["language"] = TMDB_LANGUAGE

    key_items = sorted((str(k), str(v)) for k, v in query.items() if k != "api_key")
    key = f"{endpoint}|" + "&".join(f"{k}={v}" for k, v in key_items)

    responses = cache.setdefault("responses", {})
    if key in responses:
        return responses[key], True

    url = f"{TMDB_BASE_URL}{endpoint}"
    try:
        response = requests.get(url, params=query, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        raise RuntimeError(f"Network error for {endpoint}: {exc}")

    if response.status_code != 200:
        raise RuntimeError(f"TMDB API error for {endpoint}: HTTP {response.status_code}")

    try:
        payload = response.json()
    except Exception as exc:
        raise RuntimeError(f"Invalid JSON response for {endpoint}: {exc}")

    responses[key] = payload
    return payload, False


def tmdb_search(cache, media_type, query_text):
    endpoint = "/search/tv" if media_type == "series" else "/search/movie"
    payload, from_cache = cached_request(
        cache,
        endpoint,
        {
            "query": query_text,
            "include_adult": "false",
            "page": 1,
        },
    )

    results = payload.get("results")
    if not isinstance(results, list):
        raise RuntimeError("TMDB search response missing results array.")

    top = results[:5]
    if from_cache:
        log_ok(f"TMDB search cache hit for '{query_text}'")
    else:
        log_ok(f"TMDB search cache miss for '{query_text}'")
    return top


def tmdb_detail(cache, media_type, tmdb_id):
    endpoint = f"/tv/{tmdb_id}" if media_type == "series" else f"/movie/{tmdb_id}"
    payload, from_cache = cached_request(cache, endpoint, {})
    if from_cache:
        log_ok(f"TMDB detail cache hit: {endpoint}")
    else:
        log_ok(f"TMDB detail cache miss: {endpoint}")
    return payload


def download_poster(folder_path, poster_path):
    if not poster_path:
        return None

    existing = [p for p in folder_path.iterdir() if p.is_file() and p.suffix.lower() in POSTER_EXTENSIONS]
    if existing:
        return existing[0].name

    url = f"{IMAGE_BASE_URL}{poster_path}"
    target = folder_path / "poster.jpg"

    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT, stream=True)
    except requests.RequestException as exc:
        log_warning(f"Poster download network error: {exc}")
        return None

    if response.status_code != 200:
        log_warning(f"Poster download failed: HTTP {response.status_code}")
        return None

    try:
        with target.open("wb") as writer:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    writer.write(chunk)
    except Exception as exc:
        log_warning(f"Poster save failed: {exc}")
        return None

    log_ok(f"Poster downloaded: {target.name}")
    return target.name


def parse_season_from_path(relative_parent):
    if relative_parent in {".", ""}:
        return None
    parts = relative_parent.replace("\\", "/").split("/")
    for part in reversed(parts):
        for pattern in SEASON_FOLDER_PATTERNS:
            match = pattern.search(part)
            if match:
                season = int(match.group(1))
                if 1 <= season <= 99:
                    return season
    return None


def parse_episode_from_name(name, fallback_season=None):
    return parse_episode_info(name, fallback_season)


def parse_episode_info(filename, fallback_season=None):
    stem, _ = os.path.splitext(filename)

    season_episode_patterns = [
        re.compile(r"(?i)s\s*(\d{1,2})\s*e\s*(\d{1,3})"),
        re.compile(r"(?i)(\d{1,2})\s*x\s*(\d{1,3})"),
    ]
    episode_only_patterns = [
        re.compile(r"(?i)ep(?:isode)?\s*(\d{1,3})"),
        re.compile(r"第\s*(\d{1,3})\s*[集话話]"),
    ]

    for pattern in season_episode_patterns:
        match = pattern.search(stem)
        if not match:
            continue
        season = int(match.group(1))
        episode = int(match.group(2))
        return season, episode

    for pattern in episode_only_patterns:
        match = pattern.search(stem)
        if not match:
            continue
        episode = int(match.group(1))
        season = fallback_season if fallback_season else 1
        return season, episode

    return None


def prefer_video_item(current_item, candidate_item):
    current_ext = Path(current_item["relative"]).suffix.lower()
    candidate_ext = Path(candidate_item["relative"]).suffix.lower()

    if current_ext != ".mp4" and candidate_ext == ".mp4":
        return candidate_item
    if current_ext == ".mp4" and candidate_ext != ".mp4":
        return current_item

    current_size = current_item.get("size", 0)
    candidate_size = candidate_item.get("size", 0)
    if candidate_size > current_size:
        return candidate_item

    return current_item


def match_subtitles(video_files, subtitle_files):
    mapping = {video["relative"]: [] for video in video_files}
    available_subs = {subtitle["relative"]: subtitle for subtitle in subtitle_files}

    for video in video_files:
        video_name = video["relative"]
        scored = []
        for subtitle in subtitle_files:
            ratio = similarity(Path(video_name).stem, Path(subtitle["relative"]).stem)
            scored.append((ratio, subtitle))

        scored.sort(key=lambda item: (-item[0], item[1]["relative"].lower()))

        for score, subtitle in scored:
            sub_key = subtitle["relative"]
            if sub_key not in available_subs:
                continue
            if score < CONFIDENCE_THRESHOLD:
                continue

            lang = language_from_name(subtitle["name"])
            mapping[video_name].append(
                {
                    "label": label_from_lang(lang),
                    "lang": lang,
                    "file": subtitle["relative"],
                }
            )
            del available_subs[sub_key]
            break

    return mapping


def scan_series_structure(folder_path):
    video_files = []
    subtitle_files = []

    for root, _, filenames in os.walk(folder_path):
        root_path = Path(root)
        for filename in filenames:
            full_path = root_path / filename
            relative_path = full_path.relative_to(folder_path).as_posix()
            suffix = full_path.suffix.lower()

            if suffix == ".mkv":
                log_warning(f"MKV may not play on Amazon Silk browser: {relative_path}")

            item = {
                "path": full_path,
                "relative": relative_path,
                "name": filename,
                "size": full_path.stat().st_size,
            }

            if suffix in VIDEO_EXTENSIONS:
                video_files.append(item)
            elif suffix in SUBTITLE_EXTENSIONS:
                subtitle_files.append(item)

    video_files.sort(key=lambda x: x["relative"].lower())
    subtitle_files.sort(key=lambda x: x["relative"].lower())

    subtitle_map = match_subtitles(video_files, subtitle_files)

    seasons_map = {}
    preferred_episode_video = {}
    for video in video_files:
        relative_parent = str(Path(video["relative"]).parent)
        fallback_season = parse_season_from_path(relative_parent)
        parsed = parse_episode_info(video["name"], fallback_season=fallback_season)
        if not parsed:
            log_warning(f"Episode parse failed: {video['relative']}")
            continue

        season_no, episode_no = parsed
        episode_key = (season_no, episode_no)

        if episode_key in preferred_episode_video:
            preferred_episode_video[episode_key] = prefer_video_item(preferred_episode_video[episode_key], video)
        else:
            preferred_episode_video[episode_key] = video

    for (season_no, episode_no), video in sorted(preferred_episode_video.items(), key=lambda x: (x[0][0], x[0][1])):
        episode_info = {
            "episode": episode_no,
            "title": f"Episode {episode_no}",
            "description": "",
            "duration": 0,
            "video": video["relative"],
            "subtitles": subtitle_map.get(video["relative"], []),
        }
        seasons_map.setdefault(season_no, []).append(episode_info)

    seasons = []
    for season_no in sorted(seasons_map.keys()):
        episodes = sorted(seasons_map[season_no], key=lambda ep: ep["episode"])
        seasons.append(
            {
                "season": season_no,
                "title": f"Season {season_no}",
                "episodes": episodes,
            }
        )

    return seasons


def scan_movie_structure(folder_path):
    video_files = []
    subtitle_files = []

    for root, _, filenames in os.walk(folder_path):
        root_path = Path(root)
        for filename in filenames:
            full_path = root_path / filename
            relative_path = full_path.relative_to(folder_path).as_posix()
            suffix = full_path.suffix.lower()

            if suffix == ".mkv":
                log_warning(f"MKV may not play on Amazon Silk browser: {relative_path}")

            item = {
                "path": full_path,
                "relative": relative_path,
                "name": filename,
                "size": full_path.stat().st_size,
            }

            if suffix in VIDEO_EXTENSIONS:
                video_files.append(item)
            elif suffix in SUBTITLE_EXTENSIONS:
                subtitle_files.append(item)

    if not video_files:
        raise RuntimeError("No video file found for movie structure.")

    mp4_files = [video for video in video_files if Path(video["relative"]).suffix.lower() == ".mp4"]
    if mp4_files:
        mp4_files.sort(key=lambda x: (-x["size"], x["relative"].lower()))
        main_video = mp4_files[0]
    else:
        video_files.sort(key=lambda x: (-x["size"], x["relative"].lower()))
        main_video = video_files[0]

    subtitle_map = match_subtitles([main_video], subtitle_files)

    return {
        "video": main_video["relative"],
        "subtitles": subtitle_map.get(main_video["relative"], []),
    }


def handle_option_a():
    try:
        folder = choose_folder()
    except Exception as exc:
        log_error(str(exc))
        return

    if folder is None:
        return

    media_type_raw = input("Select type (1=Series, 2=Movie): ").strip()
    if media_type_raw == "1":
        media_type = "series"
    elif media_type_raw == "2":
        media_type = "movie"
    else:
        log_error("Invalid type selection.")
        return

    if not TMDB_API_KEY:
        log_error("TMDB_API_KEY not set. Option A requires API key.")
        return

    try:
        cache = load_cache()
        results = tmdb_search(cache, media_type, folder.name)
    except Exception as exc:
        log_error(str(exc))
        return

    if not results:
        log_warning("No TMDB results found.")
        return

    print("\nTop results:")
    for idx, item in enumerate(results, start=1):
        if media_type == "series":
            title = str(item.get("name") or item.get("original_name") or "Unknown").strip()
            year = detect_year_from_date(item.get("first_air_date"))
        else:
            title = str(item.get("title") or item.get("original_title") or "Unknown").strip()
            year = detect_year_from_date(item.get("release_date"))
        year_text = str(year) if year else "N/A"
        print(f"{idx}. {title} ({year_text})")

    selected = input("Select result index: ").strip()
    if not selected.isdigit():
        log_error("Invalid result selection.")
        return

    result_index = int(selected)
    if result_index < 1 or result_index > len(results):
        log_error("Result index out of range.")
        return

    picked = results[result_index - 1]
    tmdb_id = picked.get("id")
    if not tmdb_id:
        log_error("TMDB result missing id.")
        return

    try:
        detail = tmdb_detail(cache, media_type, tmdb_id)
    except Exception as exc:
        log_error(str(exc))
        return

    poster_file = download_poster(folder, detail.get("poster_path"))

    json_path = folder / "series.json" if media_type == "series" else folder / "movie.json"
    existing = read_json(json_path, default_value={})
    if existing is None:
        existing = {}
    if not isinstance(existing, dict):
        existing = {}

    if media_type == "series":
        title = str(detail.get("name") or detail.get("original_name") or folder.name)
        year = detect_year_from_date(detail.get("first_air_date"))
        genre_names = [g.get("name") for g in detail.get("genres", []) if isinstance(g, dict) and g.get("name")]

        updated = dict(existing)
        updated["id"] = existing.get("id", folder.name)
        updated["title"] = title
        updated["year"] = year if year else existing.get("year", 2000)
        updated["description"] = str(detail.get("overview") or existing.get("description") or "")
        updated["poster"] = poster_file or existing.get("poster", "poster.jpg")
        updated["tags"] = genre_names if genre_names else existing.get("tags", [])
        updated["seasons"] = existing.get("seasons", [])
        updated.pop("type", None)
    else:
        title = str(detail.get("title") or detail.get("original_title") or folder.name)
        year = detect_year_from_date(detail.get("release_date"))
        genre_names = [g.get("name") for g in detail.get("genres", []) if isinstance(g, dict) and g.get("name")]

        updated = dict(existing)
        updated["id"] = existing.get("id", folder.name)
        updated["title"] = title
        updated["year"] = year if year else existing.get("year", 2000)
        updated["description"] = str(detail.get("overview") or existing.get("description") or "")
        updated["duration"] = existing.get("duration", 0)
        if "durationHint" in existing:
            updated["durationHint"] = existing.get("durationHint")
        updated["video"] = existing.get("video", "")
        updated["poster"] = poster_file or existing.get("poster", "poster.jpg")
        updated["subtitles"] = existing.get("subtitles", [])
        updated["tags"] = genre_names if genre_names else existing.get("tags", [])
        updated.pop("type", None)

    try:
        write_json_atomic(json_path, updated)
        save_cache(cache)
        refresh_library_json()
    except Exception as exc:
        log_error(f"Failed to save metadata/cache: {exc}")
        return

    log_ok(f"Metadata updated: {json_path}")


def handle_option_b():
    try:
        folder = choose_folder()
    except Exception as exc:
        log_error(str(exc))
        return

    if folder is None:
        return

    media_type, json_path = detect_contract_type(folder)
    if not media_type or not json_path:
        log_error(f"Neither series.json nor movie.json found in: {folder}")
        return

    try:
        metadata = read_json(json_path, default_value={})
    except Exception as exc:
        log_error(str(exc))
        return

    if not isinstance(metadata, dict):
        log_error("movie.json must be a JSON object.")
        return

    if media_type == "series":
        try:
            seasons = scan_series_structure(folder)
        except Exception as exc:
            log_error(f"Series scan failed: {exc}")
            return

        metadata["id"] = metadata.get("id", folder.name)
        metadata["title"] = metadata.get("title", folder.name)
        metadata["year"] = metadata.get("year", 2000)
        metadata["description"] = metadata.get("description", "")
        metadata["poster"] = metadata.get("poster", "poster.jpg")
        metadata["tags"] = metadata.get("tags", [])
        metadata["seasons"] = seasons
        metadata.pop("type", None)
        log_ok(f"Series structure refreshed: seasons={len(seasons)}")
    else:
        try:
            movie_info = scan_movie_structure(folder)
        except Exception as exc:
            log_error(f"Movie scan failed: {exc}")
            return

        metadata["id"] = metadata.get("id", folder.name)
        metadata["title"] = metadata.get("title", folder.name)
        metadata["year"] = metadata.get("year", 2000)
        metadata["description"] = metadata.get("description", "")
        metadata["duration"] = metadata.get("duration", 0)
        if "durationHint" in metadata:
            metadata["durationHint"] = metadata.get("durationHint")
        metadata["video"] = movie_info["video"]
        metadata["poster"] = metadata.get("poster", "poster.jpg")
        metadata["subtitles"] = movie_info["subtitles"]
        metadata["tags"] = metadata.get("tags", [])
        metadata.pop("type", None)
        log_ok("Movie structure refreshed")

    try:
        write_json_atomic(json_path, metadata)
        refresh_library_json()
    except Exception as exc:
        log_error(f"Failed to save JSON: {exc}")
        return

    log_ok(f"Saved: {json_path}")


def main_menu():
    while True:
        print("\n==== Video Center Tool ====")
        print("A. Fetch metadata from TMDB")
        print("B. Refresh local folder structure")
        print("Q. Quit")

        choice = input("Select option: ").strip().upper()
        if choice == "A":
            handle_option_a()
        elif choice == "B":
            handle_option_b()
        elif choice == "Q":
            log_ok("Bye")
            break
        else:
            log_error("Invalid option.")


def main():
    try:
        main_menu()
    except KeyboardInterrupt:
        print()
        log_warning("Interrupted by user")
    except Exception as exc:
        log_error(f"Fatal error: {exc}")


if __name__ == "__main__":
    main()
