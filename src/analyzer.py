import json
import os
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
KEYWORD_SCORING_MODE = os.getenv("KEYWORD_SCORING_MODE", "context").strip().lower()
NOUN_TAGS = {"NNP", "NNG", "SL"}
PREDICATE_TAGS = {"VV", "VA"}
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+\s*@\s*[A-Za-z0-9.-]+(?:\s*\.\s*[A-Za-z]{2,})+")
URL_PATTERN = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
BYLINE_PREFIX_PATTERN = re.compile(r"^\s*(?:[가-힣]{2,4}\s+){0,5}[가-힣]{2,4}\s+기자\s*=\s*")
KEYWORD_WEAK_TOKENS = {
    "\ub354\ubd88\uc5b4\ubbfc\uc8fc\ub2f9",
    "\ubbfc\uc8fc\ub2f9",
    "\uad6d\ubbfc\uc758\ud798",
    "\uac1c\ud601\uc2e0\ub2f9",
    "\uc870\uad6d\ud601\uc2e0\ub2f9",
    "\uc9c4\ubcf4\ub2f9",
    "\uc5ec\ub2f9",
    "\uc57c\ub2f9",
    "\uc5ec\uc57c",
    "\ubcf4\uc218",
    "\uc9c4\ubcf4",
    "\ubb34\uc18c\uc18d",
    "\uc758\uc6d0",
    "\ud6c4\ubcf4",
    "\uc608\ube44\ud6c4\ubcf4",
    "\uae30\uc790",
    "\ub274\uc2a4",
    "\uc5f0\ud569\ub274\uc2a4",
    "sns",
}
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


def _strip_contact_artifacts(text):
    text = URL_PATTERN.sub(" ", str(text))
    text = EMAIL_PATTERN.sub(" ", text)
    text = BYLINE_PREFIX_PATTERN.sub(" ", text)
    return text


def _is_ascii_fragment_noise(text):
    candidate = _clean_candidate(text)
    if not re.fullmatch(r"[A-Za-z0-9._%+-]+", candidate):
        return False
    if any(ch.isdigit() for ch in candidate):
        return True
    return candidate.islower()


def _is_keyword_noise(text):
    candidate = _clean_candidate(text)
    return (
        not candidate
        or _is_numeric_noise(candidate)
        or EMAIL_PATTERN.fullmatch(candidate) is not None
        or _is_ascii_fragment_noise(candidate)
    )


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
    if len(candidate) < 2 or _is_keyword_noise(candidate):
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
    for chunk in re.findall(r"[\uac00-\ud7a3A-Za-z0-9\u00b7]+", _strip_contact_artifacts(text)):
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
            elif token.tag in {"NNB", "NR"} and forms and any(tag == "NNP" for tag in tags):
                forms.append(token.form)
                tags.append(token.tag)
            else:
                flush()
        flush()

    return list(dict.fromkeys(candidates))


def _regex_keyword_candidates(text):
    candidates = []
    for token in re.findall(r"[\uac00-\ud7a3A-Za-z0-9\u00b7]{2,20}", _strip_contact_artifacts(text)):
        token = _clean_candidate(token)
        if len(token) >= 4 and not _is_keyword_noise(token):
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


def _candidate_occurs(candidate, text):
    candidate_key = _compact(candidate)
    text_key = _compact(text)
    return bool(candidate_key and candidate_key in text_key)


def _is_weak_keyword(candidate):
    return _compact(candidate) in {_compact(token) for token in KEYWORD_WEAK_TOKENS}


def _legacy_proper_noun_keywords(records, top_n=6):
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


def _contextual_proper_noun_keywords(records, top_n=6):
    """Rank source-bound proper nouns by title presence, evidence context, and article coverage."""
    scores = defaultdict(float)
    article_hits = defaultdict(set)
    title_hits = Counter()
    evidence_hits = Counter()
    press_names = {_compact(record.get("press", "")) for record in records}

    seen_titles = set()
    title_items = []
    for record in records:
        title = str(record.get("title", "")).strip()
        if title and title not in seen_titles:
            seen_titles.add(title)
            title_items.append((title, record.get("article_id")))

    for title, article_id in title_items:
        for candidate in _keyword_candidates(title, from_title=True):
            if _compact(candidate) in press_names:
                continue
            scores[candidate] += 7
            title_hits[candidate] += 1
            article_hits[candidate].add(article_id)

    salient_sentences = _top_tfidf_sentences(records, limit=32)
    for rank, sentence in enumerate(salient_sentences, start=1):
        weight = max(1.0, 7.0 - (rank * 0.25))
        owner_ids = [record.get("article_id") for record in records if record.get("sentence") == sentence]
        owner_id = owner_ids[0] if owner_ids else None
        for candidate in _keyword_candidates(sentence, from_title=False):
            if _compact(candidate) in press_names:
                continue
            scores[candidate] += weight
            evidence_hits[candidate] += 1
            if owner_id is not None:
                article_hits[candidate].add(owner_id)

    context_texts = [title for title, _ in title_items] + salient_sentences
    article_count = max(1, len({record.get("article_id") for record in records}))
    adjusted_scores = {}
    for candidate, raw_score in scores.items():
        coverage = len(article_hits[candidate])
        context_count = sum(1 for text in context_texts if _candidate_occurs(candidate, text))
        if coverage <= 1 and not title_hits[candidate] and article_count >= 3:
            raw_score *= 0.45

        coverage_bonus = 1 + min(0.75, coverage / article_count)
        context_bonus = 1 + min(0.40, context_count / max(4, len(context_texts)))
        title_bonus = 1.25 if title_hits[candidate] else 1.0
        weak_penalty = 0.62 if _is_weak_keyword(candidate) and not title_hits[candidate] else 1.0
        adjusted_scores[candidate] = raw_score * coverage_bonus * context_bonus * title_bonus * weak_penalty

    return _dedupe_keywords(adjusted_scores, top_n=top_n)


def _proper_noun_keywords(records, top_n=6):
    if KEYWORD_SCORING_MODE == "legacy":
        return _legacy_proper_noun_keywords(records, top_n=top_n)
    return _contextual_proper_noun_keywords(records, top_n=top_n)


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
