from rest_framework import serializers

from .models import Post, Category, Heading


class PostSerializer(serializers.ModelSerializer):    
    class Meta:
        model = Post
        fields = '__all__'


class PostListSerializer(serializers.ModelSerializer):    
    class Meta:
        model = Post
        fields = [
            'id',
            'title',
            'description',
            'thumbnail',
            'slug',
            'category',
            'views'
        ]


class CategorySerializer(serializers.ModelSerializer):    
    class Meta:
        model = Category
        fields = '__all__'


class HeadingSerializer(serializers.ModelSerializer):    
    class Meta:
        model = Heading
        fields = [
            'title',
            'slug',
            'level',
            'order',
        ]