from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.views import APIView
from rest_framework_api.views import StandardAPIView
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, APIException
import redis
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.core.cache import cache

from .models import Post, Heading, PostAnalytics
from .serializers import PostListSerializer, PostSerializer, HeadingSerializer
from .tasks import increment_post_impressions
from .utils import get_client_ip
from .tasks import increment_post_views_tasks

from core.permissions import HasValidAPIKey

redis_client = redis.StrictRedis(host=settings.REDIS_HOST, port=6379, db=0)


class PostListView(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    def get(self, request, *args, **kwargs):
        try:
            cached_posts = cache.get('post_list')
            
            if cached_posts:
                for post in cached_posts:
                    redis_client.incr(f'post:impressions:{post["id"]}')
                return self.paginate(request, cached_posts)
            

            posts = Post.postobjects.all()

            if not posts.exists():
                raise NotFound(detail='No posts found.')

            serialized_posts = PostListSerializer(posts, many=True).data

            cache.set('post_list', serialized_posts, timeout=60*5)

            for post in posts:
                redis_client.incr(f'post:impressions:{post.id}')

        except Post.DoesNotExist:
            raise NotFound(detail='No posts found.')
        except Exception as e:
            raise APIException(detail=f'An unexpected error ocurreed: {str(e)}')
            
        return self.paginate(request, serialized_posts)


class PostDetailView(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    def get(self, request):
        ip_address = get_client_ip(request)
        slug = request.query_params.get('slug')
        
        try:
            cached_post = cache.get(f'post_detail:{slug}')
            if cached_post:
                increment_post_views_tasks.delay(cached_post['slug'], ip_address)
                return self.response(cached_post)


            post = Post.postobjects.get(slug=slug)
            serialized_post = PostSerializer(post).data
            
            cache.set(f'post_detail:{slug}', serialized_post, timeout=60*5)

            increment_post_views_tasks.delay(post.slug, ip_address)


        except Post.DoesNotExist:
            raise NotFound(detail='The requested post does not exist.')
        except Exception as e:
            raise APIException(detail=f'An unexpected error ocurreed: {str(e)}')

        return self.response(serialized_post)
    

class PostHeadingView(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    def get(self, request):
        post_slug = request.query_params.get('slug')
        heading_objects = Heading.objects.filter(post__slug=post_slug)
        serializer_data = HeadingSerializer(heading_objects, many=True).data
        return self.response(serializer_data)
    

class IncrementPostClickView(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    def post(self, request):
        data = request.data

        try:
            post = Post.postobjects.get(slug=data['slug'])
        except Post.DoesNotExist:
            raise NotFound(detail='The requested post does not exist.')
        
        try:
            post_analytics, created = PostAnalytics.objects.get_or_create(post=post)
            post_analytics.increment_click()
        except Exception as e:
            raise APIException(detail=f'An unexpected error ocurreed: {str(e)}')
        
        return self.response({
            'message': 'Click incremented successfully',
            'clicks': post_analytics.clicks
        })
