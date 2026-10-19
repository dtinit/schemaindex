from django.conf import settings
from hijack.permissions import superusers_only


# We're really just using this to hide the "impersonate user"
# button in the admin panel when ENABLE_ACCOUNTS is False
def hijack_superusers_with_accounts(*, hijacker, hijacked):
    return settings.ENABLE_ACCOUNTS and superusers_only(
        hijacker=hijacker, hijacked=hijacked
    )
