# Progress

這份文件是給「接手這個專案的下一個 Claude 對話」看的交接筆記,不是使用手冊。
使用方式看 [README.md](README.md),規劃看 [CLAUDE.md](CLAUDE.md)。這份只記錄
「現在做到哪、為什麼這樣做、接下來大概要做什麼」,每次做完一個階段性任務就更新。

最後更新:2026-07-20(第十七輪:加星保留 + `prune` 自動清理)

## 現況一句話

CLAUDE.md 的 MVP 加上很多擴充都做完了:**18 個 CLI 指令**(見下面清單)、自動打標籤、
hybrid search、文件分類、RSS 訂閱(CLI+網頁)、**Streamlit 五分頁網頁介面**、一鍵啟動、
翻譯成繁中、**`feeds sync` 排程自動化**、**加星保留 + `prune` 自動清理舊文件**。知識庫有
真實資料:**9 個訂閱來源**(科技/財經/新聞各 3)、**約 420 篇文件**(第 17 輪跑過 `prune` 把
一週外沒加星的文章刪掉,之後篇數會維持在「最近一週 + 加星文章」的範圍內,不再無限累積),
全部分類完畢、沒有未分類的。
**排程自動化 CLAUDE.md 原本明確排除在 MVP 外,是使用者主動要求才做的,不是自己決定跨範圍。**

## 逐輪變更摘要(新到舊,只留還有效的結論)

- **17**(2026-07-20,commit `2fa9e05`):使用者提議「新聞留一週、加星永久保留」,討論後直接動工
  (使用者說「直接做」,沒有停在 dry-run)。加三個 CLI 指令:`star <source>` / `unstar <source>`
  (依來源路徑/網址切換加星狀態)、`prune [--days 7] [-y]`(刪除超過天數、且沒加星的文件,沿用
  `remove-batch`/`clear` 的預覽+確認機制)。**`documents` 表加 `starred INTEGER NOT NULL DEFAULT 0`
  欄位**(`_ensure_column` migration,舊資料庫自動補、預設未加星)。`Document`/`DocumentSummary`
  加 `starred: bool = False`。`find_documents()` 比照 `category` 的模式加 `starred: bool | None`
  當獨立 AND 條件(疊加在原本的 OR 群組上),`prune` 用
  `find_documents(created_before=cutoff, starred=False)` 找符合的文件。網頁「瀏覽」卡片先加了
  星星切換鈕(☆/★),使用者後續要求**拿掉卡片右上角原本的「×」單篇刪除鈕、把 ☆ 移到那個位置**
  ——現在瀏覽卡片沒有單篇刪除功能了,要刪文件只能用下面的「批次刪除」區塊(`remove_document`
  import 也跟著移除)。**`prune` 已經實際對真實知識庫執行過**(`--days 7 -y`):刪除 410 篇
  一週以外、沒加星的文件,知識庫從 830 篇左右降到 **420 篇**,最舊剩下的是 2026-07-14。
  `prune` **目前沒有接進 `SecondBrainFeedsSync` 排程**,還是純手動指令,要不要自動化留給下一輪
  使用者決定。補了 9 個測試(118 個全過)。
