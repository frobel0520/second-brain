"""second-brain CLI(typer app)。"""

from __future__ import annotations

import sys
from datetime import datetime, time, timezone
from pathlib import Path

import anthropic
import typer

from second_brain.config import DISPLAY_TIMEZONE, RSS_DEFAULT_LIMIT
from second_brain.ingestion.loader import load_document
from second_brain.ingestion.pipeline import (
    FeedSyncResult,
    IngestResult,
    ingest_document,
    sync_all_feed_subscriptions,
    sync_feed_subscription,
    translate_missing_documents,
)
from second_brain.ingestion.rss_loader import get_feed_title, load_feed
from second_brain.retrieval.ask import ask as run_ask
from second_brain.retrieval.search import search as run_search
from second_brain.storage import (
    clear_all,
    find_documents,
    list_documents,
    list_feed_subscriptions,
    remove_document,
    remove_documents,
    set_document_categories,
    subscribe_feed,
    unsubscribe_feed,
    update_feed_category,
)

if sys.platform == "win32":
    # Windows 主控台預設用系統 ANSI codepage,不是 UTF-8,印中文會變亂碼。
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

app = typer.Typer(help="Second Brain — 個人化知識管理系統")
feeds_app = typer.Typer(help="管理常態追蹤的 RSS/Atom 訂閱清單")
app.add_typer(feeds_app, name="feeds")


@app.callback()
def callback() -> None:
    """add / add-feed / search / ask / list / remove / remove-batch / set-category / clear / translate / feeds 幾組指令,強制保留子指令的形式。"""


def _format_ingest_result(result: IngestResult, location: str) -> str:
    tag_suffix = f"  標籤:{', '.join(result.document.tags)}" if result.document.tags else ""

    if result.status == "added":
        return f"已加入「{result.document.title}」— {result.chunk_count} 個片段 ({location}){tag_suffix}"
    if result.status == "renamed":
        return (
            f"偵測到內容跟舊紀錄相同、但路徑變了(原路徑:{result.previous_source_path}),"
            f"視為搬家/改名並取代舊版本 — {result.chunk_count} 個片段 ({location}){tag_suffix}"
        )
    return f"已更新「{result.document.title}」— {result.chunk_count} 個片段 ({location}){tag_suffix}"


@app.command()
def add(
    file_path: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        help="要加入知識庫的 markdown/text 檔案路徑",
    ),
    category: str | None = typer.Option(
        None, "--category", "-c", help="分類(例如 科技/新聞/財經),不給就不分類"
    ),
) -> None:
    """讀取檔案 → 切塊 → 產生 embedding → 存進 SQLite + ChromaDB。

    同一個來源檔案再次 add 會取代舊版本,而不是重複塞進知識庫。
    加入時會自動用本機關鍵字抽取產生標籤。
    """
    document = load_document(file_path)
    result = ingest_document(document, category=category)

    if result is None:
        typer.echo("檔案內容是空的,沒有東西可以加入。")
        raise typer.Exit(code=1)

    typer.echo(_format_ingest_result(result, str(file_path)))


@app.command(name="add-feed")
def add_feed(
    feed_url: str = typer.Argument(..., help="RSS/Atom 訂閱網址(也可以是本機 feed 檔案路徑)"),
    limit: int = typer.Option(
        RSS_DEFAULT_LIMIT, "--limit", "-n", help="最多處理幾篇文章(依 feed 提供的順序,通常最新的在前面)"
    ),
    category: str | None = typer.Option(
        None, "--category", "-c", help="分類(例如 科技/新聞/財經),不給就不分類"
    ),
) -> None:
    """訂閱 RSS/Atom 來源,把裡面的文章當成筆記加入知識庫。

    跟 `add` 共用同一套標籤/切塊/embedding/dedupe 邏輯,每篇文章用它的連結
    當 source_path,再次 add-feed 同一個來源會 upsert,不會重複塞入。
    """
    try:
        documents = load_feed(feed_url, limit=limit)
    except Exception as error:
        # feed 抓取/解析失敗的原因很多(網路錯誤、來源網址不是合法 feed…),
        # 這裡只是 CLI 的錯誤邊界,統一印出來、不特別分類。
        typer.echo(f"抓取或解析這個訂閱來源失敗:{error}")
        raise typer.Exit(code=1)

    if not documents:
        typer.echo("這個訂閱來源目前沒有文章可以加入。")
        raise typer.Exit(code=0)

    added = 0
    skipped = 0
    for document in documents:
        result = ingest_document(document, category=category)
        if result is None:
            skipped += 1
            continue
        added += 1
        typer.echo(_format_ingest_result(result, document.source_path))

    typer.echo(f"完成:{added} 篇已處理,{skipped} 篇內容是空的被略過。")


