import json

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext

import users.services
from routes.models import Route
from users.forms import UserRegistrationForm
from users.models import Friendship, User, UserProfile


@login_required
def friends(request):
    friends_list = users.services.get_friends_with_stats(request.user)
    pending_requests = users.services.get_pending_friend_requests(request.user)

    return render(
        request,
        'friends/friends.html',
        {
            'friends': friends_list,
            'pending_friend_requests': pending_requests,
            'pending_requests_count': len(pending_requests),
            'shared_routes_count': 0,
        },
    )


@login_required
def remove_friend(request, friend_id):
    friend = get_object_or_404(User, id=friend_id)
    success = users.services.remove_friendship(request.user, friend)

    if success:
        messages.success(
            request,
            gettext('User %(username)s has been removed from your friends')
            % {'username': friend.username},
        )
    else:
        messages.error(request, gettext('Friendship not found'))

    return redirect('friends')


@login_required
def send_message(request, user_id):
    recipient = get_object_or_404(User, id=user_id)

    if not users.services.are_friends(request.user, recipient):
        messages.error(
            request, gettext('You can only send messages to your friends')
        )
        return redirect('friends')

    return redirect('chat:private_chat', user_id=user_id)


@login_required
def find_friends(request):
    search_query = request.GET.get('q', '').strip()

    user_data = users.services.find_users_for_friendship(
        request.user, search_query
    )
    pending_requests = users.services.get_pending_friend_requests(request.user)

    return render(
        request,
        'friends/find_friends.html',
        {
            'users': user_data,
            'pending_friend_requests': pending_requests,
            'pending_requests_count': len(pending_requests),
        },
    )


@login_required
def send_friend_request(request, user_id):
    to_user = get_object_or_404(User, id=user_id)
    success, message = users.services.process_friend_request(
        request.user, to_user
    )

    if success:
        messages.success(request, message)
    else:
        messages.error(request, message)

    return redirect('find_friends')


@login_required
def accept_friend_request(request, request_id):
    friend_request = get_object_or_404(
        Friendship, id=request_id, to_user=request.user
    )
    users.ervices.update_friend_request_status(friend_request, 'accepted')

    messages.success(
        request,
        gettext('You have accepted the friend request from %(username)s')
        % {'username': friend_request.from_user.username},
    )
    return redirect('friends')


@login_required
def reject_friend_request(request, request_id):
    friend_request = get_object_or_404(
        Friendship, id=request_id, to_user=request.user
    )
    users.services.update_friend_request_status(friend_request, 'rejected')

    messages.info(
        request,
        gettext('You have declined the friend request from %(username)s')
        % {'username': friend_request.from_user.username},
    )
    return redirect('friends')


@login_required
def profile(request):
    if request.method == 'POST':
        success, message = users.services.update_user_profile(
            request.user, request.POST, request.FILES
        )
        if success:
            messages.success(request, message)
        else:
            messages.error(request, message)
        return redirect('profile')

    profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)
    can_change_username, username_change_days_left = (
        users.services.get_username_change_status(profile_obj)
    )
    stats = users.services.get_user_statistics(request.user)
    pending_requests = users.services.get_pending_friend_requests(request.user)

    context = {
        'profile': profile_obj,
        'can_change_username': can_change_username,
        'username_change_days_left': username_change_days_left,
        'pending_friend_requests': pending_requests,
        'pending_requests_count': len(pending_requests),
    }
    context.update(stats)

    return render(request, 'profile/profile.html', context)


def user_profile(request, username):
    target_user = get_object_or_404(User, username=username)
    profile_data = users.services.get_public_profile_data(
        target_user, request.user
    )

    context = {
        'profile_user': target_user,
    }
    context.update(profile_data)

    if request.user.is_authenticated:
        pending = users.services.get_pending_friend_requests(request.user)
        context.update(
            {
                'pending_friend_requests': pending,
                'pending_requests_count': len(pending),
            }
        )

    return render(request, 'profile/user_profile.html', context)


def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, gettext('Registration successful!'))
            return redirect('home')
    else:
        form = UserRegistrationForm()
    return render(request, 'registration/register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(
                request,
                gettext('Welcome back, %(username)s!')
                % {'username': user.username},
            )
            return redirect('home')
    else:
        form = AuthenticationForm()
    return render(request, 'registration/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, gettext('You have been logged out'))
    return redirect('home')


@login_required
def send_to_friend(request, route_id):
    if request.method != 'POST':
        return JsonResponse(
            {'success': False, 'error': gettext('Invalid request method')}
        )

    route = get_object_or_404(Route, id=route_id)

    try:
        data = json.loads(request.body)
        friend_id = data.get('friend_id')

        success, message = users.services.share_route_with_friend(
            request.user, route, friend_id
        )

        if success:
            return JsonResponse({'success': True, 'message': message})
        else:
            return JsonResponse({'success': False, 'error': message})

    except json.JSONDecodeError:
        return JsonResponse(
            {'success': False, 'error': gettext('Invalid data format')}
        )
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def get_friends_list(request):
    friends = users.services.get_simple_friends_list(request.user)
    return JsonResponse({'success': True, 'friends': friends})


@login_required
def check_username_availability(request):
    username = request.GET.get('username', '').strip()
    result = users.services.check_username(request.user, username)
    return JsonResponse(result)
