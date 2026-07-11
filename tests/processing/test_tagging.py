from second_brain.models import Document
from second_brain.processing.tagging import KeywordFrequencyTaggingProvider


def _document(content: str) -> Document:
    return Document(id="doc-1", source_path="/tmp/note.md", title="note", content=content)


def test_tag_returns_empty_list_for_empty_content() -> None:
    provider = KeywordFrequencyTaggingProvider()

    assert provider.tag(_document("")) == []


def test_tag_filters_out_stopwords() -> None:
    provider = KeywordFrequencyTaggingProvider()

    tags = provider.tag(_document("the the the of of of database database"))

    assert "the" not in tags
    assert "of" not in tags
    assert "database" in tags


def test_tag_ranks_most_frequent_first() -> None:
    provider = KeywordFrequencyTaggingProvider()

    tags = provider.tag(_document("python python python rust rust java"))

    assert tags[0] == "python"
    assert tags.index("python") < tags.index("rust") < tags.index("java")


def test_tag_respects_max_tags() -> None:
    provider = KeywordFrequencyTaggingProvider(max_tags=2)

    tags = provider.tag(_document("alpha beta gamma delta alpha beta gamma delta"))

    assert len(tags) == 2
