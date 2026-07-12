"""Streamlit 本機網頁介面(`streamlit run second_brain/interface/web.py`)。

跟 cli.py 一樣是 interface 層的一種實作,底層共用 processing/storage/retrieval
各層,不重複寫核心邏輯——加東西一律透過 ingestion.pipeline.ingest_document()。
"""

from __future__ import annotations

import tempfile
from datetime import datetime, time, timezone
from pathlib import Path

import anthropic
import streamlit as st

from second_brain.config import DISPLAY_TIMEZONE
from second_brain.ingestion.loader import load_document
from second_brain.ingestion.pipeline import ingest_document, sync_all_feed_subscriptions, sync_feed_subscription
from second_brain.ingestion.rss_loader import get_feed_title, load_feed
from second_brain.processing.embedding import get_embedding_provider
from second_brain.processing.tagging import get_tagging_provider
from second_brain.retrieval.ask import ask as run_ask
from second_brain.retrieval.search import search as run_search
from second_brain.storage import (
    find_documents,
    get_document,
    list_categories,
    list_documents,
    list_feed_subscriptions,
    remove_document,
    remove_documents,
    set_document_categories,
    subscribe_feed,
    unsubscribe_feed,
    update_feed_category,
)

st.set_page_config(page_title="Second Brain", page_icon="📚", layout="wide")


@st.cache_resource
def _warm_up_providers() -> None:
    """第一次載入頁面時就把 embedding/tagging 模型準備好,避免每次互動都重新載入一次。"""
    get_embedding_provider()
    get_tagging_provider()


_warm_up_providers()

st.title("📚 Second Brain")

tab_browse, tab_search, tab_ask, tab_add, tab_feeds = st.tabs(
    ["瀏覽", "搜尋", "問答", "新增筆記", "訂閱管理"]
)

