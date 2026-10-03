"""Input validation and user-friendly errors for MacroSnap."""

import io
import re
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError


MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
MAX_SUMMARY_CHARACTERS = 1_500


def normalize_phone(value: str) -> str:
    """Return a phone number in international format or explain the problem."""
    phone = re.sub(r"[\s()\-]", "", value.strip())
    if not re.fullmatch(r"\+[1-9][0-9]{7,14}", phone):
        raise ValueError(
            "Enter a valid international number, such as +91 followed by your 10-digit number."
        )
    return phone


def validate_name(value: str) -> str:
    """Trim excess whitespace and validate the profile name."""
    name = " ".join(value.split())
    if not 1 <= len(name) <= 60:
        raise ValueError("Enter a name between 1 and 60 characters.")
    return name


def prepare_image(data: bytes) -> tuple[bytes, str]:
    """Validate a JPG or PNG, remove metadata, and return a smaller JPEG."""
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Choose a JPG or PNG image smaller than 5 MB.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if image.format not in {"JPEG", "PNG"}:
                    raise ValueError("Only JPG and PNG images are supported.")
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    raise ValueError("Choose a photo with fewer than 20 million pixels.")

                image.load()
                photo = ImageOps.exif_transpose(image).convert("RGB")
                photo.thumbnail((1_600, 1_600))

                output = io.BytesIO()
                photo.save(output, format="JPEG", quality=85)
                return output.getvalue(), "image/jpeg"
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as error:
        raise ValueError(
            "This image could not be read. Try a different JPG or PNG."
        ) from error


def clean_summary(text: str, limit: int = MAX_SUMMARY_CHARACTERS) -> str:
    """Normalize a generated summary and reject empty or oversized content."""
    summary = " ".join((text or "").split())
    if not summary:
        raise ValueError("No summary was generated. Please try again.")
    if len(summary) > limit:
        raise ValueError("The summary is too long to send. Generate a shorter summary again.")
    return summary


def friendly_error(error: Exception, service: str = "Gemini") -> str:
    """Map known provider errors to safe messages without exposing raw details."""
    code = str(getattr(error, "code", "") or getattr(error, "status_code", ""))

    if service == "Twilio":
        messages = {
            "63016": (
                "The WhatsApp messaging window has closed. Send a WhatsApp message "
                "to your Twilio sender, then retry, or use an approved template."
            ),
            "63015": "This number must join your Twilio WhatsApp sandbox before receiving messages.",
            "20003": "Twilio authentication failed. Check the Account SID and Auth Token.",
            "21211": "Twilio rejected the recipient number. Check the country code and number.",
        }
        return messages.get(
            code,
            "Twilio did not confirm the request. Check the Twilio message logs before retrying to avoid duplicate messages.",
        )

    messages = {
        "400": "Gemini rejected the request. Check the model setting and try a smaller photo.",
        "401": "Check your Gemini API key in the secrets file.",
        "403": "Gemini access was denied. Check the API key and project permissions.",
        "404": "The configured Gemini model is unavailable. Set GEMINI_MODEL to a model your account can use.",
        "429": "Gemini's quota or rate limit was reached. Check your quota and try again later.",
        "503": "Gemini is temporarily busy. Please try again shortly.",
    }
    return messages.get(
        code,
        "Gemini could not finish this request. Check your connection and configuration, then try again.",
    )
