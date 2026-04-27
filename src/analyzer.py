import json
import re
from collections import Counter
from collections import defaultdict

from keybert import KeyBERT
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.embedding import _get_model


KOREAN_STOPWORDS = {
    "\uae30\uc790",
    "\ub274\uc2a4",
    "\uad00\ub828",
    "\uc9c0\ub09c",
    "\uc774\ubc88",
    "\ub300\ud55c",
    "\ud1b5\ud574",
    "\uc788\ub294",
    "\ud588\ub2e4",
    "\ud55c\ub2e4",
    "\ub41c\ub2e4",
    "\uc704\ud574",
    "\uac83\uc73c\ub85c",
    "\uadf8\ub9ac\uace0",
}

_KEYBERT = None
TOKEN_PATTERN = r"(?u)\b[\uac00-\ud7a3A-Za-z0-9]{2,}\b"
MAX_KEYBERT_CHARS = 5000
PROPER_NOUN_RE = re.compile(r"[\uac00-\ud7a3A-Za-z0-9·]{2,20}")
PROPER_NOUN_STOPWORDS = KOREAN_STOPWORDS | {
    "\uac83\uc73c\ub85c",
    "\uac83\uc740",
    "\uac83\uc774",
    "\uac83\uc744",
    "\uc788\ub2e4",
    "\uc5c6\ub2e4",
    "\ub41c\ub2e4",
    "\ud55c\ub2e4",
    "\ud588\ub2e4",
    "\ub9d0\ud588\ub2e4",
    "\ubc1d\ud614\ub2e4",
    "\uc804\ud588\ub2e4",
    "\ub300\ud574",
    "\uad00\ud574",
    "\uc704\ud574",
    "\ub4f1\uc744",
    "\ub4f1\uc774",
    "\ub4f1\uc5d0",
    "\ucd9c\ub9c8",
    "\uc120\uc5b8",
    "\ucd9c\ub9c8\uc120\uc5b8",
    "\ud6c4\ubcf4",
    "\ubcf4\ub3c4",
    "\uad00\ub828",
    "\ub17c\ub780",
    "\uc624\ub298",
    "\uc5b4\uc81c",
    "\uc774\ub0a0",
    "\ud604\uc7ac",
    "\uc774\ubc88",
    "\uc9c0\ubc29\uc120\uac70",
    "\ubcf4\uad90\uc120\uac70",
    "\uacbd\uc120",
    "\ud68c\uc758",
    "\uc815\ubd80",
    "\uc5ec\uc57c",
    "\uc815\uce58",
    "\uc0ac\uac74",
    "\uc7ac\ud310",
    "\ud56d\uc18c\uc2ec",
    "\ud610\uc758",
    "\uc120\uace0",
    "\uc2dc\uc791",
    "\ub0b4\ub780",
    "\uc6b0\ub450\uba38\ub9ac",
    "\ubb34\uae30\uc9d5\uc5ed",
    "1\uc2ec",
    "2\uc2ec",
    "67\uc77c",
    "\uc591\ub2f9",
    "\uae30\ub4dd\uad8c",
    "\ucc0d\uace0",
    "\uc2f6\uc740",
    "\uc800\ubc16\uc5d0",
    "\uc9c0\uc5ed\uad6c",
    "\uad6d\ud68c",
    "\ub2f9\uc2dc",
    "\uc0ac\ub78c",
    "\ubd10\ub3c4",
}
PARTICLE_SUFFIXES = (
    "\uc5d0\uc11c\ub294",
    "\uc73c\ub85c\ub294",
    "\uc73c\ub85c",
    "\uc5d0\uc11c",
    "\uc5d0\uac8c",
    "\uae4c\uc9c0",
    "\ubd80\ud130",
    "\ubcf4\ub2e4",
    "\ucc98\ub7fc",
    "\ub77c\uace0",
    "\uc774\ub77c",
    "\uc640\uc758",
    "\uacfc\uc758",
    "\uc758",
    "\uc740",
    "\ub294",
    "\uc774",
    "\uac00",
    "\uc744",
    "\ub97c",
    "\uacfc",
    "\uc640",
    "\ub3c4",
    "\ub9cc",
    "\uc5d0",
    "\ub85c",
)
ORG_SUFFIXES = (
    "\ub2f9",
    "\uc2e0\ub2f9",
    "\ubbfc\uc8fc\ub2f9",
    "\uad6d\ubbfc\uc758\ud798",
    "\uc815\ubd80",
    "\uad6d\ud68c",
    "\ubc95\uc6d0",
    "\uac80\ucc30",
    "\uccad\uc640\ub300",
    "\uc704\uc6d0\ud68c",
    "\uc7ac\ud310\ubd80",
    "\uc120\uad00\uc704",
)
PLACE_SUFFIXES = ("\uc2dc", "\ub3c4", "\uad70", "\uad6c", "\ubd81\uac11", "\ub0a8\uac11", "\ubd81\uc744", "\ub0a8\uc744")