- **16**(2026-07-13-14,commit `12da665` + 收尾一筆):瀏覽/搜尋頁面,只動 `web.py`。瀏覽依加入時間
  由新到舊、一頁 10 筆左右兩欄各 5、箭頭式分頁、移除「片段數」、刪除鍵縮成小「×」、
  **瀏覽卡片不再顯示標籤 🏷️**(2026-07-14 補;標籤仍存在 `document.tags`/後台,search 照樣用);
  搜尋加排序下拉(相關性/日期新到舊)。**搜尋結果卡片的標籤還留著**(搜尋情境下對判斷相關性有幫助)。**修掉一個埋著的問題:搜尋結果原本被寫死永遠依
  日期排,等於 hybrid search 的相關度排序失效了**,這輪預設改回相關性、日期變可選。
  ⚠️ **這輪只做 `ast.parse` 語法檢查,沒開 Streamlit 實測渲染**(使用者要求收工),
  下一輪動這頁建議補 Browser pane 驗證(欄位左右分佈、箭頭首末頁 disabled、× 位置)。
  **另外討論過部署(沒改碼)**:GitHub Pages 不行(只託管靜態檔、跑不了 Python、個資隱私、
  違背 local-first);使用者要「老家電腦也能用」,三選項(A 老家裝獨立一份 / B Tailscale 遠端
  連回主力機 / C 雲端 PaaS)裡**選 A,且明確說資料不用同步、功能能用就好**。下一步若使用者
  follow-up 就引導在老家:裝 Python 3.11+ → `git clone https://github.com/frobel0520/second-brain.git`
  → 建 venv → `pip install -e ".[ui]"` →(要問答/翻譯才 `setx ANTHROPIC_API_KEY`)→ `run_web.bat`。
  注意 `.gitignore` 排除 `data/`,clone 下來是**空知識庫**(這是對的);首次啟動要連網下載模型。
- **15**(commit `e8e1959`):網頁介面打磨三項——新增筆記後自動跳「瀏覽」分頁、瀏覽加分頁、
  「同步全部」失敗改折疊分組。**技術前提:導覽從 `st.tabs()` 換成 `st.segmented_control()`**
  (`st.tabs()` 無法用程式碼切換分頁;`segmented_control` 可綁 `key` 到 session_state,在
  widget 建立**前**先改值再 `st.rerun()` 達成跳轉)。整個檔案從 `with tab:` 改成
  `active_tab = st.segmented_control(...); if active_tab == "x":`。三項都用 Browser pane 實測過。
- **14**(無改碼):查證排程行為——`StartWhenAvailable=True`(電腦關機錯過那次,會在下次
  登入時補跑),但 `LogonType=Interactive`(綁使用者登入,不是「開機就跑」)。目前沒設 key,
  自動翻譯靜默失敗、不花 token;**但若之後設了 key(例如只是想用 `ask`),排程會無感地開始
  幫每天新文章呼叫 API 翻譯、長期會產生費用**,設 key 時要主動提醒這個關聯。移除兩個 TODO
  (更多財經來源、翻譯品質驗證)。
- **13**(commit `f846938`):`feeds sync --log-file` + Windows 排程自動化(見下面專節)。
- **12**:退訂三個英文科技來源(The Verge/Hacker News/Simon Willison)**並刪除其所有文章**
  (使用者明確要求連文章刪),改訂三個中文新聞來源(中央社國際/BBC中文網/ETtoday)。
- **11**(無改碼):訂三個中文科技來源(iThome/TechNews 科技新報/DIGITIMES);使用者要求之後
  一律繁中回覆(已存 memory `feedback_language.md`);bnext/INSIDE 目前找不到公開 RSS。
- **10**(commit `f0ef6d6`):訂三個財經來源 + 做完文件分類功能。
- **9**(commit `f44d231`):做完 hybrid search。
- 更早:remove →「更聰明 dedupe」+ clear → 自動打標籤(殼)→ RSS ingestion → Streamlit 網頁
  → 一鍵啟動 → feeds 訂閱清單(CLI + 網頁)→ remove-batch(CLI + 網頁)→ 訂真實 RSS →
  翻譯繁中 + 時間戳改 UTC+8。細節都在下面各節。

## 環境

- Windows,Python 3.14.4,`.venv/` 在專案根目錄(已裝好所有依賴:torch/sentence-transformers/
  chromadb/anthropic/jieba/feedparser/rank_bm25/streamlit)。
- git remote:`origin` → `https://github.com/frobel0520/second-brain.git`。交接時
  `git status --short --branch` 看有沒有 ahead/behind、有沒有沒 commit 的東西。
