from django.core.management.base import BaseCommand
from topic_extraction.models import Topic
from topic_extraction.taxonomy_data import INITIAL_TOPICS


class Command(BaseCommand):
    help = 'Seed the Topic table from the built-in taxonomy list. Safe to re-run (skips existing slugs).'

    def handle(self, *args, **options):
        created = 0
        skipped = 0
        for slug, label_en in INITIAL_TOPICS:
            _, was_created = Topic.objects.get_or_create(
                slug=slug,
                defaults={'label_en': label_en, 'labels': {}},
            )
            if was_created:
                created += 1
            else:
                skipped += 1
        self.stdout.write(
            self.style.SUCCESS(f'Done. Created: {created}, skipped (already exist): {skipped}')
        )
