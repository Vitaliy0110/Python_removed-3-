from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from collections import defaultdict


from .forms import CommentForm, CommentHTMLValidator, sanitize_comment_html
from .models import Comment


MAX_BIGINT = 9223372036854775807  # предел PostgreSQL bigint

def attach_cached_replies(root_comments):
    """Достает всё дерево ответов для переданных корневых комментариев
    и раскладывает его по атрибуту `cached_replies` на каждом объекте.
    """
    root_ids = [comment.id for comment in root_comments]
    all_comments = {comment.id: comment for comment in root_comments}

    frontier_ids = root_ids
    while frontier_ids:
        children = list(Comment.objects.filter(parent_id__in=frontier_ids))
        if not children:
            break
        for child in children:
            all_comments[child.id] = child
        frontier_ids = [child.id for child in children]

    children_map = defaultdict(list)
    for comment in all_comments.values():
        if comment.parent_id is not None:
            children_map[comment.parent_id].append(comment)

    for comment in all_comments.values():
        comment.cached_replies = children_map.get(comment.id, [])

    return root_comments

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

                return redirect(f'{request.path}#comment-{reply_parent.id}')

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
    attach_cached_replies(list(comments))


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