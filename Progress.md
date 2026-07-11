# Progress

這份文件是給「接手這個專案的下一個 Claude 對話」看的交接筆記,不是使用手冊。
使用方式看 [README.md](README.md),規劃看 [CLAUDE.md](CLAUDE.md)。這份只記錄
「現在做到哪、為什麼這樣做、接下來大概要做什麼」,每次做完一個階段性任務就更新。

最後更新:2026-07-11

## 現況一句話

CLAUDE.md 的 MVP(`add` / `search` / `ask`)已經做完,另外多做了 `list` 指令、
`add` 的 upsert(重複加入同一個檔案會取代舊版本,不會重複塞)、跟 `remove` 指令
(從知識庫刪除指定檔案的紀錄)。26 個測試全過。git 有四個 commit
(`a53f756` skeleton+add/search、`a02095a` ask、`d72a479` list+upsert、
本輪新增的 remove commit)。

## 環境

- Windows,Python 3.14.4,`.venv/` 在專案根目錄(已裝好所有依賴,含 torch/sentence-transformers/chromadb/anthropic)
- 沒有 git remote,只有本機 repo
- 常用指令:
  ```bash
  ./.venv/Scripts/python.exe -m pytest -q                    # 跑測試,~2 秒,不用真的 embedding 模型
  ./.venv/Scripts/python.exe -m second_brain add <file>       # 手動驗證要真的跑一次
  ```
- `ANTHROPIC_API_KEY` 這台機器上沒設,`ask` 指令沒辦法真的打 API,只驗證過「沒設 key 時的錯誤處理」

## 已經做完的東西

五個 CLI 指令全部能動,架構細節看 [README.md](README.md#架構):

1. `second-brain add <file>` — 讀 md/txt → 切塊 → embedding(本機 sentence-transformers)→ 存 SQLite + ChromaDB。**同一個 `source_path` 再 add 一次會先刪舊版本再存新的**(`storage/store.py:replace_existing_document`),不是 append。
2. `second-brain search "<query>" [--top-k K]` — query 轉 embedding → ChromaDB cosine 相似度搜尋 → 印出來源+分數。
3. `second-brain ask "<query>" [--top-k K]` — 在 search 結果上組 context,呼叫 Anthropic API(`claude-opus-4-8`,寫死在 `config.ANSWER_MODEL`)做 RAG 問答。
4. `second-brain list` — 列出知識庫裡的文件(標題、片段數、來源路徑)。
5. `second-brain remove <file>` — 從知識庫刪除指定檔案的紀錄(sqlite + chroma),不動硬碟上的檔案本身,今天(這輪對話)剛加的。跟 `replace_existing_document` 共用同一個底層刪除邏輯(`storage/store.py:_delete_by_source_path`),差別只在語意跟回傳訊息。`file_path` 參數**沒有** `exists=True`,因為要能刪除已經從硬碟上消失的檔案的舊紀錄。

## 中途做的非顯而易見的決策(為什麼這樣寫)

- **Windows 主控台 UTF-8 fix**([cli.py](second_brain/interface/cli.py) 開頭):手動測試時發現中文全部變亂碼,原因是 Windows 預設 stdout 編碼不是 UTF-8。已經在 CLI 進入點強制 `sys.stdout.reconfigure(encoding="utf-8")`。**這是一個真的修好的 bug,不是預防性程式碼。**
- **typer 單一指令會自動摺疊成不需要子指令名稱**:一開始只有 `add` 一個指令時,`second-brain add file.md` 會報錯要求直接 `second-brain file.md`。加了一個空的 `@app.callback()` 強制保留子指令形式,現在有 4 個指令了其實已經不需要這個 workaround,但留著無害,不用特地拿掉。
- **`sqlite_store` / `vector_store` 的 path 參數用「執行時才解析」而不是 function default 綁定**:一開始 `db_path: Path = SQLITE_PATH` 這種寫法在測試裡 monkeypatch 沒用(default 在 import 當下就綁死了),改成 `db_path: Path | None = None` 內部再 `db_path or SQLITE_PATH`,測試才能用 `monkeypatch.setattr(sqlite_store, "SQLITE_PATH", tmp_path/...)` 正確隔離。`vector_store.CHROMA_DIR` 本來就是函式內讀取,沒這問題。
- **ChromaDB collection 明確設 `hnsw:space: cosine`**:預設 space 不確定,為了讓 `score = 1 - distance` 這個算法有意義(cosine similarity),在 `_get_collection()` 建立時指定。
- **測試不下載真的 embedding 模型**:所有牽涉 embedding 的測試都用一個 `_FakeEmbeddingProvider`(回傳固定向量,依內容關鍵字區分),monkeypatch `processing.embedding._default_provider` 這個模組級 singleton。`ask` 的測試同樣 mock 掉 `anthropic.Anthropic()`,不會真的打 API。這是刻意的,讓 `pytest` 跑起來是秒級、不用網路、不用 API key。
- **`ask` 指令的認證錯誤處理有點 hacky**([cli.py](second_brain/interface/cli.py) 的 `ask()`):Anthropic SDK 在完全沒設任何憑證時丟的是 `TypeError`(不是 `AuthenticationError`,那個是 401 才會丟),訊息裡有 "authentication" 字樣。目前用字串比對 `"authentication" not in str(error).lower()` 來判斷要不要重新拋出。如果以後 SDK 改了錯誤訊息文字,這裡會失效——可以考慮但目前沒做:改成先檢查 `os.environ.get("ANTHROPIC_API_KEY")` 是否存在,或用 `ant auth status` 之類的方式判斷。

## 已知的粗糙邊界(還沒處理,不算 bug,是刻意先跳過)

- `add` 的 dedupe 是用**完全比對 resolved absolute path** 判斷是不是「同一個檔案」。檔案改名或搬家會被當成新文件,不會取代舊版本,舊版本也不會自動清掉。
- 沒有清空整個知識庫的指令(`remove` 一次只能刪一個檔案),要全清還是只能手動砍 `data/` 目錄。
- `list` 沒有分頁,文件一多會洗版(目前用不到分頁,先不做)。
- `search`/`ask` 的 `top_k` 沒有上限檢查。

## 接下來可能的方向(還沒決定,是這輪對話結尾討論到的選項)

CLAUDE.md「未來規劃方向」列的:
- 更多 ingestion 來源(瀏覽器書籤、Readwise/Instapaper、Obsidian/Notion 匯出、RSS)
- Hybrid search(關鍵字 + 語意搜尋並用)
- 自動化處理(自動打標籤、關聯筆記推薦、去重複)
- Web UI 或 Raycast/Alfred 整合

上面「已知的粗糙邊界」裡列的東西(更聰明的 dedupe、清空知識庫指令)也是候選。使用者說這些方向都想做,這輪先挑了 `remove` 指令做(範圍最小、不用連網/API key)。**下一個對話開始時,建議問使用者接下來要做哪個**,不要自己選。

## 交接檢查清單(接手時建議做的事)

1. `git log --oneline` 確認目前在哪個 commit,`git status` 確認有沒有沒 commit 的東西
2. `./.venv/Scripts/python.exe -m pytest -q` 應該要 26 個全過、~3 秒內跑完
3. 如果要手動測 `add`/`search`,第一次跑會下載 ~90MB 的 embedding 模型,需要網路
4. 如果要手動測 `ask`,需要使用者提供 `ANTHROPIC_API_KEY`
