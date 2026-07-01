"""Rozpoznawanie cyfr pierścienia numerycznego (1..20) tarczy.

Dlaczego template matching zamiast OCR ogólnego przeznaczenia?
  * Zbiór klas jest maleńki i zamknięty (1..20) — nie potrzebujemy pełnego OCR.
  * Cyfry na obręczy tarczy są OBRÓCONE względem pionu (każda pod innym kątem),
    a klasyczny OCR (Tesseract) zakłada tekst poziomy. Dopasowanie szablonu z
    jawnym przeszukaniem po kącie obrotu jest tu odporniejsze i bez zależności
    systemowych — działa offline.
  * Backend Tesseract pozostaje dostępny opcjonalnie (TesseractRecognizer) jako
    walidacja/redundancja, jeśli ktoś ma go zainstalowanego.

Interfejs DigitRecognizer jest wtykowy — BoardCalibrator przyjmuje dowolną
implementację, więc łatwo podmienić metodę po dostarczeniu realnych klatek.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import cv2
import numpy as np

# Zbiór dozwolonych etykiet — sztywne, jednoznaczne markery orientacji.
VALID_LABELS = tuple(range(1, 21))


class DigitRecognizer(ABC):
    """Klasyfikuje wycinek obrazu z obręczy na liczbę 1..20 (lub None)."""

    @abstractmethod
    def classify(self, patch: np.ndarray) -> tuple[Optional[int], float]:
        """Zwróć (etykieta lub None, pewność w [0,1]) dla wycinka w skali szarości."""
        raise NotImplementedError


class TemplateMatcher(DigitRecognizer):
    """Dopasowanie do szablonów cyfr renderowanych czcionką OpenCV.

    Buduje wzorce dla wszystkich etykiet 1..20, każdy w kilku obrotach, i wybiera
    najlepszą korelację. Odporny na obrót cyfry względem pionu.
    """

    def __init__(
        self,
        patch_size: int = 48,
        rotations_deg: tuple[float, ...] = tuple(range(-180, 180, 15)),
        font: int = cv2.FONT_HERSHEY_SIMPLEX,
        min_confidence: float = 0.45,
    ) -> None:
        self.patch_size = patch_size
        self.rotations_deg = rotations_deg
        self.font = font
        self.min_confidence = min_confidence
        self._templates = self._build_templates()

    def _render_label(self, label: int) -> np.ndarray:
        """Wyrenderuj białą cyfrę na czarnym tle (rozmiar dobierany później przez bbox)."""
        text = str(label)
        scale, thickness = 2.0, 3
        (tw, th), _ = cv2.getTextSize(text, self.font, scale, thickness)
        pad = 8
        canvas = np.zeros((th + 2 * pad, tw + 2 * pad), dtype=np.uint8)
        cv2.putText(canvas, text, (pad, th + pad), self.font, scale, 255, thickness, cv2.LINE_AA)
        return canvas

    def _rotate(self, img: np.ndarray, angle_deg: float) -> np.ndarray:
        h, w = img.shape[:2]
        m = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle_deg, 1.0)
        return cv2.warpAffine(img, m, (w, h))

    def _build_templates(self) -> dict[int, list[np.ndarray]]:
        templates: dict[int, list[np.ndarray]] = {}
        for label in VALID_LABELS:
            base = self._render_label(label)
            variants = [self._prep(self._rotate(base, a)) for a in self.rotations_deg]
            templates[label] = variants
        return templates

    def _prep(self, binary: np.ndarray) -> np.ndarray:
        """Przytnij do bounding boxa 'atramentu', przeskaluj do kwadratu i znormalizuj.

        Dzięki przycięciu do bbox dopasowanie jest niezależne od rozmiaru i
        pozycji cyfry w wycinku — kluczowe, bo render kamery i szablon mają różną
        skalę. Zwraca wektor o zerowej średniej i jednostkowej normie (do korelacji).
        """
        ys, xs = np.nonzero(binary > 127)
        if len(xs) == 0:
            return np.zeros((self.patch_size, self.patch_size), dtype=np.float32)
        crop = binary[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
        crop = cv2.resize(crop, (self.patch_size, self.patch_size), interpolation=cv2.INTER_AREA)
        f = crop.astype(np.float32)
        f -= f.mean()
        n = np.linalg.norm(f)
        return f / n if n > 1e-6 else f

    def classify(self, patch: np.ndarray) -> tuple[Optional[int], float]:
        if patch.ndim == 3:
            patch = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
        # Binaryzacja (Otsu) -> biała cyfra na czarnym tle, jak w szablonach.
        _, binary = cv2.threshold(patch, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        q = self._prep(binary)
        if not np.any(q):
            return None, 0.0

        best_label: Optional[int] = None
        best_score = -1.0
        for label, variants in self._templates.items():
            score = max(float(np.sum(q * t)) for t in variants)  # znormalizowana korelacja
            if score > best_score:
                best_score = score
                best_label = label

        confidence = max(0.0, min(1.0, best_score))
        if confidence < self.min_confidence:
            return None, confidence
        return best_label, confidence


class TesseractRecognizer(DigitRecognizer):
    """Opcjonalny backend OCR oparty o Tesseract (wymaga pakietu i binarki systemowej).

    Importuje pytesseract leniwie, aby brak zależności nie psuł reszty modułu.
    """

    def __init__(self, min_confidence: float = 0.5) -> None:
        try:
            import pytesseract  # noqa: F401
        except ImportError as exc:  # pragma: no cover - zależy od środowiska
            raise ImportError(
                "TesseractRecognizer wymaga pakietu 'pytesseract' oraz binarki tesseract. "
                "Zainstaluj extra: pip install .[ocr-tesseract]"
            ) from exc
        self.min_confidence = min_confidence

    def classify(self, patch: np.ndarray) -> tuple[Optional[int], float]:  # pragma: no cover
        import pytesseract

        if patch.ndim == 3:
            patch = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
        cfg = "--psm 8 -c tessedit_char_whitelist=0123456789"
        text = pytesseract.image_to_string(patch, config=cfg).strip()
        if not text.isdigit():
            return None, 0.0
        value = int(text)
        if value in VALID_LABELS:
            return value, 1.0
        return None, 0.0
