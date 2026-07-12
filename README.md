# Second Brain

Local-first 個人化知識管理系統。把分散在各處的筆記整合成一個可語意搜尋、可問答的本機知識庫。

設計原則與規劃詳見 [CLAUDE.md](CLAUDE.md)。這份 README 記錄目前實際長出來的架構與怎麼用。

## Quick Start

```bash
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[dev]"

./.venv/Scripts/python.exe -m second_brain add path/to/note.md
./.venv/Scripts/python.exe -m second_brain add-feed https://example.com/feed.xml
./.venv/Scripts/python.exe -m second_brain feeds add https://example.com/feed.xml
./.venv/Scripts/python.exe -m second_brain feeds sync
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

跑起來後瀏覽器會自動開 `http://localhost:8501`,五個分頁:瀏覽(含刪除,下方還有批次刪除區塊,對應 CLI 的 `remove-batch`)、搜尋、問答、新增筆記(上傳檔案 / 一次性抓 RSS)、訂閱管理(常態追蹤 RSS 來源:訂閱/同步/取消訂閱,對應 CLI 的 `feeds` 指令組)。沒有網頁版的 `clear`,清空知識庫還是要用 CLI(危險操作,刻意不放進網頁介面)。

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
│   └── pipeline.py        # ingest_document():標籤→切塊→embedding→dedupe→存檔,CLI/網頁共用;sync_feed_subscription()/sync_all_feed_subscriptions():同步訂閱清單
├── processing/       # 清洗、切塊、embedding、自動標籤
│   ├── chunking.py       # chunk_text() / chunk_document()
│   ├── embedding.py      # EmbeddingProvider 抽象介面 + SentenceTransformer 實作
│   └── tagging.py        # TaggingProvider 抽象介面 + 本機 jieba 詞頻抽取實作
├── storage/          # SQLite + ChromaDB 讀寫封裝
│   ├── sqlite_store.py   # metadata / 原文 (SQLite)
│   ├── vector_store.py   # embedding (ChromaDB, persistent, 本機檔案)
│   └── store.py          # 對外唯一介面: save_document(), search_similar(), list_documents(), replace_existing_document(), remove_document(), remove_documents(), find_documents(), clear_all(), subscribe_feed(), unsubscribe_feed(), list_feed_subscriptions(), mark_feed_synced()
├── retrieval/         # 語意搜尋、RAG 問答
│   ├── search.py         # search(): query 轉 embedding → search_similar(),回傳的 SearchResult 帶 document.created_at
│   └── ask.py            # ask(): search() 結果組 context → 呼叫 Anthropic API 做問答,回傳 AskResult(answer, sources)
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
- **feed 訂閱清單**(`feeds` 指令組)跟一次性的 `add-feed` 是分開的功能:`add-feed` 抓一次就忘記,`feeds add` 會把來源記進 SQLite 的 `feeds` 表,之後可以用 `feeds sync` 一次同步所有訂閱來源。同步邏輯(`ingestion/pipeline.py:sync_feed_subscription()`)內部還是呼叫 `load_feed()` + `ingest_document()`,不重寫抓取/dedupe 邏輯;CLI 的 `feeds add` 跟網頁介面的「訂閱管理」分頁都呼叫同一個 `sync_feed_subscription()` 做第一次同步,不各自兜一份
- **`remove-batch` 的日期/關鍵字/來源三個條件是 OR,不是 AND**:`storage/sqlite_store.py:find_documents()` 把有給的條件各自組成一段 SQL 子句,再用 `OR` 串起來;`--after`/`--before` 兩個一起給是例外,彼此是 `AND`(定義一段日期區間),這段區間本身再跟其他條件用 `OR`。跟 `clear` 一樣,刪除前會列出符合項目並要求確認(`--yes` 可跳過)。**網頁介面「瀏覽」分頁下方的批次刪除區塊是同一套 `find_documents()`/`remove_documents()`**,兩邊條件語意完全一致;網頁版用「預覽→勾選確認→刪除」兩步驟代替 CLI 的互動式 `[y/N]` 提示,「刪除這些文件」按鈕要先勾選確認 checkbox 才會出現
- **`documents.tags`/`metadata` 這兩個 JSON 欄位存的時候要用 `json.dumps(..., ensure_ascii=False)`**,不能用預設值:預設 `ensure_ascii=True` 會把中文字轉成 `\uXXXX` 跳脫序列存進 SQLite,`find_documents()` 用 `LIKE` 對 `tags` 欄位做關鍵字比對時完全比對不到中文標籤。這個修正只影響「之後新寫入」的資料;**這次修正之前就已經存在的舊資料,`tags` 欄位仍是 ASCII 跳脫格式**,要重新 `add`/`feeds sync` 過一次才會用新格式存,`remove-batch --keyword` 在那之前對舊資料的標籤比對不到(標題/內容欄位本來就是純文字,不受影響)
- `interface/` 底下的 `cli.py` 跟 `web.py` 是同一組核心邏輯的兩種操作介面,兩者都不直接碰 SQLite/ChromaDB,一律透過 `storage`/`retrieval`/`ingestion.pipeline` 的介面
- **`rss_loader.py` 對太短的 RSS description 會退回用標題當內容**:像 Hacker News 這種來源,`<description>` 只有「Comments」這種佔位文字,不是真正的文章內容。如果直接拿這種內容當 `add` 的 dedupe 比對基準(見上面的「同一份筆記」判斷邏輯),同一批裡好幾篇文章會因為內容完全相同(都是「Comments」)被誤判成「同一篇改名」,一篇篇疊代覆蓋掉——實測訂閱 Hacker News 時 5 篇文章最後只剩 1 篇存活。修法:內容長度低於 `rss_loader._MIN_CONTENT_LENGTH`(20 字)就用標題取代,標題天生就跟其他文章不同,不會互撞。

