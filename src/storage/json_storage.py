import json
import os
from config.settings import settings
from src.pipeline.logger import logger
from src.extractor.schemas import IndicadorFinanciero
from src.storage.base_storage import BaseStorage


class JSONStorage(BaseStorage):
    def __init__(self, file_path=settings.OUTPUT_FILE):
        self.file_path = file_path

    def _clave_unica(self, ind: IndicadorFinanciero) -> tuple:
        """
        Clave natural de un registro: un mismo indicador, de una misma fuente,
        para una misma fecha de dato, debe existir una sola vez en el histórico.
        Ejecuciones repetidas el mismo día sobrescriben el registro anterior
        en vez de duplicarlo.
        """
        return (ind.fecha_dato, ind.nombre_indicador.value, ind.fuente_origen.value)

    def save_indicadores(self, nuevos_indicadores: list[IndicadorFinanciero]) -> None:
        """Guarda y acumula una lista de IndicadorFinanciero en el archivo JSON,
        resguardando el histórico y evitando registros duplicados por
        (fecha_dato, nombre_indicador, fuente_origen)."""
        try:
            historico_existente = self.load_indicadores()

            registros_por_clave = {
                self._clave_unica(ind): ind for ind in historico_existente
            }
            duplicados_sobrescritos = 0
            for ind in nuevos_indicadores:
                clave = self._clave_unica(ind)
                if clave in registros_por_clave:
                    duplicados_sobrescritos += 1
                registros_por_clave[clave] = ind

            data_to_save = [ind.model_dump(mode="json") for ind in registros_por_clave.values()]

            dir_name = os.path.dirname(self.file_path)
            if dir_name and not os.path.exists(dir_name):
                os.makedirs(dir_name, exist_ok=True)

            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=4)

            if duplicados_sobrescritos:
                logger.info(
                    f"{duplicados_sobrescritos} registro(s) existente(s) fueron "
                    f"actualizados (misma fecha/indicador/fuente)."
                )
            logger.info(f"Indicadores guardados exitosamente. Total registros en histórico: {len(data_to_save)}")
        except Exception as e:
            logger.error(f"Error al guardar indicadores en JSON: {e}")

    def load_indicadores(self) -> list[IndicadorFinanciero]:
        """Carga indicadores desde el archivo JSON, devolviendo una lista de objetos Pydantic.
        Registros corruptos o que ya no cumplen el schema actual se descartan
        individualmente (no se pierde todo el histórico por un solo registro malo)."""
        if not os.path.exists(self.file_path) or os.path.getsize(self.file_path) == 0:
            logger.info(f"No existe historial previo en {self.file_path}. Se iniciará un registro nuevo.")
            return []

        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data_loaded = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Archivo JSON corrupto, no se pudo parsear: {e}")
            return []

        indicadores = []
        registros_descartados = 0
        for item in data_loaded:
            try:
                indicadores.append(IndicadorFinanciero(**item))
            except Exception as e:
                registros_descartados += 1
                logger.warning(f"Registro histórico descartado por no cumplir el schema actual: {e}")

        if registros_descartados:
            logger.warning(
                f"{registros_descartados} registro(s) histórico(s) fueron descartados "
                "por incompatibilidad con el schema vigente."
            )
        return indicadores