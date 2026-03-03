# Auto Library Generation Tools
# The new version of the tool is still in development, but the old version is available for use. 
# Please choose the version you want to use.
# And the old version of the tool will be deprecated in the future, 
# so it's recommended to use the new version when it's ready.
print("This is a placeholder for Library Auto Generation tools.\n" \
"There are 2 versions of the tool:\n" \
"A. generate_library.py: An old version script that need user to choose the media type and get information form TMDB API, and generate metadata files.\n" \
"B. A new version script that automatically detects media type and generates metadata files without user interaction." \
"Before you run the tool, please make sure that you have set your TMDB API key in tmdb_api.json.")

choice = input("Please choose the version of the tool you want to use (A/B): ").strip().upper()

if choice == "A":
    from tools.generate_library_old import main as generate_library_main
    generate_library_main()
elif choice == "B":
    import os
    import json
    import argparse

    # declaration
    MEIDA_ROOT = "./media"
    LIBRARY_FILE = "./media/library.json"

    # tools
    from tools.scan_media import scan_media 
    from tools.tmdb_client import TMDBClient

    # check the 

    # get api key from tmdb_api.json
    with open("tmdb_api.json", "r") as api_file:
        API_KEY = json.load(api_file).get("api_key")
    if not API_KEY:
        print("TMDB API key not found in tmdb_api.json. Please set it before running the tool.")
        exit(1)
    
    # tmdb client
    tmdb_client = TMDBClient(API_KEY)
    
