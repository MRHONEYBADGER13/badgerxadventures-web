"""Password hashing + signed session tokens.

Uses only Python's standard library (hashlib.scrypt is a real, modern
password-hashing KDF built into Python 3.6+) plus itsdangerous, which Flask
already depends on — nothing here needs an extra package install.
"""
import hashlib
import hmac
import os
import base64
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

_RENDER_DISK_DIR = "/opt/render/project/src/instance"
_DATA_DIR = _RENDER_DISK_DIR if os.path.isdir(_RENDER_DISK_DIR) else os.path.join(os.path.dirname(__file__), "instance")
SECRET_KEY_PATH = os.path.join(_DATA_DIR, "secret.key")


def get_secret_key():
    os.makedirs(os.path.dirname(SECRET_KEY_PATH), exist_ok=True)
    if not os.path.exists(SECRET_KEY_PATH):
        with open(SECRET_KEY_PATH, "wb") as f:
            f.write(os.urandom(32))
    with open(SECRET_KEY_PATH, "rb") as f:
        return f.read()


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_b64, hash_b64 = stored.split("$")
        assert scheme == "scrypt"
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


def _serializer(salt):
    return URLSafeTimedSerializer(get_secret_key(), salt=salt)


def make_owner_token(owner_id: int) -> str:
    return _serializer("owner-session").dumps({"owner_id": owner_id})


def read_owner_token(token: str, max_age=60 * 60 * 24 * 30):
    try:
        data = _serializer("owner-session").loads(token, max_age=max_age)
        return data.get("owner_id")
    except (BadSignature, SignatureExpired):
        return None


def make_cleaner_token(cleaner_id: int) -> str:
    return _serializer("cleaner-session").dumps({"cleaner_id": cleaner_id})


def read_cleaner_token(token: str, max_age=60 * 60 * 24 * 30):
    try:
        data = _serializer("cleaner-session").loads(token, max_age=max_age)
        return data.get("cleaner_id")
    except (BadSignature, SignatureExpired):
        return None


def make_admin_token(admin_id: int) -> str:
    return _serializer("admin-session").dumps({"admin_id": admin_id})


def read_admin_token(token: str, max_age=60 * 60 * 24 * 30):
    try:
        data = _serializer("admin-session").loads(token, max_age=max_age)
        return data.get("admin_id")
    except (BadSignature, SignatureExpired):
        return None


def pw_marker(password_hash: str) -> str:
    """A short fingerprint of a password hash. Embedding this in a reset
    token (below) means the token stops verifying the moment the password it
    was issued for actually changes -- a cheap, storage-free way to make
    reset links single-use without a database table to track them in."""
    return hashlib.sha256(password_hash.encode("utf-8")).hexdigest()[:16]


def make_reset_token(owner_id: int, password_hash: str) -> str:
    return _serializer("owner-reset").dumps({"owner_id": owner_id, "h": pw_marker(password_hash)})


def read_reset_token(token: str, max_age=60 * 60 * 2):
    """Checks only the signature and the 2-hour expiry. The caller still has
    to compare the returned payload's "h" against pw_marker(current
    password_hash) before trusting it -- that's what catches a token that's
    already been used."""
    try:
        return _serializer("owner-reset").loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None


def gen_invite_code() -> str:
    """A short, hard-to-guess, easy-to-type code like LAKE-7F3K-9QRX."""
    alphabet = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # no 0/O/1/I to avoid confusion
    import secrets
    parts = ["".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(2)]
    return "-".join(parts)
