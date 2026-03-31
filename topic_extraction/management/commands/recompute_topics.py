from django.core.management.base import BaseCommand
from topic_extraction import pipeline
from topic_extraction.models import ArticleTopic
from topic_extraction.taxonomy import invalidate_taxonomy_cache


class Command(BaseCommand):
    help = (
        'Re-run topic extraction on all previously processed articles. '
        'Use after updating the taxonomy or switching EXTRACTION_BACKEND. '
        'Example: python manage.py recompute_topics --platform ypepth'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--platform', default=None,
            help='Limit recomputation to a specific platform. Omit to recompute all.'
        )

    def handle(self, *args, **options):
        platform = options['platform']
        invalidate_taxonomy_cache()

        qs = ArticleTopic.objects.all()
        if platform:
            qs = qs.filter(platform=platform)

        # Get unique (article_id, platform) pairs from most recent records
        seen = set()
        targets = []
        for record in qs.order_by('-computed_at'):
            key = (record.article_id, record.platform)
            if key not in seen:
                seen.add(key)
                targets.append(record)

        self.stdout.write(f'Recomputing topics for {len(targets)} articles...')

        for i, record in enumerate(targets, 1):
            self.stdout.write(f'[{i}/{len(targets)}] {record.article_id[:60]}')
            try:
                # Re-run with empty comments — original comments are not stored (GDPR)
                # Article_id and platform are re-used; article text is the article_id
                pipeline.run(
                    article_id=record.article_id,
                    platform=record.platform,
                    article=record.article_id,
                    comments=[],
                )
            except Exception as e:
                self.stderr.write(f'  ERROR: {e}')

        self.stdout.write(self.style.SUCCESS('Done.'))
