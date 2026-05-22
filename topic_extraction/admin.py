from django.contrib import admin
from topic_extraction.models import Topic, ArticleTopic, ArticleEmbedding


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('slug', 'label_en', 'parent', 'is_active')
    list_filter = ('is_active', 'parent')
    search_fields = ('slug', 'label_en')
    readonly_fields = ('slug', 'label_en', 'labels')
    fields = ('slug', 'label_en', 'labels', 'parent', 'is_active')

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ArticleTopic)
class ArticleTopicAdmin(admin.ModelAdmin):
    list_display = ('article_id', 'platform', 'language', 'backend', 'taxonomy_version', 'computed_at')
    list_filter = ('platform', 'language', 'backend')
    search_fields = ('article_id',)
    readonly_fields = (
        'id', 'article_id', 'platform', 'language', 'language_source',
        'raw_topics', 'normalized', 'backend', 'taxonomy_version', 'computed_at',
    )

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ArticleEmbedding)
class ArticleEmbeddingAdmin(admin.ModelAdmin):
    list_display = ('platform', 'article_id', 'language', 'embedding_model_name', 'computed_at')
    search_fields = ('platform', 'article_id')
    readonly_fields = (
        'id', 'platform', 'article_id', 'language', 'vector',
        'embedding_model_name', 'computed_at',
    )

    def has_delete_permission(self, request, obj=None):
        return False
