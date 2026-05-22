from django.conf import settings
from rest_framework import views, status
from rest_framework.response import Response

from topic_extraction import pipeline
from topic_extraction.models import ArticleTopic, Topic
from topic_extraction.taxonomy import get_topics_for_listing
from topic_extraction.taxonomy_data import TAXONOMY_VERSION

REQUIRED_FIELDS = ('article_id', 'platform', 'article')


def _serialize_normalized(normalized, include_labels: bool, language: str):
    if not include_labels:
        return normalized
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


class ExtractConversationView(views.APIView):
    def post(self, request):
        missing = [f for f in REQUIRED_FIELDS if not request.data.get(f)]
        if missing:
            return Response(
                {'error': f'Missing required fields: {missing}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        include_labels = request.query_params.get('include_labels') == 'true'
        include_raw = request.query_params.get('include_raw') == 'true'

        try:
            record = pipeline.run(
                article_id=request.data['article_id'],
                platform=request.data['platform'],
                article=request.data['article'],
                comments=request.data.get('comments', []),
                explicit_language=request.data.get('language'),
            )
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'detail': 'Topic extraction failed.', 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        payload = {
            'id': str(record.id),
            'article_id': record.article_id,
            'platform': record.platform,
            'language': record.language,
            'language_source': record.language_source,
            'normalized': _serialize_normalized(record.normalized, include_labels, record.language),
            'backend': record.backend,
            'computed_at': record.computed_at.isoformat(),
            'taxonomy_version': record.taxonomy_version,
        }
        if include_raw:
            payload['raw_topics'] = record.raw_topics

        return Response(payload, status=status.HTTP_201_CREATED)


class ArticleTopicView(views.APIView):
    def get(self, request, article_id):
        record = (
            ArticleTopic.objects
            .filter(article_id=article_id)
            .order_by('-computed_at')
            .first()
        )
        if record is None:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        include_labels = request.query_params.get('include_labels') == 'true'
        include_raw = request.query_params.get('include_raw') == 'true'

        payload = {
            'id': str(record.id),
            'article_id': record.article_id,
            'platform': record.platform,
            'language': record.language,
            'normalized': _serialize_normalized(record.normalized, include_labels, record.language),
            'backend': record.backend,
            'computed_at': record.computed_at.isoformat(),
            'taxonomy_version': record.taxonomy_version,
        }
        if record.language_source:
            payload['language_source'] = record.language_source
        if include_raw:
            payload['raw_topics'] = record.raw_topics

        return Response(payload)


class TopicsListingView(views.APIView):
    def get(self, request):
        language = request.query_params.get('language') or settings.DEFAULT_LANGUAGE
        if language not in settings.TOPIC_LANGUAGES:
            return Response(
                {'error': f'Unsupported language: {language!r}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        etag = f'"{TAXONOMY_VERSION}-{language}"'
        if_none_match = request.headers.get('If-None-Match')
        if if_none_match == etag:
            response = Response(status=status.HTTP_304_NOT_MODIFIED)
            response['ETag'] = etag
            return response

        data = get_topics_for_listing(language)
        payload = {
            'version': TAXONOMY_VERSION,
            'language': language,
            **data,
        }
        response = Response(payload)
        response['ETag'] = etag
        response['Cache-Control'] = 'public, max-age=300'
        return response


class ArticleSimilarityView(views.APIView):
    """GET /api/articles/{platform}/{article_id}/similar?k=N&topic_slug=X

    Returns up to k articles similar to (platform, article_id), filtered to
    the same (platform, language) bucket. See similarity.py docstring and
    docs/superpowers/specs/2026-05-21-article-similarity-design.md section 5
    for the full contract.
    """

    def get(self, request, platform, article_id):
        # Parse and validate k.
        try:
            k = int(request.query_params.get('k', 10))
        except (TypeError, ValueError):
            return Response({'error': 'k must be an integer'}, status=status.HTTP_400_BAD_REQUEST)
        if k <= 0 or k > 100:
            return Response(
                {'error': 'k must be between 1 and 100'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        topic_slug = request.query_params.get('topic_slug') or None

        from topic_extraction.similarity import (
            find_similar, SourceNotFoundError, UnknownTopicSlugError,
        )
        try:
            results = find_similar(platform, article_id, k=k, topic_slug=topic_slug)
        except SourceNotFoundError:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        except UnknownTopicSlugError as e:
            return Response(
                {'error': f'Unknown topic_slug: {e.args[0]!r}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({
            'platform': platform,
            'article_id': article_id,
            'count': len(results),
            'results': [
                {
                    'platform': r.platform,
                    'article_id': r.article_id,
                    'language': r.language,
                    'raw_score': r.raw_score,
                    'z_score': r.z_score,
                }
                for r in results
            ],
        })
