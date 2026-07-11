"""Streamlit 本機網頁介面(`streamlit run second_brain/interface/web.py`)。

跟 cli.py 一樣是 interface 層的一種實作,底層共用 processing/storage/retrieval
各層,不重複寫核心邏輯——加東西一律透過 ingestion.pipeline.ingest_document()。
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import anthropic
import streamlit as st

from second_brain.ingestion.loader import load_document
from second_brain.ingestion.pipeline import ingest_document
from second_brain.ingestion.rss_loader import load_feed
from second_brain.processing.embedding import get_embedding_provider
from second_brain.processing.tagging import get_tagging_provider
from second_brain.retrieval.ask import ask as run_ask
from second_brain.retrieval.search import search as run_search
from second_brain.storage import list_documents, remove_document

st.set_page_config(page_title="Second Brain", page_icon="📚", layout="wide")


@st.cache_resource
def _warm_up_providers() -> None:
    """第一次載入頁面時就把 embedding/tagging 模型準備好,避免每次互動都重新載入一次。"""
    get_embedding_provider()
    get_tagging_provider()


_warm_up_providers()

st.title("📚 Second Brain")

tab_browse, tab_search, tab_ask, tab_add = st.tabs(["瀏覽", "搜尋", "問答", "新增筆記"])

with tab_browse:
    documents = list_documents()

    if not documents:
        st.info("知識庫是空的,先到「新增筆記」加一些內容吧。")
    else:
        for document in documents:
            with st.container(border=True):
                col_info, col_action = st.columns([6, 1])
                with col_info:
                    st.markdown(
                        f"**{document.title}**"
                        f"  ·  {document.chunk_count} 個片段"
                        f"  ·  {document.created_at:%Y-%m-%d %H:%M}"
                    )
                    if document.tags:
                        st.caption("🏷️ " + "、".join(document.tags))
                    st.caption(document.source_path)
                with col_action:
                    if st.button("刪除", key=f"remove-{document.id}"):
                        remove_document(document.source_path)
                        st.rerun()

with tab_search:
    query = st.text_input("搜尋知識庫", placeholder="想搜尋的內容")
    top_k = st.slider("回傳筆數", min_value=1, max_value=20, value=5, key="search-top-k")

    if query:
        results = run_search(query, top_k=top_k)

        if not results:
            st.info("沒有找到相關內容。")
        else:
            for rank, result in enumerate(results, start=1):
                with st.container(border=True):
                    st.markdown(f"**[{rank}] {result.document.title}**  (score={result.score:.3f})")
                    st.caption(result.document.source_path)
                    st.write(result.chunk.content)

with tab_ask:
    question = st.text_input("問知識庫一個問題", placeholder="想問的問題")
    ask_top_k = st.slider("檢索筆數", min_value=1, max_value=20, value=5, key="ask-top-k")

    if question:
        try:
            answer = run_ask(question, top_k=ask_top_k)
        except (anthropic.AuthenticationError, TypeError) as error:
            if isinstance(error, TypeError) and "authentication" not in str(error).lower():
                raise
            st.error("找不到有效的 Anthropic API key,請設定環境變數 ANTHROPIC_API_KEY 後再試一次。")
        else:
            st.write(answer)

with tab_add:
    st.subheader("上傳檔案")
    uploaded_file = st.file_uploader("選擇 markdown/text 檔案", type=["md", "markdown", "txt"])

    if uploaded_file is not None and st.button("加入這個檔案"):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / uploaded_file.name
            tmp_path.write_bytes(uploaded_file.getvalue())
            document = load_document(tmp_path)
            result = ingest_document(document)

        if result is None:
            st.warning("檔案內容是空的,沒有東西可以加入。")
        else:
            st.success(f"已處理「{result.document.title}」— {result.chunk_count} 個片段")
            if result.document.tags:
                st.caption("🏷️ " + "、".join(result.document.tags))

    st.divider()

    st.subheader("訂閱 RSS/Atom")
    feed_url = st.text_input("Feed 網址")
    limit = st.number_input("最多抓幾篇", min_value=1, max_value=50, value=10)

    if feed_url and st.button("抓取這個訂閱來源"):
        try:
            feed_documents = load_feed(feed_url, limit=int(limit))
        except Exception as error:
            st.error(f"抓取或解析這個訂閱來源失敗:{error}")
        else:
            if not feed_documents:
                st.info("這個訂閱來源目前沒有文章可以加入。")
            else:
                added = 0
                skipped = 0
                for feed_document in feed_documents:
                    feed_result = ingest_document(feed_document)
                    if feed_result is None:
                        skipped += 1
                        continue
                    added += 1
                    st.success(f"已處理「{feed_result.document.title}」— {feed_result.chunk_count} 個片段")
                st.info(f"完成:{added} 篇已處理,{skipped} 篇內容是空的被略過。")
