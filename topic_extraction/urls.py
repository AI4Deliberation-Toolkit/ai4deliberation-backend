from django.urls import path
from topic_extraction.views import ArticleTopicView, ExtractConversationView, TopicsListingView

urlpatterns = [
    path('topics/extract-conversation', ExtractConversationView.as_view(), name='extract-conversation'),
    path('topics/article/<str:article_id>', ArticleTopicView.as_view(), name='article-topics'),
    path('topics', TopicsListingView.as_view(), name='topics-listing'),
]
