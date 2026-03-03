# Use scan_media method to scan the media folder and auto recognize the media type (moive/series)
import os
import re

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov"}
SUBTITLE_EXTENSIONS = {".srt"}


def is_video_file(filename):
    return os.path.splitext(filename)[1].lower() in VIDEO_EXTENSIONS


def is_subtitle_file(filename):
    return os.path.splitext(filename)[1].lower() in SUBTITLE_EXTENSIONS


def parse_episode_number(filename):
    match = re.search(r"S(\d{2})E(\d{2})", filename, re.IGNORECASE)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None, None


def scan_series(folder_path, folder_name):
    series_data = {
        "folder": folder_name,
        "type": "series",
        "seasons": []
    }

    for entry in sorted(os.listdir(folder_path)):
        if not re.match(r"^S\d{2}$", entry):
            continue

        season_number = int(entry[1:])
        season_path = os.path.join(folder_path, entry)

        season_data = {
            "season": season_number,
            "episodes": []
        }

        for file in sorted(os.listdir(season_path)):
            if not is_video_file(file):
                continue

            season_no, episode_no = parse_episode_number(file)
            if episode_no is None:
                continue

            base_name = os.path.splitext(file)[0]
            video_relative_path = f"{entry}/{file}"

            subtitles = []

            for sub_file in os.listdir(season_path):
                if is_subtitle_file(sub_file) and sub_file.startswith(base_name):
                    subtitles.append({
                        "file": f"{entry}/{sub_file}"
                    })

            season_data["episodes"].append({
                "episode": episode_no,
                "video": video_relative_path,
                "subtitles": subtitles
            })

        # 不需要检查空季（你保证不存在）
        series_data["seasons"].append(season_data)

    return series_data


def scan_movie(folder_path, folder_name):
    files = os.listdir(folder_path)

    video_files = [f for f in files if is_video_file(f)]
    if not video_files:
        return None

    video_file = video_files[0]  # 保证只有一个

    base_name = os.path.splitext(video_file)[0]

    subtitles = []
    for file in files:
        if is_subtitle_file(file) and file.startswith(base_name):
            subtitles.append({
                "file": file
            })

    return {
        "folder": folder_name,
        "type": "movie",
        "video": video_file,
        "subtitles": subtitles
    }


def scan_media(media_root):
    results = []

    for folder_name in sorted(os.listdir(media_root)):
        folder_path = os.path.join(media_root, folder_name)

        if not os.path.isdir(folder_path):
            continue

        entries = os.listdir(folder_path)

        # 判断是否是 series（严格 Sxx）
        if any(re.match(r"^S\d{2}$", e) for e in entries):
            results.append(scan_series(folder_path, folder_name))
        else:
            movie_data = scan_movie(folder_path, folder_name)
            if movie_data:
                results.append(movie_data)

    return results