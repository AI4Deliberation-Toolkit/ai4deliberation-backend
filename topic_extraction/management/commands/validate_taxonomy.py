from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from topic_extraction.models import Topic


class Command(BaseCommand):
    help = (
        'Validate that every active Topic has a translation in every language '
        'listed in settings.TOPIC_LANGUAGES. Fails with non-zero exit if any '
        '(slug, language) pair is missing.'
    )

    def handle(self, *args, **options):
        languages = list(settings.TOPIC_LANGUAGES)
        # The canonical English label is on label_en, not labels['en']. Skip 'en'.
        languages_to_check = [lang for lang in languages if lang != 'en']

        gaps = []
        for topic in Topic.objects.filter(is_active=True):
            for lang in languages_to_check:
                if not topic.labels.get(lang):
                    gaps.append((topic.slug, lang))

        if gaps:
            lines = [f'  - {slug} missing translation for {lang}' for slug, lang in gaps]
            raise CommandError(
                f'Translation coverage incomplete ({len(gaps)} gaps):\n' + '\n'.join(lines)
            )

        self.stdout.write(self.style.SUCCESS(
            f'OK — {Topic.objects.filter(is_active=True).count()} active topics, '
            f'all translated for: {languages_to_check}'
        ))
