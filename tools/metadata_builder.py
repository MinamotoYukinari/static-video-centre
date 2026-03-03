POSTER_FILENAME = "poster.jpg"

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