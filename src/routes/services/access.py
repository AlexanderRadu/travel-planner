def can_view_route(user, route):
    if route.privacy == 'public':
        return True
    if not user.is_authenticated:
        return False
    if route.privacy == 'private' and route.author == user:
        return True
    if route.privacy == 'personal' and (
        route.author == user or user in route.shared_with.all()
    ):
        return True
    if route.privacy == 'link':
        return True
    return False
