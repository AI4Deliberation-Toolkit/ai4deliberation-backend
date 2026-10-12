import warnings

# ServeStaticMiddleware warns when STATIC_ROOT doesn't exist; tests never run collectstatic.
warnings.filterwarnings('ignore', message=r'No directory at: .*staticfiles', category=UserWarning)
