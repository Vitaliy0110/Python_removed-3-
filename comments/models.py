from django.db import models
from uuid import uuid4
from pathlib import Path
from django.core.validators import MaxLengthValidator

def attachment_path(instance, filename):
    """Keep user filenames out of storage paths and retain only the extension."""
    extension = Path(filename).suffix.lower()
    return f"attachments/{uuid4().hex}{extension}"

class Comment(models.Model):
    user_name = models.CharField(max_length=100)
    email = models.EmailField()
    home_page = models.URLField(blank=True)
    text = models.TextField(validators=[MaxLengthValidator(5000)])
    attachment = models.FileField(upload_to=attachment_path, blank=True)
    attachment_kind = models.CharField(
        max_length=5,
        blank=True,
        choices=(('image', 'Image'), ('text', 'Text')),
    )
    
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f'{self.user_name}: {self.text[:30]}'