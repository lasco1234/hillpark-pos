def notify_user_registered(new_user, registered_by=None):
    """Notify owners when a new user account is created."""
    title = f"New User Registered: {new_user.username}"
    role_display = (
        new_user.get_role_display()
        if hasattr(new_user, "get_role_display")
        else getattr(new_user, "role", "—")
    )
    store_name = new_user.store.name if getattr(new_user, "store", None) else "None (Admin)"
    msg = (
        f"New account created:\n"
        f"• Username: {new_user.username}\n"
        f"• Name: {new_user.get_full_name() or '—'}\n"
        f"• Email: {new_user.email or '—'}\n"
        f"• Phone: {getattr(new_user, 'phone', None) or '—'}\n"
        f"• Role: {role_display}\n"
        f"• Store: {store_name}"
    )
    if registered_by:
        msg += f"\nRegistered by: {registered_by.get_username()}"

    return full_notify(
        title=title,
        message=msg,
        level="success",
        icon="mdi-account-plus",
        link="/admin/authentication/customuser/",
        store=getattr(new_user, "store", None),
        related_object_type="user",
        related_object_id=new_user.pk,
        email_subject=title,
        email_body=msg,
        sms_message=f"New user: {new_user.username} ({role_display}) @ {store_name}",
        notify_owners_only=True,
    )