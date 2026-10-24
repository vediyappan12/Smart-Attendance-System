import base64
import binascii
import json

import cv2
import numpy as np
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException

from .config import settings

MAX_IMAGE_BYTES = 5 * 1024 * 1024


class FaceEngine:
    @staticmethod
    def _fernet() -> Fernet:
        if not settings.BIOMETRIC_ENCRYPTION_KEY:
            raise HTTPException(
                status_code=503,
                detail="Face enrollment is disabled until BIOMETRIC_ENCRYPTION_KEY is configured",
            )
        try:
            return Fernet(settings.BIOMETRIC_ENCRYPTION_KEY.encode("ascii"))
        except (ValueError, UnicodeEncodeError) as exc:
            raise HTTPException(status_code=500, detail="Invalid biometric encryption key configuration") from exc

    @staticmethod
    def encrypt_embedding(embedding: list[float]) -> str:
        serialized = json.dumps(embedding, separators=(",", ":")).encode("utf-8")
        return FaceEngine._fernet().encrypt(serialized).decode("ascii")

    @staticmethod
    def decrypt_embedding(encrypted_embedding: str) -> list[float]:
        try:
            decoded = FaceEngine._fernet().decrypt(encrypted_embedding.encode("ascii"))
            embedding = json.loads(decoded)
        except (InvalidToken, ValueError, UnicodeEncodeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=500, detail="Stored biometric data could not be decrypted") from exc
        if not isinstance(embedding, list) or not all(isinstance(item, (int, float)) for item in embedding):
            raise HTTPException(status_code=500, detail="Stored biometric data is invalid")
        return [float(item) for item in embedding]

    @staticmethod
    def decode_image_from_base64(value: str) -> np.ndarray:
        encoded = value.split(",", 1)[1] if value.startswith("data:") and "," in value else value
        try:
            image_bytes = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Image must be valid base64 data") from exc
        if not image_bytes or len(image_bytes) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="Image must be smaller than 5 MB")
        try:
            image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        except cv2.error as exc:
            raise HTTPException(status_code=400, detail="Uploaded data is not a valid image") from exc
        if image is None or image.size == 0:
            raise HTTPException(status_code=400, detail="Uploaded data is not a valid image")
        if image.shape[0] > 4096 or image.shape[1] > 4096:
            raise HTTPException(status_code=413, detail="Image dimensions must not exceed 4096 by 4096")
        return image

    @staticmethod
    def extract_embedding(image_bgr: np.ndarray) -> list[float]:
        try:
            import face_recognition
        except ImportError as exc:
            raise HTTPException(
                status_code=503,
                detail="Optional face recognition is not installed; install backend/requirements-face.txt",
            ) from exc

        rgb_image = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        boxes = face_recognition.face_locations(rgb_image, model="hog")
        if not boxes:
            raise HTTPException(status_code=400, detail="No face detected")
        if len(boxes) > 1:
            raise HTTPException(status_code=400, detail="Multiple faces detected; use an image with one face")

        encodings = face_recognition.face_encodings(rgb_image, boxes)
        if not encodings:
            raise HTTPException(status_code=400, detail="Could not compute a face embedding")
        return encodings[0].tolist()

    @staticmethod
    def match_face(input_encoding: list[float], stored_encoding: list[float]) -> tuple[bool, float]:
        try:
            import face_recognition
        except ImportError as exc:
            raise HTTPException(
                status_code=503,
                detail="Optional face recognition is not installed; install backend/requirements-face.txt",
            ) from exc
        distance = float(
            face_recognition.face_distance([np.asarray(stored_encoding)], np.asarray(input_encoding))[0]
        )
        confidence = max(0.0, 1.0 - distance)
        return distance <= 0.5, confidence
