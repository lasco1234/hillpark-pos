from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import CustomUser
from store.models import Store
from django import forms


class CustomUserCreationForm(UserCreationForm):
    """Form used when creating new user from Django Admin"""
    store = forms.ModelChoiceField(
        queryset=Store.objects.filter(is_active=True).order_by('name'),
        required=False,
        empty_label="No Store (Admin Only)",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    phone = forms.CharField(
        max_length=20,
        required=False,
        label="Phone (SMS)",
        help_text="e.g. 0712345678 – used for SMS notifications",
        widget=forms.TextInput(attrs={'placeholder': '0712345678'})
    )

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'phone', 'role', 'store')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].initial = 'admin'

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        store = cleaned_data.get('store')

        if role != 'admin' and not store:
            raise forms.ValidationError({
                'store': 'Store is required for non-admin users (Manager, Cashier, etc.)'
            })
        return cleaned_data


class CustomUserChangeForm(UserChangeForm):
    """Form used when editing existing user"""
    class Meta:
        model = CustomUser
        fields = '__all__'


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm

    list_display = (
        'username', 'email', 'phone', 'first_name', 'last_name',
        'role', 'get_store', 'is_active', 'is_superuser', 'date_joined'
    )

    list_filter = ('role', 'store', 'is_active', 'is_superuser', 'is_staff')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'phone')

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Information', {
            'fields': ('first_name', 'last_name', 'email', 'phone')
        }),
        ('Store & Role', {'fields': ('role', 'store')}),
        ('Permissions', {
            'fields': (
                'is_active', 'is_staff', 'is_superuser',
                'groups', 'user_permissions'
            )
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username', 'email', 'first_name', 'last_name', 'phone',
                'password1', 'password2', 'role', 'store',
            ),
        }),
    )

    def get_store(self, obj):
        return obj.store.name if obj.store else "All Stores (Admin)"

    get_store.short_description = 'Store'
    get_store.admin_order_field = 'store'