from .base import *
from decouple import Config, RepositoryEnv

dev_env_path = BASE_DIR+'/dev.env'
dev_env_config = Config(RepositoryEnv(dev_env_path))

DEBUG = dev_env_config.get('DEBUG',cast=bool)

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'postgres',
        'USER': dev_env_config.get('POSTGRES_USERNAME'),
        'PASSWORD': dev_env_config.get('POSTGRES_PASSWORD'),
        'HOST': dev_env_config.get('POSTGRES_HOST'),
        'PORT': dev_env_config.get('POSTGRES_PORT'),
    }
}

AWS_ACCESS_KEY_ID = dev_env_config.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = dev_env_config.get('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = dev_env_config.get('AWS_STORAGE_BUCKET_NAME')

STATIC_ROOT = os.path.join(BASE_DIR, "..", "www", "static")
STATIC_LOCATION = 'static'  # Settings used in storages.py
STATICFILES_STORAGE = 'xiaonon.storages.StaticStorage' ## disable static_root: will directly help you collect static files to S3 when running collectstatic 
STATIC_URL = 'https://' + AWS_STORAGE_BUCKET_NAME + '.s3.amazonaws.com/'  ## for accsessing static files in S3

LINE_CHANNEL_ACCESS_TOKEN = dev_env_config.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = dev_env_config.get('LINE_CHANNEL_SECRET')
LINE_LOGIN_CHANNEL_ID = dev_env_config.get('LINE_LOGIN_CHANNEL_ID')
LINE_LOGIN_CHANNEL_SECRET = dev_env_config.get('LINE_LOGIN_CHANNEL_SECRET')

DOMAIN = dev_env_config.get('DOMAIN')
AWS_BUCKET_URL = "https://s3-ap-southeast-1.amazonaws.com/"+AWS_STORAGE_BUCKET_NAME+"/"