def _json(value):
    return json.dumps(value, ensure_ascii=False)


def _get_keybert():
    global _KEYBERT
    if _KEYBERT is None:
        _KEYBERT = KeyBERT(model=_get_model())
    return _KEYBERT


def _tfidf_keywords(texts, top_n=6):
    text = " ".join(str(text) for text in texts if str(text).strip())
    if not text:
        return []

    try:
        vectorizer = TfidfVectorizer(max_features=top_n, token_pattern=TOKEN_PATTERN)
        matrix = vectorizer.fit_transform([text])
        if matrix.shape[1] == 0:
            return []
        return vectorizer.get_feature_names_out().tolist()
    except ValueError:
        return []


def _strip_particle(token):
    token = token.strip(" ·,.;:!?\"'“”‘’[](){}<>")
    for suffix in PARTICLE_SUFFIXES:
        if token.endswith(suffix) and len(token) > len(suffix) + 1:
            return token[: -len(suffix)]
    return token


def _looks_like_proper_noun(token, from_title=False):
    token = _strip_particle(token)
    if len(token) < 2 or token in PROPER_NOUN_STOPWORDS:
        return False
    if re.fullmatch(r"\d+\uc2ec|\d+\uc77c|\d+\ub144|\d+\uc6d4|\d+\uc2dc|\d+\ubd80|[A-Za-z]*\d+\ubd80", token):
        return False
    if re.search(r"\d", token) and "·" not in token:
        return False
    if token.endswith(("\ub2e4", "\ud55c", "\ud558\ub294", "\ub418\ub294", "\uc788\ub294", "\uc5c6\ub294")):
        return False
    if token.endswith(("\uace0", "\uba70", "\uba74", "\ub4ef", "\ubfd0", "\ubc16", "\uc2f6\uc740", "\ucc0d\uace0")):
        return False
    if any(token.endswith(suffix) for suffix in ORG_SUFFIXES):
        return True
    if any(token.endswith(suffix) for suffix in PLACE_SUFFIXES) and len(token) <= 6:
        return True
    if re.search(r"[A-Za-z0-9]", token):
        return True
    if from_title and 2 <= len(token) <= 4:
        return True
    return False


def _proper_noun_candidates(text, from_title=False):
    candidates = []
    for token in PROPER_NOUN_RE.findall(str(text)):
        token = _strip_particle(token)
        if _looks_like_proper_noun(token, from_title=from_title):
            candidates.append(token)
    return candidates


def _proper_noun_keywords(records, top_n=6):
    counts = Counter()
    press_names = {str(record.get("press", "")).strip() for record in records}
    seen_titles = set()
    for record in records:
        title = str(record.get("title", "")).strip()
        if title and title not in seen_titles:
            seen_titles.add(title)
            for candidate in _proper_noun_candidates(title, from_title=True):
                counts[candidate] += 3

    for sentence in _top_tfidf_sentences(records, limit=20):
        for candidate in _proper_noun_candidates(sentence, from_title=False):
            counts[candidate] += 1

    selected = []
    for candidate, _ in counts.most_common():
        if candidate in press_names:
            continue
        if any(candidate in item or item in candidate for item in selected):
            continue
        selected.append(candidate)
        if len(selected) >= top_n:
            break
    return selected


def _keybert_keywords(texts, top_n=6):
    text = " ".join(str(text) for text in texts if str(text).strip())[:MAX_KEYBERT_CHARS]
    if not text:
        return []

    try:
        keywords = _get_keybert().extract_keywords(
            text,
            keyphrase_ngram_range=(1, 2),
            stop_words=list(KOREAN_STOPWORDS),
            top_n=top_n,
        )
        result = [keyword for keyword, _ in keywords]
        if result:
            return result
    except Exception:
        pass

    return _tfidf_keywords(texts, top_n=top_n)


def _top_tfidf_sentences(records, limit=5):
    sentences = [record["sentence"] for record in records]
    if len(sentences) <= limit:
        return sentences

    vectorizer = TfidfVectorizer(token_pattern=TOKEN_PATTERN)
    try:
        matrix = vectorizer.fit_transform(sentences)
        scores = matrix.sum(axis=1).A.ravel()
        ranked_indexes = scores.argsort()[::-1][:limit]
        ranked_indexes = sorted(ranked_indexes, key=lambda idx: records[idx]["sentence_id"])
        return [sentences[idx] for idx in ranked_indexes]
    except ValueError:
        return sentences[:limit]


