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

    def __str__(self):
        return self.slug


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
    computed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-computed_at']
