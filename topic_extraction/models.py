import uuid
from django.db import models


class Topic(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(unique=True, max_length=100)
    label_en = models.CharField(max_length=200)
    labels = models.JSONField(default=dict)
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='children'
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.slug

    # Admin-form-only guard: bypassed by .update() and raw SQL. Not a DB constraint.
    def clean(self):
        super().clean()
        if self.parent_id is None and not self.is_active:
            from django.core.exceptions import ValidationError
            raise ValidationError(
                'Parents (topics with no parent of their own) may not be deactivated. '
                'Remove the parent from taxonomy_data.PARENTS to retire it.'
            )


class ArticleTopic(models.Model):
    BACKEND_LLM = 'llm'
    BACKEND_EMBEDDING = 'embedding'
    BACKEND_CHOICES = [
        (BACKEND_LLM, 'LLM'),
        (BACKEND_EMBEDDING, 'Embedding'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    article_id = models.CharField(max_length=255, db_index=True)
    platform = models.CharField(max_length=100, db_index=True)
    language = models.CharField(max_length=10)
    raw_topics = models.JSONField(default=list)
    normalized = models.JSONField(default=list)
    backend = models.CharField(max_length=20, choices=BACKEND_CHOICES)
    taxonomy_version = models.CharField(max_length=20, blank=True, default='')
    language_source = models.CharField(max_length=20, blank=True, default='')
    computed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.platform}/{self.article_id}'

    class Meta:
        ordering = ['-computed_at']


class ArticleEmbedding(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    article_id = models.CharField(max_length=255)
    platform = models.CharField(max_length=100)
    language = models.CharField(max_length=10)
    vector = models.JSONField()
    embedding_model_name = models.CharField(max_length=200)
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('platform', 'article_id')]
        indexes = [
            models.Index(fields=['platform', 'language', 'embedding_model_name']),
        ]
        ordering = ['-computed_at']

    def __str__(self):
        return f'{self.platform}/{self.article_id}'
