"""Streamlit 本機網頁介面(`streamlit run second_brain/interface/web.py`)。

跟 cli.py 一樣是 interface 層的一種實作,底層共用 processing/storage/retrieval
各層,不重複寫核心邏輯——加東西一律透過 ingestion.pipeline.ingest_document()。
"""

from __future__ import annotations

import math
import tempfile
from datetime import datetime, time, timezone
from pathlib import Path

import anthropic
import streamlit as st

from second_brain.config import DISPLAY_TIMEZONE
from second_brain.ingestion.loader import load_document
from second_brain.ingestion.pipeline import ingest_document, sync_all_feed_subscriptions, sync_feed_subscription
from second_brain.ingestion.rss_loader import get_feed_title, load_feed
from second_brain.models import DocumentSummary
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

_NAV_OPTIONS = ["瀏覽", "搜尋", "問答", "新增筆記", "訂閱管理"]
_BROWSE_PAGE_SIZE = 10


@st.cache_resource
def _warm_up_providers() -> None:
    """第一次載入頁面時就把 embedding/tagging 模型準備好,避免每次互動都重新載入一次。"""
    get_embedding_provider()
    get_tagging_provider()


_warm_up_providers()

st.title("📚 Second Brain")

# 「新增筆記」分頁加完東西之後,會把 nav_target 設成「瀏覽」再 st.rerun(),
# 這裡在畫導覽列之前先把它套用到 active_tab 上,才能真的切換過去
# ——單純設定 session_state["active_tab"] 沒有用,widget 的值以自己的 key
# 為準,要在 widget 建立「之前」先蓋掉那個 key 對應的值。
if "nav_target" in st.session_state:
    st.session_state["active_tab"] = st.session_state.pop("nav_target")

active_tab = st.segmented_control(
    "導覽", _NAV_OPTIONS, default=_NAV_OPTIONS[0], key="active_tab", label_visibility="collapsed"
)
if active_tab is None:
    # segmented_control 允許再點一次目前選中的選項取消選取,這裡沒有「不選任何分頁」
    # 的狀態,退回瀏覽分頁,不要整頁空白。
    active_tab = "瀏覽"
    st.session_state["active_tab"] = active_tab

if active_tab == "瀏覽":
    if "batch_delete_message" in st.session_state:
        st.success(st.session_state.pop("batch_delete_message"))
    if "batch_category_message" in st.session_state:
        st.success(st.session_state.pop("batch_category_message"))
    if "add_note_message" in st.session_state:
        st.success(st.session_state.pop("add_note_message"))

    existing_categories = list_categories()
    browse_category = st.selectbox(
        "分類篩選", options=["全部"] + existing_categories, key="browse-category-filter"
    )

    # 切換分類篩選之後,文件總數會變,舊的頁碼可能超出新的頁數範圍,
    # 這裡偵測篩選條件換了就把頁碼重設回第一頁,避免 st.number_input 的
    # key 存著舊頁碼、跟新的 max_value 衝突。
    if st.session_state.get("browse-category-prev") != browse_category:
        st.session_state["browse-page"] = 1
        st.session_state["browse-category-prev"] = browse_category

    documents = (
        list_documents() if browse_category == "全部" else find_documents(category=browse_category)
    )
    # 瀏覽頁面依加入時間由新到舊排列,最新加入的文章排在最前面。
    documents = sorted(documents, key=lambda document: document.created_at, reverse=True)

    if not documents:
        message = (
            "知識庫是空的,先到「新增筆記」加一些內容吧。"
            if browse_category == "全部"
            else f"沒有分類是「{browse_category}」的文件。"
        )
        st.info(message)
    else:
        total_pages = max(1, math.ceil(len(documents) / _BROWSE_PAGE_SIZE))

        # 頁碼存在 session_state,配合上一頁/下一頁的箭頭增減;夾在 1~總頁數之間,
        # 避免刪文件後總頁數變少、舊頁碼超出範圍。
        page = min(max(int(st.session_state.get("browse-page", 1)), 1), total_pages)
        st.session_state["browse-page"] = page

        col_prev, col_info, col_next = st.columns([1, 4, 1])
        with col_prev:
            if st.button("←", key="browse-prev", disabled=page <= 1, use_container_width=True):
                st.session_state["browse-page"] = page - 1
                st.rerun()
        with col_info:
            st.markdown(
                f"<div style='text-align:center'>第 {page} / {total_pages} 頁"
                f"(共 {len(documents)} 篇)</div>",
                unsafe_allow_html=True,
            )
        with col_next:
            if st.button("→", key="browse-next", disabled=page >= total_pages, use_container_width=True):
                st.session_state["browse-page"] = page + 1
                st.rerun()

        start = (page - 1) * _BROWSE_PAGE_SIZE
        page_documents = documents[start : start + _BROWSE_PAGE_SIZE]

        def _render_document_card(document: DocumentSummary) -> None:
            with st.container(border=True):
                col_info, col_action = st.columns([12, 1])
                with col_info:
                    st.markdown(
                        f"**{document.title}**"
                        f"  ·  {document.created_at.astimezone(DISPLAY_TIMEZONE):%Y-%m-%d %H:%M}"
                    )
                    if document.category:
                        st.caption(f"📁 {document.category}")
                    # 標籤刻意不顯示給使用者(對閱讀幫助不大),但仍存在 document.tags /
                    # 後台資料裡,search/hybrid search 也照樣用得到。
                    st.caption(document.source_path)
                    if document.has_translation:
                        with st.expander("🇹🇼 查看繁體中文翻譯"):
                            full_document = get_document(document.id)
                            if full_document is not None and full_document.translated_content:
                                st.write(full_document.translated_content)
                with col_action:
                    if st.button("×", key=f"remove-{document.id}", help="刪除"):
                        remove_document(document.source_path)
                        st.rerun()

        # 一頁 10 筆分左右兩欄,前 5 筆放左欄、後 5 筆放右欄。
        half = math.ceil(_BROWSE_PAGE_SIZE / 2)
        left_col, right_col = st.columns(2)
        for column, column_documents in (
            (left_col, page_documents[:half]),
            (right_col, page_documents[half:]),
        ):
            with column:
                for document in column_documents:
                    _render_document_card(document)

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

