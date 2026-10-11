import hashlib
import re

from django.test import TestCase
from django.utils import timezone

from gateway.keys import averify_key, generate_key, hash_key, issue_key
from gateway.models import ApiKey, Platform

KEY_RE = re.compile(r'^gw_[A-Z2-7]{8}_[0-9a-f]{64}$')


class KeyFormatTests(TestCase):
    def test_generated_keys_match_the_format(self):
        prefix, key = generate_key()
        self.assertRegex(key, KEY_RE)
        self.assertEqual(key[3:11], prefix)

    def test_keys_are_unique(self):
        self.assertNotEqual(generate_key(), generate_key())

    def test_hash_is_sha256_of_the_whole_key(self):
        _, key = generate_key()
        self.assertEqual(hash_key(key), hashlib.sha256(key.encode()).hexdigest())


class IssueKeyTests(TestCase):
    def setUp(self):
        self.platform = Platform.objects.create(name='WP site', slug='wp-site')

    def test_only_prefix_and_hash_are_stored(self):
        key, api_key = issue_key(self.platform, label='production')
        api_key.refresh_from_db()
        self.assertEqual(api_key.prefix, key[3:11])
        self.assertEqual(api_key.key_hash, hash_key(key))
        stored = [str(getattr(api_key, f.attname)) for f in ApiKey._meta.fields]
        self.assertFalse(any(key in value for value in stored))
        self.assertFalse(any(key[12:] in value for value in stored))  # nor the secret part
        self.assertNotIn(key[12:], str(api_key))


class VerifyKeyTests(TestCase):
    def setUp(self):
        self.platform = Platform.objects.create(name='WP site', slug='wp-site')
        self.key, self.api_key = issue_key(self.platform)

    async def test_valid_key(self):
        api_key = await averify_key(self.key)
        self.assertEqual(api_key.pk, self.api_key.pk)
        self.assertEqual(api_key.platform.slug, 'wp-site')  # loaded, no extra query needed

    async def test_wrong_secret(self):
        wrong = self.key[:-1] + ('0' if self.key[-1] != '0' else '1')
        self.assertIsNone(await averify_key(wrong))

    async def test_unknown_prefix(self):
        _, other = generate_key()
        self.assertIsNone(await averify_key(other))

    async def test_malformed(self):
        for value in (None, '', 'gw_abc', self.key.lower(), self.key + '\n', ' ' + self.key, 'Bearer ' + self.key):
            with self.subTest(value=value):
                self.assertIsNone(await averify_key(value))

    async def test_revoked(self):
        await ApiKey.objects.filter(pk=self.api_key.pk).aupdate(revoked_at=timezone.now())
        self.assertIsNone(await averify_key(self.key))

    async def test_inactive_platform(self):
        await Platform.objects.filter(pk=self.platform.pk).aupdate(is_active=False)
        self.assertIsNone(await averify_key(self.key))
