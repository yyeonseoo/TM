import json
import os

import pandas as pd
from pandas.errors import EmptyDataError
import streamlit as st

from src.analyzer import analyze_issues
from src.clustering import cluster_sentences
from src.crawler import crawl_articles
from src.embedding import generate_embeddings
from src.news_api import fetch_news_links
from src.preprocess import preprocess_articles


ARTICLES_CSV = "data/articles.csv"
ISSUES_CSV = "data/issues.csv"
TARGET_POLITICS_ARTICLES = 100
LINK_POOL_SIZE = 700


TXT = {
    "app_title": "\ub274\uc2a4 \uc774\uc288 \ubd84\uc11d \uc2dc\uc2a4\ud15c",
    "collect_settings": "\uc218\uc9d1 \uc124\uc815",
    "politics_only": "\uc815\uce58 \uce74\ud14c\uace0\ub9ac \uae30\uc0ac\ub9cc \uc218\uc9d1\ud569\ub2c8\ub2e4.",
    "target_count": "\ubaa9\ud45c \uc218\uc9d1 \uae30\uc0ac",
    "load_news": "\ucd5c\uc2e0 \uc815\uce58 \ub274\uc2a4 \ubd88\ub7ec\uc624\uae30",
    "analyze": "\uc8fc\uc694 \uc774\uc288 \ubd84\uc11d\ud558\uae30",
    "loading_news": "\ub124\uc774\ubc84 \uc815\uce58 \ub274\uc2a4 \ub9c1\ud06c\ub97c \uc218\uc9d1\ud558\uace0 \ubcf8\ubb38\uc744 \uac00\uc838\uc624\ub294 \uc911\uc785\ub2c8\ub2e4.",
    "no_articles": "\uc218\uc9d1\ub41c \ub124\uc774\ubc84 \uc815\uce58 \ub274\uc2a4 \ubcf8\ubb38\uc774 \uc5c6\uc2b5\ub2c8\ub2e4. API \ud0a4 \ub610\ub294 \ub124\uc774\ubc84 \uae30\uc0ac \ud398\uc774\uc9c0 \uad6c\uc870\ub97c \ud655\uc778\ud574 \uc8fc\uc138\uc694.",
    "saved": "\uac1c \uae30\uc0ac\ub97c \uc800\uc7a5\ud588\uc2b5\ub2c8\ub2e4.",
    "collect_error": "\ub274\uc2a4 \uc218\uc9d1 \uc911 \uc624\ub958\uac00 \ubc1c\uc0dd\ud588\uc2b5\ub2c8\ub2e4",
    "analyzing": "\ubb38\uc7a5 \uc784\ubca0\ub529\uacfc \uc774\uc288 \ud074\ub7ec\uc2a4\ud130\ub9c1\uc744 \uc218\ud589\ud558\ub294 \uc911\uc785\ub2c8\ub2e4. \uccab \uc2e4\ud589\uc740 \ubaa8\ub378 \ub85c\ub529 \ub54c\ubb38\uc5d0 \uc2dc\uac04\uc774 \uac78\ub9b4 \uc218 \uc788\uc2b5\ub2c8\ub2e4.",
    "analyzed": "\uac1c \uc774\uc288 \ubd84\uc11d\uc744 \uc644\ub8cc\ud588\uc2b5\ub2c8\ub2e4.",
    "analyze_error": "\uc774\uc288 \ubd84\uc11d \uc911 \uc624\ub958\uac00 \ubc1c\uc0dd\ud588\uc2b5\ub2c8\ub2e4",
    "load_first": "\uba3c\uc800 \ucd5c\uc2e0 \uc815\uce58 \ub274\uc2a4 \ubd88\ub7ec\uc624\uae30 \ubc84\ud2bc\uc744 \ub20c\ub7ec \uae30\uc0ac\ub97c \uc218\uc9d1\ud574 \uc8fc\uc138\uc694.",
    "article_count": "\ud604\uc7ac \uc800\uc7a5\ub41c \uae30\uc0ac",
    "show_articles": "\uc218\uc9d1 \uae30\uc0ac \ubcf4\uae30",
    "analyze_first": "\uae30\uc0ac \uc218\uc9d1 \ud6c4 \uc8fc\uc694 \uc774\uc288 \ubd84\uc11d\ud558\uae30 \ubc84\ud2bc\uc744 \ub20c\ub7ec \uc8fc\uc138\uc694.",
    "issue": "\uc774\uc288",
    "issue_select": "\uc774\uc288 TOP 3 \uc120\ud0dd",
    "comparison": "\ud1b5\ud569 \ube44\uad50",
    "press": "\uc5b8\ub860\uc0ac",
    "keywords": "\uc8fc\uc694 \ud0a4\uc6cc\ub4dc",
    "emphasis": "\uac15\uc870 \ubb38\uc7a5",
    "titles": "\uad00\ub828 \uae30\uc0ac \uc81c\ubaa9",
    "evidence": "\uadfc\uac70 \ubb38\uc7a5",
    "common_facts": "\uacf5\ud1b5 \uc0ac\uc2e4",
    "summary": "\uc804\uccb4 \ub0b4\uc6a9 \uc694\uc57d",
    "common_evidence": "\uacf5\ud1b5 \uadfc\uac70 \ubb38\uc7a5",
    "controversies": "\uc7c1\uc810 \ud074\ub7ec\uc2a4\ud130",
}


