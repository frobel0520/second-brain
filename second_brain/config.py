"""集中管理路徑與設定,預設全部落在本機 data/ 目錄下。"""

from __future__ import annotations

from datetime import timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SQLITE_PATH = DATA_DIR / "second_brain.db"
CHROMA_DIR = DATA_DIR / "chroma"

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

MAX_TAGS = 5

# hybrid search:語意分數(cosine 相似度)跟 BM25 關鍵字分數各自正規化到 0~1
# 後,依這個權重加權平均。兩者預設同權重,語意搜尋顧概念相關、關鍵字搜尋顧
# 精確詞彙(人名、版本號、專有名詞),沒有理由預設誰比較重要。
SEMANTIC_WEIGHT = 0.5
KEYWORD_WEIGHT = 0.5

RSS_DEFAULT_LIMIT = 10

ANSWER_MODEL = "claude-opus-4-8"

# 資料庫裡一律存 UTC(datetime.now(timezone.utc)),只有顯示給人看的時候才轉成
# 這個時區,避免時區換算邏輯散落在儲存層。
DISPLAY_TIMEZONE = timezone(timedelta(hours=8))


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