with tab_browse:
    if "batch_delete_message" in st.session_state:
        st.success(st.session_state.pop("batch_delete_message"))
    if "batch_category_message" in st.session_state:
        st.success(st.session_state.pop("batch_category_message"))

    existing_categories = list_categories()
    browse_category = st.selectbox(
        "分類篩選", options=["全部"] + existing_categories, key="browse-category-filter"
    )

    documents = (
        list_documents() if browse_category == "全部" else find_documents(category=browse_category)
    )

    if not documents:
        message = (
            "知識庫是空的,先到「新增筆記」加一些內容吧。"
            if browse_category == "全部"
            else f"沒有分類是「{browse_category}」的文件。"
        )
        st.info(message)
    else:
        for document in documents:
            with st.container(border=True):
                col_info, col_action = st.columns([6, 1])
                with col_info:
                    st.markdown(
                        f"**{document.title}**"
                        f"  ·  {document.chunk_count} 個片段"
                        f"  ·  {document.created_at.astimezone(DISPLAY_TIMEZONE):%Y-%m-%d %H:%M}"
                    )
                    if document.category:
                        st.caption(f"📁 {document.category}")
                    if document.tags:
                        st.caption("🏷️ " + "、".join(document.tags))
                    st.caption(document.source_path)
                    if document.has_translation:
                        with st.expander("🇹🇼 查看繁體中文翻譯"):
                            full_document = get_document(document.id)
                            if full_document is not None and full_document.translated_content:
                                st.write(full_document.translated_content)
                with col_action:
                    if st.button("刪除", key=f"remove-{document.id}"):
                        remove_document(document.source_path)
                        st.rerun()

    st.divider()

    st.subheader("批次刪除")
    st.caption(
        "依日期範圍、關鍵字、來源批次刪除,符合任一個條件就會列入(OR);"
        "日期範圍是例外,兩個一起給的話彼此是 AND,定義一段區間。至少要給一個條件。"
    )

    col_after, col_before = st.columns(2)
    with col_after:
        batch_after = st.date_input("加入時間之後(含)", value=None, key="batch-after")
    with col_before:
        batch_before = st.date_input("加入時間之前(含)", value=None, key="batch-before")

    batch_keyword = st.text_input("關鍵字(標題/內容/標籤)", key="batch-keyword")
    batch_source = st.text_input("來源路徑或網址包含", key="batch-source")

    if st.button("預覽符合的文件"):
        if not any([batch_after, batch_before, batch_keyword, batch_source]):
            st.warning("至少要給一個篩選條件。")
            st.session_state["batch_matches"] = []
        else:
            after_dt = (
                datetime.combine(batch_after, time.min).replace(tzinfo=timezone.utc)
                if batch_after
                else None
            )
            before_dt = (
                datetime.combine(batch_before, time(23, 59, 59, 999999)).replace(tzinfo=timezone.utc)
                if batch_before
                else None
            )
            st.session_state["batch_matches"] = find_documents(
                created_after=after_dt,
                created_before=before_dt,
                keyword=batch_keyword or None,
                source=batch_source or None,
            )

    batch_matches = st.session_state.get("batch_matches", [])

    if batch_matches:
        st.write(f"符合條件的文件共 {len(batch_matches)} 筆:")
        for match in batch_matches:
            created = match.created_at.astimezone(DISPLAY_TIMEZONE)
            st.write(f"- {created:%Y-%m-%d %H:%M}  {match.title}  ({match.source_path})")

        confirmed = st.checkbox(
            f"我確認要刪除這 {len(batch_matches)} 筆文件,這個動作無法復原。", key="batch-confirm"
        )
        if confirmed and st.button("刪除這些文件", type="primary"):
            removed_titles = remove_documents([match.id for match in batch_matches])
            st.session_state["batch_delete_message"] = f"已刪除 {len(removed_titles)} 筆文件。"
            st.session_state["batch_matches"] = []
            st.session_state["batch-confirm"] = False
            st.rerun()

    st.divider()

    st.subheader("批次設定分類")
    st.caption(
        "篩選邏輯跟上面批次刪除一樣(符合任一個條件就列入,日期範圍例外是 AND)。"
        "用在幫既有文件補分類,例如透過一次性訂閱加入、沒有訂閱紀錄可以依循的文章。"
    )

    col_cat_after, col_cat_before = st.columns(2)
    with col_cat_after:
        category_batch_after = st.date_input("加入時間之後(含)", value=None, key="category-batch-after")
    with col_cat_before:
        category_batch_before = st.date_input("加入時間之前(含)", value=None, key="category-batch-before")

    category_batch_keyword = st.text_input("關鍵字(標題/內容/標籤)", key="category-batch-keyword")
    category_batch_source = st.text_input("來源路徑或網址包含", key="category-batch-source")
    new_category_value = st.text_input("要設定的分類", key="category-batch-value")

    if st.button("預覽符合的文件", key="category-batch-preview"):
        if not any(
            [category_batch_after, category_batch_before, category_batch_keyword, category_batch_source]
        ):
            st.warning("至少要給一個篩選條件。")
            st.session_state["category_batch_matches"] = []
        else:
            cat_after_dt = (
                datetime.combine(category_batch_after, time.min).replace(tzinfo=timezone.utc)
                if category_batch_after
                else None
            )
            cat_before_dt = (
                datetime.combine(category_batch_before, time(23, 59, 59, 999999)).replace(tzinfo=timezone.utc)
                if category_batch_before
                else None
            )
            st.session_state["category_batch_matches"] = find_documents(
                created_after=cat_after_dt,
                created_before=cat_before_dt,
                keyword=category_batch_keyword or None,
                source=category_batch_source or None,
            )

    category_batch_matches = st.session_state.get("category_batch_matches", [])

    if category_batch_matches:
        st.write(f"符合條件的文件共 {len(category_batch_matches)} 筆:")
        for match in category_batch_matches:
            created = match.created_at.astimezone(DISPLAY_TIMEZONE)
            current_category = f"[{match.category}]" if match.category else "[未分類]"
            st.write(f"- {created:%Y-%m-%d %H:%M}  {current_category}  {match.title}  ({match.source_path})")

        if new_category_value and st.button("套用這個分類", type="primary", key="category-batch-apply"):
            updated_count = set_document_categories(
                [match.id for match in category_batch_matches], new_category_value
            )
            st.session_state["batch_category_message"] = (
                f"已將 {updated_count} 筆文件的分類設成「{new_category_value}」。"
            )
            st.session_state["category_batch_matches"] = []
            st.rerun()
        elif not new_category_value:
            st.caption("要先在上面填分類名稱,才能套用。")

