from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from topic_extraction.models import Topic
from topic_extraction.taxonomy import invalidate_taxonomy_cache
from topic_extraction import taxonomy_data


class Command(BaseCommand):
    help = (
        'Seed Topic table from taxonomy_data.PARENTS and LEAVES. '
        'Idempotent: upserts on slug, never sets is_active=True on existing rows, '
        'flips is_active=False for slugs no longer in code.'
    )

    def handle(self, *args, **options):
        # Integrity check: every leaf's parent must be a known PARENTS slug.
        parent_slugs = {p['slug'] for p in taxonomy_data.PARENTS}
        orphans = [leaf['slug'] for leaf in taxonomy_data.LEAVES if leaf['parent'] not in parent_slugs]
        if orphans:
            raise CommandError(
                f'Orphan leaves (parent slug not in PARENTS): {orphans}. '
                f'Fix taxonomy_data.py before seeding.'
            )

        code_slugs = parent_slugs | {leaf['slug'] for leaf in taxonomy_data.LEAVES}

        created = 0
        updated = 0
        deactivated = 0

        with transaction.atomic():
            # Pass 1: upsert PARENTS (parent=None always).
            for entry in taxonomy_data.PARENTS:
                topic, was_created = Topic.objects.get_or_create(
                    slug=entry['slug'],
                    defaults={
                        'label_en': entry['label_en'],
                        'labels': entry.get('labels') or {},
                        'parent': None,
                    },
                )
                if was_created:
                    created += 1
                else:
                    # Update label_en, labels, parent. DO NOT touch is_active.
                    topic.label_en = entry['label_en']
                    topic.labels = entry.get('labels') or {}
                    topic.parent = None
                    topic.save(update_fields=['label_en', 'labels', 'parent'])
                    updated += 1

            # Pass 2: upsert LEAVES (parent points at the corresponding PARENTS row).
            for entry in taxonomy_data.LEAVES:
                parent = Topic.objects.get(slug=entry['parent'])
                topic, was_created = Topic.objects.get_or_create(
                    slug=entry['slug'],
                    defaults={
                        'label_en': entry['label_en'],
                        'labels': entry.get('labels') or {},
                        'parent': parent,
                    },
                )
                if was_created:
                    created += 1
                else:
                    topic.label_en = entry['label_en']
                    topic.labels = entry.get('labels') or {}
                    topic.parent = parent
                    topic.save(update_fields=['label_en', 'labels', 'parent'])
                    updated += 1

            # Pass 3: deactivate slugs no longer in code.
            stale = Topic.objects.exclude(slug__in=code_slugs).filter(is_active=True)
            deactivated = stale.update(is_active=False)

        invalidate_taxonomy_cache()

        self.stdout.write(self.style.SUCCESS(
            f'Done. Created: {created}, updated: {updated}, deactivated: {deactivated}'
        ))
