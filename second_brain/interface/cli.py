"""second-brain CLI(typer app)。"""

from __future__ import annotations

import sys
from pathlib import Path

import anthropic
import typer

from second_brain.ingestion.loader import load_document
from second_brain.processing.chunking import chunk_document
from second_brain.processing.embedding import get_embedding_provider
from second_brain.retrieval.ask import ask as run_ask
from second_brain.retrieval.search import search as run_search
from second_brain.storage import save_document

if sys.platform == "win32":
    # Windows 主控台預設用系統 ANSI codepage,不是 UTF-8,印中文會變亂碼。
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

app = typer.Typer(help="Second Brain — 個人化知識管理系統")


@app.callback()
def callback() -> None:
    """add / search / ask 三個指令,強制保留子指令的形式。"""


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
    """讀取檔案 → 切塊 → 產生 embedding → 存進 SQLite + ChromaDB。"""
    document = load_document(file_path)
    chunks = chunk_document(document)

    if not chunks:
        typer.echo("檔案內容是空的,沒有東西可以加入。")
        raise typer.Exit(code=1)

    provider = get_embedding_provider()
    embeddings = provider.embed([chunk.content for chunk in chunks])
    for chunk, embedding in zip(chunks, embeddings):
        chunk.embedding = embedding

    save_document(document, chunks)

    typer.echo(f"已加入「{document.title}」— {len(chunks)} 個片段 ({file_path})")


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


if __name__ == "__main__":
    app()
