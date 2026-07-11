# Progress

這份文件是給「接手這個專案的下一個 Claude 對話」看的交接筆記,不是使用手冊。
使用方式看 [README.md](README.md),規劃看 [CLAUDE.md](CLAUDE.md)。這份只記錄
「現在做到哪、為什麼這樣做、接下來大概要做什麼」,每次做完一個階段性任務就更新。

最後更新:2026-07-12

## 現況一句話

CLAUDE.md 的 MVP(`add` / `search` / `ask`)已經做完,另外多做了 `list`、
`remove`、`clear` 三個指令,`add` 的 dedupe 也從「純比對路徑」升級成
「路徑或內容任一相同就算同一份筆記」(處理檔案改名/搬家),加了**自動打標籤**
(`add` 時自動產生標籤,存進 `Document.tags`,`list` 會顯示),這輪又加了
**第一個新的 ingestion 來源:RSS/Atom 訂閱**(`second-brain add-feed`)。
44 個測試全過。git 有六個 commit(`a53f756` skeleton+add/search、`a02095a`
ask、`d72a479` list+upsert、`1ed0686` remove、`269b58f` dedupe+clear、
`282482a` 自動標籤),**這輪的 RSS ingestion 還沒 commit**。

## 環境

- Windows,Python 3.14.4,`.venv/` 在專案根目錄(已裝好所有依賴,含 torch/sentence-transformers/chromadb/anthropic/jieba/feedparser)
- 沒有 git remote,只有本機 repo
- 常用指令:
  ```bash
  ./.venv/Scripts/python.exe -m pytest -q                    # 跑測試,~2 秒,不用真的 embedding 模型
  ./.venv/Scripts/python.exe -m second_brain add <file>       # 手動驗證要真的跑一次
  ```
- `ANTHROPIC_API_KEY` 這台機器上沒設,`ask` 指令沒辦法真的打 API,只驗證過「沒設 key 時的錯誤處理」

## 已經做完的東西

