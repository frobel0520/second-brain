"""second-brain CLI(typer app)。"""

from __future__ import annotations

import sys
from pathlib import Path

import anthropic
import typer

from second_brain.config import RSS_DEFAULT_LIMIT
from second_brain.ingestion.loader import load_document
from second_brain.ingestion.pipeline import (
    FeedSyncResult,
    IngestResult,
    ingest_document,
    sync_all_feed_subscriptions,
    sync_feed_subscription,
)
from second_brain.ingestion.rss_loader import get_feed_title, load_feed
from second_brain.retrieval.ask import ask as run_ask
from second_brain.retrieval.search import search as run_search
from second_brain.storage import (
    clear_all,
    list_documents,
    list_feed_subscriptions,
    remove_document,
    subscribe_feed,
    unsubscribe_feed,
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
    """add / add-feed / search / ask / list / remove / clear / feeds 幾組指令,強制保留子指令的形式。"""


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
) -> None:
    """讀取檔案 → 切塊 → 產生 embedding → 存進 SQLite + ChromaDB。

    同一個來源檔案再次 add 會取代舊版本,而不是重複塞進知識庫。
    加入時會自動用本機關鍵字抽取產生標籤。
    """
    document = load_document(file_path)
    result = ingest_document(document)

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
        result = ingest_document(document)
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
) -> None:
    """把一個 RSS/Atom 來源加進訂閱清單,並立刻做一次同步。

    跟一次性的 `add-feed` 不同,訂閱清單會記住這個來源,之後可以用
    `second-brain feeds sync` 一次同步所有訂閱來源的新文章。
    """
    display_name = name or get_feed_title(feed_url) or feed_url
    feed = subscribe_feed(feed_url, display_name)

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
            feed.last_synced_at.strftime("%Y-%m-%d %H:%M") if feed.last_synced_at else "尚未同步"
        )
        typer.echo(f"{feed.name}  (上次同步:{last_synced})")
        typer.echo(f"    {feed.url}")


@feeds_app.command("remove")
def feeds_remove(feed_url: str = typer.Argument(..., help="要取消訂閱的網址")) -> None:
    """從訂閱清單移除來源,不會刪除已經加入知識庫的文章。"""
    removed = unsubscribe_feed(feed_url)

    if removed is None:
        typer.echo(f"訂閱清單裡沒有找到這個網址:{feed_url}")
        raise typer.Exit(code=1)

    typer.echo(f"已取消訂閱「{removed.name}」({feed_url})")


@feeds_app.command("sync")
def feeds_sync(
    limit: int = typer.Option(
        RSS_DEFAULT_LIMIT, "--limit", "-n", help="每個來源最多處理幾篇文章"
    ),
) -> None:
    """同步訂閱清單裡的所有來源,抓取新文章加入知識庫。"""
    results = sync_all_feed_subscriptions(limit=limit)

    if not results:
        typer.echo("訂閱清單是空的,先用 `second-brain feeds add <網址>` 加一個吧。")
        raise typer.Exit(code=0)

    for result in results:
        typer.echo(_format_feed_sync_result(result))


@app.command()
def search(
    query: str = typer.Argument(..., help="要搜尋的自然語言查詢"),
    top_k: int = typer.Option(5, "--top-k", "-k", help="回傳前 k 個最相關的片段"),
) -> None:
    """把 query 轉成向量,在知識庫中做語意搜尋,回傳最相關的片段。"""
    results = run_search(query, top_k=top_k)

    if not results:
        typer.echo("沒有找到相關內容。先用 `second-brain add` 加一些筆記吧。")
        raise typer.Exit(code=0)

    for rank, result in enumerate(results, start=1):
        snippet = " ".join(result.chunk.content.split())
        if len(snippet) > 200:
            snippet = snippet[:200] + "…"

        typer.echo(f"\n[{rank}] {result.document.title}  (score={result.score:.3f})")
        typer.echo(f"    來源: {result.document.source_path}")
        typer.echo(f"    {snippet}")


@app.command()
def ask(
    query: str = typer.Argument(..., help="要詢問知識庫的問題"),
    top_k: int = typer.Option(5, "--top-k", "-k", help="檢索前 k 個最相關的片段作為上下文"),
) -> None:
    """在 search 結果基礎上,呼叫 Anthropic API 做問答總結(RAG)。"""
    try:
        answer = run_ask(query, top_k=top_k)
    except (anthropic.AuthenticationError, TypeError) as error:
        if isinstance(error, TypeError) and "authentication" not in str(error).lower():
            raise
        typer.echo("找不到有效的 Anthropic API key,請設定環境變數 ANTHROPIC_API_KEY 後再試一次。")
        raise typer.Exit(code=1)

    typer.echo(answer)


@app.command(name="list")
def list_command() -> None:
    """列出知識庫裡目前有哪些文件。"""
    documents = list_documents()

    if not documents:
        typer.echo("知識庫是空的,先用 `second-brain add` 加一些筆記吧。")
        raise typer.Exit(code=0)

    for document in documents:
        created = document.created_at.strftime("%Y-%m-%d %H:%M")
        tag_suffix = f"  [{', '.join(document.tags)}]" if document.tags else ""
        typer.echo(f"{created}  {document.title}  ({document.chunk_count} 個片段){tag_suffix}")
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


if __name__ == "__main__":
    app()
