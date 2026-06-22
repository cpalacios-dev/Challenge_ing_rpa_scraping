import time
from datetime import datetime
from playwright.sync_api import sync_playwright
from config.settings import settings
from src.extractor.schemas import (
    IndicadorFinanciero,
    EstadoExtraccion,
    NombreIndicador,
    FuenteOrigen,
)
from src.pipeline.logger import logger


class BancoCentralScraper:
    def __init__(self):
        self.url = settings.URL_BANCO_CENTRAL
        self.timeout = settings.TIMEOUT * 1000  # Playwright usa milisegundos
        self.max_retries = settings.MAX_RETRIES

    def _clean_value(self, text_value: str) -> float:
        """Normaliza los strings de moneda chilena a floats estándar."""
        cleaned = text_value.replace("$", "").replace(" ", "").strip()
        cleaned = cleaned.replace(".", "")  # Quita separador de miles
        cleaned = cleaned.replace(",", ".")  # Cambia coma decimal por punto
        return float(cleaned)

    def scrape(self) -> list[IndicadorFinanciero]:
        """Extrae la UF, Dólar, Euro y UTM usando un navegador automatizado real con Playwright."""
        indicadores = []
        fecha_hoy = datetime.now().strftime("%d-%m-%Y")

        logger.info(f"Iniciando navegador automatizado (Playwright) para {self.url}...")

        with sync_playwright() as p:
            try:
                # Lanzamos Chromium simulando ser un usuario de escritorio normal
                browser = p.chromium.launch(headless=True)

                # Configuramos un contexto con una resolución estándar para evitar banderas anti-bot
                context = browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                )

                # Navegar a la URL esperando a que el DOM básico esté cargado
                logger.info(
                    f"Navegando a la página de inicio con máximo "
                    f"{self.max_retries} intento(s)..."
                )

                ultima_excepcion = None

                for intento in range(1, self.max_retries + 1):
                    
                    page = context.new_page()
                    try:
                        logger.info(
                            f"Intento {intento}/{self.max_retries} "
                            f"de navegación hacia {self.url}"
                        )

                        page.goto(
                            self.url,
                            timeout=self.timeout,
                            wait_until="domcontentloaded"
                        )

                        logger.info(
                            f"Navegación exitosa en intento {intento}"
                        )

                        break

                    except Exception as e:
                        ultima_excepcion = e

                        logger.warning(
                            f"Falló intento {intento}/{self.max_retries}: {e}"
                        )

                        if intento < self.max_retries:

                            backoff = 2 ** intento

                            logger.info(
                                f"Esperando {backoff} segundos antes de reintentar..."
                            )

                            time.sleep(backoff)

                        else:
                            raise ultima_excepcion

                # Mapeo de indicadores basado directamente en las clases de los párrafos del HTML real
                targets = [
                    {
                        "nombre": NombreIndicador.UF,
                        "selector": ".tooltip-wrap:has-text('UF') p.fs-2",
                    },
                    {
                        "nombre": NombreIndicador.DOLAR_OBSERVADO,
                        "selector": ".tooltip-wrap:has-text('Dólar Observado') p.fs-2",
                    },
                    {
                        "nombre": NombreIndicador.EURO,
                        "selector": ".tooltip-wrap:has-text('Euro') p.fs-2",
                    },
                    {
                        "nombre": NombreIndicador.UTM,
                        "selector": ".tooltip-wrap:has-text('UTM') p.fs-2",
                    },
                ]

                for target in targets:
                    nombre = target["nombre"]
                    try:
                        # Esperamos a que el elemento aparezca renderizado en la pantalla
                        page.wait_for_selector(target["selector"], timeout=5000)

                        # Extraemos el texto directamente desde el elemento del navegador
                        valor_raw = page.locator(
                            target["selector"]
                        ).first.text_content()

                        if not valor_raw or not valor_raw.strip():
                            raise AttributeError(
                                "El elemento estaba presente pero no contenía texto."
                            )

                        valor_raw = valor_raw.strip()

                        # Limpieza por si viene el desglose del Dólar ($897,19 /$900,6)
                        if "/" in valor_raw:
                            valor_raw = valor_raw.split("/")[0].strip()

                        # Intentamos parsear el número. Si el selector funcionó pero el
                        # formato cambió (ej. BCCh modifica cómo escribe el número),
                        # esto es un caso "parcial": el dato se encontró pero no se
                        # pudo interpretar con confianza, distinto de "no se encontró nada".
                        try:
                            valor = self._clean_value(valor_raw)
                        except (ValueError, AttributeError) as e_parse:
                            logger.warning(
                                f"Indicador {nombre.value} encontrado pero con formato "
                                f"inesperado ('{valor_raw}'): {e_parse}"
                            )
                            indicadores.append(
                                IndicadorFinanciero(
                                    fecha_dato=fecha_hoy,
                                    nombre_indicador=nombre,
                                    fuente_origen=FuenteOrigen.BANCO_CENTRAL,
                                    estado_extraccion=EstadoExtraccion.PARCIAL,
                                    mensaje_error=f"Formato de valor inesperado: '{valor_raw}'",
                                )
                            )
                            continue

                        indicadores.append(
                            IndicadorFinanciero(
                                fecha_dato=fecha_hoy,
                                nombre_indicador=nombre,
                                valor=valor,
                                fuente_origen=FuenteOrigen.BANCO_CENTRAL,
                                estado_extraccion=EstadoExtraccion.EXITOSO,
                            )
                        )
                        logger.info(
                            f"Extracción exitosa en BCCh: {nombre.value} = {valor}"
                        )

                    except Exception as e_selector:
                        logger.error(
                            f"No se pudo extraer el indicador {nombre.value} con Playwright: {e_selector}"
                        )
                        indicadores.append(
                            IndicadorFinanciero(
                                fecha_dato=fecha_hoy,
                                nombre_indicador=nombre,
                                fuente_origen=FuenteOrigen.BANCO_CENTRAL,
                                estado_extraccion=EstadoExtraccion.FALLIDO,
                                mensaje_error=str(e_selector),
                            )
                        )

                context.close()
                browser.close()

            except Exception as e_global:
                logger.critical(f"Fallo crítico en el motor de Playwright: {e_global}")
                # Fallback controlado si el navegador completo falla al levantar
                for nombre in [
                    NombreIndicador.UF,
                    NombreIndicador.DOLAR_OBSERVADO,
                    NombreIndicador.EURO,
                    NombreIndicador.UTM,
                ]:
                    indicadores.append(
                        IndicadorFinanciero(
                            fecha_dato=fecha_hoy,
                            nombre_indicador=nombre,
                            fuente_origen=FuenteOrigen.BANCO_CENTRAL,
                            estado_extraccion=EstadoExtraccion.FALLIDO,
                            mensaje_error=f"Fallo crítico de Playwright: {e_global}",
                        )
                    )

        return indicadores
