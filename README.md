# Second Brain

Local-first 個人化知識管理系統。把分散在各處的筆記整合成一個可語意搜尋、可問答的本機知識庫。

設計原則與規劃詳見 [CLAUDE.md](CLAUDE.md)。這份 README 記錄目前實際長出來的架構與怎麼用。

## Quick Start

```bash
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[dev]"

./.venv/Scripts/python.exe -m second_brain add path/to/note.md
./.venv/Scripts/python.exe -m second_brain add-feed https://example.com/feed.xml
./.venv/Scripts/python.exe -m second_brain search "想搜尋的內容"
./.venv/Scripts/python.exe -m second_brain ask "想問的問題"
./.venv/Scripts/python.exe -m second_brain list
./.venv/Scripts/python.exe -m second_brain remove path/to/note.md
./.venv/Scripts/python.exe -m second_brain clear --yes
```

第一次執行 `add` 會自動下載 embedding 模型(`all-MiniLM-L6-v2`,約 90MB),之後離線可用。

`ask` 需要設定環境變數 `ANTHROPIC_API_KEY` 才能呼叫 Anthropic API;沒設定的話指令會直接印出提示並結束,不會噴出未處理的例外。

> Windows 使用者:CLI 會在啟動時把 stdout/stderr 轉成 UTF-8([cli.py](second_brain/interface/cli.py)),避免主控台預設 codepage 把中文印成亂碼。

## 網頁介面(Streamlit)

CLI 之外還有一個本機網頁介面,同一個知識庫、同一套底層邏輯,只是換一種操作方式:

```bash
./.venv/Scripts/python.exe -m pip install -e ".[ui]"
./.venv/Scripts/python.exe -m streamlit run second_brain/interface/web.py
```

跑起來後瀏覽器會自動開 `http://localhost:8501`,四個分頁:瀏覽(含刪除)、搜尋、問答、新增筆記(上傳檔案 / 訂閱 RSS)。沒有網頁版的 `clear`,清空知識庫還是要用 CLI(危險操作,刻意不放進網頁介面)。

**更快的啟動方式**(Windows):直接雙擊專案根目錄的 [run_web.bat](run_web.bat),或桌面上的「Second Brain」捷徑(第一次設定時建立的,指向這個 `.bat`)。

> Streamlit 第一次在沒有終端機互動的情況下啟動(例如雙擊捷徑)會卡住,原因是它會跳出一個一次性的「Welcome to Streamlit」提示,等使用者按 Enter 或輸入 email,但雙擊捷徑開的視窗沒有人能輸入,所以會卡住不動、永遠打不開網頁。[run_web.bat](run_web.bat) 已經處理這個問題:啟動前會自動檢查 `%USERPROFILE%\.streamlit\credentials.toml` 存不存在,不存在就自動建一個空的,讓 Streamlit 略過這個提示。如果直接用 `streamlit run` 指令手動啟動(在終端機裡跑,可以互動),不會遇到這個問題。

## 架構

```
second_brain/
├── models.py       # 共用資料結構: Document, Chunk, SearchResult, DocumentSummary
├── config.py        # 路徑與參數設定(SQLite/Chroma 路徑、chunk size 等)
├── ingestion/        # 資料擷取層 — 讀原始資料 → 轉成 Document
│   ├── loader.py         # 讀 .md / .txt 檔案
│   ├── rss_loader.py      # 讀 RSS/Atom 訂閱來源,一篇文章一個 Document
│   └── pipeline.py        # ingest_document():標籤→切塊→embedding→dedupe→存檔,CLI/網頁共用
├── processing/       # 清洗、切塊、embedding、自動標籤
│   ├── chunking.py       # chunk_text() / chunk_document()
│   ├── embedding.py      # EmbeddingProvider 抽象介面 + SentenceTransformer 實作
│   └── tagging.py        # TaggingProvider 抽象介面 + 本機 jieba 詞頻抽取實作
├── storage/          # SQLite + ChromaDB 讀寫封裝
│   ├── sqlite_store.py   # metadata / 原文 (SQLite)
│   ├── vector_store.py   # embedding (ChromaDB, persistent, 本機檔案)
│   └── store.py          # 對外唯一介面: save_document(), search_similar(), list_documents(), replace_existing_document(), remove_document(), clear_all()
├── retrieval/         # 語意搜尋、RAG 問答
│   ├── search.py         # search(): query 轉 embedding → search_similar()
│   └── ask.py            # ask(): search() 結果組 context → 呼叫 Anthropic API 做問答
└── interface/
    ├── cli.py            # typer CLI app
    └── web.py            # Streamlit 本機網頁介面
```

