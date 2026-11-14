import pytest

from parley.security.redact import find_pii, luhn_ok, redact


def kinds(text: str) -> list[str]:
    return [f.kind for f in find_pii(text)]


def test_emails_phones_and_valid_card_numbers_are_found() -> None:
    text = "Mail bob@example.com or call +44 20 7946 0958, card 4242 4242 4242 4242."
    assert kinds(text) == ["email", "card", "phone"]


@pytest.mark.parametrize(
    "text",
    [
        "Your refund of $1,234.56 was processed on 2026-04-22.",
        "Order 12345678 and invoice 1234567890123 are fine.",
        "The card number 4242 4242 4242 4241 is not valid.",
        "POL-REF-001@v2 applies.",
    ],
)
def test_amounts_dates_ids_and_invalid_cards_are_not_personal_data(text: str) -> None:
    assert find_pii(text) == []


def test_luhn_accepts_and_rejects() -> None:
    assert luhn_ok("4242424242424242") and not luhn_ok("4242424242424241")


def test_redact_masks_foreign_data_and_keeps_the_senders_own() -> None:
    text = "Write to ada@example.com or bob@example.com, card 4242 4242 4242 4242."
    cleaned = redact(text, keep=["ADA@example.com"])
    assert "ada@example.com" in cleaned and "bob@example.com" not in cleaned
    assert "[email removed]" in cleaned and "[card removed]" in cleaned
    assert "4242" not in cleaned


def test_extra_strings_are_masked_whatever_their_case() -> None:
    cleaned = redact("Order for Tomas Lund is ready.", also=["tomas lund", ""])
    assert cleaned == "Order for [personal data removed] is ready."
