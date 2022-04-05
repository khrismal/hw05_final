from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CommentForm, PostForm
from .models import Follow, Group, Post, User


def pager(request, post_list):
    paginator = Paginator(post_list, settings.PAGE_NUM)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return page_obj


def group_posts(request, slug):
    group = get_object_or_404(Group, slug=slug)
    post_list = group.posts.all()
    page_obj = pager(request, post_list)
    context = {"group": group, "page_obj": page_obj}
    return render(request, "posts/group_list.html", context)


def index(request):
    post_list = Post.objects.all()
    page_obj = pager(request, post_list)
    context = {
        "page_obj": page_obj,
    }
    return render(request, "posts/index.html", context)


def profile(request, username):
    author = get_object_or_404(User, username=username)
    posts = author.posts.all()
    user = request.user
    page_obj = pager(request, posts)
    following = (
        user.is_authenticated
        and Follow.objects.filter(user=user, author=author).exists()
    )
    context = {
        "page_obj": page_obj,
        "posts": posts,
        "following": following,
        "author": author,
    }
    return render(request, "posts/profile.html", context)


def post_detail(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    comments = post.comments.all()
    form = CommentForm(request.POST or None)
    author = post.author
    posts_count = author.posts.count()
    context = {
        "post": post,
        "posts_count": posts_count,
        "form": form,
        "comments": comments,
    }
    return render(request, "posts/post_detail.html", context)


@login_required
def post_create(request):
    form = PostForm(request.POST or None, files=request.FILES or None)
    if form.is_valid():
        new_post = form.save(commit=False)
        new_post.author = request.user
        new_post.save()
        return redirect("posts:profile", request.user)
    return render(request, "posts/create_post.html", {"form": form})


@login_required
def post_edit(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    author = request.user
    if author != post.author:
        return redirect("posts:post_detail", post_id)
    form = PostForm(
        request.POST or None, files=request.FILES or None, instance=post
    )
    if form.is_valid():
        form.save()
        return redirect("posts:post_detail", post_id)
    return render(
        request, "posts/update_post.html", {"form": form, "post": post}
    )


@login_required
def add_comment(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    form = CommentForm(request.POST or None)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.author = request.user
        comment.post = post
        comment.save()
    return redirect("posts:post_detail", post_id=post_id)


@login_required
def follow_index(request):
    post_list = Post.objects.filter(author__following__user=request.user)
    page_obj = pager(request, post_list)
    context = {"page_obj": page_obj}
    return render(request, "posts/follow.html", context)


@login_required
def profile_follow(request, username):
    author = get_object_or_404(User, username=username)
    if request.user != author:
        Follow.objects.get_or_create(author=author, user=request.user)
    return redirect("posts:profile", username)


@login_required
def profile_unfollow(request, username):
    author = get_object_or_404(User, username=username)
    Follow.objects.filter(user=request.user, author=author).delete()
    return redirect("posts:profile", username)
