import json
import os
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

class Command(BaseCommand):
    help = "Create gcp-cors-config.json file for Google Cloud Storage CORS configuration"
    
    def handle(self, *args, **options):
        if not settings.CSRF_TRUSTED_ORIGINS or len(settings.CSRF_TRUSTED_ORIGINS) == 0:
            self.stdout.write(
                self.style.ERROR("CSRF_TRUSTED_ORIGINS either not defined or empty")
            )
            return

        if not settings.GS_BUCKET_NAME:
            self.stdout.write(
                self.style.ERROR("GS_BUCKET_NAME is not defined")
            )
            return

        file_content = [{
            'origin': settings.CSRF_TRUSTED_ORIGINS,
            'method': ['GET'],
            'responseHeader': ['Content-Type'],
            'maxAgeSeconds': 3600
        }]
        
        file_path = os.path.join(settings.BASE_DIR, 'gcp-cors-config.json')
        with open(file_path, 'w') as file:
            json.dump(file_content, file, indent=4)

        self.stdout.write(
            self.style.SUCCESS('gcp-cors-config.json created')
        )
