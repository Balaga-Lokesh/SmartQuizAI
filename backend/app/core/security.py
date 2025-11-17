# app/core/security.py
import hashlib
import bcrypt


def _pre_hash_bytes(password: str) -> bytes:
    """Return the raw SHA-256 digest bytes for the provided password.

    We use the raw digest (32 bytes) to ensure the input to bcrypt is always
    <= 72 bytes. Using the raw digest preserves entropy and is deterministic
    so verification can re-compute it.
    """
    return hashlib.sha256(password.encode("utf-8", errors="ignore")).digest()


def hash_password(password: str) -> str:
    """Hash a plain password, returning a bcrypt hash string.

    The password is pre-hashed (SHA-256) and then passed to bcrypt.hashpw.
    Using bcrypt.hashpw directly avoids passlib backend detection issues and
    the 72-byte limitation for long input strings.
    """
    pre = _pre_hash_bytes(password)
    hashed = bcrypt.hashpw(pre, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a stored bcrypt hash.

    We pre-hash the candidate and use bcrypt.checkpw to verify.
    """
    pre = _pre_hash_bytes(plain_password)
    try:
        return bcrypt.checkpw(pre, hashed_password.encode("utf-8"))
    except Exception:
        return False
