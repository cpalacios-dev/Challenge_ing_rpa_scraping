from abc import ABC, abstractmethod
from src.extractor.schemas import IndicadorFinanciero


class BaseStorage(ABC):
    """
    Contrato que debe cumplir cualquier motor de persistencia
    (JSON, SQLite, CSV, etc). El runner solo conoce esta interfaz,
    nunca el detalle de implementación de cada backend.
    """

    @abstractmethod
    def save_indicadores(self, nuevos_indicadores: list[IndicadorFinanciero]) -> None:
        """Persiste nuevos indicadores, evitando duplicados por
        (fecha_dato, nombre_indicador, fuente_origen)."""
        raise NotImplementedError

    @abstractmethod
    def load_indicadores(self) -> list[IndicadorFinanciero]:
        """Recupera el histórico completo como objetos validados."""
        raise NotImplementedError