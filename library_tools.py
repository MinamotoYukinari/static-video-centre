import os
import json
import argparse

from tools.scan_media import scan_media
from tools.tmdb_client import TMDBClient
from tools.metadata_builder import update_movie, update_series, create_new_media

# Declaration
MEDIA_ROOT = "./media"
LIBRARY_FILE = "./media/library.json"

# Load library.json
def load_library():
    if not os.path.exists(LIBRARY_FILE):
        return {"movies": [], "series": []}
    with open(LIBRARY_FILE, "r") as f:
        return json.load(f)
    
# Save library.json
def save_library(library):
    with open(LIBRARY_FILE, "w") as f:
        json.dump(library, f, ensure_ascii=False, indent=2)
# Main function
def main():
    # Command Line Arguments
    parser = argparse.ArgumentParser(description="Media Library Auto Generation Tool")
    parser.add_argument("--refresh", action="store_true", help="Force refresh metadata for existing media")
    args = parser.parse_args()
    refresh = args.refresh

    # Start scanning media folders
    print("Scanning media folders...")
    scanned_items = scan_media(MEDIA_ROOT)

    if not scanned_items:
        print("No media found in the media folder.")
        return
    
    # Load existing library
    library = load_library()
    
    # Load TMDB API key from tmdb_api.json
    with open("tmdb_api.json", "r") as api_file:
        API_KEY = json.load(api_file).get("api_key")
        if not API_KEY:
            print("TMDB API key not found in tmdb_api.json. Please set it before running the tool.")
            exit(1)

    # Initialize TMDB client
    tmdb_client = TMDBClient(API_KEY)

    # Process each scanned item
    for item in scanned_items:
        folder = item["folder"]
        media_type = item["type"]

        print("\n====================================================================")
        print(f"Processing {folder}")

        if media_type == "movie":
            # If movie is not in library.json, create new metadata
            if folder not in library["movies"]:
                success = create_new_media(item, tmdb_client, library, MEDIA_ROOT)
                if success:
                    library["movies"].append(folder)
            else:
                update_movie(folder, item, tmdb_client, refresh)
        else:
            # If series is not in library.json, create new metadata
            if folder not in library["movies"]:
                success = create_new_media(item, tmdb_client, library, MEDIA_ROOT)
                if success:
                    library["movies"].append(folder)
            else:
                update_series(folder, item, tmdb_client, refresh)
    
    # Save updated library
    save_library(library)
    print("\nLibrary generation completed.")
    # print(scanned_items)

if __name__ == "__main__":
    main()