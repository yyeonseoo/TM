import math
import re
from collections import Counter

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


DISTANCE_THRESHOLD = 0.48
MERGE_SIMILARITY_THRESHOLD = 0.58
MERGE_MIN_SHARED_TOKENS = 2
MERGE_STRONG_SIMILARITY_THRESHOLD = 0.64
MIN_BODY_SENTENCES_FOR_CLUSTERING = 2
MIN_BODY_CHARS_FOR_SHORT_ARTICLE = 160
TOKEN_PATTERN = re.compile(r"[\uac00-\ud7a3A-Za-z0-9]{2,}")
TITLE_STOPWORDS = {
    "\ub2e8\ub3c5",
    "\uc18d\ubcf4",
    "\uc885\ud569",
    "\ub274\uc2a4",
    "\uae30\uc790",
    "\uc624\ub298",
    "\ub0b4\uc77c",
    "\uc774\ubc88",
    "\uad6d\ud68c",
    "\uc815\uce58",
    "\ucd9c\ub9c8",
    "\ubcf4\uc120",
    "\ubcf4\uad90\uc120\uac70",
    "\uc120\uac70",
    "\uc124\uc804",
    "sns",
}
MERGE_WEAK_TOKENS = TITLE_STOPWORDS | {
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
    "\ub300\ud45c",
    "\uc758\uc6d0",
    "\ud6c4\ubcf4",
    "\uc608\ube44\ud6c4\ubcf4",
    "\uc9c0\ubc29\uc120\uac70",
    "\uc9c0\uc120",
    "\uacbd\uc120",
    "\uacf5\ucc9c",
    "\ub2e8\uc77c\ud654",
    "\uc9c0\uc9c0\uc728",
    "\uc5ec\ub860\uc870\uc0ac",
    "\ud398\uc774\uc2a4\ubd81",
    "\uc11c\uc6b8",
}


def _clean_title(title):
    title = re.sub(r"\[[^\]]+\]", " ", str(title))
    title = re.sub(r"\([^)]*\)", " ", title)
    return re.sub(r"\s+", " ", title).strip()


def _title_tokens(title):
    return {
        token
        for token in TOKEN_PATTERN.findall(_clean_title(title))
        if token not in TITLE_STOPWORDS
    }


def _article_rows(sentence_df, sentence_embeddings):
    rows = sentence_df.reset_index(drop=True).copy()
    rows["_embedding_index"] = range(len(rows))
    article_groups = list(rows.groupby("article_id", sort=False))
    eligible_article_ids = {
        article_id
        for article_id, group in article_groups
        if not _is_low_information_article(group)
    }
    if not eligible_article_ids:
        eligible_article_ids = {article_id for article_id, _ in article_groups}

    article_ids = []
    article_titles = {}
    article_vectors = []

    for article_id, group in article_groups:
        if article_id not in eligible_article_ids:
            continue

        title_group = group[group["is_title"] == True] if "is_title" in group.columns else group.iloc[0:0]
        body_group = group[group["is_title"] != True] if "is_title" in group.columns else group

        title_vector = sentence_embeddings[title_group["_embedding_index"].to_numpy()].mean(axis=0) if not title_group.empty else None
        lead_indexes = body_group.head(3)["_embedding_index"].to_numpy()
        lead_vector = sentence_embeddings[lead_indexes].mean(axis=0) if len(lead_indexes) else title_vector

        if title_vector is None:
            vector = lead_vector
        else:
            vector = 0.72 * title_vector + 0.28 * lead_vector
        vector = vector / max(np.linalg.norm(vector), 1e-12)

        article_ids.append(article_id)
        article_titles[article_id] = str(group["title"].iloc[0])
        article_vectors.append(vector)

    return rows, np.asarray(article_ids), article_titles, np.asarray(article_vectors)


def _is_low_information_article(group):
    body_group = group[group["is_title"] != True] if "is_title" in group.columns else group
    body_sentences = [str(sentence).strip() for sentence in body_group["sentence"].tolist() if str(sentence).strip()]
    body_chars = sum(len(sentence) for sentence in body_sentences)
    return (
        len(body_sentences) < MIN_BODY_SENTENCES_FOR_CLUSTERING
        and body_chars < MIN_BODY_CHARS_FOR_SHORT_ARTICLE
    )


def _title_char_similarity(article_ids, article_titles):
    titles = [_clean_title(article_titles[article_id]) for article_id in article_ids]
    if len(titles) == 1:
        return np.ones((1, 1))
    matrix = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=1).fit_transform(titles)
    return cosine_similarity(matrix)


def _token_jaccard_similarity(article_ids, article_titles):
    token_sets = [_title_tokens(article_titles[article_id]) for article_id in article_ids]
    scores = np.eye(len(article_ids))
    for i, left in enumerate(token_sets):
        for j in range(i + 1, len(token_sets)):
            right = token_sets[j]
            union = left | right
            score = len(left & right) / len(union) if union else 0
            scores[i, j] = score
            scores[j, i] = score
    return scores


def _combined_distance(article_ids, article_titles, article_vectors):
    title_char = _title_char_similarity(article_ids, article_titles)
    semantic = cosine_similarity(article_vectors)
    token_overlap = _token_jaccard_similarity(article_ids, article_titles)

    combined = (0.50 * title_char) + (0.38 * semantic) + (0.12 * token_overlap)
    combined = np.clip(combined, 0, 1)
    distance = 1 - combined
    np.fill_diagonal(distance, 0)
    return distance


