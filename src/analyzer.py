import json
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

try:
    from kiwipiepy import Kiwi
except Exception:
    Kiwi = None


TOKEN_PATTERN = r"(?u)\b[\uac00-\ud7a3A-Za-z0-9]{2,}\b"
NOUN_TAGS = {"NNP", "NNG", "SL"}
PREDICATE_TAGS = {"VV", "VA"}
_KIWI = None


def _json(value):
    return json.dumps(value, ensure_ascii=False)


def _get_kiwi():
    global _KIWI
    if Kiwi is None:
        return None
    if _KIWI is None:
        _KIWI = Kiwi()
    return _KIWI


def _compact(text):
    return re.sub(r"[\s\W_]+", "", str(text).lower())


def _is_numeric_noise(text):
    compacted = _compact(text)
    return bool(compacted) and all(ch.isdigit() for ch in compacted)


def _clean_candidate(text):
    return str(text).strip(" \u00b7,.;:!?\"'\u2018\u2019\u201c\u201d[](){}<>")


def _normalize_predicate(text):
    """Return predicate lemmas when a non-noun fallback ever needs normalization."""
    kiwi = _get_kiwi()
    if kiwi is None:
        return str(text)

    lemmas = []
    for token in kiwi.tokenize(str(text)):
        if token.tag in PREDICATE_TAGS:
            lemmas.append(getattr(token, "lemma", token.form))
    return " ".join(lemmas) if lemmas else str(text)


def _accept_noun_phrase(forms, tags, from_title):
    if not forms:
        return None

    candidate = _clean_candidate("".join(forms))
    if len(candidate) < 2 or _is_numeric_noise(candidate):
        return None

    noun_count = sum(1 for tag in tags if tag in {"NNP", "NNG", "SL"})
    has_proper_signal = any(tag in {"NNP", "SL"} for tag in tags)

    # NNP/SL is accepted directly. Pure common-noun phrases must be compound and
    # long enough, which catches names like "국방성중앙군악단" while dropping
    # short generic words like "관심", "없어", "표시", "나래".
    if has_proper_signal:
        return candidate
    if from_title and noun_count >= 2 and len(candidate) >= 4:
        return candidate
    if noun_count >= 3 and len(candidate) >= 5:
        return candidate
    return None


def _kiwi_keyword_candidates(text, from_title=False):
    kiwi = _get_kiwi()
    if kiwi is None:
        return None

    candidates = []
    for chunk in re.findall(r"[\uac00-\ud7a3A-Za-z0-9\u00b7]+", str(text)):
        forms = []
        tags = []

        def flush():
            nonlocal forms, tags
            candidate = _accept_noun_phrase(forms, tags, from_title=from_title)
            if candidate:
                candidates.append(candidate)
            forms = []
            tags = []

        for token in kiwi.tokenize(chunk):
            if token.tag in NOUN_TAGS:
                forms.append(token.form)
                tags.append(token.tag)
            elif token.tag == "XSN" and forms:
                forms.append(token.form)
                tags.append(token.tag)
            else:
                flush()
        flush()

    return list(dict.fromkeys(candidates))


def _regex_keyword_candidates(text):
    candidates = []
    for token in re.findall(r"[\uac00-\ud7a3A-Za-z0-9\u00b7]{2,20}", str(text)):
        token = _clean_candidate(token)
        if len(token) >= 4 and not _is_numeric_noise(token):
            candidates.append(token)
    return list(dict.fromkeys(candidates))


def _keyword_candidates(text, from_title=False):
    candidates = _kiwi_keyword_candidates(text, from_title=from_title)
    if candidates is not None:
        return candidates
    return _regex_keyword_candidates(text)


def _is_near_duplicate(left, right):
    left_key = _compact(left)
    right_key = _compact(right)
    if not left_key or not right_key:
        return False
    if left_key in right_key or right_key in left_key:
        return True
    ratio = SequenceMatcher(None, left_key, right_key).ratio()
    shared_edge = left_key[:2] == right_key[:2] or left_key[-2:] == right_key[-2:]
    return ratio >= 0.72 and shared_edge


def _dedupe_keywords(scored_candidates, top_n):
    selected = []
    for candidate, score in sorted(scored_candidates.items(), key=lambda item: (item[1], len(item[0])), reverse=True):
        duplicate_index = None
        for index, (existing, existing_score) in enumerate(selected):
            if _is_near_duplicate(candidate, existing):
                duplicate_index = index
                if score > existing_score or (score == existing_score and len(candidate) > len(existing)):
                    selected[index] = (candidate, score)
                break
        if duplicate_index is not None:
            continue
        selected.append((candidate, score))
        if len(selected) >= top_n:
            break
    return [candidate for candidate, _ in selected[:top_n]]


def _proper_noun_keywords(records, top_n=6):
    """Extract keywords from titles and body evidence using POS structure, not hardcoded stopwords."""
    scores = Counter()
    article_hits = defaultdict(set)
    press_names = {_compact(record.get("press", "")) for record in records}

    seen_titles = set()
    for record in records:
        title = str(record.get("title", "")).strip()
        if title and title not in seen_titles:
            seen_titles.add(title)
            for candidate in _keyword_candidates(title, from_title=True):
                if _compact(candidate) not in press_names:
                    scores[candidate] += 5
                    article_hits[candidate].add(record.get("article_id"))

    for rank, sentence in enumerate(_top_tfidf_sentences(records, limit=24), start=1):
        weight = max(1, 6 - (rank // 4))
        owner_ids = [record.get("article_id") for record in records if record.get("sentence") == sentence]
        owner_id = owner_ids[0] if owner_ids else None
        for candidate in _keyword_candidates(sentence, from_title=False):
            if _compact(candidate) in press_names:
                continue
            scores[candidate] += weight
            if owner_id is not None:
                article_hits[candidate].add(owner_id)

    for candidate, hits in article_hits.items():
        scores[candidate] += 2 * len(hits)

    return _dedupe_keywords(scores, top_n=top_n)


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
