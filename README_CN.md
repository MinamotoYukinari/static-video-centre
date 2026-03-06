# 靜態媒體庫（Static Video Centre）
[English Version](README.md)

這是一個「前端化」的媒體庫專案，目標是在低效能裝置上穩定運行（例如 Amlogic 盒子、小型 ARM 主機）。

核心設計：
- 純靜態網站（可直接用 Nginx / 任意靜態伺服器託管）
- 無後端 API
- 無資料庫
- 無轉碼流程
- 以最小後端成本提供可用的媒體瀏覽與播放體驗

播放器採用 [**Video.js**](https://github.com/videojs/video.js)，若載入失敗時會自動回退到瀏覽器原生 `<video>` 播放。如需使用 Video.js，請參考[這裡](vendor/README_CN.md)

## 功能概覽

- 片牆瀏覽（海報卡片）
- 關鍵字搜尋（片名）
- 標籤篩選（`tags`）
- 電影與影集共用入口
- 影集季 / 集切換（播放器頁）
- 字幕支援（`.srt` 會在前端轉為 WebVTT；也支援 `.vtt`）
- 觀看進度記錄（`localStorage`）

## 專案結構

```text
.
├─ index.html                 # 片庫首頁
├─ player.html                # 播放器頁
├─ script.js                  # 前端核心邏輯
├─ style.css                  # 樣式
├─ library_tools.py           # 媒體庫生成 / 更新入口（Python）
├─ tmdb_api.json              # TMDB API Key 設定
├─ requirements.txt           # Python 依賴
├─ media/
│  ├─ library.json            # 媒體索引
│  ├─ movie.schema.json       # 電影中繼資料（metadata）schema
│  ├─ series.schema.json      # 影集中繼資料（metadata）schema
│  ├─ <MovieFolder>/movie.json
│  └─ <SeriesFolder>/series.json
├─ tools/
│  ├─ scan_media.py           # 掃描本地媒體檔案
│  ├─ metadata_builder.py     # 建立 / 更新中繼資料（metadata）
│  └─ tmdb_client.py          # TMDB API 客戶端
└─ vendor/
	 ├─ video.min.js
	 └─ video-js.css
```

## 資料模型（核心）

### 1) `media/library.json`

僅維護資料夾索引：

```json
{
	"movies": ["Titanic", "NCIS"]
}
```

> 專案目前以 `movies` 陣列作為統一索引（電影與影集都可放在此陣列，前端會再判斷 `movie.json` / `series.json`）。

### 2) 電影 `media/<Folder>/movie.json`

```json
{
	"id": "Sample_Movie_A",
	"title": "範例電影 A",
	"year": 2026,
	"description": "...",
	"duration": 5400,
	"tags": ["科幻"],
	"video": "Sample_Movie_A_2026.mp4",
	"poster": "poster.jpg",
	"subtitles": [
		{ "label": "繁體中文", "file": "Sample_Movie_A_zh.srt" }
	]
}
```

### 3) 影集 `media/<Folder>/series.json`

```json
{
	"id": "Sample_Series_B",
	"type": "series",
	"title": "範例影集 B",
	"year": 2025,
	"description": "...",
	"poster": "poster.jpg",
	"tags": ["科幻"],
	"seasons": [
		{
			"season": 1,
			"title": "第 1 季",
			"episodes": [
				{
					"episode": 1,
					"title": "第 1 集",
					"description": "...",
					"duration": 2700,
					"video": "S01/S01E01.mp4",
					"subtitles": [
						{ "label": "繁體中文", "file": "S01/S01E01_zh.srt" }
					]
				}
			]
		}
	]
}
```

## 本地開發與啟動

### 1) Python 依賴

```bash
pip install -r requirements.txt
```

### 2) 設定 TMDB API Key

建立或修改 `tmdb_api.json`：

```json
{
	"api_key": "YOUR_TMDB_API_KEY"
}
```

### 3) 生成 / 更新媒體中繼資料（metadata）

```bash
python library_tools.py
```

強制刷新既有條目（重新抓 TMDB 資料）：

```bash
python library_tools.py --refresh
```

### 4) 啟動靜態伺服器

```bash
python -m http.server 8000
```

開啟：
- `http://localhost:8000/index.html`

## 媒體檔案放置建議

- 電影：
	- `media/<MovieName>/movie.json`
	- `media/<MovieName>/<video-file>.mp4`
	- `media/<MovieName>/poster.jpg`
- 影集：
	- `media/<SeriesName>/series.json`
	- `media/<SeriesName>/S01/S01E01.mp4`（建議命名規則 `SxxExx`）
	- `media/<SeriesName>/S01/S01E01_zh.srt`

## 設計取向

本專案刻意避免「高後端成本」方案：
- 不做即時轉碼
- 不引入資料庫服務
- 不依賴常駐後端程序

適合情境：
- 家用內網媒體庫
- 輕量 NAS / 電視盒環境
- 想快速部署、低維護成本的影音索引站

## 已知限制

- MKV 是否可播取決於瀏覽器編解碼能力
- 觀看進度保存在瀏覽器本機（換裝置不會同步）
- 目前流程偏向「本地檔案結構 + TMDB 中繼資料（metadata）」

---
