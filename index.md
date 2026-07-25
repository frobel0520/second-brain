---
title: Second Brain
---

# 📚 Second Brain

**Local-first 的個人知識管理系統** —— 把散落各處的筆記、RSS 訂閱整合成一個可以語意搜尋、可以問答的私人知識庫,資料全部留在自己電腦上,沒有雲端依賴。

[![Repo](https://img.shields.io/badge/GitHub-repo-181717?logo=github)](https://github.com/frobel0520/second-brain)

---

## 這是什麼

平常會存筆記、訂 RSS,但東西散在各處,想找的時候常常想不起關鍵字、或根本不記得存在哪。Second Brain 讓你:

- **丟進去就好** —— 貼上一篇筆記或訂閱一個 RSS 來源,系統自動切塊、產生 embedding、存進資料庫
- **用語意找,不用背關鍵字** —— 搜尋「最近日圓有沒有機會」也能找到標題完全沒提到「日圓」兩個字但內容相關的文章
- **直接問,不用自己翻** —— 針對知識庫內容做 RAG 問答,答案附來源出處

## 畫面

<!-- TODO: 補上 Streamlit 網頁介面截圖(瀏覽 / 搜尋 / 問答分頁) -->
> 截圖準備中

## 架構亮點

整個系統刻意分層,每一層只做一件事,方便之後替換技術:

```
ingestion   讀取來源(檔案 / RSS)→ 統一轉成 Document
processing  切塊、embedding、自動標籤、翻譯
storage     SQLite(metadata/原文)+ ChromaDB(embedding),對外只暴露乾淨介面
retrieval   語意搜尋、RAG 問答
interface   CLI(typer)與 Streamlit 網頁,共用同一套底層邏輯
```

- **Embedding / 標籤 / 翻譯都包成抽象介面**(`EmbeddingProvider`、`TaggingProvider`、`TranslationProvider`),換模型或換成 API 不用動上層邏輯
- **本機 embedding 模型**(`sentence-transformers`),下載一次後離線可用,不吃 API 額度
- **CLI 跟網頁介面共用同一套 ingestion pipeline**,不會有兩邊邏輯兜不起來的問題

## 技術棧

Python 3.11+ · Typer(CLI) · Streamlit(網頁介面) · SQLite · ChromaDB · sentence-transformers · Anthropic API(問答/翻譯,選用)

## 想看細節?

完整功能清單、CLI 指令、開發規則都在 [README](https://github.com/frobel0520/second-brain#readme)。

這是個人 side project,主要使用情境是我自己整理新聞訂閱跟筆記,持續開發中。
