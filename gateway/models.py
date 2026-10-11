from django.db import models


class Platform(models.Model):
    """A platform (e.g. the WP site) that calls tools through the gateway."""

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=64, unique=True)
    contact = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class ApiKey(models.Model):
    """A platform key. Only the prefix and the SHA-256 of the whole key are stored."""

    platform = models.ForeignKey(Platform, on_delete=models.PROTECT, related_name='api_keys')
    prefix = models.CharField(max_length=8, unique=True, editable=False)
    key_hash = models.CharField(max_length=64, editable=False)
    label = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'API key'

    def __str__(self):
        return f'gw_{self.prefix}_…'
