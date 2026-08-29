from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required

from .forms import CustomUserCreationForm, CustomLoginForm


def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = form.cleaned_data['role']
            user.save()

            try:
                from notifications.services import notify_user_registered
                result = notify_user_registered(user)
                print("NOTIFY RESULT:", result)
            except Exception as e:
                import traceback
                print("========== NOTIFY ERROR ==========")
                print(e)
                traceback.print_exc()
                print("==================================")

            messages.success(
                request,
                f"Account created successfully for {user.username}! You can now login."
            )
            return redirect('login')

    else:
        form = CustomUserCreationForm()

    return render(request, 'register.html', {'form': form})


class CustomLoginView(LoginView):
    template_name = 'login.html'
    form_class = CustomLoginForm
    redirect_authenticated_user = True
    
    def get_success_url(self):
        return reverse_lazy('home')
    
    # Add this method to clear old messages when login page loads
    def get(self, request, *args, **kwargs):
        # Clear messages when user visits login page
        storage = messages.get_messages(request)
        storage.used = True
        return super().get(request, *args, **kwargs)


@login_required
def user_logout(request):
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect('login')