def _ensure_data_dir():
    os.makedirs("data", exist_ok=True)


def _load_csv(path):
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        return pd.read_csv(path).fillna("")
    except EmptyDataError:
        return pd.DataFrame()


def _parse_json(value, default):
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value) if value else default
    except (TypeError, json.JSONDecodeError):
        return default


def _issue_label(row, index):
    fallback = f"{TXT['issue']} {index + 1}"
    title = str(row.get("title", "")).strip() or fallback
    return f"{fallback}: {title}"


st.set_page_config(page_title=TXT["app_title"], layout="wide")
st.title(TXT["app_title"])

_ensure_data_dir()

with st.sidebar:
    st.subheader(TXT["collect_settings"])
    st.write(TXT["politics_only"])
    st.metric(TXT["target_count"], f"{TARGET_POLITICS_ARTICLES}\uac1c")

col1, col2 = st.columns(2)

with col1:
    if st.button(TXT["load_news"], use_container_width=True):
        with st.spinner(TXT["loading_news"]):
            try:
                links = fetch_news_links(target_count=LINK_POOL_SIZE)
                articles = crawl_articles(
                    links,
                    max_articles=TARGET_POLITICS_ARTICLES,
                    category_filter="\uc815\uce58",
                )
                df_articles = pd.DataFrame(articles)
                if df_articles.empty:
                    st.warning(TXT["no_articles"])
                else:
                    df_articles.to_csv(ARTICLES_CSV, index=False, encoding="utf-8-sig")
                    if os.path.exists(ISSUES_CSV):
                        os.remove(ISSUES_CSV)
                    st.success(f"{len(df_articles)}{TXT['saved']}")
                    if len(df_articles) < TARGET_POLITICS_ARTICLES:
                        st.warning(
                            f"\uc815\uce58 \uce74\ud14c\uace0\ub9ac\ub85c \ud655\uc778\ub41c \uae30\uc0ac\uac00 {len(df_articles)}\uac1c\uc785\ub2c8\ub2e4. "
                            f"\ubaa9\ud45c {TARGET_POLITICS_ARTICLES}\uac1c\ubcf4\ub2e4 \uc801\uc73c\uba74 \ub124\uc774\ubc84 API \uacb0\uacfc\uc5d0 n.news \uc815\uce58 \uae30\uc0ac\uac00 \ubd80\uc871\ud55c \uac83\uc785\ub2c8\ub2e4."
                        )
            except Exception as exc:
                st.error(f"{TXT['collect_error']}: {exc}")

df_articles = _load_csv(ARTICLES_CSV)