- **這台沒設 `ANTHROPIC_API_KEY`**:`ask`/`translate` 只驗證過「沒 key 時清楚報錯」這條路徑。
- 依賴分兩組:`pip install -e ".[dev]"`(CLI/測試)+ `pip install -e ".[ui]"`(streamlit,
  **不在**預設 dev 裡)。第一次 `add`/`search` 會下載 ~90MB embedding 模型(要連網),
  jieba 首次會在本機建 prefix dict 快取(純本機、慢零點幾秒)。
- 常用指令:
  ```bash
  ./.venv/Scripts/python.exe -m pytest -q                  # ~8 秒,不連網/不用 API,應 118 個全過
  ./.venv/Scripts/python.exe -m second_brain add <file>     # 手動驗證要真的跑一次
  ```

## 18 個 CLI 指令(架構看 [README.md](README.md#架構))

1. `add <file> [-c 分類]` — md/txt → 自動打標籤 → 切塊 → embedding → 存 SQLite+ChromaDB。
   同一份筆記再 add 會先刪舊版再存(dedupe 見下),不是 append。
2. `add-feed <url> [-n N] [-c 分類]` — **一次性**抓 RSS/Atom,跑同一套 ingest 流程,不記住來源。
3. `search "<q>" [--top-k K] [-c 分類]` — **hybrid search**(語意 + BM25 正規化加權),印
   來源 + 合併分數 + 時間。`-c` 限定只在該分類內搜。
4. `ask "<q>" [--top-k K] [-c 分類]` — 在 search 結果上組 context 呼叫 Anthropic
   (`claude-opus-4-8`,寫死在 `config.ANSWER_MODEL`)做 RAG,回傳 `AskResult(answer, sources)`。
5. `list [-c 分類]` — 列文件(標題/片段數/來源/標籤),`-c` 時標題前加 `[分類]`。
6. `remove <source>` — 刪指定來源紀錄(sqlite+chroma),不動硬碟檔。純比對 `source_path`。
   參數是 `source: str`(能刪已從硬碟消失的檔,也能刪 RSS 網址)。
7. `star <source>` / `unstar <source>`(第 17 輪)— 依來源路徑/網址切換加星狀態,標記
   永久保留;`prune` 清理時會跳過加星的文件。
8. `clear [-y]` — 清空整庫,預設 `typer.confirm()` 確認,`-y` 跳過。不動硬碟原始檔。
9. `feeds add <url> [--name] [-n N] [-c 分類]` — 加訂閱並立刻同步一次;`--name` 不給會抓 feed
   標題、抓不到用網址;重複訂閱同一網址會被拒(exit 1)。內部直接呼叫 `sync_feed_subscription()`。
10. `feeds list` — 列訂閱(名稱/分類/網址/上次同步時間)。
11. `feeds remove <url>` — 移除訂閱那一列,**不動**已加入知識庫的文章。
12. `feeds sync [-n N] [--log-file PATH]` — 同步**所有**訂閱,單一來源失敗不擋其他;凡是這次
    有抓回來的文章會用該訂閱**目前的分類重新蓋**(只蓋這次抓到的,滾出範圍的舊文不碰)。
    `--log-file` 附加一行彙總結果(給排程用),不給則行為不變。
13. `feeds set-category <url> <分類>` — 改訂閱分類,只影響**之後**同步進來的新文章。
14. `remove-batch [--after/--before/--keyword/--source] [-y]` — 批次刪,三條件 **OR**(使用者
    明確要求),`--after`+`--before` 一起是 AND 區間;**至少要給一個條件**;預覽 + 確認。
15. `set-category <分類> [同上篩選] [-y]` — 同 remove-batch 的篩選/安全機制,把符合文件的分類
    設成同一值(補分類用)。
16. `prune [--days 7] [-y]`(第 17 輪)— 刪除超過指定天數、且沒加星的文件;跟 remove-batch/
    clear 同樣的預覽+確認機制;目前**沒有**接排程,要不要自動跑由使用者決定(見下面第 17 輪)。
17. `translate` — 幫還沒翻譯(`translated_content IS NULL`)的文件補繁中翻譯,需 key;認證失敗
    直接停並清楚報錯,其他單篇失敗只計數。網頁介面沒有對應功能(批次翻譯久,留在 CLI)。

