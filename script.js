const LIBRARY_INDEX_URL = "./media/library.json";
const WATCH_PROGRESS_PREFIX = "vc_progress_";

const state = {
  items: [],
  search: "",
  selectedTag: "全部",
};

const runtime = {
  player: null,
  nativeHandlers: [],
  subtitleBlobUrls: [],
  playerHandlers: null,
};

function byId(id) {
  return document.getElementById(id);
}

async function fetchJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`無法載入 ${url}`);
  }
  return response.json();
}

function normalizeMediaPath(folder, filename) {
  return `./media/${folder}/${filename}`;
}

function toMediaUrl(path) {
  return encodeURI(path);
}

function isMkvSource(path) {
  return String(path || "").toLowerCase().endsWith(".mkv");
}

function warnIfPotentiallyUnsupported(path) {
  if (!isMkvSource(path)) return;
  const ua = navigator.userAgent || "";
  if (/Silk/i.test(ua)) {
    console.warn("[WARNING] MKV may not play on Amazon Silk browser:", path);
  } else {
    console.warn("[WARNING] MKV playback depends on browser codec support:", path);
  }
}

async function warnIfMediaMissing(path) {
  try {
    const response = await fetch(path, { method: "HEAD", cache: "no-store" });
    if (!response.ok) {
      console.warn("[WARNING] Media file may be missing or inaccessible:", path, response.status);
    }
  } catch {
    console.warn("[WARNING] Cannot verify media file accessibility:", path);
  }
}

function getProgressKey(movieId) {
  return `${WATCH_PROGRESS_PREFIX}${movieId}`;
}