with tab_search:
    query = st.text_input("搜尋知識庫", placeholder="想搜尋的內容")
    top_k = st.slider("回傳筆數", min_value=1, max_value=20, value=5, key="search-top-k")
    search_category = st.selectbox(
        "限定分類", options=["全部"] + list_categories(), key="search-category"
    )

    if query:
        results = run_search(query, top_k=top_k, category=None if search_category == "全部" else search_category)

        if not results:
            st.info("沒有找到相關內容。")
        else:
            for rank, result in enumerate(results, start=1):
                with st.container(border=True):
                    created = result.document.created_at.astimezone(DISPLAY_TIMEZONE).strftime("%Y-%m-%d %H:%M")
                    st.markdown(f"**[{rank}] {result.document.title}**  (score={result.score:.3f}, {created})")
                    st.caption(result.document.source_path)
                    st.write(result.chunk.content)

with tab_ask:
    question = st.text_input("問知識庫一個問題", placeholder="想問的問題")
    ask_top_k = st.slider("檢索筆數", min_value=1, max_value=20, value=5, key="ask-top-k")
    ask_category = st.selectbox("限定分類", options=["全部"] + list_categories(), key="ask-category")

    if question:
        try:
            ask_result = run_ask(
                question, top_k=ask_top_k, category=None if ask_category == "全部" else ask_category
            )
        except (anthropic.AuthenticationError, TypeError) as error:
            if isinstance(error, TypeError) and "authentication" not in str(error).lower():
                raise
            st.error("找不到有效的 Anthropic API key,請設定環境變數 ANTHROPIC_API_KEY 後再試一次。")
        else:
            st.write(ask_result.answer)
            if ask_result.sources:
                st.caption(
                    "來源:"
                    + "、".join(
                        f"{source.document.title}"
                        f"({source.document.created_at.astimezone(DISPLAY_TIMEZONE):%Y-%m-%d %H:%M})"
                        for source in ask_result.sources
                    )
                )

with tab_add:
    st.subheader("上傳檔案")
    uploaded_file = st.file_uploader("選擇 markdown/text 檔案", type=["md", "markdown", "txt"])
    upload_category = st.text_input("分類(留空不分類)", key="upload-category")

    if uploaded_file is not None and st.button("加入這個檔案"):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / uploaded_file.name
            tmp_path.write_bytes(uploaded_file.getvalue())
            document = load_document(tmp_path)
            result = ingest_document(document, category=upload_category or None)

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
    add_feed_category = st.text_input("分類(留空不分類)", key="add-feed-category")

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
                    feed_result = ingest_document(feed_document, category=add_feed_category or None)
                    if feed_result is None:
                        skipped += 1
                        continue
                    added += 1
                    st.success(f"已處理「{feed_result.document.title}」— {feed_result.chunk_count} 個片段")
                st.info(f"完成:{added} 篇已處理,{skipped} 篇內容是空的被略過。")

