
import os
from collections import defaultdict

import django
import numpy as np
from bertopic import BERTopic
from django.apps import apps as django_apps
from fastapi import FastAPI, HTTPException, Response, Header
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer, util
from transformers import pipeline
from umap import UMAP

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai4deliberation_backend.settings.settings')
if not django_apps.ready:
    django.setup()

from ai_tools.utils import categorization
from topic_extraction import pipeline as topic_pipeline

app = FastAPI()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#EMBEDDING_MODEL_NAME = "sentence-transformers/distiluse-base-multilingual-cased-v2" # empty topics
#EMBEDDING_MODEL_NAME = "joeddav/xlm-roberta-large-xnli" # 3 irrelevant topics
#EMBEDDING_MODEL_NAME = "sentence-transformers/all-roberta-large-v1" # empty
EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2" # 3 somewhat relevant, low confidence

TOPIC_LABELS = [

    # GOVERNANCE
    "democratic governance",
    "public institutions",
    "policy making",
    "regulation",
    "institutional design",

    # PARTICIPATION & DELIBERATION
    "citizen engagement",
    "deliberative processes",
    "public reasoning",
    "collective decision making",
    "participatory mechanisms",

    # DISCOURSE & INFORMATION
    "public discourse",
    "political communication",
    "media ecosystems",
    "information quality",
    "online communities",

    # TECHNOLOGY
    "artificial intelligence",
    "digital infrastructure",
    "platform governance",
    "algorithmic systems",
    "data driven decision making",

    # SOCIETAL IMPACT
    "social impact",
    "economic impact",
    "environmental impact",
    "technological change",
    "societal transformation",

    # RIGHTS & ETHICS
    "human rights",
    "ethical considerations",
    "fairness",
    "accountability",
    "transparency",

    # POLICY AREAS
    "climate policy",
    "energy policy",
    "education systems",
    "health systems",
    "labor markets",
    "migration policy",
    "urban policy",

    # POWER & JUSTICE
    "inequality",
    "social justice",
    "access and inclusion",
    "representation",
    "minority protection",

    # DIGITAL PUBLIC SPACE
    "digital participation",
    "online platforms",
    "content moderation",
    "freedom of expression",
    "trust and safety",

    # COMMUNITY & CIVIC LIFE
    "civil society",
    "community engagement",
    "grassroots initiatives",
    "collective action",
    "social cohesion",

    # DEMOCRACY & GOVERNANCE
    "democracy",
    "digital democracy",
    "deliberative democracy",
    "citizen participation",
    "civic engagement",
    "public consultation",
    "citizen assemblies",
    "participatory governance",
    "public decision making",
    "institutional trust",
    "government transparency",
    "accountability",
    "rule of law",
    "electoral systems",
    "voting and elections",

    # DELIBERATION & PUBLIC DISCOURSE
    "online deliberation",
    "public debate",
    "argumentation",
    "consensus building",
    "polarization",
    "misinformation",
    "disinformation",
    "media literacy",
    "freedom of expression",
    "moderation and governance of speech",

    # POLICY DOMAINS
    "public policy",
    "social policy",
    "economic policy",
    "environmental policy",
    "climate change",
    "energy transition",
    "healthcare policy",
    "education policy",
    "migration",
    "urban development",
    "housing",
    "transportation",
    "labor and employment",
    "inequality",
    "social justice",

    # TECHNOLOGY & SOCIETY
    "artificial intelligence",
    "algorithmic decision making",
    "automation",
    "digital platforms",
    "social media",
    "data governance",
    "privacy and data protection",
    "cybersecurity",
    "surveillance technologies",
    "open data",
    "digital inclusion",

    # RIGHTS, VALUES & ETHICS
    "human rights",
    "civil liberties",
    "ethical governance",
    "transparency in AI",
    "bias and fairness",
    "accountability in technology",
    "accessibility",
    "inclusion",
    "minority rights",
    "gender equality",
    "intergenerational justice",

    # CIVIC & COMMUNITY LIFE
    "community building",
    "local governance",
    "grassroots movements",
    "non governmental organizations",
    "civil society",
    "volunteering",
    "collective action",
    "social cohesion",

]

