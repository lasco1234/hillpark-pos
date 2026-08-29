from django.apps import AppConfig

class StoreConfig(AppConfig):        # Change 'StoreConfig' to your actual app config name
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'store'                   # ← Change to your app name

    def ready(self):
        import store.signals          # ← Import your signals