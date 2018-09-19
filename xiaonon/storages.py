### storages.py (somewhere near settings)
from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage

class StaticStorage(S3Boto3Storage):
    location = settings.STATIC_LOCATION  # Note that setting

# class MediaStorage(S3Boto3Storage):
#     location = settings.MEDIA_LOCATION  # Note that setting
#     default_acl = 'private'
#     # file_overwrite = False
#     custom_domain = False