資料預設存在 `data/`(已 gitignore):
- `data/second_brain.db` — SQLite,存文件原文與 metadata
- `data/chroma/` — ChromaDB persistent store,存 embedding

## CLI 指令

| 指令 | 狀態 | 說明 |
|---|---|---|
| `second-brain add <file_path>` | ✅ 已實作 | 讀取 markdown/text 檔案 → 自動標籤 → 切塊 → 產生 embedding → 存進 SQLite + ChromaDB |
| `second-brain add-feed <feed_url> [--limit/-n N]` | ✅ 已實作 | 一次性抓取 RSS/Atom 來源,每篇文章當一份筆記加入知識庫(預設最多 10 篇),不會記住這個來源 |
| `second-brain feeds add <feed_url> [--name] [--limit/-n N]` | ✅ 已實作 | 把來源加進訂閱清單並立刻同步一次;名稱不給的話會嘗試抓 feed 標題,抓不到就用網址本身 |
| `second-brain feeds list` | ✅ 已實作 | 列出訂閱清單(名稱、網址、上次同步時間) |
| `second-brain feeds remove <feed_url>` | ✅ 已實作 | 從訂閱清單移除來源,不會刪除已經加入知識庫的文章 |
| `second-brain feeds sync [--limit/-n N]` | ✅ 已實作 | 同步訂閱清單裡的所有來源,抓新文章、更新舊文章,一個來源失敗不會擋住其他來源 |
| `second-brain search "<query>" [--top-k K]` | ✅ 已實作 | 把 query 轉成向量,語意搜尋,回傳最相關的片段(含來源、分數、加入時間) |
| `second-brain ask "<query>" [--top-k K]` | ✅ 已實作 | 在 search 結果基礎上用 Anthropic API(`claude-opus-4-8`)做 RAG 問答,答案下面附來源標題與時間,需要 `ANTHROPIC_API_KEY` |
| `second-brain list` | ✅ 已實作 | 列出知識庫裡目前有哪些文件(標題、片段數、來源路徑、標籤) |
| `second-brain remove <source>` | ✅ 已實作 | 從知識庫移除指定來源的紀錄(sqlite + chroma),不動硬碟上的檔案本身;本機檔案路徑或 RSS 文章網址都可以,檔案不用還存在 |
| `second-brain remove-batch [--after DATE] [--before DATE] [--keyword K] [--source S] [--yes/-y]` | ✅ 已實作 | 依日期範圍/關鍵字/來源批次刪除文件,三種條件符合任一個就刪(OR);至少要給一個條件;刪除前列出符合項目並要求確認 |
| `second-brain clear [--yes/-y]` | ✅ 已實作 | 清空整個知識庫(sqlite + chroma);預設會互動確認,`--yes` 跳過確認 |

## 開發

```bash
# 跑測試
./.venv/Scripts/python.exe -m pytest -q
```

測試結構鏡射 `second_brain/`,放在 `tests/` 底下。
