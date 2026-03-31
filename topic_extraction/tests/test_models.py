import uuid
from django.test import TestCase
from topic_extraction.models import Topic, ArticleTopic


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
