from celery import shared_task

import logging
import redis
from django.conf import settings

from .models import PostAnalytics, Post, CategoryAnalytics

logger = logging.getLogger(__name__)

redis_client = redis.StrictRedis(host=settings.REDIS_HOST, port=6379, db=0)


@shared_task
def increment_post_impressions(post_id):
    try:
        analytics, created = PostAnalytics.objects.get_or_create(post__id=post_id)
        analytics.increment_impressions()
    except Exception as e:
        logger.info(f'Error incrementing impressions for Post ID {post_id}: {str(e)}')


@shared_task
def increment_post_views_tasks(slug, ip_address):
    try:
        post = Post.objects.get(slug=slug)
        post_analytics, created = PostAnalytics.objects.get_or_create(post=post)
        post_analytics.increment_view(ip_address)
    except Exception as e:
        logger.info(f'Error incrementing views for Post slug {slug}: {str(e)}')


@shared_task
def sync_impressions_to_db():
    keys = redis_client.keys('post:impressions:*')
    for key in keys:
        try:
            post_id = key.decode('utf-8').split(":")[-1]
            impressions = int(redis_client.get(key))

            analytics, _ = PostAnalytics.objects.get_or_create(post__id=post_id)
            analytics.impressions += impressions
            analytics.save()

            analytics._update_click_through_rate()

            redis_client.delete(key)

        except Exception as e:
            logger.info(f'Error syncing impressions for {key}: {str(e)}')


@shared_task
def sync_category_impressions_to_db():
    keys = redis_client.keys('category:impressions:*')
    for key in keys:
        try:
            category_id = key.decode('utf-8').split(":")[-1]
            impressions = int(redis_client.get(key) or 0)
            
            from .models import Category
            try:
                category = Category.objects.get(id=category_id)
                
                analytics, created = CategoryAnalytics.objects.get_or_create(
                    category=category
                )
                
                analytics.impressions += impressions
                analytics.save()
                
                if hasattr(analytics, '_update_click_through_rate'):
                    analytics._update_click_through_rate()
                
                redis_client.delete(key)
                
            except Category.DoesNotExist:
                logger.info(f'Category with ID {category_id} not found, skipping')
                redis_client.delete(key)
                
        except Exception as e:
            logger.info(f'Error syncing impressions for {key}: {str(e)}')