# Second Brain

Local-first 個人化知識管理系統。把分散在各處的筆記整合成一個可語意搜尋、可問答的本機知識庫。

設計原則與規劃詳見 [CLAUDE.md](CLAUDE.md)。這份 README 記錄目前實際長出來的架構與怎麼用。

## Quick Start

```bash
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[dev]"

./.venv/Scripts/python.exe -m second_brain add path/to/note.md
./.venv/Scripts/python.exe -m second_brain search "想搜尋的內容"
```

第一次執行 `add` 會自動下載 embedding 模型(`all-MiniLM-L6-v2`,約 90MB),之後離線可用。

> Windows 使用者:CLI 會在啟動時把 stdout/stderr 轉成 UTF-8([cli.py](second_brain/interface/cli.py)),避免主控台預設 codepage 把中文印成亂碼。

## 架構

```
second_brain/
├── models.py       # 共用資料結構: Document, Chunk, SearchResult
├── config.py        # 路徑與參數設定(SQLite/Chroma 路徑、chunk size 等)
├── ingestion/        # 資料擷取層 — 讀原始資料 → 轉成 Document
│   └── loader.py         # 讀 .md / .txt 檔案
├── processing/       # 清洗、切塊、embedding
│   ├── chunking.py       # chunk_text() / chunk_document()
│   └── embedding.py      # EmbeddingProvider 抽象介面 + SentenceTransformer 實作
├── storage/          # SQLite + ChromaDB 讀寫封裝
│   ├── sqlite_store.py   # metadata / 原文 (SQLite)
│   ├── vector_store.py   # embedding (ChromaDB, persistent, 本機檔案)
│   └── store.py          # 對外唯一介面: save_document(), search_similar()
├── retrieval/         # 語意搜尋、RAG 問答
│   └── search.py         # search(): query 轉 embedding → search_similar()
└── interface/
    └── cli.py            # typer CLI app
```

**設計規則**(承襲自 CLAUDE.md):
- `ingestion` 的 loader 只負責「讀原始資料 → Document」,不碰 embedding / 儲存
- `storage` 對外只暴露 `save_document()`、`search_similar()` 這種乾淨介面,上層不直接碰 SQLite/ChromaDB
- `EmbeddingProvider` 是抽象介面,之後要換模型或改用 API 只需新增一個實作

資料預設存在 `data/`(已 gitignore):
- `data/second_brain.db` — SQLite,存文件原文與 metadata
- `data/chroma/` — ChromaDB persistent store,存 embedding

## CLI 指令

| 指令 | 狀態 | 說明 |
|---|---|---|
| `second-brain add <file_path>` | ✅ 已實作 | 讀取 markdown/text 檔案 → 切塊 → 產生 embedding → 存進 SQLite + ChromaDB |
| `second-brain search "<query>" [--top-k K]` | ✅ 已實作 | 把 query 轉成向量,語意搜尋,回傳最相關的片段(含來源、分數) |
| `second-brain ask "<query>"` | ⏳ 規劃中 | 在 search 結果基礎上用 Anthropic API 做 RAG 問答 |

## 開發

```bash
# 跑測試
./.venv/Scripts/python.exe -m pytest -q
```

測試結構鏡射 `second_brain/`,放在 `tests/` 底下。
