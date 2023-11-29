import json
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.db import IntegrityError
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from datetime import datetime

# from flask import render_template
from .models import *

ini = 0
end = 10

def index(request):
    if request.user.is_authenticated:
        return render(request, "network/index.html")
    else:
        return render(request, "network/login.html")


@csrf_exempt
@login_required
def load_profile(request, get_user_id, option):
    if (request.method !="GET" and request.method !="PUT"):
        return JsonResponse({"error": "Invalid request method"})

    if request.method == "GET":
        if (option == "self" and get_user_id == 0):
            get_user = request.user
        elif (option == "other" and get_user_id != 0):
            get_user = User.objects.get(id = get_user_id)
        try:
            info = Info.objects.get(user=request.user, user2=get_user)
        except Info.DoesNotExist:
            info = Info(user=request.user, user2=get_user)
            info.save()
        return JsonResponse(info.info_format(), status=201)

    elif request.method == "PUT":
        get_user = User.objects.get(id = get_user_id)
        if option == "follow":
            try:
                info = Info.objects.get(user=request.user, user2=get_user)
            except Info.DoesNotExist:
                info = Info(user=request.user, user2 = get_user)
                info.save()
            if info.connected == False:
                request.user.following.add(get_user)
                get_user.followers.add(request.user)
                info.connected = True
                info.save()
            else:
                request.user.following.remove(get_user)
                get_user.followers.remove(request.user)
                info.connected = False
                info.save()
            return JsonResponse(info.info_format(), status=201)

        elif option == "block":
            get_user = User.objects.get(id = get_user_id)
            try:
                info = Info.objects.get(user = request.user, user2 = get_user)
            except Info.DoesNotExist:
                info = Info(user = request.user, user2 = get_user)
                info.save()
            if info.blocked == True:
                request.user.blocklist.remove(get_user)
                info.blocked = False
            else:
                info.blocked = True
                request.user.blocklist.add(get_user)
                request.user.following.remove(get_user)
                get_user.followers.remove(request.user)
                info.connected = False
            info.save()
            return JsonResponse(info.block_format(), status=201)


@csrf_exempt
@login_required
def write_post(request):
    if request.method == "POST":
        data = json.loads(request.body)
        new_post = data.get("text")
        if new_post != "":
            Post.objects.create(user=request.user, content=new_post)
            return JsonResponse({"message": "post sent successfully"})
        else:
            return JsonResponse({"error": "error in posting"})


@csrf_exempt
def load_posts(request, option, nav_option):

    global ini
    global end

    if nav_option == "previous":
       if (ini % 10 == 0 and ini > 0):
            ini -= 10
            end -= 10
    elif nav_option == "next":
        ini += 10
        end += 10
    elif nav_option == "reload":
        ini = 0
        end = 10

    if request.method != "GET":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    blocklist = request.user.blocklist.all().order_by("username").all()

    if option == "default":
        Post.objects.filter(user = request.user).update(editable = True)
        Post.objects.exclude(user = request.user).update(editable = False)
        posts = Post.objects.exclude(user__in = blocklist).order_by("-date_time").all()[ini:end]
    elif option == "following":
        following = request.user.following.all()
        posts = Post.objects.filter(user__in = following).exclude(user__in = blocklist).order_by("-date_time").all()[ini:end]
    elif option == "self":
        posts = Post.objects.filter(user=request.user).order_by("-date_time").all()[ini:end]
    elif option == "blocklist":
        return JsonResponse([block.blocklist_format() for block in blocklist], safe=False, status=201)
    elif (option != "previous" and option != "next"):
        if option == "0":
            option = request.user.id
        get_user = User.objects.get(id = int(option))
        try:
            posts = Post.objects.filter(user = get_user).exclude(user__in = blocklist).order_by("-date_time").all()[ini:end]
        except Post.DoesNotExist:
            return JsonResponse({"error": "Not found any result"}, status=201)
    else:
        return JsonResponse({"error": "Not found Anything (something went wrong"})

    return JsonResponse([post.format() for post in posts], safe=False, status=201)


@csrf_exempt
@login_required
def update_post(request, post_id, option):

    if request.method == "PUT":
        data = json.loads(request.body)
        get_user_id = data.get("get_user_id")
        get_user = User.objects.get(id=get_user_id)
        post = Post.objects.get(id=post_id)
        try:
            engage = Engage.objects.get(user=get_user, post=post)
        except Engage.DoesNotExist:
            engage = Engage.objects.create(user=get_user, post=post)
        if option == "likes":
            if engage.liked == False:
                post.likes += 1
                engage.liked = True
            else:
                post.likes -= 1
                engage.liked = False
        elif option == "dislikes":
            if engage.disliked == False:
                post.dislikes += 1
                engage.disliked = True
            else:
                post.dislikes -= 1
                engage.disliked = False
        elif option == "save":
            new_text = data.get("content", "")
            if new_text!= "":
                post.content = new_text
            else:
                return JsonResponse({"error": "Provide valid text to update"}, status=200)
        post.save()
        engage.save()
        return JsonResponse(post.format(), status=201)


@csrf_exempt
def login_view(request):
    if request.method == "POST":

        # Attempt to sign user in
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)

        # Check if authentication successful
        if user is not None:
            login(request, user)
            return HttpResponseRedirect(reverse("index"))
        else:
            return render(request, "network/login.html", {
                "message": "Invalid username and/or password."
            })
    else:
        return render(request, "network/login.html")


def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse("index"))


@csrf_exempt
def register(request):
    if request.method == "POST":
        username = request.POST["username"]
        email = request.POST["email"]

        # Ensure password matches confirmation
        password = request.POST["password"]
        confirmation = request.POST["confirmation"]
        if password != confirmation:
            return render(request, "network/register.html", {
                "message": "Passwords must match."
            })

        # Attempt to create new user
        try:
            user = User.objects.create_user(username, email, password)
            user.save()
        except IntegrityError:
            return render(request, "network/register.html", {
                "message": "Username already taken."
            })
        login(request, user)
        return HttpResponseRedirect(reverse("index"))
    else:
        return render(request, "network/register.html")
