from rest_framework import views, status
from rest_framework.response import Response

from topic_extraction import pipeline
from topic_extraction.models import ArticleTopic, Topic

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
        record = ArticleTopic.objects.filter(article_id=article_id).first()
        if record is None:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            'article_id': record.article_id,
            'platform': record.platform,
            'language': record.language,
            'raw_topics': record.raw_topics,
            'normalized': record.normalized,
            'backend': record.backend,
            'computed_at': record.computed_at.isoformat(),
        })