elif active_tab == "搜尋":
    query = st.text_input("搜尋知識庫", placeholder="想搜尋的內容")
    top_k = st.slider("回傳筆數", min_value=1, max_value=20, value=5, key="search-top-k")
    col_category, col_sort = st.columns(2)
    with col_category:
        search_category = st.selectbox(
            "限定分類", options=["全部"] + list_categories(), key="search-category"
        )
    with col_sort:
        search_sort = st.selectbox(
            "排序方式", options=["相關性", "日期(新到舊)"], key="search-sort"
        )

    if query:
        results = run_search(query, top_k=top_k, category=None if search_category == "全部" else search_category)

        if not results:
            st.info("沒有找到相關內容。")
        else:
            # run_search 回傳的順序本來就是依相關度由高到低;選「日期」時才把呈現順序
            # 改成依加入時間由新到舊,相關度分數在兩種排序下都保留在 score 顯示。
            if search_sort == "日期(新到舊)":
                results = sorted(
                    results, key=lambda result: result.document.created_at, reverse=True
                )
            for result in results:
                with st.container(border=True):
                    created = result.document.created_at.astimezone(DISPLAY_TIMEZONE).strftime("%Y-%m-%d %H:%M")
                    st.markdown(f"**{result.document.title}**  (score={result.score:.3f}, {created})")
                    st.caption(result.document.source_path)
                    st.write(result.chunk.content)

elif active_tab == "問答":
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

elif active_tab == "新增筆記":
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
            tag_suffix = f"  🏷️ {'、'.join(result.document.tags)}" if result.document.tags else ""
            st.session_state["add_note_message"] = (
                f"已加入「{result.document.title}」— {result.chunk_count} 個片段{tag_suffix}"
            )
            st.session_state["nav_target"] = "瀏覽"
            st.rerun()

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

                if added > 0:
                    st.session_state["add_note_message"] = (
                        f"完成:{added} 篇已處理,{skipped} 篇內容是空的被略過。"
                    )
                    st.session_state["nav_target"] = "瀏覽"
                    st.rerun()
                else:
                    st.info(f"完成:{added} 篇已處理,{skipped} 篇內容是空的被略過。")

elif active_tab == "訂閱管理":
    st.subheader("訂閱清單")
    st.caption("跟上面「新增筆記」的一次性訂閱不同,這裡的來源會被記住,之後按同步就能一次抓所有來源的新文章。")

    subscriptions = list_feed_subscriptions()

    if not subscriptions:
        st.info("訂閱清單是空的,在下面加一個吧。")
    else:
        if st.button("同步全部"):
            sync_results = sync_all_feed_subscriptions()
            failures = [result for result in sync_results if result.error is not None]
            successes = [result for result in sync_results if result.error is None]

            if successes:
                total_added = sum(result.added for result in successes)
                total_updated = sum(result.updated for result in successes)
                st.success(
                    f"{len(successes)} 個來源同步成功 — 共新增 {total_added} 篇、更新 {total_updated} 篇。"
                )
            if failures:
                with st.expander(f"⚠️ {len(failures)} 個來源同步失敗", expanded=True):
                    for result in failures:
                        st.error(f"「{result.feed.name}」:{result.error}")
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
