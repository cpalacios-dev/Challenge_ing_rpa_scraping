import sqlite3
import os
from contextlib import contextmanager

from config.settings import settings
from src.pipeline.logger import logger
from src.extractor.schemas import IndicadorFinanciero, EstadoExtraccion, NombreIndicador, FuenteOrigen
from src.storage.base_storage import BaseStorage


class SQLiteStorage(BaseStorage):
    def __init__(self, db_path: str = settings.SQLITE_DB_PATH):
        self.db_path = db_path
        self._ensure_schema()

    @contextmanager
    def _connect(self):
        dir_name = os.path.dirname(self.db_path)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        """Crea la tabla si no existe. El UNIQUE constraint es la fuente
        de verdad para deduplicar: la base de datos rechaza/reemplaza
        duplicados, no dependemos de lógica manual en Python."""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS indicadores_financieros (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fecha_dato TEXT NOT NULL,
                    nombre_indicador TEXT NOT NULL,
                    valor REAL,
                    fuente_origen TEXT NOT NULL,
                    fecha_extraccion TEXT NOT NULL,
                    estado_extraccion TEXT NOT NULL,
                    mensaje_error TEXT,
                    UNIQUE(fecha_dato, nombre_indicador, fuente_origen)
                )
            """)

    def save_indicadores(self, nuevos_indicadores: list[IndicadorFinanciero]) -> None:
        """Inserta nuevos indicadores. Si ya existe un registro con la misma
        (fecha_dato, nombre_indicador, fuente_origen), lo reemplaza
        (INSERT OR REPLACE) en vez de duplicarlo."""
        if not nuevos_indicadores:
            logger.warning("No hay indicadores para guardar en SQLite.")
            return

        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                for ind in nuevos_indicadores:
                    cursor.execute("""
                        INSERT OR REPLACE INTO indicadores_financieros
                            (fecha_dato, nombre_indicador, valor, fuente_origen,
                             fecha_extraccion, estado_extraccion, mensaje_error)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        ind.fecha_dato,
                        ind.nombre_indicador.value,
                        ind.valor,
                        ind.fuente_origen.value,
                        ind.fecha_extraccion,
                        ind.estado_extraccion.value,
                        ind.mensaje_error,
                    ))

                total = cursor.execute(
                    "SELECT COUNT(*) FROM indicadores_financieros"
                ).fetchone()[0]

            logger.info(f"Indicadores guardados exitosamente en SQLite. Total registros en histórico: {total}")
        except Exception as e:
            logger.error(f"Error al guardar indicadores en SQLite: {e}")

    def load_indicadores(self) -> list[IndicadorFinanciero]:
        """Recupera el histórico completo como objetos validados.
        Registros corruptos (no deberían existir si solo se escribió vía
        este mismo storage, pero por robustez se descartan individualmente)."""
        if not os.path.exists(self.db_path):
            logger.info(f"No existe base de datos previa en {self.db_path}. Se iniciará un registro nuevo.")
            return []

        try:
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute("SELECT * FROM indicadores_financieros").fetchall()
        except Exception as e:
            logger.error(f"Error al leer SQLite: {e}")
            return []

        indicadores = []
        registros_descartados = 0
        for row in rows:
            try:
                indicadores.append(IndicadorFinanciero(
                    fecha_dato=row["fecha_dato"],
                    nombre_indicador=row["nombre_indicador"],
                    valor=row["valor"],
                    fuente_origen=row["fuente_origen"],
                    fecha_extraccion=row["fecha_extraccion"],
                    estado_extraccion=row["estado_extraccion"],
                    mensaje_error=row["mensaje_error"],
                ))
            except Exception as e:
                registros_descartados += 1
                logger.warning(f"Registro SQLite descartado por no cumplir el schema actual: {e}")

        if registros_descartados:
            logger.warning(
                f"{registros_descartados} registro(s) descartados por incompatibilidad con el schema vigente."
            )
        return indicadores