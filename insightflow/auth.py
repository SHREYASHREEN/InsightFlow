"""Authentication: scrypt password hashing (Python standard library), roles and permissions."""
import base64
import hashlib
import hmac
import os
import re
from . import timeutil

SCRYPT_N, SCRYPT_R, SCRYPT_P = 2 ** 14, 8, 1
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")

PERMISSIONS = {
    "Admin": {"view", "export", "requirement.write", "requirement.delete", "docs.write", "docs.delete",
              "request.write", "request.delete", "import", "report", "user.manage", "settings.manage"},
    "Business Analyst": {"view", "export", "requirement.write", "docs.write", "request.write", "import", "report"},
    "Viewer": {"view", "export"},
}


def has_permission(role, permission):
    return permission in PERMISSIONS.get(role, set())


def hash_password(password):
    if not isinstance(password, str) or password == "":
        raise ValueError("Password must be a non-empty string")
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
    return "scrypt${}${}${}${}${}".format(SCRYPT_N, SCRYPT_R, SCRYPT_P,
                                          base64.b64encode(salt).decode(), base64.b64encode(dk).decode())


def verify_password(password, stored):
    try:
        scheme, n, r, p, salt_b64, dk_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        salt, expected = base64.b64decode(salt_b64), base64.b64decode(dk_b64)
        dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=int(n), r=int(r), p=int(p), dklen=len(expected))
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


def validate_new_user(username, full_name, password):
    errors = []
    if not USERNAME_RE.match(username or ""):
        errors.append("Username must be 3-30 characters: letters, digits, '_', '.' or '-'.")
    if not (full_name or "").strip():
        errors.append("Full name is required.")
    pw = password or ""
    if len(pw) < 8:
        errors.append("Password must be at least 8 characters.")
    elif not (re.search(r"[A-Za-z]", pw) and re.search(r"\d", pw)):
        errors.append("Password must contain at least one letter and one digit.")
    return errors


def create_user(conn, username, full_name, password, role="Viewer"):
    """Returns (user_id, errors)."""
    errors = validate_new_user(username, full_name, password)
    if role not in PERMISSIONS:
        errors.append("Invalid role.")
    if errors:
        return None, errors
    exists = conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
    if exists:
        return None, ["That username is already taken."]
    with conn:
        cur = conn.execute(
            "INSERT INTO users(username, full_name, password_hash, role, active, created_at) VALUES (?,?,?,?,1,?)",
            (username, full_name.strip(), hash_password(password), role, timeutil.to_str(timeutil.now_utc())))
    return cur.lastrowid, []


def authenticate(conn, username, password):
    """Returns (user_dict_or_None, message). Same message for unknown user / wrong password."""
    if not username or not password:
        return None, "Please enter both username and password."
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username.strip(),)).fetchone()
    if row is None or not verify_password(password, row["password_hash"]):
        return None, "Invalid username or password."
    if not row["active"]:
        return None, "This account is disabled. Contact an administrator."
    return {"id": row["id"], "username": row["username"], "full_name": row["full_name"], "role": row["role"]}, "OK"


def list_users(conn):
    return [dict(r) for r in conn.execute(
        "SELECT id, username, full_name, role, active, created_at FROM users ORDER BY username")]


def set_user_role(conn, user_id, role):
    if role not in PERMISSIONS:
        raise ValueError("Invalid role")
    with conn:
        conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))


def set_user_active(conn, user_id, active):
    with conn:
        conn.execute("UPDATE users SET active = ? WHERE id = ?", (1 if active else 0, user_id))


def reset_password(conn, user_id, new_password):
    errors = validate_new_user("placeholder", "x", new_password)
    errors = [e for e in errors if "Password" in e]
    if errors:
        return errors
    with conn:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(new_password), user_id))
    return []


def delete_user(conn, user_id):
    with conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
