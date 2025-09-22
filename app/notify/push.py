import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

from pywebpush import WebPushException, webpush

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat
except Exception:  # pragma: no cover - optional dependency
    ec = None  # type: ignore
    Encoding = None  # type: ignore
    PrivateFormat = None  # type: ignore
    NoEncryption = None  # type: ignore
    PublicFormat = None  # type: ignore
    serialization = None  # type: ignore


logger = logging.getLogger(__name__)


class SubscriptionStore:
    def __init__(self, file_path: str = "subscriptions.json") -> None:
        self.file_path = Path(file_path)
        self._ensure_file()

    def _ensure_file(self) -> None:
        if not self.file_path.exists():
            self.file_path.write_text("[]", encoding="utf-8")

    def list(self) -> List[Dict]:
        try:
            return json.loads(self.file_path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def add(self, subscription: Dict) -> None:
        items = self.list()
        # Deduplicate by endpoint
        endpoints = {it.get("endpoint") for it in items if isinstance(it, dict)}
        if subscription.get("endpoint") not in endpoints:
            items.append(subscription)
            self.file_path.write_text(json.dumps(items), encoding="utf-8")

    def remove(self, endpoint: str) -> None:
        items = [it for it in self.list() if it.get("endpoint") != endpoint]
        self.file_path.write_text(json.dumps(items), encoding="utf-8")


def _get_env(name: str, default: str) -> str:
    return os.getenv(name, default)


def ensure_vapid_keys(private_file: str = "vapid_private_key.pem", public_file: str = "vapid_public_key.txt") -> Optional[Dict[str, str]]:
    public_env = _get_env("VAPID_PUBLIC_KEY", "").strip()
    private_env = _get_env("VAPID_PRIVATE_KEY", "").strip()
    subject = _get_env("VAPID_SUBJECT", "mailto:admin@example.com").strip()
    if public_env and private_env:
        return {"public": public_env, "private": private_env, "subject": subject}

    # Try file-based keys
    priv_path = Path(private_file)
    pub_path = Path(public_file)
    if priv_path.exists() and pub_path.exists():
        try:
            private_pem = priv_path.read_text(encoding="utf-8")
            public_b64u = pub_path.read_text(encoding="utf-8").strip()
            return {"public": public_b64u, "private": private_pem, "subject": subject}
        except Exception as exc:
            logger.warning(f"Konnte VAPID Keys nicht lesen: {exc}")

    # Generate new keys if cryptography available
    try:
        if ec is None:
            logger.warning("cryptography nicht verfügbar. Push wird deaktiviert bis Keys bereitgestellt werden.")
            return None
        private_key = ec.generate_private_key(ec.SECP256R1())
        private_pem = private_key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=NoEncryption(),
        ).decode("utf-8")

        public_key = private_key.public_key()
        public_bytes = public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
        # Base64 URL-safe without padding for browser subscription
        import base64

        public_b64u = base64.urlsafe_b64encode(public_bytes).rstrip(b"=").decode("ascii")

        priv_path.write_text(private_pem, encoding="utf-8")
        pub_path.write_text(public_b64u, encoding="utf-8")
        logger.info(f"VAPID Keys generiert und gespeichert unter {priv_path} / {pub_path}")
        return {"public": public_b64u, "private": private_pem, "subject": subject}
    except Exception as exc:  # pragma: no cover
        logger.warning(f"VAPID Key-Generierung fehlgeschlagen: {exc}")
        return None


def send_push_to_all(store: SubscriptionStore, payload: Dict, vapid: Optional[Dict[str, str]]) -> int:
    if vapid is None:
        return 0
    subs = store.list()
    sent = 0
    for sub in subs:
        try:
            webpush(
                subscription_info=sub,
                data=json.dumps(payload),
                vapid_private_key=vapid["private"],
                vapid_claims={"sub": vapid["subject"]},
            )
            sent += 1
        except WebPushException as exc:
            logger.warning(f"Push fehlgeschlagen, entferne Subscription: {exc}")
            endpoint = sub.get("endpoint")
            if endpoint:
                try:
                    store.remove(endpoint)
                except Exception:
                    pass
        except Exception as exc:  # pragma: no cover
            logger.warning(f"Push Fehler: {exc}")
    return sent

