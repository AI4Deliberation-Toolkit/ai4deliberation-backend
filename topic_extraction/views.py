from rest_framework import views, status
from rest_framework.response import Response

from topic_extraction import pipeline
from topic_extraction.models import ArticleTopic

REQUIRED_FIELDS = ('article_id', 'platform', 'article')


class ExtractConversationView(views.APIView):
    def post(self, request):
        missing = [f for f in REQUIRED_FIELDS if not request.data.get(f)]
        if missing:
            return Response(
                {'error': f'Missing required fields: {missing}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            record = pipeline.run(
                article_id=request.data['article_id'],
                platform=request.data['platform'],
                article=request.data['article'],
                comments=request.data.get('comments', []),
            )
        except Exception as e:
            return Response(
                {'detail': 'Topic extraction failed.', 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(
            {
                'id': str(record.id),
                'language': record.language,
                'raw_topics': record.raw_topics,
                'normalized': record.normalized,
                'backend': record.backend,
            },
            status=status.HTTP_201_CREATED,
        )


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