def _format_feed_sync_result(result: FeedSyncResult) -> str:
    if result.error is not None:
        return f"「{result.feed.name}」同步失敗:{result.error}"
    return (
        f"「{result.feed.name}」— 新增 {result.added} 篇、更新 {result.updated} 篇、"
        f"略過 {result.skipped} 篇空內容"
    )


@feeds_app.command("add")
def feeds_add(
    feed_url: str = typer.Argument(..., help="要訂閱的 RSS/Atom 網址(也可以是本機 feed 檔案路徑)"),
    name: str | None = typer.Option(
        None, "--name", help="這個訂閱來源的顯示名稱,不給的話會嘗試從 feed 本身抓標題,抓不到就用網址"
    ),
    limit: int = typer.Option(
        RSS_DEFAULT_LIMIT, "--limit", "-n", help="訂閱時第一次同步最多處理幾篇文章"
    ),
    category: str | None = typer.Option(
        None, "--category", "-c", help="這個來源的分類(例如 科技/新聞/財經),之後同步進來的文章都會標上這個分類"
    ),
) -> None:
    """把一個 RSS/Atom 來源加進訂閱清單,並立刻做一次同步。

    跟一次性的 `add-feed` 不同,訂閱清單會記住這個來源,之後可以用
    `second-brain feeds sync` 一次同步所有訂閱來源的新文章。
    """
    display_name = name or get_feed_title(feed_url) or feed_url
    feed = subscribe_feed(feed_url, display_name, category=category)

    if feed is None:
        typer.echo(f"已經訂閱過這個來源了:{feed_url}")
        raise typer.Exit(code=1)

    typer.echo(f"已訂閱「{feed.name}」({feed_url})")

    result = sync_feed_subscription(feed, limit=limit)
    if result.error is not None:
        typer.echo(f"訂閱成功,但第一次同步失敗:{result.error}")
        raise typer.Exit(code=1)

    typer.echo(_format_feed_sync_result(result))


@feeds_app.command("list")
def feeds_list() -> None:
    """列出目前訂閱清單裡的所有 RSS/Atom 來源。"""
    subscriptions = list_feed_subscriptions()

    if not subscriptions:
        typer.echo("訂閱清單是空的,先用 `second-brain feeds add <網址>` 加一個吧。")
        raise typer.Exit(code=0)

    for feed in subscriptions:
        last_synced = (
            feed.last_synced_at.astimezone(DISPLAY_TIMEZONE).strftime("%Y-%m-%d %H:%M")
            if feed.last_synced_at
            else "尚未同步"
        )
        category_suffix = f"  [{feed.category}]" if feed.category else "  [未分類]"
        typer.echo(f"{feed.name}{category_suffix}  (上次同步:{last_synced})")
        typer.echo(f"    {feed.url}")


@feeds_app.command("remove")
def feeds_remove(feed_url: str = typer.Argument(..., help="要取消訂閱的網址")) -> None:
    """從訂閱清單移除來源,不會刪除已經加入知識庫的文章。"""
    removed = unsubscribe_feed(feed_url)

    if removed is None:
        typer.echo(f"訂閱清單裡沒有找到這個網址:{feed_url}")
        raise typer.Exit(code=1)

    typer.echo(f"已取消訂閱「{removed.name}」({feed_url})")


@feeds_app.command("set-category")
def feeds_set_category(
    feed_url: str = typer.Argument(..., help="要設定分類的訂閱網址"),
    category: str = typer.Argument(..., help="新的分類(例如 科技/新聞/財經)"),
) -> None:
    """更新一個已訂閱來源的分類。

    只影響之後同步進來的新文章,不會回頭改已經加入知識庫的舊文章——舊文章
    要一併改分類的話,請用 `second-brain set-category` 依來源批次設定。
    """
    updated = update_feed_category(feed_url, category)

    if updated is None:
        typer.echo(f"訂閱清單裡沒有找到這個網址:{feed_url}")
        raise typer.Exit(code=1)

    typer.echo(f"已把「{updated.name}」的分類設為「{category}」(只影響之後同步的新文章)")


