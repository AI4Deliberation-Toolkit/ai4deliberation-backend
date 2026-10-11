from django import forms
from django.contrib import admin, messages
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.cache import add_never_cache_headers

from gateway.adapters import ADAPTERS
from gateway.keys import assign_new_key
from gateway.models import ApiKey, Platform, Tool


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

    @admin.action(description='Revoke selected keys', permissions=['change'])
    def revoke_keys(self, request, queryset):
        count = queryset.filter(revoked_at__isnull=True).update(revoked_at=timezone.now())
        self.message_user(request, f'Revoked {count} key(s).')


class ToolAdminForm(forms.ModelForm):
    new_tool_key = forms.CharField(
        label='Tool key', required=False, widget=forms.PasswordInput(render_value=False),
        help_text='Write-only. Leave blank to keep the current key.',
    )
    clear_tool_key = forms.BooleanField(label='Clear tool key', required=False)
    adapter = forms.ChoiceField(choices=())

    class Meta:
        model = Tool
        fields = (
            'tool_id', 'name', 'description', 'docs_url', 'base_url', 'depth', 'adapter', 'operations',
            'key_header', 'gateway_only', 'timeout_seconds', 'health_path', 'enabled',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['adapter'].choices = [(name, name) for name in sorted(ADAPTERS)]

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('new_tool_key') and cleaned.get('clear_tool_key'):
            raise forms.ValidationError('Either set a new key or clear it, not both.')
        return cleaned


@admin.register(Tool)
class ToolAdmin(admin.ModelAdmin):
    form = ToolAdminForm
    list_display = ('tool_id', 'name', 'depth', 'adapter', 'enabled', 'key_status', 'reachability')
    list_filter = ('enabled', 'depth')
    search_fields = ('tool_id', 'name')

    @admin.display(description='Tool key')
    def key_status(self, obj):
        return 'set' if obj.has_tool_key else 'not set'

    def save_model(self, request, obj, form, change):
        if form.cleaned_data.get('clear_tool_key'):
            obj.clear_tool_key()
        elif form.cleaned_data.get('new_tool_key'):
            obj.set_tool_key(form.cleaned_data['new_tool_key'])
        super().save_model(request, obj, form, change)
        if obj.uses_plain_http_off_loopback:
            messages.warning(request, f'{obj.tool_id} uses plain http to a non-loopback host: '
                                      f'its tool key travels unencrypted.')
