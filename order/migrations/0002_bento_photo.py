# Generated by Django 2.0.6 on 2018-06-16 11:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('order', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='bento',
            name='photo',
            field=models.TextField(default='', max_length=100),
            preserve_default=False,
        ),
    ]