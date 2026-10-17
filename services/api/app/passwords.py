"""Password policy for accounts created by the CLI: length first, then a few obvious rejects."""

MIN_PASSWORD_LENGTH = 12
_COMMON = frozenset(
    {
        "password1234",
        "passwordpassword",
        "123456789012",
        "1234567890123",
        "qwertyuiop12",
        "qwertyuiopasdf",
        "administrator",
        "welcome12345",
        "letmein123456",
        "changemechangeme",
    }
)


class WeakPasswordError(ValueError):
    """The password does not meet the policy; the message says why."""


def check_password(password: str, email: str = "") -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise WeakPasswordError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
    lowered = password.lower()
    if lowered in _COMMON:
        raise WeakPasswordError("password is too common")
    if len(set(password)) < 5:
        raise WeakPasswordError("password uses too few distinct characters")
    local = email.split("@", 1)[0].lower()
    if len(local) >= 4 and local in lowered:
        raise WeakPasswordError("password must not contain the email name")
