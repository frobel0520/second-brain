# Progress

這份文件是給「接手這個專案的下一個 Claude 對話」看的交接筆記,不是使用手冊。
使用方式看 [README.md](README.md),規劃看 [CLAUDE.md](CLAUDE.md)。這份只記錄
「現在做到哪、為什麼這樣做、接下來大概要做什麼」,每次做完一個階段性任務就更新。

最後更新:2026-07-12

## 現況一句話

CLAUDE.md 的 MVP(`add` / `search` / `ask`)已經做完,另外多做了 `list`、
`remove`、`clear`、`add-feed`(RSS/Atom ingestion)四個指令,`add` 的 dedupe
也升級成「路徑或內容任一相同就算同一份筆記」,加了**自動打標籤**,今天這一整天
的對話裡又疊了三層東西:(1) 用真實的 BBC News RSS 網址實測 `add-feed` 全流程;
(2) 加了 **Streamlit 本機網頁介面**(`second_brain/interface/web.py`),把
`add`/`add-feed` 共用的核心邏輯從 `interface/cli.py` 抽到 `ingestion/pipeline.py`;
(3) 加了 [run_web.bat](run_web.bat) 一鍵啟動批次檔 + Windows 開始功能表捷徑,
過程中抓到並修掉一個真的會卡死的 bug(Streamlit 第一次非互動啟動會卡在歡迎
訊息提示)。**使用者後來自己用 Windows 開始功能表捷徑打開網頁介面、在自己的瀏覽器上完整跑過一次**:
一開始貼的是 `https://www.bbc.com/news`(BBC 首頁,不是 feed,失敗),換成正確的
`http://feeds.bbci.co.uk/news/world/rss.xml` 之後成功抓到 10 篇真實新聞,是**這輪
唯一一次由使用者本人、在使用者自己的環境(不是我這邊的自動化瀏覽器)完整走過一次
「新增筆記」流程的驗證**,比先前所有 Claude Browser pane 上的自動化測試都更有代表性。
對話最後有另外建議一個 BBC 中文網的網址(`feeds.bbci.co.uk/zhongwen/trad/rss.xml`)
給使用者測中文內容,**但沒有實際驗證過這個中文網址有沒有效**,下次要用時建議先測一次
再假設它可靠。48 個測試全過。git 有九個 commit(`a53f756` skeleton+add/search、
`a02095a` ask、`d72a479` list+upsert、`1ed0686` remove、`269b58f` dedupe+clear、
`282482a` 自動標籤、`d27e201` RSS ingestion、`8ec7442` pipeline 重構+網頁介面、
`bf94c0c` 一鍵啟動批次檔)。**今天對話最後把網頁介面的圖示從 🧠 換成 📚,這批
還沒 commit**,下一個對話開始時記得先確認要不要 commit 掉。

## 環境

- Windows,Python 3.14.4,`.venv/` 在專案根目錄(已裝好所有依賴,含 torch/sentence-transformers/chromadb/anthropic/jieba/feedparser/streamlit)
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
2. `second-brain add-feed <feed_url> [--limit/-n N]` — 抓取 RSS/Atom 來源,把每篇文章轉成一個 Document,跑同一套 `ingest_document()` 流程(標籤/切塊/embedding/dedupe/存檔)。這輪用真實的 BBC News 網址實測過,見下面專節說明。
3. `second-brain search "<query>" [--top-k K]` — query 轉 embedding → ChromaDB cosine 相似度搜尋 → 印出來源+分數。
4. `second-brain ask "<query>" [--top-k K]` — 在 search 結果上組 context,呼叫 Anthropic API(`claude-opus-4-8`,寫死在 `config.ANSWER_MODEL`)做 RAG 問答。
5. `second-brain list` — 列出知識庫裡的文件(標題、片段數、來源路徑、標籤)。
6. `second-brain remove <file>` — 從知識庫刪除指定檔案的紀錄(sqlite + chroma),不動硬碟上的檔案本身。純比對 `source_path`,**不會**做內容比對(remove 是明確指名要刪哪個路徑,跟 add 的模糊 dedupe 語意不一樣)。`file_path` 參數**沒有** `exists=True`,因為要能刪除已經從硬碟上消失的檔案的舊紀錄。
7. `second-brain clear [--yes/-y]` — 清空整個知識庫(sqlite + chroma)。預設用 `typer.confirm()` 互動確認,`--yes`/`-y` 跳過確認直接清空(給腳本/非互動情境用)。不動硬碟上的原始檔案。