def _cluster_labels(distance):
    if len(distance) == 1:
        return np.array([0])
    return AgglomerativeClustering(
        n_clusters=None,
        metric="precomputed",
        linkage="complete",
        distance_threshold=DISTANCE_THRESHOLD,
    ).fit_predict(distance)


def _representative_title(cluster_indexes, article_ids, article_titles, distance):
    if not cluster_indexes:
        return ""
    submatrix = distance[np.ix_(cluster_indexes, cluster_indexes)]
    central_index = cluster_indexes[int(np.argmin(submatrix.mean(axis=1)))]
    return article_titles.get(article_ids[central_index], "")


def _cluster_tokens(cluster, article_ids, article_titles):
    counts = Counter()
    for index in cluster:
        article_id = article_ids[index]
        counts.update(_title_tokens(article_titles[article_id]))
    if len(cluster) <= 1:
        return set(counts)

    min_count = max(2, math.ceil(len(cluster) * 0.4))
    core_tokens = {token for token, count in counts.items() if count >= min_count}
    if core_tokens:
        return core_tokens

    return {token for token, _ in counts.most_common(4)}


def _strong_merge_tokens(tokens):
    return {
        token
        for token in tokens
        if token not in MERGE_WEAK_TOKENS and not re.fullmatch(r"\d+", token)
    }


def _max_title_similarity(left, right, article_ids, article_titles):
    left_titles = [_clean_title(article_titles[article_ids[index]]) for index in left]
    right_titles = [_clean_title(article_titles[article_ids[index]]) for index in right]
    titles = left_titles + right_titles
    if not all(titles):
        return 0

    matrix = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=1).fit_transform(titles)
    similarities = cosine_similarity(matrix[: len(left_titles)], matrix[len(left_titles) :])
    return float(similarities.max()) if similarities.size else 0


def _should_merge_clusters(left, right, article_ids, article_titles, article_vectors):
    left_tokens = _cluster_tokens(left, article_ids, article_titles)
    right_tokens = _cluster_tokens(right, article_ids, article_titles)
    shared_tokens = left_tokens & right_tokens
    if len(shared_tokens) < MERGE_MIN_SHARED_TOKENS:
        return False

    strong_shared = _strong_merge_tokens(shared_tokens)
    if not strong_shared:
        return False

    left_centroid = article_vectors[left].mean(axis=0)
    right_centroid = article_vectors[right].mean(axis=0)
    semantic_similarity = float(cosine_similarity([left_centroid], [right_centroid])[0][0])
    if semantic_similarity < MERGE_SIMILARITY_THRESHOLD:
        return False

    if len(strong_shared) >= MERGE_MIN_SHARED_TOKENS:
        return True

    return (
        semantic_similarity >= MERGE_STRONG_SIMILARITY_THRESHOLD
        and _max_title_similarity(left, right, article_ids, article_titles) >= 0.42
    )


def _merge_related_labels(labels, article_ids, article_titles, article_vectors):
    clusters = {}
    for index, label in enumerate(labels):
        clusters.setdefault(int(label), []).append(index)

    merged = [sorted(indexes) for indexes in clusters.values()]
    changed = True
    while changed:
        changed = False
        for left_index in range(len(merged)):
            if changed:
                break
            for right_index in range(left_index + 1, len(merged)):
                if _should_merge_clusters(merged[left_index], merged[right_index], article_ids, article_titles, article_vectors):
                    merged[left_index] = sorted(set(merged[left_index] + merged[right_index]))
                    del merged[right_index]
                    changed = True
                    break

    next_labels = np.zeros(len(labels), dtype=int)
    for label, indexes in enumerate(merged):
        for index in indexes:
            next_labels[index] = label
    return next_labels


def cluster_sentences(embeddings, sentence_df):
    """Cluster same-issue articles with strict complete-link similarity, then keep body sentences."""
    embeddings = np.asarray(embeddings)
    if len(sentence_df) != len(embeddings):
        raise ValueError("\ubb38\uc7a5 \uc218\uc640 \uc784\ubca0\ub529 \uc218\uac00 \uc77c\uce58\ud558\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.")

    rows, article_ids, article_titles, article_vectors = _article_rows(sentence_df, embeddings)
    distance = _combined_distance(article_ids, article_titles, article_vectors)
    labels = _cluster_labels(distance)
    labels = _merge_related_labels(labels, article_ids, article_titles, article_vectors)
    article_label_map = dict(zip(article_ids, labels))

    rows["cluster_id"] = rows["article_id"].map(article_label_map)
    evidence_rows = rows[rows["is_title"] != True].copy() if "is_title" in rows.columns else rows.copy()

    clusters = []
    for cluster_id, group in evidence_rows.groupby("cluster_id"):
        cluster_article_ids = group["article_id"].drop_duplicates().to_numpy()
        cluster_indexes = [int(np.where(article_ids == article_id)[0][0]) for article_id in cluster_article_ids]
        cluster_titles = [article_titles.get(article_id, "") for article_id in cluster_article_ids]

        clusters.append(
            {
                "cluster_id": int(cluster_id),
                "representative_title": _representative_title(cluster_indexes, article_ids, article_titles, distance),
                "article_titles": cluster_titles,
                "records": group.drop(columns=["cluster_id"]).to_dict("records"),
                "size": int(len(group)),
                "article_count": int(group["article_id"].nunique()),
                "press_count": int(group["press"].nunique()),
            }
        )

    clusters.sort(key=lambda item: (item["article_count"], item["press_count"], item["size"]), reverse=True)
    return clusters