七個 CLI 指令全部能動,架構細節看 [README.md](README.md#架構):

1. `second-brain add <file>` — 讀 md/txt → 自動打標籤(本機 jieba 詞頻抽取)→ 切塊 → embedding(本機 sentence-transformers)→ 存 SQLite + ChromaDB。**同一份筆記再 add 一次會先刪舊版本再存新的**(`storage/store.py:replace_existing_document`),不是 append。「同一份筆記」的判斷邏輯之前升級過,見下面決策說明。
2. `second-brain add-feed <feed_url> [--limit/-n N]` — 這輪新加的。抓取 RSS/Atom 來源,把每篇文章轉成一個 Document,跑同一套 `_ingest_document()` 流程(標籤/切塊/embedding/dedupe/存檔)。見下面「已經做完的東西」下方的專節說明。
3. `second-brain search "<query>" [--top-k K]` — query 轉 embedding → ChromaDB cosine 相似度搜尋 → 印出來源+分數。
4. `second-brain ask "<query>" [--top-k K]` — 在 search 結果上組 context,呼叫 Anthropic API(`claude-opus-4-8`,寫死在 `config.ANSWER_MODEL`)做 RAG 問答。
5. `second-brain list` — 列出知識庫裡的文件(標題、片段數、來源路徑、標籤)。
6. `second-brain remove <file>` — 從知識庫刪除指定檔案的紀錄(sqlite + chroma),不動硬碟上的檔案本身。純比對 `source_path`,**不會**做內容比對(remove 是明確指名要刪哪個路徑,跟 add 的模糊 dedupe 語意不一樣)。`file_path` 參數**沒有** `exists=True`,因為要能刪除已經從硬碟上消失的檔案的舊紀錄。
7. `second-brain clear [--yes/-y]` — 清空整個知識庫(sqlite + chroma)。預設用 `typer.confirm()` 互動確認,`--yes`/`-y` 跳過確認直接清空(給腳本/非互動情境用)。不動硬碟上的原始檔案。

**自動打標籤**(是「自動化處理」這個大方向的第一小步):`add`/`add-feed` 讀進文件後會呼叫 `processing/tagging.py` 的 `get_tagging_provider().tag(document)`,把結果存進 `Document.tags`(SQLite `documents.tags` 欄位,JSON 字串)。`list`/`add`/`add-feed` 的輸出訊息都會顯示標籤。`TaggingProvider` 是抽象介面(跟 `EmbeddingProvider` 同樣的設計慣例),目前唯一實作是 `KeywordFrequencyTaggingProvider`:用 jieba 斷詞(中文)+ 保留原樣的英文單字,濾掉停用詞,取詞頻最高的前 `config.MAX_TAGS`(預設 5)個當標籤。之後要換成 LLM 分類或規則式邏輯,只要換掉 `get_tagging_provider()` 回傳的實作。

**RSS/Atom ingestion**(這輪新加的,CLAUDE.md「更多 ingestion 來源」的第一個):新增 `ingestion/rss_loader.py` 的 `load_feed(feed_url, limit=None) -> list[Document]`,用 `feedparser` 解析 feed,每個 entry 轉成一個 `Document`:
  - `source_path` 用文章的 `link`(dedupe/`remove` 都靠這個欄位比對,語意上等同本機檔案的路徑)
  - `content` 優先取 `content:encoded`,沒有就退回 `summary`/`description`,再過一個很陽春的正則去標籤(`_strip_html`,不是完整 HTML parser)
  - `feed_url` 參數其實是「feedparser 看得懂的任何東西」——網址、本機檔案路徑、feed 原始內容字串都吃,測試/手動驗證因此可以完全不連網(直接餵 XML 字串或本機檔案)
  - CLI 端 `add-feed` 每篇文章都跑 `_ingest_document()`(跟 `add` 共用的核心邏輯,見下面決策說明),所以自動有標籤/dedupe/embedding,不用重寫

## 中途做的非顯而易見的決策(為什麼這樣寫)

- **Windows 主控台 UTF-8 fix**([cli.py](second_brain/interface/cli.py) 開頭):手動測試時發現中文全部變亂碼,原因是 Windows 預設 stdout 編碼不是 UTF-8。已經在 CLI 進入點強制 `sys.stdout.reconfigure(encoding="utf-8")`。**這是一個真的修好的 bug,不是預防性程式碼。**
- **typer 單一指令會自動摺疊成不需要子指令名稱**:一開始只有 `add` 一個指令時,`second-brain add file.md` 會報錯要求直接 `second-brain file.md`。加了一個空的 `@app.callback()` 強制保留子指令形式,現在有 4 個指令了其實已經不需要這個 workaround,但留著無害,不用特地拿掉。
- **`sqlite_store` / `vector_store` 的 path 參數用「執行時才解析」而不是 function default 綁定**:一開始 `db_path: Path = SQLITE_PATH` 這種寫法在測試裡 monkeypatch 沒用(default 在 import 當下就綁死了),改成 `db_path: Path | None = None` 內部再 `db_path or SQLITE_PATH`,測試才能用 `monkeypatch.setattr(sqlite_store, "SQLITE_PATH", tmp_path/...)` 正確隔離。`vector_store.CHROMA_DIR` 本來就是函式內讀取,沒這問題。
- **ChromaDB collection 明確設 `hnsw:space: cosine`**:預設 space 不確定,為了讓 `score = 1 - distance` 這個算法有意義(cosine similarity),在 `_get_collection()` 建立時指定。
- **測試不下載真的 embedding 模型**:所有牽涉 embedding 的測試都用一個 `_FakeEmbeddingProvider`(回傳固定向量,依內容關鍵字區分),monkeypatch `processing.embedding._default_provider` 這個模組級 singleton。`ask` 的測試同樣 mock 掉 `anthropic.Anthropic()`,不會真的打 API。這是刻意的,讓 `pytest` 跑起來是秒級、不用網路、不用 API key。
- **`ask` 指令的認證錯誤處理有點 hacky**([cli.py](second_brain/interface/cli.py) 的 `ask()`):Anthropic SDK 在完全沒設任何憑證時丟的是 `TypeError`(不是 `AuthenticationError`,那個是 401 才會丟),訊息裡有 "authentication" 字樣。目前用字串比對 `"authentication" not in str(error).lower()` 來判斷要不要重新拋出。如果以後 SDK 改了錯誤訊息文字,這裡會失效——可以考慮但目前沒做:改成先檢查 `os.environ.get("ANTHROPIC_API_KEY")` 是否存在,或用 `ant auth status` 之類的方式判斷。
- **「更聰明的 dedupe」的具體設計**(`storage/store.py:replace_existing_document`):改成先比對 `source_path`,找不到再比對 `content` 是否**完全相同**(exact match,不是 fuzzy/相似度)。這樣可以處理「檔案改名/搬家但內容沒變」的情況,同時保留「同路徑但內容編輯過」也要 upsert 的原行為。**刻意沒做的事**:沒有加 content hash 欄位,直接拿 SQLite 的 `content = ?` 查詢比對全文——對個人筆記的資料量來說夠用,不用為了效能先做索引。**已知的取捨**:如果剛好有兩份「內容完全一樣但其實是不同筆記」的檔案,第二次 add 會被誤判成第一份的搬家/改名,舊的那份會被取代掉。對個人知識庫來說這種巧合機率低,先接受這個 trade-off,沒有另外問使用者。**沒處理的情況**:如果檔案「又搬家又編輯內容」(路徑跟內容同時變了),兩種比對都不會命中,舊紀錄會變孤兒(不會被自動清掉),要靠新加的 `remove` 或 `clear` 手動處理。
- **`clear` 指令的確認機制**:比照一般 CLI 慣例,預設互動確認(`typer.confirm`),避免使用者手滑清空整個知識庫;加 `--yes`/`-y` 是為了以後如果要串腳本或自動化清庫時可以跳過互動。
- **自動標籤一開始用純 regex n-gram、後來改成 jieba**:第一版偷懶用「連續中文字 2~4 個字」當候選詞(不用額外依賴),結果實測(用一篇講資料庫索引的中文筆記)標籤變成「資料庫索」「引筆記」這種無意義片段,問過使用者後決定加 `jieba` 依賴(純 Python、本機執行、不用連網/API key,符合 local-first 原則)換成真的中文斷詞。同一篇筆記改善後的標籤是「索引、資料、查詢、效能、筆記」,明顯可用。**教訓**:粗糙的字元切分對中文完全不 work,之後如果還有需要斷詞的功能,直接用 jieba,不要再嘗試 regex 捷徑。
- **`documents` 表加了 `tags` 欄位**(`TEXT NOT NULL DEFAULT '[]'`,JSON 字串):因為 schema 是 `CREATE TABLE IF NOT EXISTS`,不會自動幫已存在的舊資料庫加欄位。這次開發過程中就踩到一次——手動測試時本機已經有一個空的 `data/second_brain.db`(之前 smoke test `clear` 指令留下的,0 筆文件),沒有 `tags` 欄位,導致 `add` 直接噴 `OperationalError: no such column: tags`。因為那個 db 是空的(不是使用者的真實資料),直接刪掉重建解決。**如果之後 schema 還要再改,要注意這個專案目前沒有 migration 機制**,`data/` 是空的時候可以直接刪重建,但如果使用者已經囤了真實筆記,刪重建就會把知識庫清空——到時候要嘛先做個簡單的 migration(`ALTER TABLE ... ADD COLUMN`),要嘛提醒使用者資料要重新 `add` 一次。
- **把 `add` 的核心邏輯抽成 `_ingest_document()`**(`interface/cli.py`):加 `add-feed` 之前,「標籤 → 切塊 → embedding → dedupe → 存檔」這段邏輯只有 `add` 在用;現在 `add-feed` 要處理一批文章,重複這段邏輯不划算,所以抽成共用函式。回傳值設計成 `str | None`(訊息字串,或 `None` 代表內容是空的),讓兩個呼叫端各自決定空內容要怎麼處理——`add` 是硬錯誤(`exit(1)`),`add-feed` 是略過繼續跑下一篇(因為一個 feed 裡某篇文章是空的,不該讓整批失敗)。**這是刻意的介面設計**,不是隨便回傳 `None`。
- **RSS 內容的 HTML 去標籤用正則,不是完整 parser**(`rss_loader.py:_strip_html`):跟自動標籤一開始犯的錯一樣的取捨——先用最簡單的方法(`<[^>]+>` 正則 + `html.unescape`)讓 pipeline 跑起來,不追求對所有不規則 HTML 都正確。手動測試過一段有 `<p>`/`<b>` 巢狀標籤的內容,結果是乾淨的,但沒有測過更複雜的 HTML(例如 `<script>`/`<style>` 內容目前不會被特別排除,標籤內的文字會被當成一般內容留下)。如果之後發現真實 RSS 來源的內容跑出奇怪的殘留文字,可以考慮換成 `beautifulsoup4` 之類的正規 HTML parser。
- **`feed_url` 參數故意設計成「網址或本機路徑或原始內容都吃」**:因為 `feedparser.parse()` 本身就支援這三種輸入、會自動判斷,沒有特別去區分反而讓測試/手動驗證可以完全不連網(單元測試直接餵 RSS XML 字串,手動驗證用本機 `.xml` 檔案),这次全程沒有對外發過一次真的網路請求也驗證過整條流程能動。**沒驗證到的事**:還沒對一個真實的 HTTP(S) feed 網址跑過 `add-feed`,理論上 `feedparser` 會用 `urllib` 發請求,行為上應該跟餵字串一樣,但沒有實測過真的網路延遲/重導向/HTTP 錯誤情境。

## 已知的粗糙邊界(還沒處理,不算 bug,是刻意先跳過)

- `add` 的 dedupe 現在是「路徑相同」或「內容完全相同」任一命中就算同一份筆記。**路徑跟內容同時變的情況還是抓不到**(見上面決策說明),舊紀錄會變孤兒,要靠 `remove`/`clear` 手動清。
- `list` 沒有分頁,文件一多會洗版(目前用不到分頁,先不做)。
- `search`/`ask` 的 `top_k` 沒有上限檢查。
- **自動標籤只是「殼」,不是真的智慧分類**:目前是純本機詞頻統計(jieba 斷詞 + 出現次數排序),沒有語意理解。標籤品質對「內容夠長、主題明確」的筆記還可以,短筆記或用詞分散的筆記標籤會不準。使用者當初要求就是先求有殼,之後可以換成 LLM 分類(`TaggingProvider` 介面已經是抽換式設計,換實作不用動 `add` 流程)。
- `search`/`ask` 目前**不會**顯示文件的標籤,只有 `add`/`add-feed` 完成訊息跟 `list` 會顯示。
- 沒有針對標籤的操作(例如按標籤過濾 `list`/`search`),純粹先把資料存起來。
- `add-feed` 的 HTML 去標籤是陽春正則,不是完整 HTML parser(見上面決策說明);`<script>`/`<style>` 內容不會被排除。
- `add-feed` 還沒對一個真實的網址跑過(只測過本機檔案/原始字串),真的 HTTP 請求路徑理論上沒問題但沒實測過。
- `add-feed` 沒有記錄「這個 feed 訂閱過」這件事,每次都要使用者自己再打一次網址,沒有「訂閱清單」的概念(例如 `second-brain feeds list`/`second-brain feeds sync` 這種),要重複抓新文章得手動再跑一次 `add-feed`。

## 接下來可能的方向(還沒決定,是這輪對話結尾討論到的選項)

CLAUDE.md「未來規劃方向」列的:
- 更多 ingestion 來源的其餘部分(瀏覽器書籤、Readwise/Instapaper、Obsidian/Notion 匯出——RSS 這一個已經做完)
- Hybrid search(關鍵字 + 語意搜尋並用)
- 自動化處理的其餘部分(關聯筆記推薦、去重複——自動打標籤這一小塊已經做完)
- Web UI 或 Raycast/Alfred 整合

使用者說這些方向都想做,已經照優先順序做完 `remove` → 「更聰明的 dedupe」+「清空知識庫指令」→ 「自動打標籤(殼)」→ 「RSS ingestion」。問過使用者 ingestion 來源要先做哪個,選了 RSS(理由:範圍最小、不用 API key)。**下一個對話開始時,建議問使用者接下來要做哪個**,不要自己選。

「已知的粗糙邊界」裡 `add-feed` 的部分(訂閱清單、真實網址還沒實測)也是候選,如果使用者常態性地要追蹤同一批 feed,「訂閱清單 + 一鍵同步全部」會比現在的「每次手動打網址」更有用,可以主動提。

## 交接檢查清單(接手時建議做的事)

1. `git log --oneline` 確認目前在哪個 commit,`git status` 確認有沒有沒 commit 的東西(這次交接時,**RSS ingestion 這批預期還沒 commit**)
2. `./.venv/Scripts/python.exe -m pytest -q` 應該要 44 個全過、~4 秒內跑完
3. 如果要手動測 `add`/`search`,第一次跑會下載 ~90MB 的 embedding 模型,需要網路;jieba 第一次執行也會在本機建 prefix dict 快取(不用連網,純本機運算,第一次會慢個零點幾秒)
4. 如果要手動測 `ask`,需要使用者提供 `ANTHROPIC_API_KEY`
5. `pyproject.toml` 這輪陸續加了 `jieba>=0.42`、`feedparser>=6.0` 依賴,如果是全新環境要記得 `pip install -e ".[dev]"` 重新裝一次
6. 如果要手動測 `add-feed` 又不想真的連網,`feedparser.parse()` 吃本機檔案路徑或原始 XML 字串都可以,不用真的丟一個 HTTP 網址進去
