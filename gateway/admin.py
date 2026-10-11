from django.contrib import admin
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.cache import add_never_cache_headers

from gateway.keys import assign_new_key
from gateway.models import ApiKey, Platform


@admin.register(Platform)
class PlatformAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'platform', 'label', 'created_at', 'revoked_at')
    list_filter = ('platform',)
    actions = ('revoke_keys',)
    _detail_fields = ('platform', 'label', 'prefix', 'key_hash', 'created_at', 'revoked_at')

    def get_fields(self, request, obj=None):
        return ('platform', 'label') if obj is None else self._detail_fields

    def get_readonly_fields(self, request, obj=None):
        # After issuing, only the label can change.
        return () if obj is None else tuple(f for f in self._detail_fields if f != 'label')

    def has_delete_permission(self, request, obj=None):
        return False  # revoke instead, so the key history stays intact

    def save_model(self, request, obj, form, change):
        if not change:
            obj._issued_key = assign_new_key(obj)
        super().save_model(request, obj, form, change)

    def response_add(self, request, obj, post_url_continue=None):
        """Show the key once on its own page: never through `messages`, which cookies and sessions carry."""
        response = TemplateResponse(request, 'admin/gateway/apikey/issued.html', {
            **self.admin_site.each_context(request),
            'title': 'API key issued',
            'opts': self.model._meta,
            'api_key': obj,
            'issued_key': obj._issued_key,
        })
        add_never_cache_headers(response)
        return response

    @admin.action(description='Revoke selected keys')
    def revoke_keys(self, request, queryset):
        count = queryset.filter(revoked_at__isnull=True).update(revoked_at=timezone.now())
        self.message_user(request, f'Revoked {count} key(s).')