**自動打標籤**(是「自動化處理」這個大方向的第一小步):`add`/`add-feed` 讀進文件後會呼叫 `processing/tagging.py` 的 `get_tagging_provider().tag(document)`,把結果存進 `Document.tags`(SQLite `documents.tags` 欄位,JSON 字串)。`list`/`add`/`add-feed` 的輸出訊息都會顯示標籤。`TaggingProvider` 是抽象介面(跟 `EmbeddingProvider` 同樣的設計慣例),目前唯一實作是 `KeywordFrequencyTaggingProvider`:用 jieba 斷詞(中文)+ 保留原樣的英文單字,濾掉停用詞,取詞頻最高的前 `config.MAX_TAGS`(預設 5)個當標籤。之後要換成 LLM 分類或規則式邏輯,只要換掉 `get_tagging_provider()` 回傳的實作。

**RSS/Atom ingestion**(CLAUDE.md「更多 ingestion 來源」的第一個):`ingestion/rss_loader.py` 的 `load_feed(feed_url, limit=None) -> list[Document]`,用 `feedparser` 解析 feed,每個 entry 轉成一個 `Document`:
  - `source_path` 用文章的 `link`(dedupe/`remove` 都靠這個欄位比對,語意上等同本機檔案的路徑)
  - `content` 優先取 `content:encoded`,沒有就退回 `summary`/`description`,再過一個很陽春的正則去標籤(`_strip_html`,不是完整 HTML parser)
  - `feed_url` 參數其實是「feedparser 看得懂的任何東西」——網址、本機檔案路徑、feed 原始內容字串都吃,單元測試因此完全不連網(直接餵 XML 字串)
  - **這輪已經用真實網址實測過**:`http://feeds.bbci.co.uk/news/world/rss.xml`(BBC News 國際版),`add-feed --limit 5` 抓了 5 篇真實文章,標籤、dedupe(重跑一次變成「已更新」不會重複)、`search` 語意排序全部驗證過在真實英文新聞內容上正常運作。之前「還沒對真實網址測過」這個粗糙邊界已經解決。

**Streamlit 網頁介面**(這輪新加的,使用者要求要能「自己使用看看」):`second_brain/interface/web.py`,`streamlit run` 啟動,四個分頁:
  - **瀏覽**:列出所有文件(標題/片段數/標籤/來源),每筆有刪除按鈕
  - **搜尋**:文字框 + 滑桿(top-k),結果卡片顯示分數/來源/片段內容
  - **問答**:文字框問問題,沒有 `ANTHROPIC_API_KEY` 會顯示友善錯誤(跟 CLI 的 `ask` 一致)
  - **新增筆記**:上傳本機檔案(存到 temp file 再走 `load_document()`)、或輸入 RSS 網址走 `load_feed()`
  - 用 `@st.cache_resource` 包一個 `_warm_up_providers()`,頁面第一次載入就把 embedding/tagging 模型準備好,避免 Streamlit 每次互動重跑整支 script 時反覆重新載入模型
  - **沒有網頁版的 `clear`**:清空整個知識庫這種危險操作刻意只留在 CLI,網頁介面不放
  - **圖示是 📚(書本),不是 🧠**:一開始隨手用了大腦 emoji(`page_icon`/`st.title` 都是),使用者說想要「知識庫的感覺,不要大腦的圖」,換成 📚。改動範圍只有 `web.py` 這兩處,`.claude/launch.json`、README、桌面/開始功能表捷徑都沒有大腦圖案,不用跟著改。**這批圖示改動這輪對話結束時還沒 commit**,見上面「現況一句話」。