CANDIDATE_TOPICS = [

    # DEMOCRACY & GOVERNANCE
    "democracy",
    "digital democracy",
    "deliberative democracy",
    "citizen participation",
    "civic engagement",
    "public consultation",
    "citizen assemblies",
    "participatory governance",
    "public decision making",
    "institutional trust",
    "government transparency",
    "accountability",
    "rule of law",
    "electoral systems",
    "voting and elections",

    # DELIBERATION & PUBLIC DISCOURSE
    "online deliberation",
    "public debate",
    "argumentation",
    "consensus building",
    "polarization",
    "misinformation",
    "disinformation",
    "media literacy",
    "freedom of expression",
    "moderation and governance of speech",

    # POLICY DOMAINS
    "public policy",
    "social policy",
    "economic policy",
    "environmental policy",
    "climate change",
    "energy transition",
    "healthcare policy",
    "education policy",
    "migration",
    "urban development",
    "housing",
    "transportation",
    "labor and employment",
    "inequality",
    "social justice",

    # TECHNOLOGY & SOCIETY
    "artificial intelligence",
    "algorithmic decision making",
    "automation",
    "digital platforms",
    "social media",
    "data governance",
    "privacy and data protection",
    "cybersecurity",
    "surveillance technologies",
    "open data",
    "digital inclusion",

    # RIGHTS, VALUES & ETHICS
    "human rights",
    "civil liberties",
    "ethical governance",
    "transparency in AI",
    "bias and fairness",
    "accountability in technology",
    "accessibility",
    "inclusion",
    "minority rights",
    "gender equality",
    "intergenerational justice",

    # CIVIC & COMMUNITY LIFE
    "community building",
    "local governance",
    "grassroots movements",
    "non governmental organizations",
    "civil society",
    "volunteering",
    "collective action",
    "social cohesion",

]


# ==================
# Pydantic models
# ==================

class TextIn(BaseModel):
    text: str

class CategorizationOut(BaseModel):
    topics: list

class SingleArticleInput(BaseModel):
    text: str

class TopicOut(BaseModel):
    topic: str
    score: float

class TopicsResponse(BaseModel):
    topics: list[TopicOut]

class ConversationIn(BaseModel):
    article_id: str
    platform: str
    article: str
    comments: list[str] = []
    language: str | None = None

class ConversationTopicsOut(BaseModel):
    id: str
    language: str
    raw_topics: list
    normalized: list
    backend: str


# ==================
# Embedding
# ==================

_embedding_model = None

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _embedding_model


def embed_texts(texts: list[str]):
    model = get_embedding_model()
    return model.encode(
        texts,
        convert_to_numpy=True,
        show_progress_bar=False,
    )


# ==================
# BERTopic model
# ==================

_topic_model = None

def get_topic_model():
    """global _topic_model
    if _topic_model is None:
        _topic_model = BERTopic(
            embedding_model=get_embedding_model(),
            language="multilingual",
            calculate_probabilities=True,
            verbose=True,
            min_topic_size=2,
        )
    return _topic_model"""

    umap_model = UMAP(
        n_neighbors=2,
        n_components=2,
        min_dist=0.0,
        metric="cosine",
    )

    return BERTopic(
        embedding_model=get_embedding_model(),
        umap_model=umap_model,
        language="multilingual",
        calculate_probabilities=True,
        verbose=True,
        min_topic_size=2,
    )


def extract_topics(documents: list[str]):
    model = get_topic_model()
    topics, probs = model.fit_transform(documents)
    topic_info = model.get_topic_info()
    return topics, probs, topic_info


def group_by_topic(documents, topic_ids):
    grouped = defaultdict(list)
    for doc, topic_id in zip(documents, topic_ids):
        grouped[int(topic_id)].append(doc)
    return grouped


# ==================
# Recommendation
# ==================

def recommend_related(
    current_text: str,
    all_texts: list[str],
    top_k: int = 5,
):
    embeddings = embed_texts(all_texts)
    query_emb = embed_texts([current_text])[0]

    scores = util.cos_sim(query_emb, embeddings)[0].numpy()
    best_indices = np.argsort(scores)[::-1][1 : top_k + 1]

    return [
        {"text": all_texts[i], "score": float(scores[i])}
        for i in best_indices
    ]


# ======================================================
# Single-article topic extraction (embedding-based)
# ======================================================

def extract_topics_single_article(
    article_text: str,
    top_k: int = 10,
    threshold: float = 0.20,
):
    topic_descriptions = list(TOPIC_LABELS)
    topic_embeddings = embed_texts(topic_descriptions)
    article_embedding = embed_texts([article_text])[0]

    scores = util.cos_sim(article_embedding, topic_embeddings)[0]

    results = []
    for name, score in zip(topic_descriptions, scores):
        if float(score) >= threshold:
            results.append({"topic": name, "score": float(score)})

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


# ========================
# Zero-shot classifier
# ========================

classifier = pipeline(
    "zero-shot-classification",
    model="joeddav/xlm-roberta-large-xnli",
)


