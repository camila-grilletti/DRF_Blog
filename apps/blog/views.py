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
from django.db.models import Q, F

from .models import Post, Heading, PostAnalytics, Category
from .serializers import PostListSerializer, PostSerializer, HeadingSerializer
from .tasks import increment_post_impressions
from .utils import get_client_ip
from .tasks import increment_post_views_tasks

from faker import Faker
import random
import uuid
from django.utils.text import slugify

from core.permissions import HasValidAPIKey

redis_client = redis.StrictRedis(host=settings.REDIS_HOST, port=6379, db=0)


class PostListView(StandardAPIView):
    permission_classes = [HasValidAPIKey]

    def get(self, request, *args, **kwargs):
        try:
            search = request.query_params.get("search", "")
            sorting = request.query_params.get("sorting", None)
            ordering = request.query_params.get("ordering", None)
            categories = request.query_params.getlist("category", [])

            cached_posts = cache.get(f'post_list:{search}:{sorting}:{ordering}:{categories}')
            
            if cached_posts:
                for post in cached_posts:
                    redis_client.incr(f'post:impressions:{post["id"]}')
                return self.paginate(request, cached_posts)

            if search != "":
                posts = Post.postobjects.filter(
                    Q(title__icontains=search) |
                    Q(description__icontains=search) |
                    Q(content__icontains=search) |
                    Q(keywords__icontains=search)
                )
            else:
                posts = Post.postobjects.all()

            if not posts.exists():
                raise NotFound(detail='No posts found.')
            
            if categories:
                category_queries = Q()
                for category in categories:
                    try:
                        uuid.UUID(category)
                        uuid_query = (
                            Q(category__id=category)
                        )
                        category_queries |= uuid_query
                    except:
                        slug_query = (
                            Q(category__slug=category)
                        )
                        category_queries |= slug_query
                
                posts = posts.filter(category_queries).distinct()

            if sorting:
                if sorting == 'newest':
                    posts = posts.order_by("-created_at")
                elif sorting == 'recently_updated':
                    posts = posts.order_by('-updated_at')
                elif sorting == 'most_viewed':
                    posts = posts.annotate(popularity=F("post_analytics__views")).order_by('-popularity')

            if ordering:
                if ordering == 'az':
                    posts = posts.order_by("title")
                elif ordering == 'za':
                    posts = posts.order_by('-title')

            serialized_posts = PostListSerializer(posts, many=True).data

            cache.set(f'post_list:{search}:{sorting}:{ordering}:{categories}', serialized_posts, timeout=60*5)

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

class GenerateFakePostsView(StandardAPIView):

    def get(self, request):

        fake = Faker()

        categories = list(Category.objects.all())

        if not categories:
            return self.response("No categories availables for posts", 400)
        
        posts_to_generate = 100
        status_options = ["draft", "published"]

        for _ in range(posts_to_generate):
            title = fake.sentence(nb_words=6)
            post = Post(
                id=uuid.uuid4(),
                title=title,
                description=fake.sentence(nb_words=12),
                content=fake.paragraph(nb_sentences=4),
                keywords=", ".join(fake.words(nb=5)),
                slug=slugify(title),
                category=random.choice(categories),
                status=random.choice(status_options),
            )
            post.save()

        return self.response(f"{posts_to_generate} posts generated successfully.")
    

class GenerateFakeAnalyticsView(StandardAPIView):

    def get(self, request):

        posts = Post.objects.all()

        if not posts:
            return self.response("No posts availables for analytics", 400)
        
        analytics_to_generate = len(posts)

        for post in posts:
            views = random.randint(50, 1000)
            impressions = views + random.randint(100, 2000)
            clicks = random.randint(0, views)
            avg_time_on_page = round(random.uniform(10, 300), 2)

            analytics, created = PostAnalytics.objects.get_or_create(post=post)
            analytics.views = views
            analytics.impressions = impressions
            analytics.clicks = clicks
            analytics.avg_time_on_page = avg_time_on_page
            analytics._update_click_through_rate()
            analytics.save()

        return self.response(f"{analytics_to_generate} analytics generated successfully.")
    