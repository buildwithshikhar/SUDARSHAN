import pytest

from app.passwords import WeakPasswordError, check_password


@pytest.mark.parametrize(
    ("password", "email", "message"),
    [
        ("short", "", "at least 12"),
        ("password1234", "", "too common"),
        ("aaaaaaaaaaaaaa", "", "distinct"),
        ("samira-is-here-1", "samira@unit.example", "email name"),
    ],
)
def test_weak_passwords_are_rejected(password: str, email: str, message: str) -> None:
    with pytest.raises(WeakPasswordError, match=message):
        check_password(password, email)


def test_reasonable_password_passes() -> None:
    check_password("correct-horse-battery", "ops@unit.example")
