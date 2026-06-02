"""Captura de vídeo RTSP (ou arquivo) com pulo de frames e reconexão automática."""
from __future__ import annotations

import logging
import time
from typing import Iterator

import cv2

logger = logging.getLogger(__name__)


class RTSPStream:
    """Abre uma fonte de vídeo e produz frames já amostrados (frame skipping).

    `source` pode ser uma URL RTSP ou um caminho de arquivo de vídeo.
    Para RTSP, reconecta automaticamente em caso de falha de leitura.
    """

    def __init__(
        self,
        source: str,
        frame_skip: int = 5,
        reconnect_delay_seconds: int = 5,
    ) -> None:
        self.source = source
        self.frame_skip = max(1, frame_skip)
        self.reconnect_delay = reconnect_delay_seconds
        self._is_file = not str(source).lower().startswith("rtsp")
        self._cap: cv2.VideoCapture | None = None
        self._stopped = False

    def _try_open(self) -> bool:
        """Tenta abrir a fonte. Retorna True se conseguiu."""
        self.close()
        self._cap = cv2.VideoCapture(self.source, cv2.CAP_FFMPEG)
        if self._cap.isOpened():
            logger.info("Fonte de vídeo aberta: %s", self.source)
            return True
        self.close()
        return False

    def _open_with_retry(self) -> bool:
        """Tenta abrir repetidamente até conseguir ou ser parado.

        Para arquivos de vídeo, não insiste: uma falha é definitiva.
        """
        while not self._stopped:
            if self._try_open():
                return True
            if self._is_file:
                logger.error("Não foi possível abrir o arquivo de vídeo: %s", self.source)
                return False
            logger.warning(
                "Câmera inacessível (%s). Nova tentativa em %ss.",
                self.source,
                self.reconnect_delay,
            )
            time.sleep(self.reconnect_delay)
        return False

    def frames(self) -> Iterator["cv2.typing.MatLike"]:
        """Gera frames amostrados. Para RTSP, reconecta em caso de falha."""
        if not self._open_with_retry():
            return
        skip_counter = 0
        while not self._stopped and self._cap is not None:
            # grab() descarta o frame do buffer sem decodificar (barato);
            # só decodificamos (retrieve) o frame que de fato será processado.
            grabbed = self._cap.grab()
            if not grabbed:
                if self._is_file:
                    logger.info("Fim do arquivo de vídeo.")
                    break
                logger.warning("Falha na leitura do stream. Reconectando...")
                time.sleep(self.reconnect_delay)
                if not self._open_with_retry():
                    break
                skip_counter = 0
                continue

            skip_counter += 1
            if skip_counter < self.frame_skip:
                continue
            skip_counter = 0

            ok, frame = self._cap.retrieve()
            if not ok or frame is None:
                continue
            yield frame

        self.close()

    def stop(self) -> None:
        self._stopped = True

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
