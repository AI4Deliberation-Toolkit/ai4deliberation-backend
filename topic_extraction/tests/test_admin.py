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


class TopicParentDeactivationGuardTest(TestCase):
    def setUp(self):
        call_command('seed_taxonomy')

    def test_parent_cannot_be_deactivated(self):
        parent = Topic.objects.filter(parent__isnull=True).first()
        parent.is_active = False
        with self.assertRaises(ValidationError):
            parent.full_clean()