**一鍵啟動網頁介面**(使用者要求「在專案資料夾那邊就可以跑,或者有個本機捷徑」):
  - [run_web.bat](run_web.bat):放在專案根目錄,雙擊就會 `cd` 到自己所在的目錄再跑 `streamlit run`,不用先手動開終端機/`cd`。
  - **捷徑放在哪裡有調整過**:一開始建了桌面捷徑「Second Brain.lnk」,但使用者說自己平常習慣從 Windows 開始功能表開東西,把桌面那個刪了。改成在開始功能表的 Programs 資料夾(`%APPDATA%\Microsoft\Windows\Start Menu\Programs\`)建同名捷徑,一樣指向 `run_web.bat`。**這兩種捷徑都只存在使用者這台機器,不在 git repo 裡,`.lnk` 是機器特定的東西,理所當然不追蹤**——如果之後又聽到「捷徑不見了」,先確認是不是又手動刪過,不是 repo 這邊的問題。
  - **手動驗證時踩到一個真的會卡住的 bug**,已經修掉,細節見下面決策說明。
  - **這是唯一一個有被使用者本人在自己電腦上真的用過的功能**(見上面「現況一句話」的 BBC 新聞驗證),不只是 Claude 這邊測過。

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
- **把 `add` 的核心邏輯抽成 `ingest_document()`**:一開始(上輪加 `add-feed` 時)先抽成 `interface/cli.py` 裡的私有函式 `_ingest_document()`,回傳訊息字串。這輪因為使用者要求要有網頁介面,`web.py` 也需要同一套邏輯,再把它從 `interface/cli.py` 搬到 `ingestion/pipeline.py`(獨立模組,不屬於任何一個 interface),回傳值也從「預先格式化好的中文訊息字串」改成結構化的 `IngestResult`(dataclass:`document`/`chunk_count`/`status: Literal["added","updated","renamed"]`/`previous_source_path`)。**為什麼要改成結構化資料而不是字串**:CLI 跟 Streamlit 兩種介面對「怎麼呈現這個結果」需求不一樣(CLI 印一行文字,Streamlit 要分 `st.success`/`st.warning`、加 emoji、分段顯示),如果繼續回傳寫死的中文字串,Streamlit 那端就會被迫重新解析字串或整個繞過共用函式各自兜一份邏輯,回頭又製造重複。CLI 這邊另外寫了 `_format_ingest_result()` 把結構化結果轉成人類看的訊息。
- **RSS 內容的 HTML 去標籤用正則,不是完整 parser**(`rss_loader.py:_strip_html`):跟自動標籤一開始犯的錯一樣的取捨——先用最簡單的方法(`<[^>]+>` 正則 + `html.unescape`)讓 pipeline 跑起來,不追求對所有不規則 HTML 都正確。用真實 BBC 新聞內容測過,結果是乾淨的,但沒有測過更複雜的 HTML(例如 `<script>`/`<style>` 內容目前不會被特別排除,標籤內的文字會被當成一般內容留下)。如果之後發現某些 RSS 來源的內容跑出奇怪的殘留文字,可以考慮換成 `beautifulsoup4` 之類的正規 HTML parser。
- **`feed_url` 參數故意設計成「網址或本機路徑或原始內容都吃」**:因為 `feedparser.parse()` 本身就支援這三種輸入、會自動判斷,讓單元測試可以直接餵 RSS XML 字串、完全不連網。這輪額外用真實網址(BBC News)驗證過同一個函式對 HTTP(S) 網址一樣有效,行為跟餵字串/檔案一致。
- **Streamlit UI 選型**:問過使用者「要哪種 UI」,選項是 Streamlit 網頁 / 終端機互動介面(TUI)/ 正式 Web App(FastAPI+前端),使用者選 Streamlit。理由記錄下來以防之後想換:Streamlit 是單一 Python 依賴、一個指令跑起來、不用寫前後端分離的架構,最符合目前「先求能動」的階段;缺點是不像正式 web app 那麼有彈性(之後如果要多人使用或要更精緻的互動,可能得換掉)。
- **網頁介面故意不做 `clear`**:清空整個知識庫是最危險的操作,CLI 版本已經有 `typer.confirm()` 互動確認 + `--yes` 兩層設計;網頁介面上按鈕很容易手滑點到,決定先不做,清空知識庫這件事保留在 CLI(需要打指令,天然多一層「刻意」的門檻)。
- **`add-feed`/上傳檔案在網頁介面上不是「新增就馬上出現在瀏覽分頁」**:Streamlit 每次互動都是重新整個 script 重跑一次,`ingest_document()` 執行完之後資料已經寫進 SQLite/ChromaDB,但使用者要手動切到「瀏覽」分頁(觸發新的一次 rerun)才會看到最新結果,目前沒有自動跳轉或者 toast 提示「已經存好了,去瀏覽分頁看看」。這是能接受的粗糙點,不是 bug。
- **手動驗證網頁介面時發現的自動化工具限制**(跟程式碼本身無關,記錄下來是因為之後如果還要用瀏覽器自動化測 Streamlit 應用會再踩到):`computer` 工具的 `type`/`key` 動作有時候不會觸發 Streamlit React 元件的內部事件處理(尤其是 `st.text_input` 需要「真的」keydown 事件才會 commit 值並觸發 rerun),用 `javascript_tool` 搭配原生 `HTMLInputElement` 的 setter(`Object.getOwnPropertyDescriptor(...).set`)+ 手動 `dispatchEvent(new KeyboardEvent('keydown', {keyCode:13,...}))` 比較可靠。另外這次的瀏覽器 `screenshot` 動作一直逾時,改用 `get_page_text`/`read_page`/直接查 DB 驗證資料正確性,不影響驗證結果。
- **`run_web.bat` 一開始沒處理 Streamlit 的「Welcome」提示,會整個卡死**:第一次手動測試雙擊啟動時,發現視窗開了、python 進程也在跑,但 port 8501 永遠沒 bind、瀏覽器打不開。原因是 Streamlit 第一次在「有 console 但沒人可以互動輸入」的情況下執行(例如被 `Start-Process`/雙擊捷徑這種方式啟動的分離視窗),會卡在一個一次性的「Welcome to Streamlit,請輸入 email 或按 Enter 跳過」的 stdin 提示——沒有 `%USERPROFILE%\.streamlit\credentials.toml` 這個檔案就會觸發,而這個提示沒人能按,就永遠卡住,連錯誤訊息都不會印。**這是一個真的修好的 bug,不是預防性程式碼**:一開始想用手動在使用者機器上建一個全域 `credentials.toml` 來解決,但那樣的話這個 repo 換一台機器/換一個使用者就會重現同樣的卡住,所以改成讓 `run_web.bat` 自己在啟動前檢查、不存在就自動建立空的 `credentials.toml`(內容是 `[general]\nemail = ""`),讓它在任何機器上第一次雙擊都能正常動,不用任何人先手動用終端機跑過一次去回答那個提示。用「先刪掉這個檔案模擬全新機器」的方式驗證過批次檔真的能自己處理好這個情況。

## 已知的粗糙邊界(還沒處理,不算 bug,是刻意先跳過)

- `add` 的 dedupe 現在是「路徑相同」或「內容完全相同」任一命中就算同一份筆記。**路徑跟內容同時變的情況還是抓不到**(見上面決策說明),舊紀錄會變孤兒,要靠 `remove`/`clear` 手動清。
- `list` 沒有分頁,文件一多會洗版(目前用不到分頁,先不做)。
- `search`/`ask` 的 `top_k` 沒有上限檢查。
- **自動標籤只是「殼」,不是真的智慧分類**:目前是純本機詞頻統計(jieba 斷詞 + 出現次數排序),沒有語意理解。標籤品質對「內容夠長、主題明確」的筆記還可以,短筆記或用詞分散的筆記標籤會不準。使用者當初要求就是先求有殼,之後可以換成 LLM 分類(`TaggingProvider` 介面已經是抽換式設計,換實作不用動 `add` 流程)。
- `search`/`ask` 目前**不會**顯示文件的標籤,只有 `add`/`add-feed` 完成訊息跟 `list` 會顯示。
- 沒有針對標籤的操作(例如按標籤過濾 `list`/`search`),純粹先把資料存起來。
- `add-feed` 的 HTML 去標籤是陽春正則,不是完整 HTML parser(見上面決策說明);`<script>`/`<style>` 內容不會被排除。
- `add-feed` 沒有記錄「這個 feed 訂閱過」這件事,每次都要使用者自己再打一次網址,沒有「訂閱清單」的概念(例如 `second-brain feeds list`/`second-brain feeds sync` 這種),要重複抓新文章得手動再跑一次 `add-feed`。
- **Streamlit 網頁介面沒有 `clear`**(刻意的,見上面決策說明),要清空知識庫還是得用 CLI。
- **網頁介面的「新增筆記」完成後不會自動導去「瀏覽」分頁**,使用者要自己點過去才看得到剛加的東西(見上面決策說明)。
- **網頁介面目前沒有針對大量文件的分頁/捲動優化**,跟 CLI 的 `list` 一樣是先求能動,文件一多畫面會變長。
- **`streamlit` 是獨立的 optional dependency**(`pyproject.toml` 的 `[project.optional-dependencies].ui`),裝 `.[dev]` 不會自動裝到,要另外 `pip install -e ".[ui]"` 或 `.[dev,ui]`。

## 接下來可能的方向(還沒決定)

CLAUDE.md「未來規劃方向」列的:
- 更多 ingestion 來源的其餘部分(瀏覽器書籤、Readwise/Instapaper、Obsidian/Notion 匯出——RSS 這一個已經做完)
- Hybrid search(關鍵字 + 語意搜尋並用)
- 自動化處理的其餘部分(關聯筆記推薦、去重複——自動打標籤這一小塊已經做完)
- Web UI 或 Raycast/Alfred 整合(**Streamlit 網頁介面已經做完基本版,而且使用者本人已經用過**,如果要往「多人使用」或更精緻互動的方向,可能要考慮換成正式 web app)

使用者說這些方向都想做,已經照優先順序做完 `remove` → 「更聰明的 dedupe」+「清空知識庫指令」→ 「自動打標籤(殼)」→ 「RSS ingestion」→ 「Streamlit 網頁介面」→「一鍵啟動」。**下一個對話開始時,建議問使用者接下來要做哪個**,不要自己選。

候選(不代表優先順序):
- **feed 訂閱清單**(見「已知的粗糙邊界」):如果使用者常態性要追蹤同一批 RSS 來源,「訂閱清單 + 一鍵同步全部」會比現在的「每次手動打網址」更有用。
- 更多 ingestion 來源(瀏覽器書籤、Readwise/Instapaper、Obsidian/Notion 匯出)。
- **YouTube 頻道 RSS**:對話中討論過,使用者問過但決定「先不做」。要注意的是 YouTube 頻道 RSS 只有標題+短描述,**沒有逐字稿**,能做的頂多是「新影片書籤」,不是「影片內容知識庫」;如果之後想做後者,得另外接字幕/逐字稿的來源,不是單純的 RSS ingestion 可以解決的,下次有人提這個要先講清楚這個限制。
- Hybrid search、關聯筆記推薦、去重複。
- 網頁介面的細節打磨(新增後自動跳轉、分頁、更明確的操作回饋)——使用者已經開始實際用網頁介面,這些會變得比較有感。

## 交接檢查清單(接手時建議做的事)

1. `git log --oneline` 確認目前在哪個 commit,`git status` 確認有沒有沒 commit 的東西(這次交接時,**只有網頁介面圖示改成 📚 這批預期還沒 commit**,其他都已經進 `bf94c0c`)
2. `./.venv/Scripts/python.exe -m pytest -q` 應該要 48 個全過、~4 秒內跑完
3. 如果要手動測 `add`/`search`,第一次跑會下載 ~90MB 的 embedding 模型,需要網路;jieba 第一次執行也會在本機建 prefix dict 快取(不用連網,純本機運算,第一次會慢個零點幾秒)
4. 如果要手動測 `ask`,需要使用者提供 `ANTHROPIC_API_KEY`(這台機器目前沒設,使用者已經知道怎麼設定,是自己的事,不用主動催)
5. `pyproject.toml` 這輪陸續加了 `jieba>=0.42`、`feedparser>=6.0`、`streamlit>=1.38`(在 `[project.optional-dependencies].ui`,不在預設 `dev` 裡)依賴,如果是全新環境要記得重新 `pip install -e ".[dev]"`(CLI/測試)跟 `pip install -e ".[ui]"`(網頁介面)
6. 如果要手動測 `add-feed` 又不想真的連網,`feedparser.parse()` 吃本機檔案路徑或原始 XML 字串都可以;這輪也已經用真實網址(BBC News 英文版)驗證過連網路徑沒問題,是使用者自己驗證的
7. 開始功能表有一個「Second Brain」捷徑指向 [run_web.bat](run_web.bat)(這輪在使用者機器上建的,不在 git 裡,取代了原本刪掉的桌面捷徑);如果要驗證雙擊啟動的行為,記得先刪掉 `%USERPROFILE%\.streamlit\credentials.toml` 模擬全新機器,不然「歡迎訊息卡住」那個 bug 修好了沒有根本測不出來
8. 如果要用瀏覽器自動化測 Streamlit 網頁介面,見「中途做的決策」裡記錄的工具限制(text_input 用 `computer` 的 type/key 不一定會觸發 rerun,要用 `javascript_tool` 搭配原生 setter + dispatchEvent)
