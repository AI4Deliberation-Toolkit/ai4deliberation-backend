from django.core.management.base import BaseCommand, CommandError
from topic_extraction import pipeline


INGESTOR_REGISTRY = {
    'ypepth': ('topic_extraction.ingestors.xls', 'XLSIngestor'),
}


class Command(BaseCommand):
    help = (
        'Load conversations from a platform data source and run topic extraction on each. '
        'Example: python manage.py ingest --platform ypepth --source data.xls'
    )

    def add_arguments(self, parser):
        parser.add_argument('--platform', required=True, help='Platform identifier (e.g. ypepth)')
        parser.add_argument('--source', required=True, help='File path or URL to load data from')

    def handle(self, *args, **options):
        platform = options['platform']
        source = options['source']

        if platform not in INGESTOR_REGISTRY:
            raise CommandError(
                f'Unknown platform: {platform!r}. '
                f'Available: {list(INGESTOR_REGISTRY.keys())}'
            )

        module_path, class_name = INGESTOR_REGISTRY[platform]
        import importlib
        module = importlib.import_module(module_path)
        ingestor_cls = getattr(module, class_name)
        ingestor = ingestor_cls(platform=platform)

        self.stdout.write(f'Loading conversations from {source!r}...')
        conversations = ingestor.load(source)
        self.stdout.write(f'Found {len(conversations)} conversations.')

        for i, conv in enumerate(conversations, 1):
            self.stdout.write(f'[{i}/{len(conversations)}] Processing: {conv.article_id[:60]}')
            try:
                pipeline.run(
                    article_id=conv.article_id,
                    platform=conv.platform,
                    article=conv.article,
                    comments=conv.comments,
                )
            except Exception as e:
                self.stderr.write(f'  ERROR: {e}')

        self.stdout.write(self.style.SUCCESS('Done.'))