## 功能重點(細節/取捨)

**自動打標籤**:`processing/tagging.py` 的 `KeywordFrequencyTaggingProvider`,jieba 斷詞 + 停用詞
過濾 + 詞頻取前 `config.MAX_TAGS`(5)個。`TaggingProvider` 是抽象介面,之後換 LLM 分類只要換
`get_tagging_provider()` 回傳的實作。斷詞邏輯抽在共用的 `processing/text.py:tokenize()`,跟 BM25 共用。

**Hybrid search**(`retrieval/search.py`):解決語意搜尋對精確詞彙(人名/版本號/專有名詞)抓不準。
語意分數(ChromaDB cosine)+ BM25 關鍵字分數(`retrieval/keyword_search.py`,`rank_bm25.BM25Okapi`)
各自 min-max 正規化到 0~1,依 `config.SEMANTIC_WEIGHT`/`KEYWORD_WEIGHT`(各 0.5)加權平均。
**先撈全部 chunk 再截斷 top_k**(向量查詢用 `_ALL_CHUNKS_TOP_K=10_000`),不是各自查 top_k 再合併——
否則會漏掉「一邊排很前、另一邊排不進 top_k」的 chunk,正規化基準也會失真。BM25 語料每次查詢即時
從 SQLite 撈全部 chunk 現算(量體小、夠快)。`-c` 分類會先篩掉其他分類的 chunk 再各自正規化。
`search()`/`ask()` 對外介面沒變。**測試教訓**:BM25 測試語料至少 3 篇不同文件,只用 2 篇 idf 可能算出
退化值(`log(1.5/1.5)=0`)讓測試碰巧通過卻沒驗到排序。

**文件分類**:三類 `科技`/`新聞`/`財經`,**自由文字非 enum**。`Document`/`FeedSubscription`/
`DocumentSummary` 都有 `category: str | None`,`documents`/`feeds` 兩表加 `category TEXT`(用通用的
`_ensure_column()` migration)。**分類是存在 Document 上的固定值,不是即時 join `feeds` 算的**——這樣
訂閱被取消/改分類時,已存文件的分類不會憑空消失/改變(跟 `feeds remove` 不動文章一致)。代價:
`feeds set-category` 只影響之後同步的新文,舊文要靠下次同步剛好還在 feed 範圍、或 `set-category` 手動改。

**RSS/Atom ingestion**(`ingestion/rss_loader.py`):`load_feed(url, limit)`,每 entry 轉一個 Document,
`source_path` 用文章 `link`(dedupe/remove 靠它)。`feed_url` 參數吃網址/本機路徑/原始 XML 字串
(`feedparser.parse()` 自動判斷,單元測試因此不連網)。HTML 去標籤用陽春正則 `_strip_html`(非完整
parser,`<script>`/`<style>` 內容不排除)。**`_MIN_CONTENT_LENGTH=20`**:內容太短(如 Hacker News 的
`<description>` 永遠是「Comments」)就退回用標題當內容,避免 dedupe 把不同文章誤判成「同一篇改名」
互相覆蓋(這 bug 曾讓一批 5 篇只存活 1 篇)。副作用:這類來源存進去只有標題,搜尋品質較差。

**Streamlit 網頁介面**(`interface/web.py`,`streamlit run` 或 `run_web.bat` 啟動,📚 圖示):五分頁
`st.segmented_control()` 導覽(允許再點一次變 `None`,有 `if active_tab is None: active_tab = "瀏覽"` 防呆)。
- **瀏覽**:文件卡片(標題/時間/分類/來源 + 右上小「×」刪除鈕;標籤刻意不顯示、仍存後台)。第 16 輪:依加入時間新到舊、
  一頁 10 筆左右兩欄各 5、箭頭式分頁(頁碼存 `session_state["browse-page"]`,夾在 1~總頁數;切換分類
  重設回第 1 頁)。下方有批次刪除區塊(篩選→預覽→勾選→刪除)。
