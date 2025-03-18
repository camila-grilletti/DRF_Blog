from django.urls import path

from .views import (
    PostListView,
    PostDetailView,
    PostHeadingView,
    IncrementPostClickView,
    GenerateFakeAnalyticsView,
    GenerateFakePostsView,
)


urlpatterns = [
    path('generate_posts/', GenerateFakePostsView.as_view(), name='generate-fake-posts'),
    path('generate_analytics/', GenerateFakeAnalyticsView.as_view(), name='generate-fake-analytics'),
    path('posts/', PostListView.as_view(), name='posts-list'),
    path('post/', PostDetailView.as_view(), name='posts-detail'),
    path('post/headings/', PostHeadingView.as_view(), name='post-headings'),
    path('post/increment_click/', IncrementPostClickView.as_view(), name='increment-post-clicks'),
]