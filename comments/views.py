from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render


from .forms import CommentForm, CommentHTMLValidator, sanitize_comment_html
from .models import Comment


MAX_BIGINT = 9223372036854775807  # предел PostgreSQL bigint


def get_parent_comment(raw_id):
    """Безопасно достает родительский комментарий по id из GET/POST.
    Возвращает None, если id не передан, не является числом
    или выходит за пределы допустимого диапазона."""
    if not raw_id or not str(raw_id).isdigit():
        return None
    value = int(raw_id)
    if value > MAX_BIGINT:
        return None
    return get_object_or_404(Comment, id=value)

def notify_new_comment():
    channel_layer = get_channel_layer()
    if channel_layer is not None:
        async_to_sync(channel_layer.group_send)(
            "comments", {"type": "comment.created"}
        )

def comment_preview(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'method not allowed'}, status=405)

    text = request.POST.get('text', '')

    parser = CommentHTMLValidator()
    try:
        parser.feed(text)
        parser.close()
        parser.validate()
    except ValueError as error:
        return JsonResponse({'error': str(error)}, status=400)

    return JsonResponse({'html': sanitize_comment_html(text)})

def comment_list(request):
    reply_parent = None

    if request.method == 'POST':
        parent_id = request.POST.get('parent_id')

        reply_parent = get_parent_comment(parent_id)
        
        if reply_parent:
            # Отправили форму ответа
            reply_form = CommentForm(
                request.POST,
                request.FILES
            )

            if reply_form.is_valid():
                comment = reply_form.save(commit=False)
                comment.parent = reply_parent
                comment.save()
                notify_new_comment()

                return redirect('comment_list')

            form = CommentForm()

        else:
            # Отправили основную форму
            form = CommentForm(
                request.POST,
                request.FILES
            )

            if form.is_valid():
                form.save()
                notify_new_comment()
                return redirect('comment_list')

            reply_form = CommentForm()

    else:
        form = CommentForm()

        reply_parent = get_parent_comment(request.GET.get('reply'))
        reply_form = CommentForm()

    sort = request.GET.get('sort', 'created_at')
    direction = request.GET.get('direction', 'desc')

    allowed_sorts = {
        'user_name': 'user_name',
        'email': 'email',
        'created_at': 'created_at',
    }

    sort_field = allowed_sorts.get(sort, 'created_at')

    if direction == 'asc':
        comments = Comment.objects.filter(
            parent=None
        ).order_by(sort_field)
    else:
        comments = Comment.objects.filter(
            parent=None
        ).order_by(f'-{sort_field}')


    paginator = Paginator(comments, 25)

    page_number = request.GET.get('page')
    comments = paginator.get_page(page_number)


    context = {
        'form': form,
        'reply_form': reply_form,
        'reply_parent': reply_parent,
        'comments': comments,
    }

    return render(
        request,
        'comments/index.html',
        context
    )