def _format_sync_log_line(results: list[FeedSyncResult]) -> str:
    """把這次同步所有來源的結果彙整成一行,給 `--log-file` 寫檔用。

    只給彙總數字(不像 `_format_feed_sync_result` 逐來源印出來),失敗的來源
    額外列出名稱+原因,方便之後回頭查「昨天同步到底發生了什麼」。
    """
    total_added = sum(result.added for result in results)
    total_updated = sum(result.updated for result in results)
    failures = [result for result in results if result.error is not None]

    timestamp = datetime.now(DISPLAY_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
    line = f"{timestamp}  新增 {total_added} 篇、更新 {total_updated} 篇、失敗 {len(failures)} 個來源"
    if failures:
        line += ":" + "、".join(f"{result.feed.name} 同步失敗:{result.error}" for result in failures)
    return line


@feeds_app.command("sync")
def feeds_sync(
    limit: int = typer.Option(
        RSS_DEFAULT_LIMIT, "--limit", "-n", help="每個來源最多處理幾篇文章"
    ),
    log_file: Path | None = typer.Option(
        None, "--log-file", help="把這次同步的彙總結果(一行)附加到這個檔案,給排程自動化用"
    ),
) -> None:
    """同步訂閱清單裡的所有來源,抓取新文章加入知識庫。"""
    results = sync_all_feed_subscriptions(limit=limit)

    if not results:
        typer.echo("訂閱清單是空的,先用 `second-brain feeds add <網址>` 加一個吧。")
        raise typer.Exit(code=0)

    for result in results:
        typer.echo(_format_feed_sync_result(result))

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as f:
            f.write(_format_sync_log_line(results) + "\n")


@app.command()
def search(
    query: str = typer.Argument(..., help="要搜尋的自然語言查詢"),
    top_k: int = typer.Option(5, "--top-k", "-k", help="回傳前 k 個最相關的片段"),
    category: str | None = typer.Option(None, "--category", "-c", help="只在這個分類的文件裡搜尋"),
) -> None:
    """把 query 轉成向量,在知識庫中做語意 + 關鍵字混合搜尋,回傳最相關的片段。"""
    results = run_search(query, top_k=top_k, category=category)

    if not results:
        typer.echo("沒有找到相關內容。先用 `second-brain add` 加一些筆記吧。")
        raise typer.Exit(code=0)

    for rank, result in enumerate(results, start=1):
        snippet = " ".join(result.chunk.content.split())
        if len(snippet) > 200:
            snippet = snippet[:200] + "…"

        created = result.document.created_at.astimezone(DISPLAY_TIMEZONE).strftime("%Y-%m-%d %H:%M")
        typer.echo(f"\n[{rank}] {result.document.title}  (score={result.score:.3f}, {created})")
        typer.echo(f"    來源: {result.document.source_path}")
        typer.echo(f"    {snippet}")


@app.command()
def ask(
    query: str = typer.Argument(..., help="要詢問知識庫的問題"),
    top_k: int = typer.Option(5, "--top-k", "-k", help="檢索前 k 個最相關的片段作為上下文"),
    category: str | None = typer.Option(None, "--category", "-c", help="只在這個分類的文件裡檢索"),
) -> None:
    """在 search 結果基礎上,呼叫 Anthropic API 做問答總結(RAG)。"""
    try:
        result = run_ask(query, top_k=top_k, category=category)
    except (anthropic.AuthenticationError, TypeError) as error:
        if isinstance(error, TypeError) and "authentication" not in str(error).lower():
            raise
        typer.echo("找不到有效的 Anthropic API key,請設定環境變數 ANTHROPIC_API_KEY 後再試一次。")
        raise typer.Exit(code=1)

    typer.echo(result.answer)

    if result.sources:
        typer.echo("\n來源:")
        for source in result.sources:
            created = source.document.created_at.astimezone(DISPLAY_TIMEZONE).strftime("%Y-%m-%d %H:%M")
            typer.echo(f"  - {source.document.title}  ({created})")


@app.command(name="list")
def list_command(
    category: str | None = typer.Option(None, "--category", "-c", help="只列出這個分類的文件"),
) -> None:
    """列出知識庫裡目前有哪些文件。"""
    documents = find_documents(category=category) if category is not None else list_documents()

    if not documents:
        message = (
            f"沒有分類是「{category}」的文件。" if category is not None
            else "知識庫是空的,先用 `second-brain add` 加一些筆記吧。"
        )
        typer.echo(message)
        raise typer.Exit(code=0)

    for document in documents:
        created = document.created_at.astimezone(DISPLAY_TIMEZONE).strftime("%Y-%m-%d %H:%M")
        category_prefix = f"[{document.category}] " if document.category else ""
        tag_suffix = f"  [{', '.join(document.tags)}]" if document.tags else ""
        translation_suffix = "  🇹🇼已翻譯" if document.has_translation else ""
        typer.echo(
            f"{created}  {category_prefix}{document.title}  ({document.chunk_count} 個片段)"
            f"{tag_suffix}{translation_suffix}"
        )
        typer.echo(f"    {document.source_path}")


@app.command()
def remove(
    source: str = typer.Argument(
        ...,
        help="要從知識庫移除的來源——本機檔案路徑或 RSS 文章網址都可以(檔案不需要還存在於硬碟上)",
    ),
) -> None:
    """從知識庫移除指定來源的紀錄(sqlite + chroma),不會動到硬碟上的檔案本身。

    本機檔案路徑會正規化成絕對路徑再比對(跟 `add` 存進去的 source_path 一致);
    網址(例如 RSS 文章連結)不會被當成檔案路徑處理,直接原樣比對,避免在 Windows
    上被 `Path.resolve()` 把網址裡的斜線打散成反斜線。
    """
    source_path = source if "://" in source else str(Path(source).resolve())
    removed_title = remove_document(source_path)

    if removed_title is None:
        typer.echo(f"知識庫裡沒有找到這個來源:{source}")
        raise typer.Exit(code=1)

    typer.echo(f"已從知識庫移除「{removed_title}」({source})")


def _parse_filter_date(value: str, *, end_of_day: bool) -> datetime:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError as error:
        raise typer.BadParameter(f"日期格式錯誤,請用 YYYY-MM-DD:{value}") from error
    if end_of_day:
        parsed = datetime.combine(parsed.date(), time(23, 59, 59, 999999))
    return parsed.replace(tzinfo=timezone.utc)


@app.command(name="remove-batch")
def remove_batch(
    after: str | None = typer.Option(None, "--after", help="只找這個日期(含)之後加入的文件,格式 YYYY-MM-DD"),
    before: str | None = typer.Option(None, "--before", help="只找這個日期(含)之前加入的文件,格式 YYYY-MM-DD"),
    keyword: str | None = typer.Option(None, "--keyword", "-k", help="標題/內容/標籤符合這個關鍵字的文件"),
    source: str | None = typer.Option(None, "--source", help="來源路徑或網址包含這段文字的文件"),
    yes: bool = typer.Option(False, "--yes", "-y", help="跳過確認,直接刪除"),
) -> None:
    """依日期範圍、關鍵字、來源批次刪除文件。

    三個條件是「符合任一個就刪」(OR),不是同時符合(AND);--after/--before
    兩個一起給的話,這兩個之間是 AND,定義出一段日期區間,這段區間再跟關鍵字/
    來源用 OR 組合。至少要給一個條件,不然請用 `second-brain clear` 清空整個
    知識庫。刪除前會先列出符合的文件並要求確認,跟 `clear` 同樣的安全機制。
    """
    if not any([after, before, keyword, source]):
        typer.echo(
            "至少要給一個篩選條件(--after/--before/--keyword/--source)。"
            "如果是想清空整個知識庫,請用 `second-brain clear`。"
        )
        raise typer.Exit(code=1)

    after_dt = _parse_filter_date(after, end_of_day=False) if after else None
    before_dt = _parse_filter_date(before, end_of_day=True) if before else None

    matches = find_documents(created_after=after_dt, created_before=before_dt, keyword=keyword, source=source)

    if not matches:
        typer.echo("沒有符合條件的文件。")
        raise typer.Exit(code=0)

    typer.echo(f"符合條件的文件共 {len(matches)} 筆:")
    for document in matches:
        created = document.created_at.astimezone(DISPLAY_TIMEZONE)
        typer.echo(f"  {created:%Y-%m-%d %H:%M}  {document.title}  ({document.source_path})")

    if not yes:
        confirmed = typer.confirm(f"確定要刪除這 {len(matches)} 筆文件嗎?這個動作無法復原。")
        if not confirmed:
            typer.echo("已取消。")
            raise typer.Exit(code=0)

    removed_titles = remove_documents([document.id for document in matches])
    typer.echo(f"已刪除 {len(removed_titles)} 筆文件。")


@app.command(name="set-category")
def set_category(
    category: str = typer.Argument(..., help="要設定的分類(例如 科技/新聞/財經)"),
    after: str | None = typer.Option(None, "--after", help="只找這個日期(含)之後加入的文件,格式 YYYY-MM-DD"),
    before: str | None = typer.Option(None, "--before", help="只找這個日期(含)之前加入的文件,格式 YYYY-MM-DD"),
    keyword: str | None = typer.Option(None, "--keyword", "-k", help="標題/內容/標籤符合這個關鍵字的文件"),
    source: str | None = typer.Option(None, "--source", help="來源路徑或網址包含這段文字的文件"),
    yes: bool = typer.Option(False, "--yes", "-y", help="跳過確認,直接設定"),
) -> None:
    """依日期範圍、關鍵字、來源批次把符合條件的文件分類設成同一個值。

    篩選邏輯跟 `remove-batch` 一樣(三個條件符合任一個就算,--after/--before
    兩個一起給則彼此是 AND、定義一段區間),至少要給一個條件。用在幫既有文件
    補分類——例如透過一次性 `add-feed` 加入、沒有訂閱紀錄可以依循的文章,
    或想更正已經分類錯的文件;`feeds set-category` 只會影響訂閱之後同步進來
    的新文章,不會回頭改已經存在的文件,這個指令才是用來動既有文件的。
    """
    if not any([after, before, keyword, source]):
        typer.echo(
            "至少要給一個篩選條件(--after/--before/--keyword/--source)。"
        )
        raise typer.Exit(code=1)

    after_dt = _parse_filter_date(after, end_of_day=False) if after else None
    before_dt = _parse_filter_date(before, end_of_day=True) if before else None

    matches = find_documents(created_after=after_dt, created_before=before_dt, keyword=keyword, source=source)

    if not matches:
        typer.echo("沒有符合條件的文件。")
        raise typer.Exit(code=0)

    typer.echo(f"符合條件的文件共 {len(matches)} 筆:")
    for document in matches:
        created = document.created_at.astimezone(DISPLAY_TIMEZONE)
        current_category = f"[{document.category}]" if document.category else "[未分類]"
        typer.echo(f"  {created:%Y-%m-%d %H:%M}  {current_category}  {document.title}  ({document.source_path})")

    if not yes:
        confirmed = typer.confirm(f"確定要把這 {len(matches)} 筆文件的分類設成「{category}」嗎?")
        if not confirmed:
            typer.echo("已取消。")
            raise typer.Exit(code=0)

    updated_count = set_document_categories([document.id for document in matches], category)
    typer.echo(f"已將 {updated_count} 筆文件的分類設成「{category}」。")


@app.command()
def clear(
    yes: bool = typer.Option(False, "--yes", "-y", help="跳過確認,直接清空"),
) -> None:
    """清空整個知識庫(sqlite + chroma),不會動到硬碟上的原始檔案。"""
    if not yes:
        confirmed = typer.confirm("確定要清空整個知識庫嗎?這個動作無法復原。")
        if not confirmed:
            typer.echo("已取消。")
            raise typer.Exit(code=0)

    removed_count = clear_all()
    typer.echo(f"已清空知識庫,共移除 {removed_count} 份文件。")


@app.command()
def translate() -> None:
    """幫知識庫裡還沒有翻譯的文件補上繁體中文翻譯,需要 `ANTHROPIC_API_KEY`。

    `add`/`add-feed`/`feeds` 系列指令已經會自動翻譯新加入的文件(失敗會靜默
    跳過,不擋 ingestion);這個指令是用來補翻譯「當初沒設 API key、或翻譯
    當下失敗」的舊文件。
    """
    result = translate_missing_documents()

    if result.auth_error is not None:
        if result.translated:
            typer.echo(f"已翻譯 {result.translated} 篇。")
        typer.echo("找不到有效的 Anthropic API key,請設定環境變數 ANTHROPIC_API_KEY 後再試一次。")
        raise typer.Exit(code=1)

    if result.translated == 0 and result.failed == 0:
        typer.echo("沒有需要翻譯的文件。")
        raise typer.Exit(code=0)

    typer.echo(f"完成:{result.translated} 篇已翻譯,{result.failed} 篇失敗。")


if __name__ == "__main__":
    app()
