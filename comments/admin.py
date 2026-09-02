from django.contrib import admin
from .models import Comment

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('user_name', 'email', 'created_at', 'parent', 'attachment_kind', 'avatar')
    list_filter = ('created_at', 'parent')
    search_fields = ('user_name', 'email', 'text')
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)