- **搜尋**:文字框 + top-k 滑桿 + 限定分類 + **排序方式(相關性/日期新到舊,第 16 輪)**,卡片顯示分數/來源/內容。
- **問答**:沒 key 顯示友善錯誤(跟 CLI 一致)。
- **新增筆記**:上傳檔案或輸入 RSS 網址(一次性)。成功(`added>0`)後自動跳「瀏覽」分頁。
- **訂閱管理**:訂閱清單(名稱/分類/網址/上次同步 + 同步/取消訂閱鈕)+「同步全部」(失敗折疊分組)
  + 新增訂閱表單。底層共用 storage/pipeline 同一組函式,不重寫。
- 用 `@st.cache_resource` 的 `_warm_up_providers()` 預熱模型;**刻意沒有網頁版 `clear`**(危險操作留 CLI)。

**`feeds sync` 排程自動化**(第 13 輪):Windows 內建 Task Scheduler(不寫常駐程式,符合 local-first),
排程工作 `SecondBrainFeedsSync` 每天 08:00 跑 `.venv\Scripts\python.exe -m second_brain feeds sync
--log-file data\sync.log`,working dir 設專案根目錄(`config.PROJECT_ROOT` 用 `__file__` 算、不依賴
cwd)。**`--log-file` 只寫一行彙總**(`_format_sync_log_line()`:時間戳 + 新增/更新總篇數 + 失敗來源數)。
**這是機器層級設定,不在 git 裡**,換機器要重新 `Register-ScheduledTask`。`data/sync.log` 沒有輪替
機制(每天一行,累積無所謂)。查是否正常:看 `data/sync.log` 或
`Get-ScheduledTask -TaskName SecondBrainFeedsSync | Get-ScheduledTaskInfo` 的 `LastTaskResult`(0=成功)。

**一鍵啟動**:[run_web.bat](run_web.bat) 放專案根目錄,雙擊會 `cd` 到自己所在目錄再跑 `streamlit run`。
**啟動前會自動建空的 `%USERPROFILE%\.streamlit\credentials.toml`**——否則 Streamlit 第一次在分離視窗跑
會卡在無人能回答的「Welcome 輸入 email」stdin 提示、永遠不 bind port(這是真的修好的 bug)。開始功能表
有「Second Brain」捷徑指向它(機器特定、不在 git;桌面捷徑已依使用者習慣刪掉改放開始功能表)。

## 非顯而易見的設計決策(為什麼這樣寫)

- **Windows 主控台 UTF-8 fix**(`cli.py` 開頭 `sys.stdout.reconfigure(encoding="utf-8")`):不然中文亂碼。真 bug。
- **path 參數執行時才解析**:`db_path: Path | None = None` 內部 `db_path or SQLITE_PATH`,不用 function
  default 綁定(default 在 import 當下就綁死,測試 monkeypatch 會失效)。
- **ChromaDB collection 明設 `hnsw:space: cosine`**:讓 `score = 1 - distance` 有意義。
- **測試不下載真模型/不打 API**:`_FakeEmbeddingProvider` 回傳固定向量、mock `anthropic.Anthropic()`,
  monkeypatch 模組級 singleton。pytest 秒級、免網路/key。
- **`ask` 認證錯誤處理有點 hacky**:SDK 完全沒憑證時丟的是 `TypeError`(不是 `AuthenticationError`),
  用字串比對 `"authentication" not in str(error).lower()` 判斷要不要重拋。SDK 改訊息文字會失效,
  之後可改成先檢查 `os.environ.get("ANTHROPIC_API_KEY")`。
- **dedupe**(`store.py:replace_existing_document`):先比 `source_path`,找不到再比 `content` **完全相同**
  (非 fuzzy)。處理「改名/搬家但內容沒變」。沒加 content hash(資料量小夠用)。**已知取捨**:兩份內容
  完全一樣的不同筆記,第二次 add 會被誤判成搬家、覆蓋掉第一份;「又搬家又改內容」兩種比對都不中、
  舊紀錄變孤兒,要手動 remove/clear。
