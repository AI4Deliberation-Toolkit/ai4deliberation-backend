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

            # Pass 3a: soft-deactivate stale LEAVES (existing semantics, scoped to leaves only).
            # Leaves are identified by parent__isnull=False; runtime curation via admin
            # is supported per D9 so deletion is not appropriate.
            stale_leaves = Topic.objects.exclude(slug__in=code_slugs).filter(
                parent__isnull=False, is_active=True
            )
            deactivated = stale_leaves.update(is_active=False)

            # Pass 3b: hard-delete stale PARENTS after active-leaf-reference check (D10).
            # Parents are pure aggregation nodes — they should not linger as soft-deactivated
            # rows pointing-at by other rows. Topic.parent uses on_delete=SET_NULL, so any
            # inactive leaf still referencing the parent gets its FK cleared on delete; the
            # orphan-check below catches the only state that would be unsafe: an ACTIVE leaf
            # in the DB still pointing at a parent that's being removed from code. By
            # this point Pass 3a has already deactivated stale leaves, so the check is
            # defensive against an inconsistent DB state (e.g., admin manually toggled
            # is_active back on a leaf), not the normal seed flow.
            stale_parents = Topic.objects.exclude(slug__in=code_slugs).filter(parent__isnull=True)
            deleted_parents = 0
            for stale_parent in stale_parents:
                active_refs = list(
                    Topic.objects.filter(parent=stale_parent, is_active=True)
                    .values_list('slug', flat=True)
                )
                if active_refs:
                    raise CommandError(
                        f'Cannot remove parent {stale_parent.slug!r}: '
                        f'active leaves still reference it: {active_refs}. '
                        f'Update taxonomy_data.py to remove or reparent these leaves first.'
                    )
                stale_parent.delete()
                deleted_parents += 1

        invalidate_taxonomy_cache()

        self.stdout.write(self.style.SUCCESS(
            f'Done. Created: {created}, updated: {updated}, deactivated: {deactivated}, deleted: {deleted_parents}'
        ))
