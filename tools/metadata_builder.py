POSTER_FILENAME = "poster.jpg"

import os
import json
import urllib

def build_series_metadata(folder_name, scan_data, tmdb_details, tmdb_client):
    """
    folder_name: "NCIS"
    scan_data: {
        "seasons": [...]
    }
    tmdb_details: /tv/{id} 返回数据
    tmdb_client: 用于调用 get_tv_season
    """

    title = tmdb_details.get("name", folder_name)
    first_air = tmdb_details.get("first_air_date", "")
    year = int(first_air[:4]) if first_air else 0
    description = tmdb_details.get("overview", "")

    genres = tmdb_details.get("genres", [])
    tags = [g["name"] for g in genres if "name" in g]

    metadata = {
        "id": folder_name,
        "type": "series",
        "title": title,
        "year": year,
        "description": description,
        "poster": POSTER_FILENAME,
        "tags": tags,
        "seasons": []
    }

    tv_id = tmdb_details.get("id")

    # Only build episodes that exist locally
    for season_scan in scan_data["seasons"]:
        season_number = season_scan["season"]

        print(f"Fetching TMDB season {season_number}...")

        season_details = tmdb_client.get_tv_season(tv_id, season_number)
        if not season_details:
            print(f"Warning: TMDB season {season_number} not found")
            continue

        season_data = {
            "season": season_number,
            "title": season_details.get("name", f"Season {season_number}"),
            "episodes": []
        }

        tmdb_episodes = {
            ep["episode_number"]: ep
            for ep in season_details.get("episodes", [])
        }

        # Only build episodes that exist locally
        for episode_scan in season_scan["episodes"]:
            episode_number = episode_scan["episode"]

            tmdb_ep = tmdb_episodes.get(episode_number)

            if tmdb_ep:
                ep_title = tmdb_ep.get("name", f"Episode {episode_number}")
                ep_desc = tmdb_ep.get("overview", "")
                runtime = tmdb_ep.get("runtime") or 0
            else:
                ep_title = f"Episode {episode_number}"
                ep_desc = ""
                runtime = 0

            episode_data = {
                "episode": episode_number,
                "title": ep_title,
                "description": ep_desc,
                "duration": runtime * 60 if runtime else 0,
                "video": episode_scan["video"]
            }

            # Subtitles
            if episode_scan.get("subtitles"):
                episode_data["subtitles"] = []
                for sub in episode_scan["subtitles"]:
                    episode_data["subtitles"].append({
                        "label": "Unknown",
                        "file": sub["file"]
                    })

            season_data["episodes"].append(episode_data)

        metadata["seasons"].append(season_data)

    return metadata

def build_movie_metadata(folder_name, scan_data, tmdb_details):
    """
    folder_name: "Titanic"
    scan_data: {
        "video": "...",
        "subtitles": [...]
    }
    tmdb_details: /movie/{id} 返回数据
    """

    title = tmdb_details.get("title", folder_name)
    release_date = tmdb_details.get("release_date", "")
    year = int(release_date[:4]) if release_date else 0
    description = tmdb_details.get("overview", "")
    runtime = tmdb_details.get("runtime") or 0

    genres = tmdb_details.get("genres", [])
    tags = [g["name"] for g in genres if "name" in g]

    metadata = {
        "id": folder_name,
        "title": title,
        "year": year,
        "description": description,
        "duration": runtime * 60 if runtime else 0,
        "tags": tags,
        "video": scan_data["video"],
        "poster": POSTER_FILENAME
    }

    # subtitles
    if scan_data.get("subtitles"):
        metadata["subtitles"] = []
        for sub in scan_data["subtitles"]:
            metadata["subtitles"].append({
                "file": sub["file"],
                "label": "Unknown"
            })

    # UI hits
    if runtime:
        metadata["durationHint"] = f"{runtime} 分鐘"

    return metadata

def interactive_select(results, media_type):
    items = results.get("results", [])[:5]

    if not items:
        print("No results found.")
        return None

    print()
    for idx, item in enumerate(items, 1):
        if media_type == "movie":
            title = item.get("title")
            date = item.get("release_date", "")
        else:
            title = item.get("name")
            date = item.get("first_air_date", "")

        year = date[:4] if date else ""
        print(f"{idx}) {title} ({year})")

    print("0) Skip")

    while True:
        choice = input("Select number: ").strip()
        if choice.isdigit():
            choice = int(choice)
            if choice == 0:
                return None
            if 1 <= choice <= len(items):
                return items[choice - 1]["id"]
        print("Invalid input.")

def create_new_media(item, tmdb, library, media_root_path):
    folder = item["folder"]
    media_type = item["type"]
    base_path = os.path.join(media_root_path, folder)

    print(f"[NEW] {folder}")

    if media_type == "movie":
        results = tmdb.search_movie(folder)
    else:
        results = tmdb.search_tv(folder)

    selected_id = interactive_select(results, media_type)

    if not selected_id:
        print("Skipped.")
        return

    if media_type == "movie":
        details = tmdb.get_movie_details(selected_id)
        metadata = build_movie_metadata(folder, item, details)
        json_path = os.path.join(base_path, "movie.json")
    else:
        details = tmdb.get_tv_details(selected_id)
        metadata = build_series_metadata(folder, item, details, tmdb)
        json_path = os.path.join(base_path, "series.json")

    # Save metadata
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    # Download poster
    download_poster(details.get("poster_path"), folder)

    # Update library
    library["movies"].append(folder)

def download_poster(poster_path, folder):
    if not poster_path:
        return

    url = f"https://image.tmdb.org/t/p/w500{poster_path}"
    save_path = f"media/{folder}/poster.jpg"

    try:
        urllib.request.urlretrieve(url, save_path)
        print("Poster downloaded.")
    except Exception as e:
        print("Poster download failed:", e)

