# Generated by Django 5.1.6 on 2025-02-25 22:24

import apps.blog.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0002_alter_category_description'),
    ]

    operations = [
        migrations.AlterField(
            model_name='category',
            name='thumbnail',
            field=models.ImageField(blank=True, null=True, upload_to=apps.blog.models.category_thumbnail_directory),
        ),
    ]
