from django.contrib.admin.sites import site
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from topic_extraction.models import Topic


class TopicAdminTest(TestCase):
    def setUp(self):
        call_command('seed_taxonomy')

    def test_admin_is_registered(self):
        self.assertIn(Topic, site._registry)

    def test_label_en_is_readonly(self):
        admin_cls = site._registry[Topic]
        self.assertIn('label_en', admin_cls.readonly_fields)

    def test_labels_is_readonly(self):
        admin_cls = site._registry[Topic]
        self.assertIn('labels', admin_cls.readonly_fields)

    def test_slug_is_readonly(self):
        admin_cls = site._registry[Topic]
        self.assertIn('slug', admin_cls.readonly_fields)

    def test_topic_admin_blocks_delete(self):
        admin_cls = site._registry[Topic]
        # has_delete_permission must return False regardless of object or request
        self.assertFalse(admin_cls.has_delete_permission(None))
        self.assertFalse(admin_cls.has_delete_permission(None, obj=Topic.objects.first()))


class TopicParentDeactivationGuardTest(TestCase):
    def setUp(self):
        call_command('seed_taxonomy')

    def test_parent_cannot_be_deactivated(self):
        parent = Topic.objects.filter(parent__isnull=True).first()
        parent.is_active = False
        with self.assertRaises(ValidationError):
            parent.full_clean()


class ArticleTopicAdminTest(TestCase):
    def setUp(self):
        call_command('seed_taxonomy')

    def test_admin_is_registered(self):
        from topic_extraction.models import ArticleTopic
        self.assertIn(ArticleTopic, site._registry)

    def test_article_topic_admin_blocks_delete(self):
        from topic_extraction.models import ArticleTopic
        admin_cls = site._registry[ArticleTopic]
        self.assertFalse(admin_cls.has_delete_permission(None))


class ArticleEmbeddingAdminTest(TestCase):
    def setUp(self):
        call_command('seed_taxonomy')

    def test_admin_is_registered(self):
        from topic_extraction.models import ArticleEmbedding
        self.assertIn(ArticleEmbedding, site._registry)

    def test_all_fields_are_readonly(self):
        from topic_extraction.models import ArticleEmbedding
        admin_cls = site._registry[ArticleEmbedding]
        for field in ('id', 'platform', 'article_id', 'language', 'vector',
                      'embedding_model_name', 'computed_at'):
            self.assertIn(field, admin_cls.readonly_fields)

    def test_admin_blocks_delete(self):
        from topic_extraction.models import ArticleEmbedding
        admin_cls = site._registry[ArticleEmbedding]
        self.assertFalse(admin_cls.has_delete_permission(None))
