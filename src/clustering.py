import re

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


DISTANCE_THRESHOLD = 0.48
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
    article_ids = []
    article_titles = {}
    article_vectors = []

    for article_id, group in rows.groupby("article_id", sort=False):
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


def cluster_sentences(embeddings, sentence_df):
    """Cluster same-issue articles with strict complete-link similarity, then keep body sentences."""
    embeddings = np.asarray(embeddings)
    if len(sentence_df) != len(embeddings):
        raise ValueError("\ubb38\uc7a5 \uc218\uc640 \uc784\ubca0\ub529 \uc218\uac00 \uc77c\uce58\ud558\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.")

    rows, article_ids, article_titles, article_vectors = _article_rows(sentence_df, embeddings)
    distance = _combined_distance(article_ids, article_titles, article_vectors)
    labels = _cluster_labels(distance)
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