def extract_topics_zero_shot(article_text: str, threshold: float = 0.3):
    """
    Extract topics from a single article using zero-shot classification.
    Returns a list of {topic, score} dictionaries.
    """
    raw = classifier(
        article_text,
        CANDIDATE_TOPICS,
        multi_label=True,
    )
    topics = []
    for label, score in zip(raw["labels"], raw["scores"]):
        if score >= threshold:
            topics.append({"topic": label, "score": float(score)})
    return topics


# ==================
# Routes
# ==================

@app.post("/categorize", response_model=CategorizationOut)
def categorize_text(payload: TextIn):
    predictions = categorization([payload.text])
    # Convert numpy types to Python types:
    cleaned = [
        int(p) if hasattr(p, "item") else p
        for p in predictions
    ]
    return {"topics": cleaned}


@app.post("/topics/extract")
def extract(payload: list[str]):
    topics, probs, info = extract_topics(payload)
    return {
        "topics": topics,
        "topic_info": info.to_dict(orient="records"),
    }


@app.post("/recommend")
def recommend(payload: dict):
    return recommend_related(
        payload["current_text"],
        payload["all_texts"]
    )


@app.post("/topics/single/zero-shot", response_model=TopicsResponse)
def extract_single_zero_shot(payload: SingleArticleInput):
    topics = extract_topics_zero_shot(payload.text)
    return {"topics": topics}


@app.post("/topics/single")
def extract_single(payload: SingleArticleInput):
    return {
        "topics": extract_topics_single_article(payload.text)
    }


@app.post("/topics/extract-conversation")
def extract_conversation(payload: ConversationIn, include_labels: bool = False, include_raw: bool = False):
    try:
        record = topic_pipeline.run(
            article_id=payload.article_id,
            platform=payload.platform,
            article=payload.article,
            comments=payload.comments,
            explicit_language=payload.language,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Topic extraction failed: {e}')

    body = {
        'id': str(record.id),
        'article_id': record.article_id,
        'platform': record.platform,
        'language': record.language,
        'language_source': record.language_source,
        'normalized': _serialize_normalized_fastapi(record.normalized, include_labels, record.language),
        'backend': record.backend,
        'computed_at': record.computed_at.isoformat(),
        'taxonomy_version': record.taxonomy_version,
    }
    if include_raw:
        body['raw_topics'] = record.raw_topics
    return body


def _serialize_normalized_fastapi(normalized, include_labels, language):
    if not include_labels:
        return normalized
    from topic_extraction.models import Topic
    slugs = [n['topic_id'] for n in normalized]
    topic_map = {t.slug: t for t in Topic.objects.filter(slug__in=slugs).select_related('parent')}
    out = []
    for n in normalized:
        topic = topic_map.get(n['topic_id'])
        if topic is None or not topic.is_active:
            out.append({**n, 'label': None, 'parent': None})
        else:
            label = topic.labels.get(language) or topic.label_en
            parent_slug = topic.parent.slug if topic.parent else None
            out.append({**n, 'label': label, 'parent': parent_slug})
    return out


@app.get("/topics/article/{article_id}")
def get_article_topics(article_id: str, include_labels: bool = False, include_raw: bool = False):
    from topic_extraction.models import ArticleTopic
    record = (
        ArticleTopic.objects
        .filter(article_id=article_id)
        .order_by('-computed_at')
        .first()
    )
    if record is None:
        raise HTTPException(status_code=404, detail='Not found.')
    body = {
        'id': str(record.id),
        'article_id': record.article_id,
        'platform': record.platform,
        'language': record.language,
        'normalized': _serialize_normalized_fastapi(record.normalized, include_labels, record.language),
        'backend': record.backend,
        'computed_at': record.computed_at.isoformat(),
        'taxonomy_version': record.taxonomy_version,
    }
    if record.language_source:
        body['language_source'] = record.language_source
    if include_raw:
        body['raw_topics'] = record.raw_topics
    return body


@app.get("/topics")
def topics_listing(
    response: Response,
    language: str | None = None,
    if_none_match: str | None = Header(default=None),
):
    from django.conf import settings
    from topic_extraction.taxonomy import get_topics_for_listing
    from topic_extraction.taxonomy_data import TAXONOMY_VERSION

    lang = language or settings.DEFAULT_LANGUAGE
    if lang not in settings.TOPIC_LANGUAGES:
        raise HTTPException(status_code=400, detail=f'Unsupported language: {lang!r}')

    etag = f'"{TAXONOMY_VERSION}-{lang}"'
    if if_none_match == etag:
        return Response(status_code=304, headers={'ETag': etag})

    data = get_topics_for_listing(lang)
    body = {'version': TAXONOMY_VERSION, 'language': lang, **data}
    response.headers['ETag'] = etag
    response.headers['Cache-Control'] = 'public, max-age=300'
    return body
