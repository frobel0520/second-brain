# Progress

這份文件是給「接手這個專案的下一個 Claude 對話」看的交接筆記,不是使用手冊。
使用方式看 [README.md](README.md),規劃看 [CLAUDE.md](CLAUDE.md)。這份只記錄
「現在做到哪、為什麼這樣做、接下來大概要做什麼」,每次做完一個階段性任務就更新。

最後更新:2026-07-12(第十五輪,網頁介面細節打磨)

## 現況一句話

CLAUDE.md 的 MVP 加上這些都做完了:`list`/`remove`/`clear`/`add-feed`/自動
打標籤/Streamlit 網頁介面/一鍵啟動/feed 訂閱清單(CLI+網頁)/`search`/`ask`
顯示時間/`remove-batch` 批次刪除(CLI+網頁)/UTC+8 時間顯示/翻譯成繁體中文
(第七輪)/hybrid search(第九輪,已 commit 進 `f44d231`)/文件分類(第十輪,
`科技`/`新聞`/`財經` 三個分類,`list`/`search`/`ask`/瀏覽頁面都能按分類篩選,
已 commit 進 `f0ef6d6` 並 push)/**`feeds sync` 排程自動化**(第十三輪,
Windows 排程工作每天早上 8 點自動跑一次,已 commit 進 `f846938` 並 push,
見下面專節)。**CLAUDE.md 原本把「自動化排程」明確排除在 MVP 範圍外,這次
是使用者主動要求才做,不是我自己決定跨出範圍。**

**第十五輪:網頁介面細節打磨**,問過使用者候選清單裡具體要做哪幾項(不是
全部做),選了三個:(1) 「新增筆記」加完文件後自動跳轉到「瀏覽」分頁;
(2) 「瀏覽」分頁加文件列表分頁(pagination,一頁 20 篇);(3) 「訂閱管理」
分頁「同步全部」的失敗提示改成折疊區塊,不是每個來源印一則訊息洗版。
**技術前提是把導覽從 `st.tabs()` 換成 `st.segmented_control()`**,因為
`st.tabs()` 沒辦法用程式碼切換分頁,細節見下面「網頁介面細節打磨」專節。
**三項都用 Claude Browser pane 實際操作過網頁介面驗證,包含手動訂閱一個
故意失效的網址來驗證失敗折疊區塊真的正確顯示,不是只看程式碼合理就結案**,
驗證完有把測試用的失效訂閱清乾淨。**第十五輪的程式碼已經 commit 進 `e8e1959` 並 push。**

**第十四輪沒有改程式碼**,做了兩件事:(1) 使用者問排程工作在「電腦當天
是關機狀態」跟「會不會用到 API token」這兩個問題,細節見下面「`feeds
sync` 排程自動化」專節新增的說明——重點是 `StartWhenAvailable=True` 會在
下次登入時補跑、但工作本身是 `LogonType: Interactive`(綁在使用者登入,
不是「電腦開機就跑」);目前沒設 `ANTHROPIC_API_KEY` 所以自動翻譯呼叫會
靜默失敗、不花 token,但**如果之後設了 key,排程會開始自動幫每天新文章
呼叫 Anthropic API 翻譯,是無感的背景行為**,要記得。(2) 使用者要求把
「待辦清單」裡的兩項拿掉:**更多財經 RSS 來源**、**翻譯功能品質驗證**,
其餘候選都保留,已經從「接下來可能的方向」跟「已知的粗糙邊界」/「交接
檢查清單」裡對應的地方刪掉,不是還沒做完只是先不追蹤。

**第十二輪:使用者決定把知識庫換成全部中文內容**——退訂 The Verge/Hacker
News/Simon Willison's Weblog 這三個英文科技來源、**並刪除這三個來源已經拉
進來的所有文章**(使用者明確要求連文章一起刪,不是只退訂),改訂閱三個中文
新聞類來源:**中央社(國際)**、**BBC中文網(繁體)**、**ETtoday(即時新聞)**。
細節見下面「訂閱異動」專節。知識庫現在有 **9 個訂閱來源**(科技 3:iThome/
TechNews 科技新報/DIGITIMES,財經 3:經濟日報/自由時報財經版/Yahoo股市,
新聞 3:中央社(國際)/BBC中文網/ETtoday),**109 篇文件**,分類統計是新聞
32、財經 47、科技 30,全部分類完畢、沒有遺漏。

**第十一輪沒有改程式碼**,做了三件事:(1) 使用者回報網頁介面噴
`ImportError: cannot import name 'list_categories'`——這是**已知問題,不是
新 bug**(見下面決策說明「長時間執行的 process 快取住舊模組」那條),使用者
自己在 8501 port 上跑的 Streamlit process 是在第十輪加 `list_categories` 之前
就啟動的,`sys.modules` 快取住舊版 `second_brain.storage`。**修法**:找到
PID(`Get-CimInstance Win32_Process` 查 `CommandLine` 確認是哪個 process,
不要瞎猜)、`Stop-Process` 砍掉、用 `preview_start` 重開一個全新的,新 process
重新 import 就抓到新程式碼了,同時也清掉了我自己前一輪測試留下的 port 8600
殘留 process。(2) 使用者要求**之後對話一律用繁體中文回覆**,已經存進
persistent memory(`feedback_language.md`),之後每次對話開始都要記得套用,
不用等使用者再次提醒。(3) 使用者想加中文科技類的來源,用 `WebSearch` +
瀏覽器找到三個有實際用 `feedparser.parse()` 驗證過可用的台灣科技媒體
RSS,列出來讓使用者選,使用者選**全部訂閱**:**iThome**
(`https://www.ithome.com.tw/rss`)、**TechNews 科技新報**
(`https://technews.tw/feed/`)、**DIGITIMES 科技/產業**
(`https://www.digitimes.com.tw/tech/rss/xml/xmlrss_10_0.xml`,這個 feed 有個
無害的 `document declared as us-ascii, but parsed as utf-8` bozo 警告,
`feedparser` 還是正確解析出 30 篇文章,不影響使用)。**這次直接在
`feeds add --category 科技` 一次到位**,不像第十輪訂財經來源時是先訂閱、
之後才回填分類,不需要事後 `set-category` 補救。**查過但沒有列進候選**:
數位時代(bnext.com.tw)、INSIDE(inside.com.tw)這兩家目前網站上都找不到
公開的 RSS 連結(猜測的網址回傳 404 或首頁完全沒有 rss/feed 相關連結),
可能已經停用公開 RSS、改成只有 App 或電子報訂閱,之後如果有人想訂這兩家,
要先確認他們是不是真的還有 RSS,不要直接假設網址存在。

**第十輪的內容(訂閱三個財經 RSS 來源 + 做完文件分類功能)沒有變動**,細節
還是看下面各專節,這裡不重複。**訂閱來源清單本身已經被第十二輪異動過**,
上面「第十二輪」那段的數字才是目前正確的現況,這裡不重複列。

**第八輪沒有改程式碼,做了兩件事**:(1) 使用者回饋第七輪的翻譯功能「其實好像
還好」,實際閱讀習慣是「想細看的文章再點進去用 Google 自動翻譯」,不需要整個
知識庫預先批次翻好。問過要不要把翻譯功能整個復原掉,**使用者選擇保留現有
程式碼跟 schema,不要撤掉**,理由是「未來還是有可能會串 API key 進來」——
這個功能目前是**做完但先擱置(不會主動去推進),不是沒用要刪掉的東西**,
之後如果又有人想动它,不用預設要重寫。(2) 使用者問我 hybrid search 具體
能改善什麼,我用他實際訂閱的內容舉例解釋完(語意搜尋對人名/版本號/專有名詞
這種精確詞彙容易抓不準,例如 Simon Willison 那篇講 `sqlite-utils` 套件更新的
筆記,語意搜尋不保證會排在「sqlite-utils」這個查詢的最前面),**使用者聽懂
且同意,下一輪的任務就是做 hybrid search**。**這輪對話因為 context window
快滿了,在使用者要求下提前收尾去交接,不是任務做完了才停**,下一輪從
「開始實作 hybrid search」接著做,不用再問方向。

## 環境

- Windows,Python 3.14.4,`.venv/` 在專案根目錄(已裝好所有依賴,含 torch/sentence-transformers/chromadb/anthropic/jieba/feedparser/streamlit)
- **git remote 已確認存在**(`origin` → `https://github.com/frobel0520/second-brain.git`),第四輪筆記已經記過,第四輪的東西已經 push 上去了,交接時 `git status --short --branch` 順便看一下是否 `ahead`/`behind`。
- 常用指令:
  ```bash
  ./.venv/Scripts/python.exe -m pytest -q                    # 跑測試,~4 秒,不用真的 embedding 模型
  ./.venv/Scripts/python.exe -m second_brain add <file>       # 手動驗證要真的跑一次
  ```
- `ANTHROPIC_API_KEY` 這台機器上沒設,`ask` 指令沒辦法真的打 API,只驗證過「沒設 key 時的錯誤處理」

## 已經做完的東西

十五個 CLI 指令全部能動,架構細節看 [README.md](README.md#架構):

1. `second-brain add <file> [--category/-c C]` — 讀 md/txt → 自動打標籤(本機 jieba 詞頻抽取)→ 切塊 → embedding(本機 sentence-transformers)→ 存 SQLite + ChromaDB。**同一份筆記再 add 一次會先刪舊版本再存新的**(`storage/store.py:replace_existing_document`),不是 append。「同一份筆記」的判斷邏輯之前升級過,見下面決策說明。`--category` 是**第十輪新加**,不給就不分類。
2. `second-brain add-feed <feed_url> [--limit/-n N] [--category/-c C]` — **一次性**抓取 RSS/Atom 來源,把每篇文章轉成一個 Document,跑同一套 `ingest_document()` 流程(標籤/切塊/embedding/dedupe/存檔),不會記住這個來源。這輪用真實的 BBC News 網址實測過,見下面專節說明。`--category` 是**第十輪新加**。
3. `second-brain search "<query>" [--top-k K] [--category/-c C]` — **第九輪改成 hybrid search**:語意搜尋(query 轉 embedding → ChromaDB cosine 相似度)+ BM25 關鍵字搜尋兩種分數正規化後加權合併,印出來源+**合併後的分數**+加入時間(時間是第四輪加的,`Document.created_at` 本來就有,只是沒印出來)。細節見下面「hybrid search」專節。`--category` 是**第十輪新加**,限定只在該分類的文件裡搜尋,見下面「文件分類」專節。
4. `second-brain ask "<query>" [--top-k K] [--category/-c C]` — 在 search 結果上組 context,呼叫 Anthropic API(`claude-opus-4-8`,寫死在 `config.ANSWER_MODEL`)做 RAG 問答。**第四輪把 `ask()` 的回傳型別從純字串改成 `AskResult(answer, sources)` dataclass**,CLI 在答案下面多印一段「來源:標題(時間)」清單,見下面決策說明。`--category` 是**第十輪新加**。
5. `second-brain list [--category/-c C]` — 列出知識庫裡的文件(標題、片段數、來源路徑、標籤)。`--category` 是**第十輪新加**,只列出該分類的文件,標題前面會加 `[分類]` 前綴。
6. `second-brain remove <source>` — 從知識庫刪除指定來源的紀錄(sqlite + chroma),不動硬碟上的檔案本身。純比對 `source_path`,**不會**做內容比對(remove 是明確指名要刪哪個來源,跟 add 的模糊 dedupe 語意不一樣)。`source` 參數型別**這輪改成 `str`,不是 `Path`**,而且**沒有** `exists=True`,因為要能刪除已經從硬碟上消失的檔案的舊紀錄,也要能刪 RSS 文章的網址(見下面決策說明的 bug 修復)。
7. `second-brain clear [--yes/-y]` — 清空整個知識庫(sqlite + chroma)。預設用 `typer.confirm()` 互動確認,`--yes`/`-y` 跳過確認直接清空(給腳本/非互動情境用)。不動硬碟上的原始檔案。
8. `second-brain feeds add <feed_url> [--name] [--limit/-n N] [--category/-c C]` — 把來源加進訂閱清單(SQLite `feeds` 表)並立刻同步一次;`--name` 不給的話會嘗試呼叫 `rss_loader.get_feed_title()` 抓 feed 頻道標題,抓不到就用網址本身當名稱。同一個網址重複 `feeds add` 會被拒絕(印出「已經訂閱過」,exit code 1),不會建立第二筆訂閱紀錄。內部直接呼叫 `sync_feed_subscription()` 做第一次同步,不會自己重複一遍 load/ingest 迴圈。`--category` 是**第十輪新加**,之後每次同步進來的文章都會標上這個分類。
9. `second-brain feeds list` — 列出訂閱清單:名稱、**分類**(第十輪新加,`[未分類]` 或分類名稱)、網址、上次同步時間(`尚未同步` 或時間戳)。
10. `second-brain feeds remove <feed_url>` — 從訂閱清單移除來源(刪 `feeds` 表那一列),**不會**動到已經加入知識庫的文章——訂閱清單只是「要不要繼續追蹤」的紀錄,跟文章本身是否留在知識庫是兩件事,要連文章一起刪要另外用 `second-brain remove <文章網址>`。
11. `second-brain feeds sync [--limit/-n N] [--log-file PATH]` — 同步訂閱清單裡的**所有**來源:對每個訂閱依序呼叫 `sync_feed_subscription()`,更新 `last_synced_at`,印出每個來源「新增 X 篇、更新 Y 篇、略過 Z 篇」。**單一來源抓取/解析失敗不會擋住其他來源**——`pipeline.sync_feed_subscription()` 把例外包進 `FeedSyncResult.error`,不會往外拋,`feeds sync` 對每個來源印出「同步失敗:{原因}」後繼續處理下一個。**每次同步時,凡是這次有被抓回來的文章都會用該訂閱目前的分類重新蓋掉分類**(見下面「文件分類」專節),這是刻意的行為,不是副作用;但**只有這次同步真的抓到的文章會被蓋**,已經滾出 feed 目前回傳範圍的舊文章不會被觸碰到,分類要嘛維持原樣、要嘛(如果從來沒被同步過)維持未分類,細節見下面的已知限制。`--log-file` 是**第十三輪新加**,給了的話會把這次同步的彙總結果(新增/更新總篇數、失敗來源數+原因)當一行附加寫進指定檔案,是給下面「排程自動化」專節的 Windows 排程工作用的,不用 `--log-file` 的話行為完全不變。
12. `second-brain feeds set-category <feed_url> <category>` — **第十輪新加**。更新一個已訂閱來源的分類,只影響**之後**同步進來的新文章,不會回頭改已經存在的文件——舊文件要改分類要用下面的 `set-category` 指令。
13. `second-brain remove-batch [--after DATE] [--before DATE] [--keyword K] [--source S] [--yes/-y]` — 依日期範圍/關鍵字/來源批次刪除文件,三個條件是**使用者要求的 OR**(符合任一個就刪,不是同時符合),`--after`/`--before` 兩個一起給是例外、彼此是 AND(定義一段區間)。**至少要給一個條件**,不然要用 `clear`。刪除前會列出符合的文件並要求確認(跟 `clear` 同樣的安全機制,`--yes` 可跳過)。日期格式是 `YYYY-MM-DD`,格式錯會被 typer 擋下來,不會靜默失敗。底層是 `storage/sqlite_store.py:find_documents()`,用動態組出的 `WHERE (cond1) OR (cond2) OR (cond3)` 查詢,`storage.remove_documents(ids)` 批次刪。**第五輪在網頁介面「瀏覽」分頁下方加了對應的批次刪除區塊**,同一套底層函式,UX 是「篩選條件 → 預覽符合的文件 → 勾選確認 → 刪除這些文件」四步驟,細節見下面決策說明。
14. `second-brain set-category <category> [--after DATE] [--before DATE] [--keyword K] [--source S] [--yes/-y]` — **第十輪新加**。跟 `remove-batch` 一模一樣的篩選邏輯跟安全機制(預覽 → 確認 → 執行),差別是把符合條件的文件分類**設成同一個值**,不是刪除。主要用途是幫既有文件補分類(例如透過一次性 `add-feed` 加入、沒有訂閱紀錄可以依循的文章),細節見下面「文件分類」專節。
15. `second-brain translate` — **第七輪新加**。幫知識庫裡還沒有翻譯(`translated_content IS NULL`)的文件補上繁體中文翻譯,需要 `ANTHROPIC_API_KEY`。跟 `add`/`add-feed`/`feeds` 的自動翻譯不同,這個指令是使用者主動要求,遇到認證失敗會直接停止並清楚回報(印出跟 `ask` 一樣的「找不到有效的 Anthropic API key」訊息),不會對每篇文件都重複噴出同一個錯誤;其他非認證類的單篇翻譯失敗只計進失敗數,不影響其他篇繼續翻。網頁介面沒有對應功能(批次翻譯可能要跑一段時間,先留在 CLI)。

**自動打標籤**(是「自動化處理」這個大方向的第一小步):`add`/`add-feed` 讀進文件後會呼叫 `processing/tagging.py` 的 `get_tagging_provider().tag(document)`,把結果存進 `Document.tags`(SQLite `documents.tags` 欄位,JSON 字串)。`list`/`add`/`add-feed` 的輸出訊息都會顯示標籤。`TaggingProvider` 是抽象介面(跟 `EmbeddingProvider` 同樣的設計慣例),目前唯一實作是 `KeywordFrequencyTaggingProvider`:用 jieba 斷詞(中文)+ 保留原樣的英文單字,濾掉停用詞,取詞頻最高的前 `config.MAX_TAGS`(預設 5)個當標籤。之後要換成 LLM 分類或規則式邏輯,只要換掉 `get_tagging_provider()` 回傳的實作。

**Hybrid search(第九輪新加)**:解決的問題是語意搜尋對精確詞彙(人名、版本號、專有名詞)容易抓不準——實際案例是知識庫裡 Simon Willison 那篇講 `sqlite-utils 4.1` 套件更新的筆記,搜尋「sqlite-utils」這個精確字串。
  - **實作前跟使用者確認過兩個細節**(上一輪筆記就寫了「這兩個還沒拍板,下一輪要邊做邊問」):(1) 關鍵字搜尋要不要加 `rank_bm25` 這個新依賴——使用者選**要加**;(2) 語意分數跟 BM25 分數怎麼合併——使用者選**正規化後加權平均**(不是簡單加總原始分數,因為兩種分數尺度天差地遠:cosine 相似度落在 0~1,BM25 分數沒有固定上限)。
  - `second_brain/retrieval/keyword_search.py` 新增 `keyword_scores(query) -> dict[chunk_id, float]`:把知識庫裡**全部**的 chunk(`storage.list_all_chunks()`,新加的函式,直接查 `chunks` 表)當 BM25 語料,用 `rank_bm25.BM25Okapi` 算分數。**語料是每次查詢即時從 SQLite 撈,沒有另外維護索引**——現有 chunk 數量(幾十篇文章、一兩百個 chunk)量體小,即時算完全夠用,之前筆記就記過不用先假設需要索引結構,實測也證實跑起來很快。
  - `second_brain/retrieval/search.py` 的 `search()` 改成:向量庫查詢時故意把 `top_k` 開一個很大的數字(`_ALL_CHUNKS_TOP_K = 10_000`)把**所有** chunk 的語意分數都拿到,再跟 BM25 分數(同樣覆蓋全部 chunk)做 min-max 正規化(各自 0~1),依 `config.SEMANTIC_WEIGHT`/`config.KEYWORD_WEIGHT`(預設都 0.5)加權平均,排序後才截斷成呼叫端要的 `top_k`。**為什麼要先撈全部再截斷,不是各自查 top_k 再合併**:如果各自只查 top_k,會漏掉「BM25 排很前面但語意排不進 top_k」或反過來的 chunk,正規化的基準(min/max)也會失真;知識庫量體小,先撈全部不是效能問題。
  - `search()`/`ask()` 對外的介面完全沒變(呼叫端 `cli.py`/`web.py`/`ask.py` 都不用改),這是刻意的——之前筆記就寫了「這是純粹換掉 `retrieval/search.py` 內部的排序邏輯,不是新增指令」。
  - **把斷詞邏輯從 `tagging.py` 抽成共用模組** `second_brain/processing/text.py`(`tokenize()` 函式,含 jieba 斷詞 + 停用詞過濾 + 長度/字元過濾),自動標籤跟 BM25 關鍵字搜尋現在共用同一套斷詞規則,不是分別各兜一份——`tagging.py` 原本的 `_tokenize()`/`_STOPWORDS`/`_MEANINGFUL_TOKEN` 整段搬過去,行為完全沒變(舊的 tagging 測試沒改也全過)。
  - 實測過真實知識庫:`second-brain search "sqlite-utils"` 前五名全部來自那篇 `sqlite-utils 4.1` 文章(分數 1.000 → 0.667),含精確字串的 chunk 排最前面。
  - **測試踩到一個值得記錄的細節,不是 bug,是 BM25 演算法本身的特性**:一開始寫 `keyword_scores` 的測試只用兩篇文件,結果 BM25 的 idf 剛好算出 0(`log(1.5/1.5) = 0`,corpus 只有兩篇、詞只出現在其中一篇時的數學巧合),測試「碰巧」通過但完全沒驗證到真正的排序邏輯。**改成三篇文件之後 idf 才有意義**,測試才是真的在測東西。**教訓**:BM25 相關的測試至少要三篇以上不同文件的語料,不能只用兩篇,不然 idf 可能算出退化值讓測試變成只是巧合通過。

**文件分類(第十輪新加)**:使用者想把知識庫的文章分成 `科技`/`新聞`/`財經` 三類,瀏覽頁面能按分類過濾。實作前問過使用者兩個問題:(1) 分類要怎麼決定——選項是「依訂閱來源固定分類」/「自動關鍵字判斷」/「純手動」,使用者選**依訂閱來源固定分類**;(2) 分類要怎麼用——使用者選**瀏覽頁面過濾 + search/ask 限定分類搜尋**(兩個都要)。
  - **`Document`/`FeedSubscription`/`DocumentSummary` 都加了 `category: str | None` 欄位**,自由文字(不是寫死的 enum),SQLite `documents`/`feeds` 兩個表都加了 `category TEXT` 欄位(用跟 `translated_content` 同一套 `_ensure_column()` migration 機制補欄位,這輪把 `_ensure_translated_content_column` 順手重構成通用的 `_ensure_column(conn, table, column, ddl)`,因為現在有三個地方要補欄位,值得抽成共用函式)。
  - **分類是存在 `Document` 上的固定值,不是靠即時 join `feeds` 表算出來的**:`ingestion/pipeline.py:ingest_document(document, category=None)` 在存檔前把 `category` 蓋到 `document.category` 上,`sync_feed_subscription()` 呼叫時傳入 `feed.category`。這是刻意的設計,跟這個專案一貫的原則一致(`feeds remove` 不影響已存文件)——如果分類是即時 join 出來的,那訂閱來源被取消或改分類時,已經存進去的文件的分類會跟著憑空消失/改變,這不是想要的行為。**代價**:`feeds set-category` 之後只影響「之後同步進來的新文章」,舊文件不會自動更新分類,要嘛靠下次同步時該文章剛好還在 feed 回傳範圍內順便更新,要嘛用 `second-brain set-category` 手動批次改。
  - **`second-brain set-category`(CLI)/網頁介面「批次設定分類」是新增的,不是 `remove-batch` 的變形,但共用同一套篩選邏輯**(`storage.find_documents()` 的 date/keyword/source OR 篩選 + 新加的 `category` AND 篩選)。主要用途:幫沒有訂閱紀錄可以依循的文件補分類(見下面「財經 RSS 訂閱與分類回填」專節裡 BBC 文章的例子),或修正分類分錯的文件。
  - **hybrid search(`retrieval/search.py:search()`)加了 `category` 參數**:給了的話,語意搜尋跟 BM25 兩邊都先篩掉其他分類的 chunk,再各自正規化——這是為了讓正規化的 min/max 基準只反映這個分類內的分數分布,不會被其他分類的分數尺度影響排名。`keyword_search.keyword_scores()` 也加了可選的 `chunks` 參數,讓呼叫端可以傳入篩選過的子集合當 BM25 語料,不用改成每次都重新查全部。`ask()` 原樣把 `category` 傳給 `search()`。
  - **CLI 跟網頁介面完整對稱**:`add`/`add-feed`/`feeds add` 都有 `--category`;`list`/`search`/`ask` 都有 `--category` 篩選;`feeds set-category` 改訂閱分類;`set-category` 批次改文件分類。網頁介面「瀏覽」分頁加分類篩選下拉選單 + 每篇文件顯示 `📁 分類` + 批次設定分類區塊(跟批次刪除同樣的「篩選條件 → 預覽 → 套用」流程,UI 直接照抄批次刪除那段的結構,沒有重新設計);「搜尋」/「問答」分頁加「限定分類」下拉選單;「訂閱管理」分頁每個訂閱顯示分類 + 一個小的文字輸入框+按鈕可以現場改分類;「新增筆記」分頁的上傳檔案/一次性訂閱表單都加了分類輸入框。
  - **手動驗證時真的用 Streamlit 網頁介面走過一次**:啟動 `streamlit run` 開瀏覽器確認分類篩選下拉選單、文件的 `📁 分類` 標籤、訂閱清單的分類顯示跟編輯欄位都正常渲染,沒有停留在「程式碼看起來對」就結束。**這輪剛好撞到另一個對話 session 也在跑同一個 `second-brain-web` 開發伺服器(同一個 `port: 8501`)**,`.claude/launch.json` 加了 `"autoPort": true` 解決衝突(讓 harness 自動換一個空的 port),這個設定檔的改動之後也不用改回去,不影響其他人正常使用。

**財經 RSS 訂閱與分類回填(第十輪)**:使用者想加財經類的來源,先用 `WebSearch`/瀏覽器找了幾個台灣財經媒體的 RSS 網址、逐一用 `feedparser.parse()` 實際驗證過抓得到文章(不是憑空猜網址),列出候選讓使用者選,使用者選了 3 個:**經濟日報**(`https://money.udn.com/rssfeed/news/1001/5588`)、**自由時報財經版**(`https://news.ltn.com.tw/rss/business.xml`)、**Yahoo股市**(`https://tw.stock.yahoo.com/rss?category=news`),都用 `feeds add` 訂閱並各抓了 10 篇。
  - **分類回填的完整過程**:先用 `feeds set-category` 把 6 個訂閱來源都設好分類(The Verge/HN/Simon Willison → 科技,新訂的 3 個財經來源 → 財經),再跑一次 `feeds sync` 讓**當下還在 feed 回傳範圍內**的文章重新蓋上分類。**這樣沒辦法涵蓋所有舊文件**:(1) 有幾篇比較早期加入、已經滾出 feed 目前回傳範圍的文章沒被這次 resync 碰到,依然是未分類;(2) 知識庫裡另外有 10 篇 BBC 中文網文章,是很久以前用**一次性** `add-feed`(不是 `feeds add` 訂閱)加進來的,根本沒有對應的 `feeds` 表紀錄可以依循,「依訂閱來源固定分類」這個規則對它們完全不適用。**兩種情況都用 `second-brain set-category <分類> --source <網域關鍵字> --yes` 手動掃過去補齊**(例如 `--source bbc.com` 補 BBC 文章的「新聞」分類,`--source money.udn.com`/`ec.ltn.com.tw`/`yahoo.com` 補財經來源滾出視窗的舊文章)。**這個過程中犯了一次操作失誤**:掃 `yahoo.com` 網域補財經分類之後,又手滑對 `tw.news.yahoo.com` 這個子網域跑了一次「科技」分類(原意是想確認還有沒有漏網之魚,結果打錯分類值),把已經正確設成財經的幾篇文章覆蓋成科技,發現後立刻用同一個指令重新掃一次改回財經修正。**教訓**:`set-category`/`remove-batch` 這類批次操作在下指令前,即使有 `--yes` 想跳過確認,也應該先不加 `--yes` 看一下預覽的分類清單再決定,尤其是要覆蓋「已經設定過」的欄位時,打錯值不會有任何警告(跟刪除不一樣,刪除至少東西會消失比較容易發現,分類設定錯了不會有明顯徵兆,可能過一陣子才會發現)。
  - **回填後最終結果**:90 篇文件全部分類完畢,科技 33 篇、財經 47 篇、新聞 10 篇,用 `sqlite_store.list_documents()` 直接查過 `category is None` 的數量確認是 0,不是只看 CLI 輸出的表面訊息。
  - **這輪(第十輪)筆記原本寫錯一件事,第十二輪退訂 Hacker News 時才發現、順便訂正**:原本以為「3 篇連結到外部網站(goeteia.dev/fabiensanglard.net/arxiv.org)的項目」是 Simon Willison's Weblog 的 linkblog 貼文,**其實是 Hacker News 的文章**——HN 的 RSS 本來就是連到原始文章網址(不是連到 news.ycombinator.com 討論頁),所以看起來很像某個部落格的「引用連結」貼文格式,兩種來源長得很像,光看 URL 本身容易搞混。第十二輪要精準區分「這篇文章到底是不是 HN 的」時,用了一個可靠的判斷法:HN 的 `<description>` 永遠是「Comments」這幾個字(見上面第六輪那個 bug 修法),觸發 `_MIN_CONTENT_LENGTH` fallback 後 `document.content` 會**完全等於** `document.title`;而 Simon Willison 的部落格文章(即使是短的 linkblog 貼文,例如「Quoting X」)`content` 都會有實際內容,不會跟 `title`一模一樣。用這個「`content == title`」訊號一查,原本以為的 3 篇 Simon Willison 文章其實全部符合 HN 的訊號,加上其他 10 篇也是同樣訊號,總共 13 篇——這才是真正的 HN 文章數量。**教訓**:這個專案的 `Document` 沒有存「這篇文章是從哪個訂閱來源進來的」這個關聯(`category` 是分類本身,不是來源本身的記錄),之後如果又要做「精準區分某篇文章到底來自哪個 feed」這種操作,不能只看 URL 網域,對於「RSS 連到外部網站」的來源(HN 是最典型的例子)要用內容特徵(例如 `content == title` 這個 HN 特有的訊號)去反推,不要憑 URL 長相用猜的。

**訂閱異動:退訂三個英文科技來源、改訂三個中文新聞來源(第十二輪)**:使用者決定把知識庫換成全部中文內容。
  - **退訂 + 刪除既有文章**:`second-brain feeds remove <url>` 退訂 The Verge/Hacker News/Simon Willison's Weblog 三個訂閱(這步驟本身不影響已存文件,是既有行為);接著使用者明確要求連文章也要刪掉,不是只退訂,所以再用 `remove-batch --source theverge.com --yes` 刪掉 10 篇 Verge 文章、`remove-batch --source simonwillison.net --yes` 刪掉 10 篇 Simon Willison 文章。**Hacker News 沒辦法用 `--source` 網域比對**,因為 HN 的文章連結是原始文章網址(散布在十幾個不同網域),不像其他來源網址網域統一——用上面決策說明提到的「`content == title`」訊號抓出精確的 13 篇 HN 文章 id,逐一用 `second-brain remove <url>` 刪除。
  - **新訂閱直接在 `feeds add --category 新聞` 一次到位**:**中央社(國際)**(`https://feeds.feedburner.com/rsscna/intworld`)、**BBC中文網**(`http://feeds.bbci.co.uk/zhongwen/trad/rss.xml`)、**ETtoday**(`https://feeds.feedburner.com/ettoday/realtime`),都是先用 `WebSearch` + 瀏覽器找候選、逐一用 `feedparser.parse()` 實測過才列進候選給使用者選,不是憑空猜網址。**BBC中文網這次變成正式訂閱**:知識庫裡本來就有 10 篇 BBC 中文網文章(很久以前用一次性 `add-feed` 加進來、被歸類「新聞」),`feeds add` 訂閱同一個 feed 之後,`sync_feed_subscription()` 的 dedupe 邏輯(比對 `source_path`)自動把這 10 篇的分類重新蓋上(還是「新聞」,值沒變但走的是同一套機制)、再加 2 篇新文章,不需要額外處理就自然接上了。
  - **查過但沒有列進候選的中文新聞來源**:**公視新聞**(`https://about.pts.org.tw/rss/XML/newsfeed.xml`)網址存在、頁面上有列出來,但實際用 `feedparser`/`urllib` 連線會噴 `SSL: CERTIFICATE_VERIFY_FAILED`(伺服器憑證缺 Subject Key Identifier,是對方網站憑證設定有問題,不是我們這邊的問題),沒有辦法用,之後如果又有人想訂公視新聞,先確認對方憑證問題有沒有修好,不要假設能直接接上。
  - **最終結果**:9 個訂閱來源(科技 3、財經 3、新聞 3),109 篇文件,分類統計新聞 32、財經 47、科技 30,全部分類完畢。

**`feeds sync` 排程自動化(第十三輪新加)**:CLAUDE.md 明確把「自動化排程」排除在 MVP 範圍外,這是使用者主動要求要跨出這個範圍才做的,不是自己決定的。
  - **兩個問題先問過使用者才動工**:(1) 多久同步一次——使用者選**每天一次**;(2) 要不要留執行紀錄——使用者選**要**,方便之後查「昨天有沒有正常同步」。
  - `second_brain/interface/cli.py` 的 `feeds sync` 加了 `--log-file PATH` 選項。**只是彙總結果,不是逐來源的詳細 log**:新增 `_format_sync_log_line(results)` 把這次同步所有來源的 `added`/`updated` 加總、統計失敗來源數,格式化成一行(例如 `2026-07-13 08:00:00  新增 12 篇、更新 3 篇、失敗 0 個來源`,失敗的話後面接 `:來源名 同步失敗:原因`),用 `--log-file` 給的路徑以 append 模式寫進去。**沒給 `--log-file` 的話行為完全沒變**,這個選項是純粹加值,不影響既有用法。
  - **排程機制用 Windows 內建工作排程器(Task Scheduler),不是自己寫常駐程式或裝額外的排程套件**:透過 PowerShell 的 `Register-ScheduledTask` 建立一個叫 `SecondBrainFeedsSync` 的排程工作,每天早上 8:00 執行 `.venv\Scripts\python.exe -m second_brain feeds sync --log-file <專案路徑>\data\sync.log`,working directory 設成專案根目錄。**選 Task Scheduler 而不是寫一個 Python 常駐程式**:符合 local-first 原則(不額外引入新的常駐服務/依賴),而且 `config.py` 的 `PROJECT_ROOT` 是用 `Path(__file__).resolve().parent.parent` 算出來的,不依賴呼叫時的工作目錄,所以排程工作用絕對路徑呼叫 `python.exe` 就能正確找到 `data/second_brain.db`,不需要額外處理路徑問題。
  - **手動觸發驗證過一次真的能動**:用 `Start-ScheduledTask` 手動觸發,一開始檢查 `LastTaskResult` 時看到 `267009`(SCHED_S_TASK_RUNNING,還在跑,不是失敗),多等一下之後變成 `0`(成功),`data/sync.log` 也確實多了一行,不是只看排程有沒有建立就假設會動。**這個排程工作是機器層級的設定,不在 git 裡**,跟 Start Menu 捷徑、`.streamlit/credentials.toml` 一樣是機器特定的東西,換一台機器要重新建立(可以用同一段 `Register-ScheduledTask` PowerShell 指令)。
  - **已知限制,故意先不處理**:`data/sync.log` 沒有輪替(rotation)機制,每天一行,累積個幾年也才幾千行,對個人用途的檔案大小不是問題,先不做自動清理/輪替。
  - **第十四輪:實際查證過「電腦當天沒開機」會怎樣,上一輪筆記原本猜錯,這輪訂正**:上一輪筆記原本寫「沒有補跑機制,電腦當天沒開機那天就不會同步」,是沒有實際查證就寫下去的猜測。這輪用 `Get-ScheduledTask` 查這個工作實際的 `Settings`/`Principal` 才發現:建立時用的 `New-ScheduledTaskSettingsSet -StartWhenAvailable` **確實有生效**(`StartWhenAvailable = True`),代表如果 8:00 電腦是關機狀態,排程器會在下一次符合條件時把錯過的這次補上。但 `Principal.LogonType` 是 `Interactive`(綁在 `ytwei` 這個使用者的登入身份,不是「電腦開機就跑」、也不是不管有沒有人登入都跑的系統層級工作),所以精確的行為是:**電腦開機、使用者登入之後,排程器會偵測到今天這次還沒跑、很快補跑一次**,不是完全不會補、但也不是「開機瞬間」就觸發,是要等到實際登入那個時間點。**教訓**:排程/系統設定這類「聲稱會怎麼運作」的細節,尤其牽涉到「missed run 會不會補」這種容易讓人日常誤解的行為,要直接查詢實際設定值(`Get-ScheduledTask`/`Get-ScheduledTaskInfo`)才寫進筆記,不要靠對 Windows Task Scheduler 一般印象去猜,猜錯了下一個人接手會被誤導。
  - **第十四輪:確認過排程本身不花 API token,但如果之後設定 `ANTHROPIC_API_KEY` 會改變**:`feeds sync` 每篇文章的 embedding(sentence-transformers)、自動打標籤(jieba)都是本機運算,不叫任何 API,永遠不花 token。但 `ingest_document()` 內建的自動翻譯(`processing/translation.py:AnthropicTranslationProvider`)每篇新/更新的文章都會嘗試呼叫一次 Anthropic API——**這台機器目前沒設 `ANTHROPIC_API_KEY`,所以這個呼叫現在會失敗且被 `_translate_best_effort()` 靜默吞掉,完全不花 token**。但**如果使用者之後真的設定了 `ANTHROPIC_API_KEY`**(例如只是想手動用 `ask` 問答),這個每天自動跑的排程會**自動、無感地**開始幫每天新抓進來的文章呼叫 API 翻譯,9 個訂閱來源、一天可能新增幾十篇,長期下來是會產生實際費用的——這不是這輪要處理的問題,只是先記下來,等使用者真的設定 key 的時候要主動提醒這個關聯,不要假設他自己會想到「設 key 給 ask 用」會連帶讓排程開始花錢做翻譯。

**RSS/Atom ingestion**(CLAUDE.md「更多 ingestion 來源」的第一個):`ingestion/rss_loader.py` 的 `load_feed(feed_url, limit=None) -> list[Document]`,用 `feedparser` 解析 feed,每個 entry 轉成一個 `Document`:
  - `source_path` 用文章的 `link`(dedupe/`remove` 都靠這個欄位比對,語意上等同本機檔案的路徑)
  - `content` 優先取 `content:encoded`,沒有就退回 `summary`/`description`,再過一個很陽春的正則去標籤(`_strip_html`,不是完整 HTML parser)
  - `feed_url` 參數其實是「feedparser 看得懂的任何東西」——網址、本機檔案路徑、feed 原始內容字串都吃,單元測試因此完全不連網(直接餵 XML 字串)
  - **這輪已經用真實網址實測過**:`http://feeds.bbci.co.uk/news/world/rss.xml`(BBC News 國際版),`add-feed --limit 5` 抓了 5 篇真實文章,標籤、dedupe(重跑一次變成「已更新」不會重複)、`search` 語意排序全部驗證過在真實英文新聞內容上正常運作。之前「還沒對真實網址測過」這個粗糙邊界已經解決。

**Streamlit 網頁介面**:`second_brain/interface/web.py`,`streamlit run` 啟動,**五個分頁**:
  - **瀏覽**:列出所有文件(標題/片段數/標籤/來源),每筆有刪除按鈕
  - **搜尋**:文字框 + 滑桿(top-k),結果卡片顯示分數/來源/片段內容
  - **問答**:文字框問問題,沒有 `ANTHROPIC_API_KEY` 會顯示友善錯誤(跟 CLI 的 `ask` 一致)
  - **新增筆記**:上傳本機檔案(存到 temp file 再走 `load_document()`)、或輸入 RSS 網址走 `load_feed()`(一次性,不記住來源)
  - **訂閱管理**(**這輪(第三輪)新加**):列出訂閱清單(名稱/網址/上次同步時間),每筆有「同步」「取消訂閱」按鈕,上面還有一個「同步全部」;下半部是新增訂閱的表單(網址/顯示名稱/首次同步篇數)。CLI 有的 `feeds add/list/remove/sync` 這個分頁全部對應得到,底層呼叫同一組 `storage.subscribe_feed()`/`unsubscribe_feed()`/`list_feed_subscriptions()` + `pipeline.sync_feed_subscription()`/`sync_all_feed_subscriptions()`,不重寫邏輯。
  - 用 `@st.cache_resource` 包一個 `_warm_up_providers()`,頁面第一次載入就把 embedding/tagging 模型準備好,避免 Streamlit 每次互動重跑整支 script 時反覆重新載入模型
  - **沒有網頁版的 `clear`**:清空整個知識庫這種危險操作刻意只留在 CLI,網頁介面不放
  - **圖示是 📚(書本),不是 🧠**:使用者說想要「知識庫的感覺,不要大腦的圖」換的,這批上一輪已經 commit 進 `a6d4cc1`。
  - **第十五輪:分頁導覽從 `st.tabs()` 改成 `st.segmented_control()`**:原因是 `st.tabs()` 沒有公開 API 可以用程式碼切換到指定分頁,`st.segmented_control()`(Streamlit 1.37+,這個專案裝的是 1.59.1)可以透過 `key` 綁定 `st.session_state`,在 widget 建立**之前**先蓋掉 `st.session_state["active_tab"]` 的值再 `st.rerun()`,下一次執行時 widget 就會用新的值渲染,達到「跳轉到指定分頁」的效果——這是這輪要做「新增後自動跳轉」的必要前提,不是隨意換元件。整個檔案結構也從 `tab_x = st.tabs(...); with tab_x:` 改成 `active_tab = st.segmented_control(...); if active_tab == "x": ...`,五個分頁的內容邏輯本身沒有任何改變,純粹是外層容器換掉。**`segmented_control` 允許再點一次目前選中的選項讓它變成「沒有選取」(回傳 `None`)**,程式碼多加了 `if active_tab is None: active_tab = "瀏覽"` 防呆,不然會整頁空白。

**網頁介面細節打磨(第十五輪)**:候選清單裡列了三個小項,問過使用者要做哪幾個(不是全部一次做完),使用者選了以下三項:
  - **「新增筆記」加完之後自動跳轉到「瀏覽」分頁**:上傳檔案或一次性抓 RSS,只要至少有一篇成功處理(`added > 0`),就把結果訊息存進 `st.session_state["add_note_message"]`、把 `st.session_state["nav_target"]` 設成「瀏覽」,再 `st.rerun()`;腳本最上方(畫導覽列之前)把 `nav_target` 套用到 `active_tab`,「瀏覽」分頁最上面則檢查 `add_note_message` 印出來(跟既有的 `batch_delete_message`/`batch_category_message` 用同一套「訊息存 session_state、下個分頁載入時彈出來顯示」的既有慣例,沒有另外發明新機制)。**如果全部文件都是空內容被略過(`added == 0`)則不跳轉**,原地顯示「完成:0 篇已處理...」,因為沒有新東西可以去瀏覽分頁看。
  - **「瀏覽」分頁加文件列表分頁(pagination)**:`_BROWSE_PAGE_SIZE = 20`,用 `st.number_input` 讓使用者輸入頁碼,`math.ceil(len(documents) / 20)` 算總頁數,對 `documents` list 做切片。**切換分類篩選時會把頁碼重設回第一頁**:偵測 `browse-category-filter` 這次的值跟上次記錄的值(`browse-category-prev`)是否不同,不同就把 `browse-page` 重設成 1——這是必要的防呆,不然「篩選後文件變少,但頁碼還停在篩選前的較大頁數」會讓 `st.number_input` 的 `max_value` 跟已存的 session_state 值互相打架。**已知的（可以接受的）行為**:手動測試時發現,切到別的分頁(例如「搜尋」)再切回「瀏覽」,頁碼也會重置回第一頁,即使分類篩選沒有變——推測是 Streamlit 對「這次腳本執行沒有被實例化的 widget」在下次重新出現時,不一定會保留舊的 session_state 值(這輪沒有深入查證 Streamlit 內部確切機制,只確認了現象),但這不在使用者要求的範圍內(沒有人要求切分頁要記住頁碼),不特地修。
  - **「同步全部」的失敗提示分組**:原本 9 個來源全部同步完會列出 9 則 `st.success`/`st.error`,畫面很長。改成:成功的來源全部彙總成一行(`f"{len(successes)} 個來源同步成功 — 共新增 {total_added} 篇、更新 {total_updated} 篇。"`),失敗的來源用 `st.expander(f"⚠️ {len(failures)} 個來源同步失敗", expanded=True)` 包起來(預設展開,因為失敗需要立刻被注意到,不是隨便找個地方藏起來),裡面才逐一列出每個失敗來源的名稱+原因。**手動測試時真的訂閱一個故意失效的網址(`https://this-is-not-a-real-feed-url-12345.invalid/rss.xml`)驗證過失敗折疊區塊會正確顯示**(「⚠️ 1 個來源同步失敗」+ 展開後看到「測試失效來源:無法解析這個 RSS/Atom 來源」),不是只看程式碼邏輯合理就假設沒問題,驗證完馬上用 `feeds remove` 把這個測試訂閱清掉,沒有留在真實知識庫裡。
  - **三項都用 Claude Browser pane 實際跑過 Streamlit 網頁介面驗證,不是只看程式碼**:自動跳轉用真的上傳/抓 RSS 測過、跳轉後訊息確實出現在瀏覽分頁,且用 JS 查證 `segmented_control` 的 `aria-checked` 真的切到「瀏覽」;分頁用真的點頁碼增減鈕測過,文件內容確實隨頁碼變化;失敗分組如上所述用真的失效網址測過。
  - **這輪沒有選的候選,還留著沒做**:批次刪除/設定分類的「預覽符合的文件」清單切換分頁不會自動更新,這個不在這次要打磨的範圍裡。

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
- **feed 訂閱清單跟一次性的 `add-feed` 是刻意分開、不是取代關係**:`add-feed` 保留原樣(抓一次就忘記),新的 `feeds add/list/remove/sync` 是獨立的一組指令,存進新的 SQLite `feeds` 表(`id`/`url`/`name`/`added_at`/`last_synced_at`)。這樣選是因為兩種用法都合理——偶爾想臨時抓一次某個網址不需要訂閱,常態追蹤的來源才需要訂閱清單,沒有理由把兩者綁在一起或互相取代。
- **`feeds remove` 不會刪除已經加入知識庫的文章**:訂閱清單的 `feeds` 表跟 `documents`/`chunks` 表完全獨立,`feeds remove` 只刪 `feeds` 表那一列。**刻意這樣設計**:取消訂閱通常是「不想再抓新文章」,不代表「連已經讀過存起來的舊文章都要刪掉」,這兩個意圖不一樣,合併成同一個操作反而危險(容易誤刪知識庫內容)。要清文章要另外呼叫 `remove <文章網址>`。
- **`feeds sync` 一個來源失敗不擋住其他來源**:`pipeline.sync_feed_subscription()` 把 `load_feed()` 的例外接住存進 `FeedSyncResult.error`,不往外拋;`sync_all_feed_subscriptions()` 對每個訂閱各自呼叫,不會因為第一個來源網路逾時就整批失敗。跟 `add-feed` 原本「抓取失敗就整個指令 exit 1」的行為不同,是刻意的取捨:`add-feed` 只抓一個來源,失敗就是全部失敗;`feeds sync` 抓多個來源,「其中一個壞掉」不該連累其他還在正常運作的訂閱。
- **`feeds add` 重複訂閱同一個網址會被拒絕,不是靜默忽略或更新**:`storage/store.py:subscribe_feed()` 先查 `get_feed_subscription_by_url()`,已存在就回傳 `None`,CLI 印「已經訂閱過這個來源了」並 exit 1。選擇「明確報錯」而不是「靜默升級成 no-op」,是因為使用者打錯字或忘記自己訂閱過的機率不低,直接告訴他比默默什麼都不做更有幫助。
- **修掉一個既有 bug:`remove` 指令對網址用 `Path.resolve()` 在 Windows 上會壞掉**:這輪手動驗證 `feeds` 系列指令時,想清掉自己加的測試文章,發現 `second-brain remove https://example.com/...` 完全找不到紀錄。原因是 `remove` 的 `file_path` 參數型別是 `Path`,`file_path.resolve()` 在 Windows 上會把網址當成相對路徑正規化,`/` 全部變成 `\`,結果拿去查 `source_path` 當然查不到(RSS 文章的 `source_path` 是 `rss_loader.py` 存進去的原始網址,不會有反斜線)。**這個 bug 從 `add-feed` 那次對話就存在**,只是一直沒人真的用 `remove` 刪過 RSS 來源的文章,沒被踩到。修法:`remove` 的參數改成 `source: str`,只有「不含 `://`」才當本機路徑做 `Path(source).resolve()`,網址原樣傳給 `remove_document()`。用真的加一篇 RSS 文章再 `remove` 掉驗證過修好了,`second_brain/interface/web.py` 的瀏覽分頁刪除按鈕本來就是直接呼叫 `remove_document(document.source_path)`(不經過這段 CLI 的路徑解析),不受影響、不用改。
- **上一輪筆記寫錯的地方,這輪順便更正**:上一輪 Progress.md 說「BBC 中文網網址沒有實際驗證過」,但這輪手動測試時發現資料庫裡已經有 10 篇 `bbc.com/zhongwen/...` 的真實文章(標題像「颱風巴威登陸浙江」),代表使用者上輪對話結束後其實有自己再測過一次中文網址,只是沒有回報、筆記也沒更新。以後如果資料庫裡的內容跟筆記寫的對不上,**優先相信資料庫裡看到的實際狀態**,筆記只是輔助記憶,不是唯一真相來源。
- **第三輪:`feeds add` 訂閱後 `last_synced_at` 沒更新,是重複實作邏輯造成的 bug**:CLI 的 `feeds_app.command("add")` 一開始寫的時候,是自己手動呼叫 `load_feed()` + 迴圈 `ingest_document()`(仿照 `add-feed` 的寫法),沒有意識到這樣繞過了 `sync_feed_subscription()` 裡「更新 `last_synced_at`」那一步。這輪加網頁介面訂閱管理分頁、要重用同一套同步邏輯時才發現這個落差(因為網頁介面一開始就是直接呼叫 `sync_feed_subscription()`,兩邊行為對不起來)。**教訓**:兩個地方都要做「訂閱來源的第一次同步」這件事時,不該分別手動兜一份 load+ingest 迴圈,應該直接呼叫共用的 `sync_feed_subscription()`——這也是為什麼 `pipeline.py` 要把同步邏輯獨立成一個函式而不是直接寫在 CLI 指令裡。修法:`feeds_add` 改成 `subscribe_feed()` 拿到 `FeedSubscription` 之後直接呼叫 `sync_feed_subscription(feed, limit=limit)`,不再自己重複一遍 load/ingest 迴圈,程式碼也變短。
- **第三輪:網頁介面「同步」按鈕的訊息被自己呼叫的 `st.rerun()` 洗掉,是真的會發生的 bug**:一開始寫的時候,`st.success(...)`/`st.error(...)` 印完馬上接一行 `st.rerun()`(想法是讓上面「上次同步」的時間戳立刻更新)。用 Claude Browser pane 實際點過一次才發現:`st.rerun()` 會讓整個 script 重新從頭執行,這個執行環境裡剛剛印出的訊息不會被保留下來,使用者完全看不到同步結果,只會看到清單瞬間「消失又出現」。**修法是拿掉這兩處(單一同步、同步全部)的 `st.rerun()`**,讓訊息留在畫面上;代價是「上次同步」時間戳要等下一次互動(切分頁、點別的按鈕)才會反映最新值——這跟「新增筆記」分頁「新增後不會自動跳轉去瀏覽分頁」是同一類已經接受的 Streamlit rerun 模型下的取捨,不是新問題。**判斷原則,以後遇到類似情況可以參考**:一個互動的回饋(`st.success`/`st.error`/`st.warning`)跟「馬上強制重整」這兩件事衝突時,優先保留使用者看得到的回饋,強制重整可以晚一點靠使用者自己的下一個動作觸發。「取消訂閱」按鈕沒有這個問題(它本來就沒有訊息要顯示),保留 `st.rerun()` 沒問題。
- **第三輪:瀏覽器自動化操作 Streamlit 的 `text_input` 這次踩到的細節,補充上一輪的筆記**:上一輪筆記寫「要用 `javascript_tool` 搭配原生 setter + dispatchEvent keydown Enter」,這輪實測發現:用 `form_input` 工具(原生 setter,不含事件派發)先把值寫進 DOM,再用 `computer` 的 `left_click` 點擊**另一個欄位**(觸發 blur)一樣能讓 Streamlit 端收到新值、跑出對應的按鈕/畫面——不一定要模擬 Enter 鍵。另外**踩到一個新陷阱**:用 `computer` 的 `key` 動作送 `ctrl+a` 想清空欄位再 `type` 新內容,結果兩次的內容疊在一起變成重複貼上(可能是 `ctrl+a` 在該元件裡沒有真的選取全部文字)。**以後要清空 Streamlit 文字輸入框再填新值,優先用 `form_input` 直接設定完整值(它是整個覆蓋,不是插入),不要用 `ctrl+a` + `type` 這個組合**,比較不會出現內容重複疊加的問題。
- **手動驗證網頁介面時發現的自動化工具限制**(跟程式碼本身無關,記錄下來是因為之後如果還要用瀏覽器自動化測 Streamlit 應用會再踩到):`computer` 工具的 `type`/`key` 動作有時候不會觸發 Streamlit React 元件的內部事件處理(尤其是 `st.text_input` 需要「真的」keydown 事件才會 commit 值並觸發 rerun),用 `javascript_tool` 搭配原生 `HTMLInputElement` 的 setter(`Object.getOwnPropertyDescriptor(...).set`)+ 手動 `dispatchEvent(new KeyboardEvent('keydown', {keyCode:13,...}))` 比較可靠。另外這次的瀏覽器 `screenshot` 動作一直逾時,改用 `get_page_text`/`read_page`/直接查 DB 驗證資料正確性,不影響驗證結果。
- **`run_web.bat` 一開始沒處理 Streamlit 的「Welcome」提示,會整個卡死**:第一次手動測試雙擊啟動時,發現視窗開了、python 進程也在跑,但 port 8501 永遠沒 bind、瀏覽器打不開。原因是 Streamlit 第一次在「有 console 但沒人可以互動輸入」的情況下執行(例如被 `Start-Process`/雙擊捷徑這種方式啟動的分離視窗),會卡在一個一次性的「Welcome to Streamlit,請輸入 email 或按 Enter 跳過」的 stdin 提示——沒有 `%USERPROFILE%\.streamlit\credentials.toml` 這個檔案就會觸發,而這個提示沒人能按,就永遠卡住,連錯誤訊息都不會印。**這是一個真的修好的 bug,不是預防性程式碼**:一開始想用手動在使用者機器上建一個全域 `credentials.toml` 來解決,但那樣的話這個 repo 換一台機器/換一個使用者就會重現同樣的卡住,所以改成讓 `run_web.bat` 自己在啟動前檢查、不存在就自動建立空的 `credentials.toml`(內容是 `[general]\nemail = ""`),讓它在任何機器上第一次雙擊都能正常動,不用任何人先手動用終端機跑過一次去回答那個提示。用「先刪掉這個檔案模擬全新機器」的方式驗證過批次檔真的能自己處理好這個情況。
- **第四輪:問清楚「時間戳記」要解決的問題,結果比想像中簡單**:一開始收到「每筆資料加上時間戳記」這個需求時,先入為主猜可能是要解決「更新等於刪掉重建、原始加入時間會被洗掉」這個更深的問題(這個問題確實存在,見下一條),準備了兩個選項問使用者。使用者選的是最簡單那個:`Document.created_at` 本來就有,只是 `search`/`ask` 沒印出來。**教訓**:需求字面上的意思跟我腦補的「應該是想解決的深層問題」不一定一樣,寧可先問清楚範圍,不要直接動 schema。
- **第四輪:`ask()` 回傳型別從 `str` 改成 `AskResult(answer, sources)` dataclass,不是加一個平行的新函式**:因為要在答案下面附上來源標題+時間,`ask()` 內部本來就已經呼叫過 `search()` 拿到帶時間戳的 `SearchResult` 列表,直接把這個列表原封不動放進回傳值最省事,不用再呼叫一次 `search()`(那樣會重複算一次 embedding,浪費且可能因為非確定性 embedding provider 導致兩次結果不一致)。**這是一個會動到既有介面的改動**:`ask()` 的呼叫端(`cli.py`、`web.py`、`tests/retrieval/test_ask.py`)都要跟著改讀 `.answer`/`.sources`,不是巧合地保持相容——這類「回傳值型別變更」的改動要記得抓 grep 一次所有呼叫端,不能只改定義端。
- **第四輪(真的會壞掉的 bug):`documents.tags`/`metadata` 用預設 `json.dumps()` 存,中文字被跳脫成 `\uXXXX`,導致 `LIKE` 關鍵字比對比不到**:寫 `remove-batch --keyword` 的關鍵字比對邏輯時,對三個欄位(`title`/`content`/`tags`)都用 `LIKE '%關鍵字%'`,`title`/`content` 是純文字沒問題,但 `tags` 欄位是 `json.dumps(document.tags)` 存的 JSON 字串——**Python `json.dumps()` 預設 `ensure_ascii=True`,中文字元會被轉成 `\uXXXX` 逃逸序列**,存進 SQLite 的實際內容變成類似 `["資料庫"]` 而不是 `["資料庫"]`,拿中文關鍵字下去 `LIKE` 當然比對不到。寫測試(`test_find_documents_matches_keyword_in_title_content_or_tags`)時當場抓到,不是憑空想到的。**修法**:`sqlite_store.py` 裡三個 `json.dumps()` 呼叫(`document.metadata`、`document.tags`、`chunk.metadata`)全部加上 `ensure_ascii=False`,讓中文以原始 UTF-8 存進 SQLite(SQLite 本身是 UTF-8,原生支援,沒有理由多繞一層跳脫)。**這個修正只對「之後新寫入」的資料有效**,這次修正之前就已經存在的舊資料(包含使用者真實的 BBC 中文網文章)`tags` 欄位仍然是舊的跳脫格式,`remove-batch --keyword` 對這些舊文件的標籤比對還是會比不到(標題/內容本來就是純文字欄位,不受影響,還是比對得到)——這個專案目前沒有 migration 機制(同樣的坑之前 `tags` 欄位本身、`feeds` 表都踩過),要嘛重新 `add`/`feeds sync` 一次讓資料用新格式重寫,要嘛之後有需要再考慮寫一個一次性的 migration script 把舊 `tags` 欄位轉成 `ensure_ascii=False` 格式。
- **第四輪:`remove-batch` 的 OR 邏輯是使用者明確要求的,不是我預設的選擇**:實作前有問使用者「日期/關鍵字/來源同時給的話要 AND 還是 OR」,使用者選 OR(符合任一個就刪)。這跟我原本設想的「AND 比較不容易誤刪」直覺不一樣,**這是使用者確認過的設計,不是應該被「修正」的東西**,以後如果要改這個行為要重新跟使用者確認,不要自己覺得「AND 比較安全」就默默改掉。`--after`/`--before` 兩個一起給是唯一的例外(彼此是 AND,定義一段日期區間),因為單獨拆成兩個 OR 條件會沒有意義(任何日期都會符合「早於某天」或「晚於某天」其中之一)。
- **第四輪:`remove-batch` 沿用 `clear` 的安全機制(列出項目 + 互動確認 + `--yes` 跳過),沒有另外問使用者**:因為這是既有專案慣例(`clear` 已經這樣做),批次刪除又比單筆 `remove` 危險,套用同一個模式是最小驚訝的做法,不需要每次遇到「這個操作有點危險」就重新問一次要怎麼做確認機制。
- **第四輪:`remove-batch` 至少要求一個篩選條件,不給任何條件會被擋下來並導去 `clear`**:如果讓「什麼條件都不給」的 `remove-batch` 等同「刪除全部」,會跟 `clear` 語意重疊、而且更容易因為忘記打條件而誤刪全部知識庫(`clear` 至少指令名稱就在警告你「這是清空」,`remove-batch` 沒打條件不會有這種直覺提示)。
- **第五輪(真的會壞掉的 bug):`st.expander()` 沒設 `expanded=True` 的話,每次欄位失焦觸發 rerun 就會自動收合**:一開始把批次刪除的表單包在 `st.expander("批次刪除")` 裡(想法是預設收起來、不要一直佔畫面)。手動測試填表單時發現:填完「關鍵字」欄位、游標移到「來源」欄位觸發 blur → Streamlit rerun → **`st.expander()` 預設是每次重跑都重新算 collapsed 狀態,不會記住使用者剛剛手動展開過**,整個區塊自己關起來,使用者填到一半東西就消失,完全無法正常使用。**這是真的會發生的 bug,不是預防性修改**(用 Claude Browser pane 實測到表單「自己關起來」)。**修法**:拿掉 `expander`,批次刪除區塊直接固定顯示在「瀏覽」分頁最下面(用 `st.divider()` + `st.subheader()` 分隔,跟頁面其他區塊風格一致)。**教訓**:Streamlit 的 `expander`/類似「可摺疊」元件,只要底下有任何會觸發 rerun 的互動元件(text_input 的 blur、date_input 的選擇……),沒有額外用 session_state 記住展開狀態的話,預設行為就是每次 rerun 都摺疊回去——這個專案目前唯一一處用到 `expander` 就踩到這個坑,以後這個專案裡應該避免在會員互動的表單外面包 `expander`,除非額外處理展開狀態的持久化。
- **第五輪:`form_input` 工具這次對 Streamlit 的 `text_input` 沒有效果,DOM 值改了但 Python 端讀不到**:這輪重新測試批次刪除的關鍵字欄位時,先用 `form_input` 設值,`javascript_tool` 直接查 DOM 確認值真的寫進去了(`el.value` 印出來是對的),但點擊「預覽符合的文件」後 Streamlit 端印出「至少要給一個篩選條件」——代表 Python 端的 `st.text_input()` 讀到的還是空字串,`form_input` 的原生 setter 沒有觸發 Streamlit React 元件真正監聽的事件。**跟上一輪(第三輪)的結論不完全一樣**:第三輪筆記寫「`form_input` + 點別的欄位觸發 blur」有效,這輪同樣的組合卻沒用——**不確定原因是不同元件實例的差異還是环境本身不穩定,先記錄「這個工具在這個專案的 Streamlit 元件上不可靠」這個結論,不要再假設它一定有效**。**最後真的有效的作法**:改用 `computer` 工具的 `triple_click`(選取欄位既有文字)+ `type`(真的鍵盤輸入,不是 DOM setter)+ 按 `Enter` 或點別的地方觸發 blur。**以後在這個專案測 Streamlit 文字輸入,優先用 `computer` 的 triple_click+type,不要優先嘗試 `form_input`**,可以省掉來回除錯的時間。
- **第五輪:Streamlit 的 `st.checkbox` 用 react-aria 做無障礙處理,真正的 `<input type="checkbox">` 被 `clip-path` 視覺隱藏,直接點擊/`.click()` 都不會觸發**:用 `read_page` 拿到的 checkbox ref 定位去點,或用 `javascript_tool` 對 input 元素本身呼叫 `.click()`,DOM 的 `checked` 屬性都沒有變化,Python 端的 `st.checkbox()` 也讀不到勾選狀態。查了 DOM 結構才發現真正的 `<input>` 包在一個 `clip-path: inset(50%)` 的 `<span>` 裡(視覺上完全隱藏,只留給螢幕閱讀器用),畫面上看到的方框圖示是另一個 `aria-hidden` 的裝飾元素,不是可互動的 DOM 節點。**有效的作法**:用 `javascript_tool` 找到 checkbox 的 `closest('label')`,對這個 `<label>` 呼叫 `.click()`——HTML 原生的 `<label>` 點擊會自動委派給它包住的表單元件並觸發正常的 `click`/`change` 事件,這是瀏覽器原生行為,不受 react-aria 的自訂事件處理影響。**以後在這個專案測 Streamlit checkbox,直接跳過點 input/point 座標這條路,用 JS 點 `label` 元素**。
- **第六輪(真的會造成資料遺失的 bug):RSS 來源的內容太短時,dedupe 邏輯會把不同文章互相誤判成「同一篇改名」**:訂閱 Hacker News 時發現 5 篇文章 `feeds add` 完只剩 1 篇存活。追根究底是 HN 的 RSS `<description>` 對每篇文章都只放「Comments」這幾個字(連到討論串的佔位文字,不是文章摘要),`ingest_document()` 的 dedupe(`storage/store.py:replace_existing_document`)在「同路徑找不到」時會退回比對 `content` 是否完全相同——同一批次裡每篇 HN 文章的 `content` 都是一模一樣的「Comments」,所以每加一篇新的,就會被判定成「跟前一篇是同一份筆記改名」,把前一篇的資料整個取代掉,如此連環覆蓋,一批 N 篇最後只剩 1 篇。**這個 bug 不是這次新出現的——從 `add-feed`/`feeds` 系列指令一開始做出來就存在,只是先前測試用的 BBC 新聞/自己寫的測試筆記,內容都夠長夠獨特,沒有踩到過**;這次是實際訂閱一個「description 天生很短」的真實來源才第一次暴露出來,再次印證「用真實資料測試比自己編的測試資料更容易發現邊界案例」這個之前已經在 RSS ingestion 那輪學到的教訓。**修法**:`rss_loader.py` 新增 `_MIN_CONTENT_LENGTH = 20`,`_entry_to_document()` 抽出來的內容如果比這個短,就退回用文章標題當內容——標題天生逐篇不同,不會互撞,同時也不用去改共用的 `replace_existing_document()` dedupe 邏輯(那段邏輯服務所有 ingestion 來源,是共用機制,改了影響面太廣,問題其實出在「餵給它的內容太廉價/太短」這個上游,修上游比較安全)。**已經清掉損毀的舊資料(單獨存活的那篇 HN 文章)、重新 `feeds sync` 一次,確認 10 篇 HN 文章這次全部正確分開存進去了**。**這個修法的已知限制**:HN 這類「RSS 沒有真正內容,只有標題+連結」的來源,存進知識庫的筆記內容永遠只有標題本身,不會有摘要或全文——這是 HN RSS 設計本身的限制,不是這個修法能解決的,`search`/`ask` 對這類筆記的語意搜尋品質會比有完整內容的筆記差(可搜尋的文字只有標題那幾個字)。

- **第七輪:翻譯功能的兩個設計問題都問過使用者,不是自己假設**:「要翻現有的還是也要自動翻以後新增的」跟「翻譯要取代原文還是另存」這兩個都是有明顯不同後果的分岔(前者影響 API 成本跟行為範圍,後者直接影響既有 embedding/search 品質會不會被動到),先問過再做,使用者選「都自動翻」+「另存,原文不動」。**這是使用者確認過的設計,不是我自己拍板的**,以後如果要改行為要重新確認。
- **第七輪:自動翻譯(`ingest_document()` 內)跟主動翻譯(`translate` 指令)的錯誤處理刻意不一樣**:自動翻譯失敗要「靜默跳過,不擋 ingestion」——因為 `add`/`add-feed`/`feeds` 這些指令長期以來的不變量是「不需要 Anthropic API key 也能動」,如果自動翻譯失敗就讓整個 ingestion 掛掉,等於把翻譯變成新的隱性必要條件,破壞了這個不變量,使用者甚至可能沒發現自己的筆記加不進去是因為翻譯失敗。`translate` 指令則相反,使用者是「明確要求翻譯」,失敗理應清楚回報,而且遇到認證失敗這種對整批文件都會重複發生的錯誤,直接停止比一篇篇跑完再列出 N 個一樣的錯誤訊息更合理。兩條路徑用同一個 `TranslationProvider`,差別只在呼叫端怎麼處理例外。
- **第七輪:`translated_content` 用真的 `ALTER TABLE` migration,不是要求砍掉資料庫重建**:這個專案先前加欄位(`tags`)、加資料表(`feeds`)都沒做過真的 migration,遇到舊資料庫沒有新欄位時的做法是「反正是空的測試資料庫,砍掉重建」,那次的決策筆記裡也明講「如果使用者已經囤了真實筆記,刪重建就會把知識庫清空」是還沒解決的風險。這次使用者已經有 40 篇真實資料(訂閱的三個 RSS 來源),砍掉重建不是選項,所以寫了 `_ensure_translated_content_column()`:每次連線用 `PRAGMA table_info` 檢查欄位存不存在,不存在才補一次 `ALTER TABLE ADD COLUMN`。已經拿真實的 `data/second_brain.db`(舊 schema)實測過,`list` 指令跑起來沒有任何錯誤,40 篇資料都還在。**這是這個專案第一次做真的 schema migration,之後如果還要加欄位,照這個模式做就好**,不用再讓使用者選擇「刪掉重來」。
- **第七輪:兩次遇到 Streamlit 長時間執行的 process 快取住舊版模組,`ImportError: cannot import name X`,不是真的程式碼 bug**:這輪對 `config.py` 加 `DISPLAY_TIMEZONE`、對 `storage/__init__.py` 加 `get_document` 之後,瀏覽器裡看到的 Streamlit 頁面各噴了一次 `ImportError`——實際檢查過原始檔案,兩次改動都確實寫進磁碟上的 `.py` 檔案了,問題出在**這個 Streamlit process 是長時間執行、沒有重啟過的舊進程**(從更早的對話輪次就一直開著),Python 的 `sys.modules` 快取住了它第一次 import 當下的 `second_brain.config`/`second_brain.storage` 模組物件,Streamlit 的檔案監看/自動重跑機制會重新執行 `web.py` 的頂層程式碼,但**不會**強制重新 import 已經在 `sys.modules` 裡的套件模組,所以新加的名稱在那個舊 process 裡永遠找不到。**修法**:直接用 `Stop-Process` 砍掉舊 process,再用 `preview_start` 重開一個全新的,全新 process 的 `sys.modules` 是乾淨的,重新 import 就會拿到磁碟上最新的程式碼。**教訓,以後遇到類似情況可以參考**:如果改了 `.py` 檔案、確認過磁碟內容是對的,但瀏覽器裡的 Streamlit 還是報「找不到某個剛加的名稱」的 `ImportError`,不用懷疑檔案寫壞了,先假設是長時間執行的 process 快取住舊模組,直接重啟 process 通常就解決,不用花時間除錯「為什麼檔案明明是對的卻導不進去」。

## 已知的粗糙邊界(還沒處理,不算 bug,是刻意先跳過)

- `add` 的 dedupe 現在是「路徑相同」或「內容完全相同」任一命中就算同一份筆記。**路徑跟內容同時變的情況還是抓不到**(見上面決策說明),舊紀錄會變孤兒,要靠 `remove`/`clear` 手動清。
- `list` 沒有分頁,文件一多會洗版(目前用不到分頁,先不做)。
- `search`/`ask` 的 `top_k` 沒有上限檢查。
- **自動標籤只是「殼」,不是真的智慧分類**:目前是純本機詞頻統計(jieba 斷詞 + 出現次數排序),沒有語意理解。標籤品質對「內容夠長、主題明確」的筆記還可以,短筆記或用詞分散的筆記標籤會不準。使用者當初要求就是先求有殼,之後可以換成 LLM 分類(`TaggingProvider` 介面已經是抽換式設計,換實作不用動 `add` 流程)。
- `search`/`ask` 目前**不會**顯示文件的標籤,只有 `add`/`add-feed` 完成訊息跟 `list` 會顯示。
- 沒有針對標籤的操作(例如按標籤過濾 `list`/`search`),純粹先把資料存起來。
- `add-feed` 的 HTML 去標籤是陽春正則,不是完整 HTML parser(見上面決策說明);`<script>`/`<style>` 內容不會被排除。
- **`feeds sync` 是依序同步,不是平行處理**:訂閱來源一多、其中有網路慢的來源,`sync_all_feed_subscriptions()` 會依序等每個來源做完才處理下一個,沒有做並行抓取。對個人用途的訂閱數量(大概幾個到十幾個)應該還好,但沒有實測過同步大量來源時的耗時。
- **`feeds add`/`feeds sync` 沒有記錄「這次同步抓到幾篇新文章、幾篇失敗」的歷史**,只有 `last_synced_at` 一個時間戳跟(第十三輪加的)`data/sync.log` 彙總結果,沒有逐次的詳細紀錄,沒辦法回頭查「上次同步到底發生了什麼細節」。
- **Streamlit 網頁介面沒有 `clear`**(刻意的,見上面決策說明),要清空知識庫還是得用 CLI。
- **第十五輪:網頁介面「瀏覽」分頁切換分頁籤(例如切去「搜尋」)再切回「瀏覽」,文件列表的頁碼會重置回第一頁**,即使分類篩選沒變。細節、猜測原因見上面「網頁介面細節打磨」決策說明,這輪沒有深入查證 Streamlit 內部機制,判斷這不影響核心功能、也不在使用者這輪要求的範圍內,先不修。
- **第十五輪:批次刪除/批次設定分類的「預覽符合的文件」清單不會自動更新這個既有限制(第五輪就記錄過,見下面)沒有變**,這輪打磨網頁介面時有特地問過使用者要做哪幾項,這項沒有被選進來,維持原樣。
- **`streamlit` 是獨立的 optional dependency**(`pyproject.toml` 的 `[project.optional-dependencies].ui`),裝 `.[dev]` 不會自動裝到,要另外 `pip install -e ".[ui]"` 或 `.[dev,ui]`。
- **第十輪:分類是自由文字,不是寫死的 enum**,CLI/網頁介面都不會擋你打錯字或打出跟現有分類不一致的新分類(例如手滑打成「財金」而不是「財經」),`list_categories()` 只會忠實反映資料庫裡實際出現過的值,打錯字不會被攔下來,要靠人工發現、用 `set-category` 修正。
- **第十輪:`feeds set-category` 不會回頭改已經存在的文件**,只影響之後同步進來的新文章;舊文件要嘛靠下次同步時該文章剛好還在 feed 回傳範圍內順便更新,要嘛要另外用 `second-brain set-category` 手動批次改——這是刻意的設計(理由見上面「文件分類」決策說明),但代表**改一個訂閱來源的分類,不會馬上讓瀏覽頁面上這個來源的舊文章分類跟著變**,如果沒讀過決策說明容易誤以為是 bug。
- **第十輪:RSS 來源分類回填只能靠「文章還在 feed 目前回傳範圍內」這個條件**,滾出範圍的舊文章不會在 resync 時自動被蓋上分類,需要額外用 `set-category --source <網域>` 手動掃。目前知識庫已經全部手動掃過一輪、沒有遺漏,但**之後如果又有新的一次性 `add-feed`(不是 `feeds add` 訂閱)加進來的文章**,一樣不會有分類,需要意識到這件事、記得手動補。
- **第十輪:網頁介面「批次設定分類」的分類輸入是純文字框,沒有下拉選單提示既有分類**(瀏覽頁面的篩選跟搜尋/問答分頁的限定分類都是下拉選單,只有這個批次設定的地方是純文字輸入),想套用既有分類名稱要自己記得打一樣的字,容易手滑打錯(這輪的分類回填在 CLI 上就真的手滑打錯過一次,細節見上面決策說明)。之後如果要改進,可以考慮換成下拉選單 + 「新增分類」的組合輸入。
- **第十二輪:`Document` 沒有存「這篇文章是從哪個訂閱來源進來的」這個關聯**,只有分類(`category`)是存在文件上的固定值,分類本身不等於來源記錄(例如同一個分類底下可以有好幾個不同來源)。這代表「只刪掉某一個特定訂閱來源拉進來的文章」這種操作,沒辦法直接查詢,只能用 `source_path` 網域比對(適用大部分來源)或內容特徵(適用像 Hacker News 這種連到外部網站、網域五花八門的來源,細節見上面決策說明的「`content == title`」訊號)去反推,是手動的偵探工作,不是一個指令就能做到。如果之後這種「整批移除單一訂閱來源的文章」的需求變得常見,可以考慮加一個 `documents.source_feed_url` 欄位在 ingest 時記錄,現在先不做(YAGNI,目前只遇到過一次這種需求)。
- **第五輪:網頁介面批次刪除的「預覽符合的文件」結果存在 `st.session_state`,切換分頁或做其他操作不會自動清掉**,如果使用者預覽完之後跑去別的分頁刪了某篇筆記、又切回來直接勾確認刪除,實際刪除時是照「當初預覽的那份清單」執行(`remove_documents()` 用的是預覽當下記下的 id 列表),已經被刪掉的 id 會被 `remove_documents()` 靜默略過(`sqlite_store.get_document(id)` 找不到就跳過,不會報錯),不會導致誤刪別的東西,但如果知識庫在預覽之後有新增符合條件的文件,不會自動出現在待刪清單裡,要重新按一次「預覽符合的文件」才會抓到最新結果。
- **第四輪:`remove-batch` 的 `--after`/`--before` 只支援 `YYYY-MM-DD` 絕對日期,沒有「N 天前」這種相對日期的簡寫**,要刪「30 天前的文章」得自己算出日期字串。之後如果常用可以加 `--older-than-days N` 這種語法糖,MVP 先不做。
- **第四輪:`remove-batch --keyword` 對這次修正之前就存在的舊資料,標籤比對不到中文**(`tags` 欄位還是舊的 `ensure_ascii=True` 跳脫格式),標題/內容欄位不受影響。見上面「決策」段落的詳細說明,要嘛重新 `add`/`feeds sync`,要嘛之後寫一次性 migration script。
- **第七輪:`translate` 指令/自動翻譯沒有記錄「翻譯失敗的原因」**,只有 `translate` 指令當下印出來的訊息,沒有存進資料庫或 log,失敗的文件下次執行 `translate` 只是「再試一次」,不會知道上次為什麼失敗(除非剛好還記得當時的輸出)。
- **第七輪:網頁介面的「查看繁體中文翻譯」展開區塊,每次頁面渲染都會對每一篇有翻譯的文件多查一次資料庫**(`get_document(document.id)` 在迴圈裡呼叫,不管使用者有沒有真的展開那個 expander)。對個人用途的文件量(幾十到幾百篇)效能上不是問題,文件量大幅成長的話可以考慮改成真的懶載入(例如用 `st.session_state` 快取或按需查詢)。
- **第七輪:翻譯的內容長度沒有特別處理**,`max_tokens=4096` 對一般新聞文章長度應該夠,但沒有測過特別長的文章(例如 Ars Technica 的深度報導)會不會被截斷。
- **第六輪:Hacker News 這類「description 只有佔位文字」的 RSS 來源,存進知識庫的筆記內容永遠只有標題**,沒有摘要或全文,`search`/`ask` 對這些筆記的語意搜尋品質會比有完整內容的來源(例如 BBC News、The Verge)差,可搜尋的文字量很少。這是 HN RSS 設計本身的限制,不是 bug,已知先接受。
- **第九輪:`SEMANTIC_WEIGHT`/`KEYWORD_WEIGHT` 是寫死在 `config.py` 的常數(各 0.5),沒有讓使用者依查詢調整**,例如明確知道自己在找精確詞彙時沒辦法臨時把關鍵字權重調高。CLI/網頁介面也沒有開關可以「只用語意搜尋」或「只用關鍵字搜尋」——之前的架構(純語意)反而還留在 git 歷史裡,如果之後真的需要可以回頭參考,但目前沒有計畫要做這個開關,先觀察加權平均的效果好不好再說。
- **第九輪:BM25 語料是「這次查詢當下」即時從 SQLite 撈全部 chunk 現算,沒有快取**:每次 `search()`/`ask()` 都會重新建一次 `BM25Okapi`(掃全部 chunk、重算 idf)。對目前的資料量(一兩百個 chunk)實測起來很快,沒有感覺得到的延遲,但如果知識庫成長到幾千篇文章、上萬個 chunk,這裡會是第一個變慢的地方,到時候可以考慮加快取(例如以「chunk 總數有沒有變」當快取失效條件)。
- **第九輪:hybrid search 沒有針對「BM25 語料極小(corpus 只有 1~2 篇文件)時 idf 可能算出 0 或負值退化」做特別處理**——寫測試時就踩到這個 BM25 演算法本身的數學特性(見上面決策說明),對知識庫目前的規模(幾十篇)不是問題,但如果使用者的知識庫長期只有極少數幾篇文件,關鍵字排序的效果可能不如預期,語意分數會變成主要的排序依據(這其實也是合理的降級行為,不算 bug)。

## 接下來可能的方向(還沒決定)

CLAUDE.md「未來規劃方向」列的:
- 更多 ingestion 來源的其餘部分(瀏覽器書籤、Readwise/Instapaper、Obsidian/Notion 匯出——RSS 這一個已經做完)
- 自動化處理的其餘部分(關聯筆記推薦、去重複——自動打標籤這一小塊已經做完)
- Web UI 或 Raycast/Alfred 整合(**Streamlit 網頁介面已經做完基本版,而且使用者本人已經用過**,如果要往「多人使用」或更精緻互動的方向,可能要考慮換成正式 web app)

Hybrid search(關鍵字 + 語意搜尋並用)**第九輪已經做完**,文件分類**第十輪已經做完**,細節都在上面「已經做完的東西」跟「中途做的決策」兩節。

使用者說這些方向都想做,已經照優先順序做完 `remove` → 「更聰明的 dedupe」+「清空知識庫指令」→ 「自動打標籤(殼)」→ 「RSS ingestion」→ 「Streamlit 網頁介面」→「一鍵啟動」→ 「feed 訂閱清單(CLI)」→ 「feed 訂閱清單補進網頁介面」→ 「search/ask 顯示時間 + remove-batch 批次刪除(CLI)」→ 「remove-batch 補進網頁介面」(第五輪)→ 「訂閱真實 RSS 來源」(第六輪)→ 「翻譯成繁體中文 + 時間戳記改 UTC+8」(第七輪)→ 「hybrid search」(第九輪)→ 「訂閱財經 RSS 來源 + 文件分類」(第十輪)→ 「訂閱中文科技 RSS 來源」(第十一輪)→ 「退訂英文科技來源、改訂中文新聞來源」(第十二輪)→ 「`feeds sync` 排程自動化」(第十三輪)→ 「網頁介面細節打磨」(第十五輪)。

## 下一輪要做的事:還沒決定,先問使用者

跟第八輪不一樣,**這次沒有已經拍板的下一步**——文件分類做完之後還沒
跟使用者討論過接下來要做什麼,下一輪一開始應該先問,不要自己選一個候選就
直接動工。

候選(不代表優先順序):
- 更多 ingestion 來源(瀏覽器書籤、Readwise/Instapaper、Obsidian/Notion 匯出)。
- 關聯筆記推薦、去重複。
- 網頁介面細節打磨的其餘部分(第十五輪已做完新增後自動跳轉/文件列表分頁/同步全部失敗分組,還沒做的是批次刪除/批次設定分類的預覽清單不會自動更新)。
- **舊資料的 `tags` 欄位 migration**:把這次修正之前存進去的 ASCII 跳脫格式標籤轉成 `ensure_ascii=False` 格式,讓 `remove-batch --keyword` 對舊文件的標籤比對也能生效。不急,先重新 `add`/`feeds sync` 一次也能解決,只是比較手動。
- **分類下拉選單/自動建議**:見上面「已知的粗糙邊界」,網頁介面批次設定分類的地方目前是純文字輸入,容易手滑打錯字;可以考慮換成下拉選單 + 新增選項的組合。

## 交接檢查清單(接手時建議做的事)

1. `git log --oneline` 確認目前在哪個 commit,`git status --short --branch` 確認有沒有沒 commit 的東西、有沒有 `ahead`/`behind` origin。**這次交接時,第十五輪(網頁介面細節打磨)已經 commit 進 `e8e1959` 並 push**(第十三輪/第十輪/第九輪也分別 commit 進 `f846938`/`f0ef6d6`/`f44d231`)——工作目錄應該是乾淨的,`git status --short --branch` 應該只顯示 `## master...origin/master`,沒有多餘的修改。第十一輪、第十二輪、第十四輪都沒有改任何程式碼。`.claude/launch.json` 有改過(加 `autoPort: true`),但這個檔案本來就在 `.gitignore` 裡,不會出現在 `git status`,不用理它。
2. **這台機器上有一個 Windows 排程工作 `SecondBrainFeedsSync`(第十三輪建的),每天早上 8:00 自動跑 `second-brain feeds sync --log-file data/sync.log`**——這是機器層級設定,不在 git 裡,換一台機器要重新用 `Register-ScheduledTask` 建立(指令見上面「`feeds sync` 排程自動化」決策說明)。想查排程有沒有正常執行,看 `data/sync.log`(每次同步一行,格式:時間戳 + 新增/更新總篇數 + 失敗來源數)或用 `Get-ScheduledTask -TaskName SecondBrainFeedsSync | Get-ScheduledTaskInfo` 查 `LastTaskResult`(0 是成功)。
3. **知識庫裡現在有真實資料,訂閱來源這輪(第十二輪)大換血過**:科技類是 iThome、TechNews 科技新報、DIGITIMES(第十一輪訂的,原本的 The Verge/Hacker News/Simon Willison's Weblog 這三個英文來源已經在第十二輪退訂並刪除所有文章);財經類是經濟日報、自由時報財經版、Yahoo股市(第十輪);新聞類是中央社(國際)、BBC中文網、ETtoday(第十二輪)。`feeds list` 應該看到這 9 個訂閱、`list` 應該看到 100 多篇文件(排程每天都會跑,篇數會持續變動),全部都已經分類完畢(科技/財經/新聞三類,沒有未分類的)。手動測試/除錯時要小心別誤刪這些真實訂閱或文章(用 `remove-batch`/`clear`/`set-category` 之前務必先 `list`/`feeds list` 確認)。
4. **這台機器沒有設 `ANTHROPIC_API_KEY`**:`ask`/`translate` 都還沒被使用者實際跑過,`second-brain translate` 目前只驗證過「沒 key 時清楚報錯退出」這條路徑。**翻譯品質不在待辦清單裡追蹤了(使用者第十四輪要求拿掉)**,如果之後真的設了 key、剛好有人想確認翻譯品質,再另外評估,不用主動提醒。
5. `./.venv/Scripts/python.exe -m pytest -q` 應該要 109 個全過(第十三輪加了 3 個新測試,106 → 109)、~6 秒內跑完
6. 如果要手動測 `add`/`search`,第一次跑會下載 ~90MB 的 embedding 模型,需要網路;jieba 第一次執行也會在本機建 prefix dict 快取(不用連網,純本機運算,第一次會慢個零點幾秒)
7. `pyproject.toml` 這輪陸續加了 `jieba>=0.42`、`feedparser>=6.0`、`streamlit>=1.38`(在 `[project.optional-dependencies].ui`,不在預設 `dev` 裡)、`rank_bm25>=0.2`(第九輪,在預設 `dependencies` 裡,不是 optional),**第十三輪沒有再加新依賴**(排程用 Windows 內建的 Task Scheduler,不需要額外套件),如果是全新環境要記得重新 `pip install -e ".[dev]"`(CLI/測試)跟 `pip install -e ".[ui]"`(網頁介面)
8. 如果要手動測 `add-feed`/`feeds add` 又不想真的連網,`feedparser.parse()` 吃本機檔案路徑或原始 XML 字串都可以;歷輪已經用多個真實網址(BBC中文網、經濟日報、自由時報財經版、Yahoo股市、iThome、TechNews 科技新報、DIGITIMES、中央社、ETtoday,以及已經退訂的 The Verge/Hacker News/Simon Willison's Weblog)驗證過連網路徑沒問題
9. 開始功能表有一個「Second Brain」捷徑指向 [run_web.bat](run_web.bat)(這輪在使用者機器上建的,不在 git 裡,取代了原本刪掉的桌面捷徑);如果要驗證雙擊啟動的行為,記得先刪掉 `%USERPROFILE%\.streamlit\credentials.toml` 模擬全新機器,不然「歡迎訊息卡住」那個 bug 修好了沒有根本測不出來
10. 如果要用瀏覽器自動化測 Streamlit 網頁介面,見「中途做的決策」裡記錄的多筆工具限制筆記(text_input 優先用 `computer` 的 triple_click+type,checkbox 要用 JS 點 `label` 元素,`expander` 沒設 `expanded=True` 會每次 rerun 自動收合,長時間執行的 process 會快取住舊模組、遇到剛加的名稱 `ImportError` 先重啟 process)。**第十輪新增一筆**:如果 `.claude/launch.json` 設定的 `second-brain-web` 這個 server name 剛好被另一個對話 session 佔用同一個 port(8501),`preview_start` 會報衝突——這個設定檔已經加了 `"autoPort": true`,harness 會自動換一個空 port,不用特地處理,只是要注意 `preview_start` 回傳的實際 port 號會變。**第十五輪新增一筆**:`st.segmented_control()`(這輪拿來當導覽用)渲染出來是 `role="radio"` 元素,`computer` 的 `left_click` 用 `ref` 點擊有時候不會真的觸發選取(點了但畫面內容沒變、`aria-checked` 也沒變),改用 `javascript_tool` 直接對元素呼叫 `.click()`(用 `textContent` 找到正確的那個 radio 再呼叫)比較可靠,遇到同樣情況可以直接跳過重試 `computer` 點擊、改用 JS 點法省時間。
