import time
import uuid
from django.db import IntegrityError
from django.test import TestCase
from topic_extraction.models import Topic, ArticleTopic, ArticleEmbedding


class TopicModelTest(TestCase):
    def test_create_topic(self):
        topic = Topic.objects.create(
            slug='education_policy',
            label_en='Education Policy',
            labels={'el': 'Εκπαιδευτική Πολιτική', 'fr': 'Politique éducative'},
        )
        self.assertIsInstance(topic.id, uuid.UUID)
        self.assertEqual(topic.slug, 'education_policy')
        self.assertEqual(topic.labels['el'], 'Εκπαιδευτική Πολιτική')
        self.assertIsNone(topic.parent)

    def test_topic_str(self):
        topic = Topic.objects.create(slug='climate_policy', label_en='Climate Policy', labels={})
        self.assertEqual(str(topic), 'climate_policy')

    def test_topic_parent_relationship(self):
        parent = Topic.objects.create(slug='social_policy', label_en='Social Policy', labels={})
        child = Topic.objects.create(
            slug='education_policy', label_en='Education Policy', labels={}, parent=parent
        )
        self.assertEqual(child.parent.slug, 'social_policy')
        self.assertIn(child, parent.children.all())


class TopicIsActiveTest(TestCase):
    def test_topic_defaults_to_active(self):
        t = Topic.objects.create(slug='test_x', label_en='Test X')
        self.assertTrue(t.is_active)

    def test_topic_can_be_deactivated(self):
        t = Topic.objects.create(slug='test_y', label_en='Test Y', is_active=False)
        self.assertFalse(t.is_active)


class ArticleTopicModelTest(TestCase):
    def test_create_article_topic(self):
        record = ArticleTopic.objects.create(
            article_id='article-123',
            platform='ypepth',
            language='el',
            raw_topics=[{'label': 'Εκπαιδευτική Πολιτική', 'score': 0.9}],
            normalized=[{'topic_id': 'education_policy', 'score': 0.9}],
            backend='embedding',
        )
        self.assertIsInstance(record.id, uuid.UUID)
        self.assertEqual(record.article_id, 'article-123')
        self.assertIsNotNone(record.computed_at)

    def test_article_topic_ordering_newest_first(self):
        from datetime import datetime, timezone, timedelta
        from unittest.mock import patch

        t1 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        t2 = t1 + timedelta(seconds=1)

        with patch('django.utils.timezone.now', side_effect=[t1, t2]):
            ArticleTopic.objects.create(
                article_id='art-1', platform='p', language='el',
                raw_topics=[], normalized=[], backend='embedding',
            )
            ArticleTopic.objects.create(
                article_id='art-1', platform='p', language='el',
                raw_topics=[], normalized=[], backend='llm',
            )
        records = list(ArticleTopic.objects.filter(article_id='art-1'))
        self.assertGreaterEqual(records[0].computed_at, records[1].computed_at)


class ArticleTopicTaxonomyVersionTest(TestCase):
    def test_existing_rows_default_to_empty_string(self):
        at = ArticleTopic.objects.create(
            article_id='a1', platform='p1', language='en',
            raw_topics=[], normalized=[], backend='embedding',
        )
        self.assertEqual(at.taxonomy_version, '')

    def test_taxonomy_version_can_be_set(self):
        at = ArticleTopic.objects.create(
            article_id='a2', platform='p1', language='en',
            raw_topics=[], normalized=[], backend='embedding',
            taxonomy_version='2026-05-15-1',
        )
        self.assertEqual(at.taxonomy_version, '2026-05-15-1')


class ArticleTopicLanguageSourceTest(TestCase):
    def test_existing_rows_default_to_empty_string(self):
        at = ArticleTopic.objects.create(
            article_id='a1', platform='p1', language='en',
            raw_topics=[], normalized=[], backend='embedding',
        )
        self.assertEqual(at.language_source, '')

    def test_language_source_can_be_set(self):
        at = ArticleTopic.objects.create(
            article_id='a2', platform='p1', language='en',
            raw_topics=[], normalized=[], backend='embedding',
            language_source='explicit',
        )
        self.assertEqual(at.language_source, 'explicit')


class ArticleEmbeddingTest(TestCase):
    def test_create_with_required_fields(self):
        emb = ArticleEmbedding.objects.create(
            platform='opengov',
            article_id='123',
            language='el',
            vector=[0.1, 0.2, 0.3],
            embedding_model_name='paraphrase-multilingual-mpnet-base-v2',
        )
        self.assertEqual(emb.platform, 'opengov')
        self.assertEqual(emb.article_id, '123')
        self.assertEqual(emb.language, 'el')
        self.assertEqual(emb.vector, [0.1, 0.2, 0.3])
        self.assertEqual(emb.embedding_model_name, 'paraphrase-multilingual-mpnet-base-v2')
        self.assertIsNotNone(emb.computed_at)
        self.assertIsInstance(emb.id, uuid.UUID)

    def test_unique_together_on_platform_and_article_id(self):
        ArticleEmbedding.objects.create(
            platform='opengov',
            article_id='123',
            language='el',
            vector=[0.1],
            embedding_model_name='m1',
        )
        with self.assertRaises(IntegrityError):
            ArticleEmbedding.objects.create(
                platform='opengov',
                article_id='123',
                language='el',
                vector=[0.2],
                embedding_model_name='m2',
            )

    def test_upsert_via_update_or_create(self):
        emb1, created1 = ArticleEmbedding.objects.update_or_create(
            platform='opengov',
            article_id='123',
            defaults={
                'language': 'el',
                'vector': [0.1],
                'embedding_model_name': 'm1',
            }
        )
        self.assertTrue(created1)

        emb2, created2 = ArticleEmbedding.objects.update_or_create(
            platform='opengov',
            article_id='123',
            defaults={
                'language': 'en',
                'vector': [0.2],
                'embedding_model_name': 'm2',
            }
        )
        self.assertFalse(created2)
        self.assertEqual(emb1.id, emb2.id)
        self.assertEqual(emb2.vector, [0.2])
        self.assertEqual(emb2.language, 'en')
        self.assertEqual(emb2.embedding_model_name, 'm2')

    def test_computed_at_updates_on_save(self):
        emb = ArticleEmbedding.objects.create(
            platform='opengov',
            article_id='123',
            language='el',
            vector=[0.1],
            embedding_model_name='m1',
        )
        initial_ts = emb.computed_at
        time.sleep(0.01)
        emb.vector = [0.2]
        emb.save()
        emb.refresh_from_db()
        self.assertGreater(emb.computed_at, initial_ts)

    def test_string_representation(self):
        emb = ArticleEmbedding.objects.create(
            platform='opengov',
            article_id='123',
            language='el',
            vector=[0.1],
            embedding_model_name='m1',
        )
        self.assertEqual(str(emb), 'opengov/123')

    def test_different_platform_or_article_id_allowed(self):
        ArticleEmbedding.objects.create(
            platform='opengov', article_id='123', language='el',
            vector=[0.1], embedding_model_name='m1',
        )
        ArticleEmbedding.objects.create(
            platform='bridge', article_id='123', language='el',
            vector=[0.2], embedding_model_name='m1',
        )
        ArticleEmbedding.objects.create(
            platform='opengov', article_id='456', language='el',
            vector=[0.3], embedding_model_name='m1',
        )
        self.assertEqual(ArticleEmbedding.objects.count(), 3)