**設計規則**(承襲自 CLAUDE.md):
- `ingestion` 的 loader 只負責「讀原始資料 → Document」,不碰 embedding / 儲存
- `storage` 對外只暴露 `save_document()`、`search_similar()` 這種乾淨介面,上層不直接碰 SQLite/ChromaDB
- `EmbeddingProvider` 是抽象介面,之後要換模型或改用 API 只需新增一個實作
- `add` 對同一份筆記是 upsert 語意:再次 add 會刪掉舊版本(sqlite + chroma)再存新的,不會重複塞入。判斷「同一份筆記」的邏輯:先比對 `source_path`(內容改了但路徑沒變),找不到再比對 `content` 是否完全相同(路徑變了但內容沒變 —— 例如檔案改名/搬家)
- `TaggingProvider` 也是抽象介面,之後要換成 LLM 或規則式分類只需新增一個實作;`add` 時會自動呼叫,把標籤存進 `Document.tags`
- `add` 跟 `add-feed` 共用同一套「標籤 → 切塊 → embedding → 存檔」邏輯(`ingestion/pipeline.py:ingest_document()`),加新的 ingestion 來源或新的 interface(CLI、網頁)只要能產生 `Document`,就自動有標籤/dedupe/embedding,不用重寫這段
- `interface/` 底下的 `cli.py` 跟 `web.py` 是同一組核心邏輯的兩種操作介面,兩者都不直接碰 SQLite/ChromaDB,一律透過 `storage`/`retrieval`/`ingestion.pipeline` 的介面

資料預設存在 `data/`(已 gitignore):
- `data/second_brain.db` — SQLite,存文件原文與 metadata
- `data/chroma/` — ChromaDB persistent store,存 embedding

## CLI 指令

| 指令 | 狀態 | 說明 |
|---|---|---|
| `second-brain add <file_path>` | ✅ 已實作 | 讀取 markdown/text 檔案 → 自動標籤 → 切塊 → 產生 embedding → 存進 SQLite + ChromaDB |
| `second-brain add-feed <feed_url> [--limit/-n N]` | ✅ 已實作 | 抓取 RSS/Atom 訂閱來源,每篇文章當一份筆記加入知識庫(預設最多 10 篇) |
| `second-brain search "<query>" [--top-k K]` | ✅ 已實作 | 把 query 轉成向量,語意搜尋,回傳最相關的片段(含來源、分數) |
| `second-brain ask "<query>" [--top-k K]` | ✅ 已實作 | 在 search 結果基礎上用 Anthropic API(`claude-opus-4-8`)做 RAG 問答,需要 `ANTHROPIC_API_KEY` |
| `second-brain list` | ✅ 已實作 | 列出知識庫裡目前有哪些文件(標題、片段數、來源路徑、標籤) |
| `second-brain remove <file_path>` | ✅ 已實作 | 從知識庫移除指定檔案的紀錄(sqlite + chroma),不動硬碟上的檔案本身;檔案不用還存在 |
| `second-brain clear [--yes/-y]` | ✅ 已實作 | 清空整個知識庫(sqlite + chroma);預設會互動確認,`--yes` 跳過確認 |

## 開發

```bash
# 跑測試
./.venv/Scripts/python.exe -m pytest -q
```

測試結構鏡射 `second_brain/`,放在 `tests/` 底下。
