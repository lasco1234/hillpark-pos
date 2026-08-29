from django.contrib.auth.decorators import login_required

class StoreMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            request.can_see_all = request.user.can_see_all
            request.user_store = request.user.store
        else:
            request.can_see_all = False
            request.user_store = None
        return self.get_response(request)