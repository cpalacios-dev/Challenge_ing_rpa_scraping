import sys
from src.pipeline.logger import logger
from src.extractor.bcentral_scraper import BancoCentralScraper
from src.storage.storage_factory import get_storage
from src.extractor.schemas import EstadoExtraccion

def run_pipeline():
    """
    Orquesta el flujo completo de Automatización RPA:
    1. Inicializa componentes.
    2. Ejecuta el Scraping del HTML.
    3. Normaliza y valida usando Pydantic (dentro del scraper).
    4. Persiste los datos resguardando el histórico.
    """
    logger.info("=== INICIANDO PIPELINE DIARIO DE INDICADORES FINANCIEROS ===")
    
    try:
        scraper = BancoCentralScraper()
        storage = get_storage()
        
        logger.info("Iniciando fase de extracción desde el Banco Central de Chile...")
        indicadores_extraidos = scraper.scrape()
        
        if not indicadores_extraidos:
            logger.warning("La fase de scraping no retornó ningún indicador. Revisar alertas.")
            return
            
        exitosos = sum(1 for x in indicadores_extraidos if x.estado_extraccion == EstadoExtraccion.EXITOSO)
        fallidos = sum(1 for x in indicadores_extraidos if x.estado_extraccion == EstadoExtraccion.FALLIDO)
        logger.info(f"Fase de extracción completada. Resultados: {exitosos} exitosos, {fallidos} fallidos.")
        
        logger.info("Iniciando fase de persistencia de datos...")
        storage.save_indicadores(indicadores_extraidos)
        
        logger.info("=== PIPELINE FINALIZADO EXITOSAMENTE ===")
        
    except Exception as e:
        logger.critical(f"Fallo catastrófico no controlado en la ejecución del pipeline: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    run_pipeline()