def update_movie(folder, item, tmdb, refresh=False):
    path = f"media/{folder}/movie.json"

    if not os.path.exists(path):
        print(f"[ERROR] movie.json missing for {folder}")
        return

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"[UPDATE] {folder} (movie)")

    local_video = item.get("video")

    # ---------- 1️⃣ 视频检查 ----------
    if not local_video:
        print("  ⚠ Video file missing locally.")
    else:
        if data.get("video") != local_video:
            print("  ➜ Video updated.")
            data["video"] = local_video

    # ---------- 2️⃣ 字幕检查 ----------
    local_subtitles = item.get("subtitles", [])

    if data.get("subtitles") != local_subtitles:
        print("  ➜ Subtitles updated.")
        data["subtitles"] = local_subtitles

    # ---------- 3️⃣ refresh ----------
    if refresh:
        print("  ➜ Refreshing metadata...")
        tmdb_id = data.get("tmdb_id")

        if tmdb_id:
            details = tmdb.get_movie_details(tmdb_id)

            data["title"] = details.get("title")
            data["year"] = details.get("release_date", "")[:4]
            data["description"] = details.get("overview")
            data["tags"] = [g["name"] for g in details.get("genres", [])]

            download_poster(details.get("poster_path"), folder)

    # ---------- 4️⃣ 保存 ----------
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("  ✓ Movie updated.")

def update_series(folder, item, tmdb, refresh=False):
    path = f"media/{folder}/series.json"

    if not os.path.exists(path):
        print(f"[ERROR] series.json missing for {folder}")
        return

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"[UPDATE] {folder} (series)")

    tmdb_id = data.get("tmdb_id")
    existing_seasons = {s["season"]: s for s in data.get("seasons", [])}
    local_seasons = item.get("seasons", {})

    # ---------- 1️⃣ 新增季 ----------
    for season_number, local_eps in local_seasons.items():

        if season_number not in existing_seasons:
            print(f"  ➜ New season detected: S{season_number:02}")

            if not tmdb_id:
                print("  ⚠ Missing tmdb_id.")
                continue

            season_details = tmdb.get_tv_season(tmdb_id, season_number)

            new_season = {
                "season": season_number,
                "episodes": []
            }

            for ep in season_details.get("episodes", []):
                ep_num = ep["episode_number"]

                if ep_num not in local_eps:
                    continue

                new_season["episodes"].append({
                    "episode": ep_num,
                    "title": ep.get("name"),
                    "video": local_eps[ep_num],
                    "subtitles": find_subtitle(folder, season_number, ep_num)
                })

            data["seasons"].append(new_season)

    # ---------- 2️⃣ 更新已有季 ----------
    for season in data["seasons"]:
        season_number = season["season"]

        if season_number not in local_seasons:
            print(f"  ⚠ Season folder missing locally: S{season_number:02}")
            continue

        local_eps = local_seasons[season_number]
        existing_eps = {e["episode"]: e for e in season["episodes"]}

        # 一次性获取 TMDB season 数据（避免重复 API）
        season_details = None
        if tmdb_id:
            season_details = tmdb.get_tv_season(tmdb_id, season_number)

        # ---------- 新增集 ----------
        for ep_num, video_file in local_eps.items():

            if ep_num not in existing_eps:
                print(f"  ➜ New episode: S{season_number:02}E{ep_num:02}")

                title = ""
                if season_details:
                    match = next(
                        (e for e in season_details["episodes"]
                         if e["episode_number"] == ep_num),
                        None
                    )
                    if match:
                        title = match.get("name")

                season["episodes"].append({
                    "episode": ep_num,
                    "title": title,
                    "video": video_file,
                    "subtitles": find_subtitle(folder, season_number, ep_num)
                })

        # ---------- 删除检测 ----------
        for ep_num in existing_eps:
            if ep_num not in local_eps:
                print(f"  ⚠ Episode missing locally: S{season_number:02}E{ep_num:02}")

        # ---------- 字幕同步 ----------
        for ep in season["episodes"]:
            ep_num = ep["episode"]
            new_subs = find_subtitle(folder, season_number, ep_num)

            if ep.get("subtitles") != new_subs:
                print(f"  ➜ Subtitle updated: S{season_number:02}E{ep_num:02}")
                ep["subtitles"] = new_subs

    # ---------- 3️⃣ refresh ----------
    if refresh and tmdb_id:
        print("  ➜ Refreshing series metadata...")
        details = tmdb.get_tv_details(tmdb_id)

        data["title"] = details.get("name")
        data["year"] = details.get("first_air_date", "")[:4]
        data["description"] = details.get("overview")
        data["tags"] = [g["name"] for g in details.get("genres", [])]

        download_poster(details.get("poster_path"), folder)

    # ---------- 4️⃣ 排序 ----------
    data["seasons"] = sorted(data["seasons"], key=lambda x: x["season"])

    for season in data["seasons"]:
        season["episodes"] = sorted(
            season["episodes"],
            key=lambda x: x["episode"]
        )

    # ---------- 5️⃣ 保存 ----------
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("  ✓ Series updated.")
   
def find_subtitle(folder, season, episode):
    base = f"media/{folder}/S{season:02}/S{season:02}E{episode:02}"
    str_path = base + ".srt"
    if os.path.exists(str_path):
        return [f"S{season:02}/S{season:02}E{episode:02}.srt"]
    return []

def update_existing_media(item, tmdb, library):
    folder = item["folder"]
    media_type = item["type"]

    if media_type == "movie":
        update_movie(folder, item, tmdb, refresh) # type: ignore
    else:
        update_series(folder, item, tmdb, refresh) # type: ignore