from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from store.models import Store
from .models import SystemSettings, StoreSettings
from .forms import SystemSettingsForm, StoreSettingsForm


def _is_admin(user):
    return getattr(user, 'can_see_all', False) or user.is_superuser


@login_required
def settings_home(request):
    is_admin = _is_admin(request.user)
    store_settings = None
    stores = []

    if is_admin:
        # Admin: list all stores so they can pick one to edit
        stores = Store.objects.filter(is_active=True).order_by('name')
    else:
        # Normal user: show their own store's settings directly
        if request.user.store:
            store_settings, _ = StoreSettings.objects.get_or_create(store=request.user.store)

    context = {
        'is_admin': is_admin,
        'store_settings': store_settings,
        'stores': stores,
    }
    return render(request, 'settings/settings_home.html', context)


@login_required
def system_settings(request):
    """Global system settings – Admin only"""
    if not _is_admin(request.user):
        messages.error(request, "Only administrators can change system settings.")
        return redirect('settings:home')

    settings_obj = SystemSettings.load()

    if request.method == 'POST':
        form = SystemSettingsForm(request.POST, request.FILES, instance=settings_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "System settings updated successfully.")
            return redirect('settings:system')
    else:
        form = SystemSettingsForm(instance=settings_obj)

    return render(request, 'settings/system_settings.html', {
        'form': form,
        'settings': settings_obj,
    })


@login_required
def store_settings_view(request, store_id=None):
    is_admin = _is_admin(request.user)

    if is_admin:
        # Admin can edit ANY store, but must pick one when no ID is in the URL
        if store_id is None:
            messages.info(request, "Please select a store to edit its settings.")
            return redirect('settings:home')   # settings:home lists stores for admins
        store = get_object_or_404(Store, pk=store_id)
    else:
        # Normal user is locked to their own store (store_id in the URL is ignored)
        if not request.user.store:
            messages.error(request, "You are not assigned to any store.")
            return redirect('settings:home')
        store = request.user.store

    settings_obj, _ = StoreSettings.objects.get_or_create(store=store)

    if request.method == 'POST':
        form = StoreSettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            form.save()
            messages.success(request, f"Settings for {store.name} updated successfully.")
            return redirect('settings:store', store_id=store.pk)
    else:
        form = StoreSettingsForm(instance=settings_obj)

    return render(request, 'settings/store_settings.html', {
        'form': form,
        'store': store,
        'is_admin': is_admin,
    })