def _common_fact_sentences(records, limit=5):
    sentences = [record["sentence"] for record in records]
    if len(sentences) <= limit:
        return sentences

    try:
        matrix = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1).fit_transform(sentences)
        similarities = cosine_similarity(matrix)
    except ValueError:
        return _top_tfidf_sentences(records, limit=limit)

    groups = []
    used = set()
    for index, record in enumerate(records):
        if index in used:
            continue
        near_indexes = [
            other_index
            for other_index, score in enumerate(similarities[index])
            if score >= 0.30 and records[other_index]["article_id"] != record["article_id"]
        ]
        if not near_indexes:
            continue
        group = sorted(set([index] + near_indexes))
        used.update(group)
        article_count = len({records[group_index]["article_id"] for group_index in group})
        groups.append((article_count, group))

    if not groups:
        return _top_tfidf_sentences(records, limit=limit)

    common = []
    for _, group in sorted(groups, key=lambda item: (item[0], len(item[1])), reverse=True):
        sub = similarities[group][:, group]
        representative_index = group[int(sub.mean(axis=1).argmax())]
        sentence = records[representative_index]["sentence"]
        if sentence not in common:
            common.append(sentence)
        if len(common) >= limit:
            break

    return common


def _controversy_clusters(records, limit=3):
    by_press = defaultdict(list)
    for record in records:
        by_press[record["press"]].append(record)

    clusters = []
    for press, press_records in by_press.items():
        evidence = _top_tfidf_sentences(press_records, limit=2)
        clusters.append(
            {
                "label": press,
                "keywords": _proper_noun_keywords(press_records, top_n=4),
                "evidence": evidence,
            }
        )

    clusters.sort(key=lambda item: len(item["evidence"]), reverse=True)
    return clusters[:limit]


def _press_data(records):
    grouped = defaultdict(list)
    for record in records:
        grouped[record["press"]].append(record)

    result = {}
    for press, press_records in grouped.items():
        titles = []
        links = []
        for record in press_records:
            if record["title"] not in titles:
                titles.append(record["title"])
            if record["link"] and record["link"] not in links:
                links.append(record["link"])

        evidence = _top_tfidf_sentences(press_records, limit=4)
        result[press] = {
            "keywords": _proper_noun_keywords(press_records, top_n=6),
            "emphasis_sentence": evidence[0] if evidence else "",
            "titles": titles[:5],
            "links": links[:5],
            "evidence": evidence,
        }

    return dict(sorted(result.items(), key=lambda item: len(item[1]["evidence"]), reverse=True))


def _issue_title(cluster, fallback):
    title = str(cluster.get("representative_title", "")).strip()
    if title:
        return title
    titles = [str(item).strip() for item in cluster.get("article_titles", []) if str(item).strip()]
    return titles[0] if titles else fallback


def _issue_summary(title, keywords, article_count, press_count):
    return (
        f"\uc774 \uc774\uc288\ub294 '{title}'\uc744 \uc911\uc2ec\uc73c\ub85c \uac19\uc740 \uc0ac\uac74\uc744 \ub2e4\ub8ec \ubcf4\ub3c4 \ubb36\uc74c\uc785\ub2c8\ub2e4. "
        f"\ucd1d {article_count}\uac1c \uae30\uc0ac\uac00 \ubb36\uc600\uace0, {press_count}\uac1c \uc5b8\ub860\uc0ac\uac00 \ud574\ub2f9 \uc774\uc288\ub97c \ubcf4\ub3c4\ud588\uc2b5\ub2c8\ub2e4. "
        f"\uc544\ub798 \uadfc\uac70 \ubb38\uc7a5\uc740 \uc774 \ubb36\uc74c\uc5d0 \ud3ec\ud568\ub41c \uae30\uc0ac \uc6d0\ubb38\uc5d0\uc11c \ucd94\ucd9c\ud55c \ub0b4\uc6a9\uc785\ub2c8\ub2e4."
    )


def analyze_issues(clusters, max_issues=3):
    """Build issue summaries from clustered original sentences without judgment scores."""
    issues = []
    eligible_clusters = [cluster for cluster in clusters if cluster["article_count"] >= 2]
    if not eligible_clusters:
        eligible_clusters = clusters

    for rank, cluster in enumerate(eligible_clusters[:max_issues], start=1):
        records = cluster["records"]
        sentences = [record["sentence"] for record in records]
        keywords = _proper_noun_keywords(records, top_n=8)
        common_facts = _common_fact_sentences(records, limit=5)
        controversy_clusters = _controversy_clusters(records, limit=3)
        press_data = _press_data(records)
        evidence_sentences = _top_tfidf_sentences(records, limit=8)
        title = _issue_title(cluster, f"\uc774\uc288 {rank}")

        issues.append(
            {
                "title": title,
                "summary": _issue_summary(title, keywords, cluster["article_count"], cluster["press_count"]),
                "keywords": _json(keywords),
                "common_facts": _json(common_facts),
                "controversy_clusters": _json(controversy_clusters),
                "presses": ", ".join(press_data.keys()),
                "press_data": _json(press_data),
                "evidence_sentences": _json(evidence_sentences),
                "article_count": cluster["article_count"],
                "sentence_count": cluster["size"],
                "press_count": cluster["press_count"],
            }
        )

    issues.sort(key=lambda item: (item["article_count"], item["sentence_count"]), reverse=True)
    return issues