- **schema migration 用真的 `ALTER TABLE`**:`_ensure_column(conn, table, column, ddl)` 每次連線用
  `PRAGMA table_info` 檢查、缺才補。**這個專案有真實資料,不能砍庫重建**。加新欄位照這模式。
- **`ingest_document()` 回傳結構化 `IngestResult`**(非預先格式化字串):CLI/Streamlit 對「怎麼呈現」需求
  不同,回傳結構化資料讓兩端各自格式化,不製造重複。放在 `ingestion/pipeline.py`(不屬任何 interface)。
- **`json.dumps(..., ensure_ascii=False)`**(sqlite_store 三處:metadata/tags/chunk.metadata):預設
  `ensure_ascii=True` 會把中文轉 `\uXXXX`,害 `tags` 欄位的 `LIKE` 中文關鍵字比對不到。**只對之後新寫入
  有效**,舊資料的 tags 仍是舊跳脫格式,`remove-batch --keyword` 對舊文標籤比不到(標題/內容不受影響),
  要重 `add`/`feeds sync` 或寫一次性 migration。
- **`remove-batch` OR 邏輯是使用者確認過的**(不是預設,別自作主張改 AND);沿用 `clear` 的預覽+確認+
  `-y` 安全機制;**至少一個條件**(不然跟 `clear` 語意重疊、易誤刪全庫)。
- **feeds 一系列的刻意設計**:`add-feed`(抓一次就忘)跟 `feeds`(訂閱清單,獨立 `feeds` 表)分開、不取代;
  `feeds remove` 只刪訂閱不刪文章(兩個意圖不同,合併危險);`feeds sync` 單一來源失敗不擋其他
  (例外收進 `FeedSyncResult.error`);`feeds add` 重複訂閱明確報錯(不靜默 no-op)。
