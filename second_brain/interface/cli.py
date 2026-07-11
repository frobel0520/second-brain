"""second-brain CLI(typer app)。"""

from __future__ import annotations

import sys
from pathlib import Path

import anthropic
import typer

from second_brain.ingestion.loader import load_document
from second_brain.processing.chunking import chunk_document
from second_brain.processing.embedding import get_embedding_provider
from second_brain.processing.tagging import get_tagging_provider
from second_brain.retrieval.ask import ask as run_ask
from second_brain.retrieval.search import search as run_search
from second_brain.storage import (
    clear_all,
    list_documents,
    remove_document,
    replace_existing_document,
    save_document,
)

if sys.platform == "win32":
    # Windows 主控台預設用系統 ANSI codepage,不是 UTF-8,印中文會變亂碼。
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

app = typer.Typer(help="Second Brain — 個人化知識管理系統")


@app.callback()
def callback() -> None:
    """add / search / ask / list / remove / clear 六個指令,強制保留子指令的形式。"""


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
    document.tags = get_tagging_provider().tag(document)
    chunks = chunk_document(document)

    if not chunks:
        typer.echo("檔案內容是空的,沒有東西可以加入。")
        raise typer.Exit(code=1)

    replaced = replace_existing_document(document.source_path, document.content)

    provider = get_embedding_provider()
    embeddings = provider.embed([chunk.content for chunk in chunks])
    for chunk, embedding in zip(chunks, embeddings):
        chunk.embedding = embedding

    save_document(document, chunks)

    tag_suffix = f"  標籤:{', '.join(document.tags)}" if document.tags else ""

    if replaced is None:
        typer.echo(f"已加入「{document.title}」— {len(chunks)} 個片段 ({file_path}){tag_suffix}")
    elif replaced.source_path != document.source_path:
        typer.echo(
            f"偵測到內容跟舊紀錄相同、但路徑變了(原路徑:{replaced.source_path}),"
            f"視為搬家/改名並取代舊版本 — {len(chunks)} 個片段 ({file_path}){tag_suffix}"
        )
    else:
        typer.echo(f"已更新「{document.title}」— {len(chunks)} 個片段 ({file_path}){tag_suffix}")


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
    file_path: Path = typer.Argument(
        ...,
        help="要從知識庫移除的檔案路徑(檔案不需要還存在於硬碟上)",
    ),
) -> None:
    """從知識庫移除指定檔案的紀錄(sqlite + chroma),不會動到硬碟上的檔案本身。"""
    removed_title = remove_document(str(file_path.resolve()))

    if removed_title is None:
        typer.echo(f"知識庫裡沒有找到這個檔案:{file_path}")
        raise typer.Exit(code=1)

    typer.echo(f"已從知識庫移除「{removed_title}」({file_path})")


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