function loadProgress(movieId) {
  const raw = localStorage.getItem(getProgressKey(movieId));
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function saveProgress(movieId, payload) {
  localStorage.setItem(getProgressKey(movieId), JSON.stringify(payload));
}

function buildSeriesEpisodeProgressId(seriesId, seasonNumber, episodeNumber) {
  return `${seriesId}__s${seasonNumber}e${episodeNumber}`;
}

function isSeriesItem(item) {
  return item && item.mediaType === "series";
}

function formatMinutes(seconds) {
  if (!Number.isFinite(seconds) || seconds <= 0) return "";
  return `${Math.floor(seconds / 60)} 分鐘`;
}

function renderStatus(message) {
  const el = byId("statusMessage");
  if (el) el.textContent = message;
}

function createCard(item) {
  const link = document.createElement("a");
  link.className = "media-card";
  link.href = `player.html?id=${encodeURIComponent(item.id)}&type=${encodeURIComponent(item.mediaType || "movie")}`;
  link.setAttribute("aria-label", `${item.title} (${item.year ?? "N/A"})`);

  const progress = isSeriesItem(item) ? null : loadProgress(item.id);
  const progressText =
    progress && progress.duration
      ? `・進度 ${Math.round((progress.currentTime / progress.duration) * 100)}%`
      : "";
  const typeText = isSeriesItem(item) ? "影集" : "電影";

  link.innerHTML = `
    <div class="poster-wrap">
      <img class="poster" loading="lazy" src="${item.poster}" alt="${item.title}" />
      <div class="desc-overlay">${item.description || "暫無簡介"}</div>
    </div>
    <div class="card-meta">
      <div class="card-title">${item.title}</div>
      <div class="card-year">${typeText} ・ ${item.year || ""} ${progressText}</div>
    </div>
  `;
  return link;
}

function uniqueTags(items) {
  const tags = new Set(["全部"]);
  items.forEach((item) => (item.tags || []).forEach((tag) => tags.add(tag)));
  return Array.from(tags);
}

function renderFilters() {
  const wrap = byId("tagFilters");
  if (!wrap) return;

  wrap.innerHTML = "";
  uniqueTags(state.items).forEach((tag) => {
    const btn = document.createElement("button");
    btn.className = `tag-btn ${state.selectedTag === tag ? "active" : ""}`;
    btn.textContent = tag;
    btn.type = "button";
    btn.addEventListener("click", () => {
      state.selectedTag = tag;
      renderFilters();
      renderGrid();
    });
    wrap.appendChild(btn);
  });
}

function renderGrid() {
  const grid = byId("mediaGrid");
  if (!grid) return;

  const keyword = state.search.trim().toLowerCase();
  const filtered = state.items.filter((item) => {
    const titleMatch = item.title.toLowerCase().includes(keyword);
    const tagMatch =
      state.selectedTag === "全部" || (item.tags || []).includes(state.selectedTag);
    return titleMatch && tagMatch;
  });

  grid.innerHTML = "";
  filtered.forEach((item) => grid.appendChild(createCard(item)));

  renderStatus(filtered.length ? `共 ${filtered.length} 部` : "找不到符合條件的影片");
}

function setupSearch() {
  const input = byId("searchInput");
  if (!input) return;

  input.addEventListener("input", (event) => {
    state.search = event.target.value;
    renderGrid();
  });
}

async function loadLibrary() {
  const index = await fetchJson(LIBRARY_INDEX_URL);
  if (!Array.isArray(index.movies)) {
    throw new Error("library.json 格式錯誤：缺少 movies 陣列");
  }

  const results = await Promise.all(
    index.movies.map(async (folder) => {
      let meta;
      let mediaType = "movie";

      try {
        meta = await fetchJson(normalizeMediaPath(folder, "movie.json"));
      } catch {
        meta = await fetchJson(normalizeMediaPath(folder, "series.json"));
        mediaType = "series";
      }

      const posterFile = meta.poster || "poster.jpg";

      return {
        id: meta.id || folder,
        folder,
        mediaType,
        title: meta.title || folder,
        year: meta.year || "",
        description: meta.description || "",
        tags: Array.isArray(meta.tags) ? meta.tags : [],
        duration: Number.isFinite(meta.duration) ? meta.duration : null,
        durationHint: meta.durationHint || "",
        poster: normalizeMediaPath(folder, posterFile),
      };
    })
  );

  return results;
}

async function loadMovieById(movieId) {
  const safeId = String(movieId || "").trim();
  if (!safeId) {
    throw new Error("缺少影片 ID");
  }

  const meta = await fetchJson(normalizeMediaPath(safeId, "movie.json"));
  const videoFile = meta.video || "movie.mp4";

  return {
    id: meta.id || safeId,
    folder: safeId,
    title: meta.title || safeId,
    year: meta.year || "",
    description: meta.description || "",
    tags: Array.isArray(meta.tags) ? meta.tags : [],
    duration: Number.isFinite(meta.duration) ? meta.duration : null,
    durationHint: meta.durationHint || "",
    poster: normalizeMediaPath(safeId, meta.poster || "poster.jpg"),
    video: normalizeMediaPath(safeId, videoFile),
    subtitles: Array.isArray(meta.subtitles) ? meta.subtitles : [],
  };
}

async function loadSeriesById(seriesId) {
  const safeId = String(seriesId || "").trim();
  if (!safeId) {
    throw new Error("缺少影集 ID");
  }

  const meta = await fetchJson(normalizeMediaPath(safeId, "series.json"));
  const seasons = Array.isArray(meta.seasons) ? meta.seasons : [];

  return {
    id: meta.id || safeId,
    folder: safeId,
    mediaType: "series",
    title: meta.title || safeId,
    year: meta.year || "",
    description: meta.description || "",
    tags: Array.isArray(meta.tags) ? meta.tags : [],
    poster: normalizeMediaPath(safeId, meta.poster || "poster.jpg"),
    seasons,
  };
}

async function loadMediaById(id, hintType) {
  if (hintType === "series") {
    return loadSeriesById(id);
  }

  if (hintType === "movie") {
    return loadMovieById(id);
  }

  try {
    return await loadMovieById(id);
  } catch {
    return loadSeriesById(id);
  }
}

function getQueryParam(name) {
  const url = new URL(window.location.href);
  return url.searchParams.get(name);
}

function srtToVtt(srtText) {
  const normalized = srtText
    .replace(/\r+/g, "")
    .replace(/^(\d+)$/gm, "")
    .replace(/(\d{2}:\d{2}:\d{2}),(\d{3})/g, "$1.$2")
    .trim();
  return `WEBVTT\n\n${normalized}\n`;
}

async function prepareSubtitleTrack(folder, track) {
  if (!track || !track.file) return null;
  const src = toMediaUrl(normalizeMediaPath(folder, track.file));
  if (track.file.toLowerCase().endsWith(".vtt")) {
    return { src, kind: "captions", srclang: track.lang || "zh", label: track.label || "字幕" };
  }

  if (track.file.toLowerCase().endsWith(".srt")) {
    const response = await fetch(src);
    if (!response.ok) {
      console.warn("[WARNING] Subtitle file missing:", src);
      return null;
    }
    const srt = await response.text();
    const vtt = srtToVtt(srt);
    const blobUrl = URL.createObjectURL(new Blob([vtt], { type: "text/vtt" }));
    runtime.subtitleBlobUrls.push(blobUrl);
    return {
      src: blobUrl,
      kind: "captions",
      srclang: track.lang || "zh",
      label: track.label || "字幕",
    };
  }

  return null;
}

function clearSubtitleBlobUrls() {
  runtime.subtitleBlobUrls.forEach((url) => URL.revokeObjectURL(url));
  runtime.subtitleBlobUrls = [];
}

function cleanupNativeHandlers(videoElement) {
  runtime.nativeHandlers.forEach(({ type, handler }) => {
    videoElement.removeEventListener(type, handler);
  });
  runtime.nativeHandlers = [];
}

function clearTrackElements(videoElement) {
  videoElement.querySelectorAll("track").forEach((node) => node.remove());
}

function disposeRuntimePlayer() {
  const videoElement = byId("videoPlayer");
  if (!videoElement) return;

  cleanupNativeHandlers(videoElement);
  clearTrackElements(videoElement);
  clearSubtitleBlobUrls();

  if (runtime.player && typeof runtime.player.dispose === "function") {
    runtime.player.dispose();
    runtime.player = null;
  }
}

function attachSubtitleTracksToVideo(videoElement, subtitleTracks) {
  if (!videoElement) return;

  clearTrackElements(videoElement);

  subtitleTracks.forEach((track, index) => {
    const trackElement = document.createElement("track");
    trackElement.kind = track.kind || "captions";
    trackElement.src = track.src;
    trackElement.srclang = track.srclang || "zh";
    trackElement.label = track.label || "字幕";
    if (index === 0) trackElement.default = true;
    videoElement.appendChild(trackElement);
  });
}

function registerNativeHandler(videoElement, type, handler) {
  videoElement.addEventListener(type, handler);
  runtime.nativeHandlers.push({ type, handler });
}

function updatePlayerMetaText(playerMeta, description, duration) {
  const text = description || "";
  const durationText = formatMinutes(duration);
  playerMeta.textContent = durationText ? `${text} ・ ${durationText}` : text;
}

function clearVideoJsRemoteTracks(player) {
  if (!player || typeof player.remoteTextTracks !== "function") return;
  const list = player.remoteTextTracks();
  const tracks = [];
  for (let i = 0; i < list.length; i += 1) {
    tracks.push(list[i]);
  }
  tracks.forEach((track) => {
    try {
      player.removeRemoteTextTrack(track);
    } catch {
    }
  });
}

function resolveSeasonAndEpisode(seriesData, seasonParam, episodeParam) {
  const seasons = Array.isArray(seriesData.seasons) ? seriesData.seasons : [];
  const fallbackSeason = seasons[0] || null;
  if (!fallbackSeason) return { season: null, episode: null };

  const parsedSeason = Number.parseInt(String(seasonParam || ""), 10);
  const selectedSeason = seasons.find((season) => season.season === parsedSeason) || fallbackSeason;

  const episodes = Array.isArray(selectedSeason.episodes) ? selectedSeason.episodes : [];
  const fallbackEpisode = episodes[0] || null;
  if (!fallbackEpisode) return { season: selectedSeason, episode: null };

  const parsedEpisode = Number.parseInt(String(episodeParam || ""), 10);
  const selectedEpisode = episodes.find((episode) => episode.episode === parsedEpisode) || fallbackEpisode;

  return { season: selectedSeason, episode: selectedEpisode };
}

function updateSeriesQuery(seriesId, seasonNumber, episodeNumber) {
  const url = new URL(window.location.href);
  url.searchParams.set("id", seriesId);
  url.searchParams.set("type", "series");
  url.searchParams.set("season", String(seasonNumber));
  url.searchParams.set("episode", String(episodeNumber));
  history.replaceState(null, "", url.toString());
}

async function buildPreparedSubtitles(folder, subtitles) {
  if (!Array.isArray(subtitles) || !subtitles.length) return [];
  const tracks = await Promise.all(subtitles.map((track) => prepareSubtitleTrack(folder, track)));
  return tracks.filter(Boolean);
}

async function playSource({
  source,
  subtitles,
  folder,
  progressId,
  description,
  durationHint,
  playerMeta,
}) {
  const videoElement = byId("videoPlayer");
  if (!videoElement) throw new Error("找不到播放器元素");

  const encodedSource = toMediaUrl(source);
  warnIfPotentiallyUnsupported(encodedSource);
  await warnIfMediaMissing(encodedSource);

  cleanupNativeHandlers(videoElement);
  clearSubtitleBlobUrls();

  const subtitleTracks = await buildPreparedSubtitles(folder, subtitles);
  attachSubtitleTracksToVideo(videoElement, subtitleTracks);

  const saved = loadProgress(progressId);

  if (typeof window.videojs === "function") {
    if (!runtime.player || typeof runtime.player.isDisposed === "function" && runtime.player.isDisposed()) {
      runtime.player = window.videojs("videoPlayer", {
        controls: true,
        autoplay: false,
        preload: "metadata",
        fluid: true,
        playbackRates: [0.75, 1, 1.25, 1.5, 2],
        html5: {
          nativeTextTracks: false,
        },
      });
    }

    clearVideoJsRemoteTracks(runtime.player);
    runtime.player.src([{ src: encodedSource, type: encodedSource.endsWith(".mkv") ? "video/x-matroska" : "video/mp4" }]);
    runtime.player.load();

    runtime.player.ready(() => {
      let textTracks = runtime.player.textTracks();

      if ((!textTracks || textTracks.length === 0) && subtitleTracks.length > 0) {
        subtitleTracks.forEach((track, index) => {
          runtime.player.addRemoteTextTrack(
            {
              kind: track.kind,
              src: track.src,
              srclang: track.srclang,
              label: track.label,
              default: index === 0,
            },
            false
          );
        });
        textTracks = runtime.player.textTracks();
      }

      if (textTracks && textTracks.length > 0) {
        textTracks[0].mode = "showing";
      }
    });

    if (saved && Number.isFinite(saved.currentTime) && saved.currentTime > 0) {
      runtime.player.one("loadedmetadata", () => {
        const maxSeek = Math.max(0, runtime.player.duration() - 8);
        runtime.player.currentTime(Math.min(saved.currentTime, maxSeek));
      });
    }

    if (runtime.playerHandlers) {
      runtime.player.off("timeupdate", runtime.playerHandlers.timeupdate);
      runtime.player.off("pause", runtime.playerHandlers.pause);
      runtime.player.off("ended", runtime.playerHandlers.ended);
    }

    let lastSavedSecond = -1;
    const persist = () => {
      saveProgress(progressId, {
        currentTime: runtime.player.currentTime(),
        duration: runtime.player.duration(),
        updatedAt: Date.now(),
      });
    };

    const onTimeupdate = () => {
      const second = Math.floor(runtime.player.currentTime());
      if (second % 5 === 0 && second !== lastSavedSecond) {
        lastSavedSecond = second;
        persist();
      }
    };
    const onPause = () => persist();
    const onEnded = () => {
      saveProgress(progressId, {
        currentTime: 0,
        duration: runtime.player.duration(),
        updatedAt: Date.now(),
      });
    };

    runtime.playerHandlers = {
      timeupdate: onTimeupdate,
      pause: onPause,
      ended: onEnded,
    };

    runtime.player.on("timeupdate", onTimeupdate);
    runtime.player.on("pause", onPause);
    runtime.player.on("ended", onEnded);

    runtime.player.one("loadedmetadata", () => {
      const duration = Number.isFinite(runtime.player.duration()) && runtime.player.duration() > 0
        ? runtime.player.duration()
        : durationHint;
      updatePlayerMetaText(playerMeta, description, duration);
      const autoPlay = runtime.player.play();
      if (autoPlay && typeof autoPlay.catch === "function") {
        autoPlay.catch(() => {
        });
      }
    });
    return;
  }

  videoElement.classList.remove("video-js", "vjs-big-play-centered");
  videoElement.src = encodedSource;
  videoElement.preload = "metadata";
  videoElement.controls = true;
  videoElement.playsInline = true;
  videoElement.load();

  if (saved && Number.isFinite(saved.currentTime) && saved.currentTime > 0) {
    const onLoadedForSeek = () => {
      const maxSeek = Math.max(0, videoElement.duration - 8);
      videoElement.currentTime = Math.min(saved.currentTime, maxSeek);
    };
    registerNativeHandler(videoElement, "loadedmetadata", onLoadedForSeek);
  }

  let lastSavedSecond = -1;
  const persistNative = () => {
    saveProgress(progressId, {
      currentTime: videoElement.currentTime,
      duration: videoElement.duration,
      updatedAt: Date.now(),
    });
  };

  const onTimeupdate = () => {
    const second = Math.floor(videoElement.currentTime);
    if (second % 5 === 0 && second !== lastSavedSecond) {
      lastSavedSecond = second;
      persistNative();
    }
  };
  const onPause = () => persistNative();
  const onEnded = () => {
    saveProgress(progressId, {
      currentTime: 0,
      duration: videoElement.duration,
      updatedAt: Date.now(),
    });
  };
  const onLoadedForMeta = () => {
    const duration = Number.isFinite(videoElement.duration) && videoElement.duration > 0
      ? videoElement.duration
      : durationHint;
    updatePlayerMetaText(playerMeta, description, duration);
  };

  registerNativeHandler(videoElement, "timeupdate", onTimeupdate);
  registerNativeHandler(videoElement, "pause", onPause);
  registerNativeHandler(videoElement, "ended", onEnded);
  registerNativeHandler(videoElement, "loadedmetadata", onLoadedForMeta);

  const nativePlay = videoElement.play();
  if (nativePlay && typeof nativePlay.catch === "function") {
    nativePlay.catch(() => {
    });
  }

  playerMeta.textContent = `${description || ""} ・ Video.js 載入失敗，已切換為原生播放器`;
}

function showSeriesPanel(show) {
  const panel = byId("seriesPanel");
  if (!panel) return;
  panel.classList.toggle("hidden", !show);
}

function renderEpisodeList({
  seriesData,
  seasonData,
  activeEpisodeNumber,
  onSelectEpisode,
}) {
  const list = byId("episodeList");
  if (!list) return;

  list.innerHTML = "";
  const episodes = Array.isArray(seasonData.episodes) ? seasonData.episodes : [];

  const select = document.createElement("select");
  select.className = "season-select";

  episodes.forEach((episode) => {
    const progressId = buildSeriesEpisodeProgressId(seriesData.id, seasonData.season, episode.episode);
    const progress = loadProgress(progressId);
    const progressText =
      progress && progress.duration
        ? `${Math.round((progress.currentTime / progress.duration) * 100)}%`
        : "未觀看";

    const option = document.createElement("option");
    option.value = String(episode.episode);
    option.textContent = `第 ${episode.episode} 集・${episode.title || "未命名"}・${progressText}`;
    select.appendChild(option);
  });

  select.value = String(activeEpisodeNumber);
  select.addEventListener("change", async (event) => {
    const targetEpisode = Number.parseInt(event.target.value, 10);
    await onSelectEpisode(targetEpisode);
  });
  list.appendChild(select);
}

async function initSeriesPlayer({ seriesData, playerTitle, playerMeta }) {
  showSeriesPanel(true);
  const seasonSelect = byId("seasonSelect");

  const seasonParam = getQueryParam("season");
  const episodeParam = getQueryParam("episode");
  let { season, episode } = resolveSeasonAndEpisode(seriesData, seasonParam, episodeParam);

  if (!season || !episode) {
    playerTitle.textContent = "影集資料不完整";
    return;
  }

  const selectSeason = async (seasonNumber, episodeNumberHint = null) => {
    const nextSeason = seriesData.seasons.find((entry) => entry.season === seasonNumber) || seriesData.seasons[0];
    if (!nextSeason) return;
    const nextEpisodes = Array.isArray(nextSeason.episodes) ? nextSeason.episodes : [];
    if (!nextEpisodes.length) return;

    const nextEpisode = nextEpisodes.find((entry) => entry.episode === episodeNumberHint) || nextEpisodes[0];
    if (!nextEpisode) return;

    season = nextSeason;
    episode = nextEpisode;

    updateSeriesQuery(seriesData.id, season.season, episode.episode);
    playerTitle.textContent = `${seriesData.title} - S${season.season}E${episode.episode} ${episode.title || ""}`;

    renderEpisodeList({
      seriesData,
      seasonData: season,
      activeEpisodeNumber: episode.episode,
      onSelectEpisode: async (targetEpisode) => selectSeason(season.season, targetEpisode),
    });

    if (seasonSelect) {
      seasonSelect.value = String(season.season);
    }

    const progressId = buildSeriesEpisodeProgressId(seriesData.id, season.season, episode.episode);
    const sourceFile = episode.video || "";
    if (!sourceFile) {
      playerMeta.textContent = "此集缺少 video 檔案定義";
      return;
    }

    await playSource({
      source: normalizeMediaPath(seriesData.folder, sourceFile),
      subtitles: Array.isArray(episode.subtitles) ? episode.subtitles : [],
      folder: seriesData.folder,
      progressId,
      description: episode.description || seriesData.description || "",
      durationHint: Number.isFinite(episode.duration) ? episode.duration : null,
      playerMeta,
    });
  };

  if (seasonSelect) {
    seasonSelect.innerHTML = "";
    seriesData.seasons.forEach((seasonEntry) => {
      const option = document.createElement("option");
      option.value = String(seasonEntry.season);
      option.textContent = seasonEntry.title || `Season ${seasonEntry.season}`;
      seasonSelect.appendChild(option);
    });
    seasonSelect.addEventListener("change", async (event) => {
      const nextSeason = Number.parseInt(event.target.value, 10);
      await selectSeason(nextSeason, null);
    });
  }

  await selectSeason(season.season, episode.episode);
}

async function initIndexPage() {
  try {
    const items = await loadLibrary();
    state.items = items;
    setupSearch();
    renderFilters();
    renderGrid();
  } catch (error) {
    renderStatus(error.message || "載入失敗");
  }
}

async function initPlayerPage() {
  const playerTitle = byId("playerTitle");
  const playerMeta = byId("playerMeta");
  const movieId = getQueryParam("id");
  const typeHint = getQueryParam("type");

  if (!movieId) {
    playerTitle.textContent = "缺少影片 ID";
    return;
  }

  try {
    const target = await loadMediaById(movieId, typeHint);

    if (target.mediaType === "series") {
      await initSeriesPlayer({
        seriesData: target,
        playerTitle,
        playerMeta,
      });
      return;
    }

    showSeriesPanel(false);
    playerTitle.textContent = `${target.title} (${target.year || "N/A"})`;
    await playSource({
      source: target.video,
      subtitles: target.subtitles,
      folder: target.folder,
      progressId: target.id,
      description: target.description || "",
      durationHint: target.duration,
      playerMeta,
    });
  } catch (error) {
    playerTitle.textContent = error.message || "播放器初始化失敗";
  }
}

function bootstrap() {
  const page = document.body.getAttribute("data-page");
  if (page === "index") {
    initIndexPage();
  } else if (page === "player") {
    initPlayerPage();
  }
}

bootstrap();
