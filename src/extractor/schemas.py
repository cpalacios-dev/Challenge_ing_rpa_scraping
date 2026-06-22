"""
Esquemas de datos del pipeline de indicadores financieros.

Define el contrato único que deben cumplir TODOS los scrapers
(Banco Central, Bolsa de Santiago, etc.) antes de que un dato
pueda considerarse válido para persistencia.
"""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


class EstadoExtraccion(str, Enum):
    """Estado del proceso de extracción para un indicador puntual."""
    EXITOSO = "exitoso"
    PARCIAL = "parcial"
    FALLIDO = "fallido"


class NombreIndicador(str, Enum):
    """
    Catálogo cerrado de indicadores soportados.

    Usar un Enum (en vez de str libre) evita inconsistencias silenciosas
    aguas abajo, por ejemplo "Dolar" vs "Dólar Observado" vs "USD",
    que romperían agrupaciones/reportes sin lanzar ningún error.
    """
    UF = "UF"
    UTM = "UTM"
    DOLAR_OBSERVADO = "Dólar observado"
    EURO = "Euro"
    IPC = "IPC"
    IPSA = "IPSA"  # índice bursátil, Bolsa de Santiago


class FuenteOrigen(str, Enum):
    """Catálogo cerrado de fuentes de scraping habilitadas."""
    BANCO_CENTRAL = "Banco Central de Chile"
    BOLSA_SANTIAGO = "Bolsa de Santiago"


class IndicadorFinanciero(BaseModel):
    fecha_dato: str = Field(
        ...,
        description="Fecha a la que corresponde el valor, formato DD-MM-YYYY",
    )
    nombre_indicador: NombreIndicador = Field(
        ..., description="Indicador financiero, ej: UF, Dólar observado, Euro"
    )
    valor: float | None = Field(
        default=None,
        ge=0,
        description="Valor numérico del indicador. None si estado_extraccion != exitoso",
    )
    fuente_origen: FuenteOrigen = Field(
        ..., description="Sitio público desde el cual se obtuvo el dato"
    )
    fecha_extraccion: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Timestamp ISO de cuándo se ejecutó el scraping",
    )
    estado_extraccion: EstadoExtraccion = Field(
        ..., description="exitoso, parcial o fallido"
    )
    mensaje_error: str | None = Field(
        default=None,
        description="Detalle del error cuando estado_extraccion != exitoso",
    )

    @field_validator("fecha_dato")
    @classmethod
    def validar_formato_fecha(cls, v: str) -> str:
        """Falla rápido si la fecha no es DD-MM-YYYY real (no solo un string)."""
        try:
            datetime.strptime(v, "%d-%m-%Y")
        except ValueError as exc:
            raise ValueError(
                f"fecha_dato='{v}' no tiene formato válido DD-MM-YYYY"
            ) from exc
        return v

    @model_validator(mode="after")
    def validar_consistencia_estado_valor(self) -> "IndicadorFinanciero":
        """
        Regla de negocio:
        - exitoso  -> debe traer un valor numérico real (no None, no 0.0)
        - parcial / fallido -> no debe traer un valor (None), porque no hay
          un número confiable que reportar; el detalle va en mensaje_error.
        """
        if self.estado_extraccion == EstadoExtraccion.EXITOSO:
            if self.valor is None or self.valor == 0.0:
                raise ValueError(
                    "Un indicador 'exitoso' debe traer un valor numérico real distinto de 0.0"
                )
        else:  # PARCIAL o FALLIDO
            if self.valor is not None:
                raise ValueError(
                    f"Un indicador con estado_extraccion='{self.estado_extraccion.value}' "
                    "no debe traer valor (debe ser None)"
                )
        return self