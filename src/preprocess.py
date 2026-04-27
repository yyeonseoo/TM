import re

import pandas as pd


SPACE_RE = re.compile(r"\s+")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|(?<=\ub2e4\.)\s*|(?<=\uc694\.)\s*")


def clean_text(text):
    text = "" if pd.isna(text) else str(text)
    text = re.sub(r"\[[^\]]+\]", " ", text)
    text = re.sub(r"\([^)]*\uae30\uc790[^)]*\)", " ", text)
    return SPACE_RE.sub(" ", text).strip()


def split_sentences(text, min_length=25):
    text = clean_text(text)
    rough_sentences = SENTENCE_SPLIT_RE.split(text)
    sentences = []
    for sentence in rough_sentences:
        sentence = clean_text(sentence)
        if len(sentence) >= min_length:
            sentences.append(sentence)
    return sentences


def preprocess_articles(df_articles):
    """Return sentence-level records while preserving article metadata."""
    records = []
    unknown_press = "\uc5b8\ub860\uc0ac \ubbf8\uc0c1"

    for article_id, row in df_articles.reset_index(drop=True).iterrows():
        title = clean_text(row.get("title", ""))
        if title:
            records.append(
                {
                    "article_id": article_id,
                    "sentence_id": -1,
                    "sentence": title,
                    "title": row.get("title", ""),
                    "press": row.get("press", unknown_press) or unknown_press,
                    "link": row.get("link", ""),
                    "is_title": True,
                }
            )
        for sentence_id, sentence in enumerate(split_sentences(row.get("content", ""))):
            records.append(
                {
                    "article_id": article_id,
                    "sentence_id": sentence_id,
                    "sentence": sentence,
                    "title": row.get("title", ""),
                    "press": row.get("press", unknown_press) or unknown_press,
                    "link": row.get("link", ""),
                    "is_title": False,
                }
            )

    if not records:
        raise ValueError("\ubd84\uc11d\ud560 \uc218 \uc788\ub294 \ubb38\uc7a5\uc774 \uc5c6\uc2b5\ub2c8\ub2e4. \uae30\uc0ac \ubcf8\ubb38 \uc218\uc9d1 \uc0c1\ud0dc\ub97c \ud655\uc778\ud574 \uc8fc\uc138\uc694.")

    return pd.DataFrame(records)
