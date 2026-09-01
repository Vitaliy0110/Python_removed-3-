from django.urls import path
from .views import comment_list, comment_preview

urlpatterns = [
    path('', comment_list, name='comment_list'),
    path('preview/', comment_preview, name='comment_preview'),
]