with tab_feeds:
    st.subheader("訂閱清單")
    st.caption("跟上面「新增筆記」的一次性訂閱不同,這裡的來源會被記住,之後按同步就能一次抓所有來源的新文章。")

    subscriptions = list_feed_subscriptions()

    if not subscriptions:
        st.info("訂閱清單是空的,在下面加一個吧。")
    else:
        if st.button("同步全部"):
            for sync_result in sync_all_feed_subscriptions():
                if sync_result.error is not None:
                    st.error(f"「{sync_result.feed.name}」同步失敗:{sync_result.error}")
                else:
                    st.success(
                        f"「{sync_result.feed.name}」— 新增 {sync_result.added} 篇、"
                        f"更新 {sync_result.updated} 篇、略過 {sync_result.skipped} 篇空內容"
                    )
            # 故意不呼叫 st.rerun():馬上 rerun 會把剛印出來的 st.success/st.error 洗掉,
            # 使用者看不到同步結果。上面「上次同步」時間要等下一次互動才會更新,
            # 跟「新增筆記」分頁同樣的已知取捨。

        for feed in subscriptions:
            with st.container(border=True):
                col_info, col_sync, col_remove = st.columns([5, 1, 1])
                with col_info:
                    last_synced = (
                        feed.last_synced_at.astimezone(DISPLAY_TIMEZONE).strftime("%Y-%m-%d %H:%M")
                        if feed.last_synced_at
                        else "尚未同步"
                    )
                    category_label = feed.category or "未分類"
                    st.markdown(f"**{feed.name}**  ·  📁 {category_label}")
                    st.caption(f"{feed.url}  ·  上次同步:{last_synced}")
                    col_category, col_category_button = st.columns([3, 1])
                    with col_category:
                        new_category_input = st.text_input(
                            "更新分類",
                            value=feed.category or "",
                            key=f"category-input-{feed.id}",
                            label_visibility="collapsed",
                        )
                    with col_category_button:
                        if st.button("更新分類", key=f"category-update-{feed.id}"):
                            update_feed_category(feed.url, new_category_input or None)
                            st.success("已更新分類(只影響之後同步的新文章)")
                            st.rerun()
                with col_sync:
                    if st.button("同步", key=f"sync-{feed.id}"):
                        sync_result = sync_feed_subscription(feed)
                        if sync_result.error is not None:
                            st.error(f"同步失敗:{sync_result.error}")
                        else:
                            st.success(
                                f"新增 {sync_result.added} 篇、更新 {sync_result.updated} 篇、"
                                f"略過 {sync_result.skipped} 篇空內容"
                            )
                with col_remove:
                    if st.button("取消訂閱", key=f"unsub-{feed.id}"):
                        unsubscribe_feed(feed.url)
                        st.rerun()

    st.divider()

    st.subheader("新增訂閱")
    new_feed_url = st.text_input("Feed 網址", key="subscribe-feed-url")
    new_feed_name = st.text_input("顯示名稱(留空會自動抓 feed 標題)", key="subscribe-feed-name")
    new_feed_category = st.text_input("分類(留空不分類,之後同步的文章都會標上這個分類)", key="subscribe-feed-category")
    new_feed_limit = st.number_input(
        "第一次同步最多抓幾篇", min_value=1, max_value=50, value=10, key="subscribe-feed-limit"
    )

    if new_feed_url and st.button("訂閱這個來源"):
        display_name = new_feed_name or get_feed_title(new_feed_url) or new_feed_url
        new_feed = subscribe_feed(new_feed_url, display_name, category=new_feed_category or None)

        if new_feed is None:
            st.warning(f"已經訂閱過這個來源了:{new_feed_url}")
        else:
            sync_result = sync_feed_subscription(new_feed, limit=int(new_feed_limit))
            if sync_result.error is not None:
                st.warning(f"已訂閱「{new_feed.name}」,但第一次同步失敗:{sync_result.error}")
            else:
                st.success(
                    f"已訂閱「{new_feed.name}」— 新增 {sync_result.added} 篇、"
                    f"更新 {sync_result.updated} 篇、略過 {sync_result.skipped} 篇空內容"
                )