with col2:
    if st.button(TXT["analyze"], use_container_width=True, disabled=df_articles.empty):
        progress = st.progress(0)
        status = st.empty()
        try:
            status.info("\uae30\uc0ac \ubcf8\ubb38\uc744 \ubb38\uc7a5 \ub2e8\uc704\ub85c \ub098\ub204\ub294 \uc911\uc785\ub2c8\ub2e4.")
            sentence_df = preprocess_articles(df_articles)
            progress.progress(20)

            status.info(f"{len(sentence_df)}\uac1c \ubb38\uc7a5\uc744 SBERT \uc784\ubca0\ub529\uc73c\ub85c \ubcc0\ud658\ud558\ub294 \uc911\uc785\ub2c8\ub2e4.")
            embeddings = generate_embeddings(sentence_df["sentence"].tolist())
            progress.progress(55)

            status.info("\ubb38\uc7a5 \uc784\ubca0\ub529\uc744 \uc774\uc288\ubcc4\ub85c \ud074\ub7ec\uc2a4\ud130\ub9c1\ud558\ub294 \uc911\uc785\ub2c8\ub2e4.")
            clusters = cluster_sentences(embeddings, sentence_df)
            progress.progress(75)

            status.info("\uc0c1\uc704 3\uac1c \uc774\uc288\uc758 \ud0a4\uc6cc\ub4dc\uc640 \uadfc\uac70 \ubb38\uc7a5\uc744 \uc815\ub9ac\ud558\ub294 \uc911\uc785\ub2c8\ub2e4.")
            issues = analyze_issues(clusters)
            df_issues = pd.DataFrame(issues)
            df_issues.to_csv(ISSUES_CSV, index=False, encoding="utf-8-sig")
            progress.progress(100)
            status.empty()
            st.success(f"{min(3, len(df_issues))}{TXT['analyzed']}")
        except Exception as exc:
            status.empty()
            st.error(f"{TXT['analyze_error']}: {exc}")

if df_articles.empty:
    st.info(TXT["load_first"])
else:
    st.caption(f"{TXT['article_count']}: {len(df_articles)}")
    with st.expander(TXT["show_articles"]):
        visible_columns = [column for column in ["category", "press", "title", "link"] if column in df_articles.columns]
        st.dataframe(df_articles[visible_columns], use_container_width=True)

df_issues = _load_csv(ISSUES_CSV)

if df_issues.empty:
    st.info(TXT["analyze_first"])
    st.stop()

top_issues = df_issues.head(3).reset_index(drop=True)
issue_options = [_issue_label(row, i) for i, row in top_issues.iterrows()]
selected_issue = st.radio(TXT["issue_select"], issue_options)
issue = top_issues.iloc[issue_options.index(selected_issue)]

press_data = _parse_json(issue.get("press_data", "{}"), {})
presses = list(press_data.keys())
tabs = st.tabs([TXT["comparison"]] + presses)

with tabs[0]:
    st.subheader(TXT["comparison"])
    comparison_rows = []
    for press, data in press_data.items():
        comparison_rows.append(
            {
                TXT["press"]: press,
                TXT["keywords"]: ", ".join(data.get("keywords", [])),
                TXT["emphasis"]: data.get("emphasis_sentence", ""),
                TXT["titles"]: " / ".join(data.get("titles", [])),
                TXT["evidence"]: " / ".join(data.get("evidence", [])),
            }
        )
    st.dataframe(pd.DataFrame(comparison_rows), use_container_width=True, hide_index=True)

    st.subheader(TXT["summary"])
    st.write(issue.get("summary", ""))

    with st.expander(TXT["common_evidence"]):
        for sentence in _parse_json(issue.get("common_facts", "[]"), []):
            st.write(f"- {sentence}")

    st.subheader(TXT["controversies"])
    for cluster in _parse_json(issue.get("controversy_clusters", "[]"), []):
        st.markdown(f"**{cluster.get('label', '')}**")
        st.write(", ".join(cluster.get("keywords", [])))
        for sentence in cluster.get("evidence", []):
            st.write(f"- {sentence}")

    st.subheader(TXT["evidence"])
    for sentence in _parse_json(issue.get("evidence_sentences", "[]"), []):
        st.write(f"- {sentence}")

for idx, press in enumerate(presses, start=1):
    data = press_data.get(press, {})
    with tabs[idx]:
        st.subheader(TXT["keywords"])
        st.write(", ".join(data.get("keywords", [])) or "-")

        st.subheader(TXT["emphasis"])
        st.write(data.get("emphasis_sentence", "-"))

        st.subheader(TXT["titles"])
        for title in data.get("titles", []):
            st.write(f"- {title}")

        st.subheader(TXT["evidence"])
        for sentence in data.get("evidence", []):
            st.write(f"- {sentence}")
