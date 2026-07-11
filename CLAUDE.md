# Second Brain — 個人化知識管理系統

## 專案目標
打造一個 local-first 的個人知識管理系統,把分散在各處的筆記/文章整合成一個
可語意搜尋、可問答的知識庫。長期持續開發,每天疊加新功能。

## 核心原則
- **Local-first**:預設所有東西跑在本機,零雲端依賴、零額外費用。
  雲端/API 選項一律設計成可替換的介面,不寫死。
- **分層架構**:每一層獨立、單一職責,方便之後替換技術或擴充功能。
- **先求能動,再求完美**:每個功能先做最小可行版本,能跑通再優化。
- **CLI-first**:所有功能先透過 CLI 驗證好用,之後才考慮 Web UI。

## 技術棧
- 語言:Python 3.11+
- CLI 框架:`typer`
- 結構化資料儲存:SQLite(存 metadata、原文、來源資訊)
- 向量儲存:`chromadb`(persistent client,純本機檔案,不開伺服器)
- Embedding:`sentence-transformers`(本機執行,離線可用,免 API key)
- 問答層(RAG 的 generation 階段):Anthropic API(之後接,MVP 階段可先跳過)

## 架構分層

```
second_brain/
├── ingestion/    # 資料擷取層 — 各種來源的 loader,統一輸出成 Document 物件
├── processing/   # 清洗、切塊(chunking)、產生 embedding
├── storage/      # SQLite + ChromaDB 的讀寫封裝
├── retrieval/    # 語意搜尋、（之後）RAG 問答
├── interface/    # CLI 指令(typer app)
└── models.py     # 共用的資料結構(Document, Chunk, SearchResult 等)
```

**設計規則**:
- `ingestion` 的每個 loader 只負責「讀取原始資料 → 轉成統一的 Document 格式」,
  不碰 embedding 或儲存邏輯。加新資料來源 = 加一個新的 loader 檔案。
- `storage` 層對外只暴露乾淨的介面(如 `save_document()`, `search_similar()`),
  上層不應該直接碰 SQLite/ChromaDB 的細節。
- Embedding 模型透過介面包一層(如 `EmbeddingProvider` 抽象類別),
  方便之後從 sentence-transformers 換成別的模型或 API。

## MVP 範圍(第一階段目標)

實作三個 CLI 指令,做出一個能跑通的最小閉環:

1. `second-brain add <file_path>`
   讀取本機 markdown/text 檔案 → 切塊 → 產生 embedding → 存進 SQLite + ChromaDB

2. `second-brain search "<query>"`
   把 query embed 之後,在 ChromaDB 做語意搜尋,回傳最相關的幾段內容(含來源資訊)

3. `second-brain ask "<query>"`
   在 search 的結果基礎上,呼叫 Anthropic API 做問答總結(RAG)

**MVP 階段先不做**:web UI、多資料來源整合、自動標籤/摘要、排程自動化。
這些留到 MVP 跑通之後再逐步加。

## 未來規劃方向(暫不實作,僅供參考)
- 更多 ingestion 來源:瀏覽器書籤、Read-it-later(Readwise/Instapaper)、
  Obsidian/Notion 匯出、RSS 訂閱
- 自動化處理:定期整理、自動打標籤、關聯筆記推薦、去重複
- Web UI 或跟 Raycast/Alfred 整合
- Hybrid search(關鍵字 + 語意搜尋並用)

## 開發慣例
- 所有函式/類別要有 type hints
- 每個模組對應的測試放在 `tests/` 底下,結構鏡射 `second_brain/`
- 新功能開發順序:先寫最小可行版本 → 手動測試能動 → 補測試 → 視需要重構