- **`remove` 對網址不能用 `Path.resolve()`**(Windows 會把 `/` 變 `\`、查不到)——只有「不含 `://`」才
  當本機路徑 resolve,網址原樣傳。(曾是隱藏 bug,沒人用 remove 刪過 RSS 文章才沒踩到。)
- **`feeds add` 的第一次同步要呼叫共用的 `sync_feed_subscription()`**,不要自己兜 load+ingest 迴圈——
  否則會漏掉更新 `last_synced_at`(曾是 bug)。這也是 pipeline 把同步邏輯獨立成函式的原因。
- **`Document` 沒存「來自哪個訂閱來源」的關聯**(只有 `category`,分類≠來源)。要「整批移除某訂閱來源
  的文章」只能靠 `source_path` 網域比對,或內容特徵(如 HN 的 `content == title` 訊號,因為 HN 連結散在
  各網域)。若這需求變常見再加 `documents.source_feed_url`,現在 YAGNI。
- **UI 選型**:使用者在 Streamlit / TUI / 正式 web app 裡選 Streamlit(單一依賴、一指令跑、免前後端分離,
  最符合「先求能動」;缺點是要多人/更精緻互動時可能得換)。

## Streamlit rerun 模型與瀏覽器自動化的坑(踩過,之後會再遇到)

- **`st.rerun()` 會洗掉剛印的 `st.success`/`st.error`**:整個 script 重跑,訊息不保留。原則:回饋訊息跟
  「馬上強制重整」衝突時,優先保留使用者看得到的回饋(靠下一個互動自然刷新時間戳)。用「訊息存
  session_state、下個分頁載入時彈出」的既有慣例(`batch_delete_message` 等)跨分頁傳訊息。
- **`st.expander` 沒設 `expanded=True`,底下有觸發 rerun 的元件時每次 rerun 會自動收合**——表單填一半消失。
  避免在會互動的表單外包 expander(除非額外用 session_state 記展開狀態)。
- **長時間執行的 Streamlit process 會 `sys.modules` 快取住舊模組**:改了 `.py`、確認磁碟內容對,但瀏覽器
  仍報「找不到剛加的名稱」`ImportError` → 別懷疑檔案,直接 `Stop-Process` 砍掉、`preview_start` 重開。
- **瀏覽器自動化測 Streamlit 元件**:`form_input` 對 `text_input` 不可靠(DOM 值改了但 Python 端讀不到);
  優先用 `computer` 的 `triple_click`+`type`(真鍵盤),別用 `ctrl+a`+`type`(會內容疊加)。checkbox 的真
  `<input>` 被 `clip-path` 隱藏,點座標/`.click()` 無效 → 用 JS 點它的 `closest('label')`。
  `segmented_control` 是 `role="radio"`,`computer` 用 ref 點有時不觸發 → 用 `javascript_tool` 對元素
  `.click()`。`screenshot` 常逾時 → 改用 `get_page_text`/`read_page`/直接查 DB。`.claude/launch.json` 已設
  `"autoPort": true`(port 8501 被別的 session 佔用時 harness 自動換 port;此檔在 `.gitignore` 裡)。

## 已知的粗糙邊界(刻意先跳過,不算 bug)

- dedupe 抓不到「路徑跟內容同時變」的情況(見上),舊紀錄變孤兒。
- `list` 沒分頁;`search`/`ask` 的 `top_k` 沒上限檢查。
- **自動標籤只是殼**(純本機詞頻,無語意理解),短筆記/用詞分散的標籤會不準。`TaggingProvider` 可抽換成 LLM。
- `search`/`ask` **不顯示標籤**(只有 `add`/`list` 顯示);沒有按標籤過濾的操作。
- `add-feed` 的 HTML 去標籤是陽春正則;`<script>`/`<style>` 內容不排除。
- `feeds sync` 依序同步、非平行;沒實測過大量來源的耗時。
- 同步歷史只有 `last_synced_at` + `data/sync.log` 彙總,沒有逐次詳細紀錄。
- 網頁介面「瀏覽」切去別分頁再切回,頁碼會重置回第 1 頁(即使分類沒變;推測是 Streamlit 對「這次
  沒被實例化的 widget」不保留舊 session_state,沒深究,不影響核心功能)。
- 批次刪除/設定分類的「預覽清單」存 session_state,不會自動更新;預覽後知識庫有變動要重按一次預覽
  (已被刪的 id 會被 `remove_documents()` 靜默略過,不會誤刪)。
- 分類是自由文字,打錯字(如「財金」vs「財經」)不會被攔,`list_categories()` 只忠實反映實際出現過的值,
  要人工發現用 `set-category` 修。網頁「批次設定分類」是純文字框、沒下拉提示既有分類,容易手滑打錯
  (CLI 上真的手滑打錯過一次:對子網域跑錯分類值把財經蓋成科技,發現後重跑改回)。**教訓**:批次
  操作即使有 `-y` 也該先不加 `-y` 看預覽,尤其覆蓋「已設定過」的欄位(打錯值不像刪除那樣有明顯徵兆)。
- RSS 分類回填只能靠「文章還在 feed 目前回傳範圍內」;滾出範圍或用一次性 `add-feed` 加的文章不會自動
  分類,要 `set-category --source <網域>` 手動掃。
- HN 這類「description 只有佔位文字」的來源,存進去只有標題,搜尋品質較差(HN RSS 本身的限制)。
- `translate`/自動翻譯不記錄失敗原因;翻譯 `max_tokens=4096` 沒測過超長文章會不會截斷;網頁「查看繁中
  翻譯」expander 每次渲染都對每篇有翻譯的文件多查一次 DB(量小沒差,大量成長可改懶載入)。
- `SEMANTIC_WEIGHT`/`KEYWORD_WEIGHT` 寫死在 `config.py`(各 0.5),沒有讓使用者臨時調整或「只用語意/
  只用關鍵字」的開關(純語意的舊架構還在 git 歷史裡);BM25 語料每次現算沒快取(幾千篇以上會是第一個
  變慢的地方);corpus 極小(1~2 篇)時 idf 可能退化,語意分數會變主要依據(合理降級,非 bug)。
- `remove-batch` 的 `--after`/`--before` 只吃 `YYYY-MM-DD` 絕對日期,沒有「N 天前」相對簡寫
  (`prune` 的 `--days` 算是這個需求的另一半解法,但只服務「清舊文件」這個特定情境,`remove-batch`
  本身沒有跟著加相對日期參數,YAGNI)。
- `prune` 目前是純手動指令,**沒有接上 `SecondBrainFeedsSync` 排程**(見第 17 輪);要自動化
  的話要另外改 Windows 排程工作的命令列,屬於機器層級設定,不在 git 裡。
- `streamlit` 是 optional dependency(`[project.optional-dependencies].ui`),`.[dev]` 不會裝到。

## 接下來(還沒決定,下一輪先問使用者,不要自己選一個就動工)

CLAUDE.md「未來規劃」剩下的 + 這輪浮現的候選:
- **`prune` 要不要接進 `SecondBrainFeedsSync` 排程**(第 17 輪做出指令但沒接自動化);使用者
  可能會先手動跑幾次觀察,再決定要不要、以及要設多少天的門檻。
- 更多 ingestion 來源(瀏覽器書籤、Readwise/Instapaper、Obsidian/Notion 匯出;RSS 已做完)。
- 自動化處理其餘(關聯筆記推薦、去重複;自動打標籤殼已做完)。
- **老家電腦部署**(第 16 輪討論,使用者選「裝獨立一份」,可能會 follow-up,步驟見上面第 16 輪摘要)。
- 網頁介面續打磨(批次刪除/設定分類的預覽清單不會自動更新;瀏覽切分頁頁碼重置)。
- 舊資料 `tags` 欄位 migration(轉成 `ensure_ascii=False`,讓 `remove-batch --keyword` 對舊文標籤生效;
  不急,重 `add`/`feeds sync` 也能解決)。
- 網頁「批次設定分類」換成分類下拉選單 + 新增選項,避免手滑打錯。

## 交接檢查清單

1. `git log --oneline` / `git status --short --branch`:**第 17 輪已 commit `2fa9e05`**(16→
   `12da665`、15→`e8e1959`、13→`f846938`、10→`f0ef6d6`、9→`f44d231`);11/12/14 沒改碼。工作目錄
   應乾淨。`.claude/launch.json` 改過(`autoPort:true`)但在 `.gitignore` 裡,不會出現在 `git status`。
2. **機器層級設定,不在 git,換機器要重建**:Windows 排程工作 `SecondBrainFeedsSync`(每天 08:00);
   開始功能表「Second Brain」捷徑;`.streamlit/credentials.toml`。
3. **知識庫有真實資料,別誤刪**:9 個訂閱(科技=iThome/TechNews/DIGITIMES,財經=經濟日報/自由時報
   財經/Yahoo股市,新聞=中央社國際/BBC中文網/ETtoday),約 420 篇全部分類完畢(第 17 輪 `prune`
   後只留最近一週 + 加星文章)。用 `remove-batch`/
   `clear`/`set-category` 前務必先 `list`/`feeds list` 確認。
4. **沒設 `ANTHROPIC_API_KEY`**:`ask`/`translate` 沒被實際跑過。翻譯品質不在 TODO 追蹤了(第 14 輪移除)。
   若之後設 key,記得排程會開始自動翻譯花錢(見第 14 輪摘要)。
5. `pytest -q` 應 118 個全過、~8 秒。
6. 全新環境要 `pip install -e ".[dev]"` + `pip install -e ".[ui]"`。第 13 輪沒加新依賴(排程用 Windows 內建)。
7. 若驗證雙擊啟動,先刪 `%USERPROFILE%\.streamlit\credentials.toml` 模擬全新機器,否則測不出「Welcome
   卡住」那個 bug 有沒有修好。瀏覽器自動化測 Streamlit 的工具限制見上面「rerun 模型與瀏覽器自動化的坑」。
