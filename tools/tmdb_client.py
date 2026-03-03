import urllib.request
import urllib.parse
import json
import sys


class TMDBClient:
    BASE_URL = "https://api.themoviedb.org/3"

    def __init__(self, api_key, language="zh-TW", timeout=10):
        self.api_key = api_key
        self.language = language
        self.timeout = timeout

    def _request(self, path, params=None):
        if params is None:
            params = {}

        params["api_key"] = self.api_key
        params["language"] = self.language

        query_string = urllib.parse.urlencode(params)
        url = f"{self.BASE_URL}{path}?{query_string}"

        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as response:
                if response.status != 200:
                    print(f"TMDB error: HTTP {response.status}")
                    return None

                data = response.read().decode("utf-8")
                return json.loads(data)

        except Exception as e:
            print(f"TMDB request failed: {e}")
            return None

    # ------------------------
    # Search
    # ------------------------

    def search_movie(self, query):
        return self._request("/search/movie", {"query": query})

    def search_tv(self, query):
        return self._request("/search/tv", {"query": query})

    # ------------------------
    # Details
    # ------------------------

    def get_movie_details(self, movie_id):
        return self._request(f"/movie/{movie_id}")

    def get_tv_details(self, tv_id):
        return self._request(f"/tv/{tv_id}")

    def get_tv_season(self, tv_id, season_number):
        return self._request(f"/tv/{tv_id}/season/{season_number}")