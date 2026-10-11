from .settings import *

from decouple import Csv, config
from django.core.exceptions import ImproperlyConfigured

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)

# Must list the public host(s) nginx passes through *and* 127.0.0.1,localhost
# (the stub tool is called at 127.0.0.1:8000).
ALLOWED_HOSTS = [host for host in config('ALLOWED_HOSTS', cast=Csv()) if host]  # ' , ' is empty too
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured('ALLOWED_HOSTS is empty: list the public host(s) plus 127.0.0.1,localhost.')

# The gateway is server-to-server: no browser origins unless listed explicitly.
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='', cast=Csv())

# TLS ends at Cloudflare, so Django sees http while the browser sends `Origin: https://…`;
# admin login needs that origin trusted. Full origins with scheme, comma-separated.
# (SECURE_PROXY_SSL_HEADER waits for deferred-decisions #8: it is only safe if the
# backend port is reachable solely through the edge.)
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='', cast=Csv())

POSTGRES_USER = config('POSTGRES_USER')
POSTGRES_PASSWORD = config('POSTGRES_PASSWORD')
POSTGRES_PORT = config('POSTGRES_PORT')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('POSTGRES_DB', default='postgres'),
        'USER': POSTGRES_USER,
        'PASSWORD': POSTGRES_PASSWORD,
        'HOST': config('POSTGRES_HOST', default='db'),
        'PORT': POSTGRES_PORT,
    }
}

GATEWAY_ENCRYPTION_KEYS = config('GATEWAY_ENCRYPTION_KEYS', cast=Csv())
GATEWAY_ENABLE_STUB = config('GATEWAY_ENABLE_STUB', default=False, cast=bool)
