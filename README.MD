# Pipeline de Indicadores Financieros — Banco Central de Chile

Automatización diaria que extrae indicadores financieros públicos (UF, Dólar
observado, Euro, UTM) mediante **web scraping**, sin uso de APIs externas,
normaliza los datos en un esquema validado y los persiste de forma histórica.

---

## Índice

1. [Arquitectura del proyecto](#arquitectura-del-proyecto)
2. [Instalación y ejecución local](#instalación-y-ejecución-local)
3. [Configuración (variables de entorno)](#configuración-variables-de-entorno)
4. [Decisiones técnicas](#decisiones-técnicas)
5. [Supuestos](#supuestos)
6. [Limitaciones conocidas y alternativas](#limitaciones-conocidas-y-alternativas)
7. [Propuesta de arquitectura en GCP](#propuesta-de-arquitectura-en-gcp)
8. [Monitoreo, alertas y seguridad](#monitoreo-alertas-y-seguridad)

---

## Arquitectura del proyecto

```
proyecto/
│   .env                      # variables de entorno (no versionado)
│   .env.example              # plantilla de referencia
│   .gitignore
│   evidencia_ejecucion.log   # log de ejecución
│   Dockerfile                # imagen para Cloud Run Job (Python + Playwright)
│   main.py                   # punto de entrada
│   requirements.txt
│
├───.github/
│   └───workflows/
│           pipeline.yml      # CI/CD: build, push y deploy a Cloud Run Job
│
├───config/
│       settings.py           # carga centralizada de configuración
│
├───src/
│   ├───extractor/
│   │       schemas.py            # contrato de datos (Pydantic + Enums)
│   │       bcentral_scraper.py   # scraping del Banco Central (Playwright)
│   │
│   ├───output/
│   │
│   ├───pipeline/
│   │       logger.py             # logging estructurado
│   │       runner.py             # orquestador del pipeline
│   │
│   └───storage/
│           base_storage.py       # interfaz común de persistencia
│           json_storage.py       # implementación JSON
│           sqlite_storage.py     # implementación SQLite
│           storage_factory.py    # selección de backend vía .env
│
└───tests/
        test_schemas.py
```

**Separación de responsabilidades:**

| Capa | Responsabilidad | No hace |
|---|---|---|
| `extractor` | Obtener HTML renderizado y devolver objetos `IndicadorFinanciero` validados | No decide dónde se guardan los datos |
| `pipeline` | Orquestar el flujo (extraer → resumir → persistir) y loguear cada fase | No conoce el detalle de cómo se scrapea ni cómo se guarda |
| `storage` | Persistir y recuperar el histórico, sin duplicar registros | No valida reglas de negocio (eso ya lo hizo Pydantic antes de llegar aquí) |

---

## Instalación y ejecución local

### Requisitos previos
- Python 3.12+
- Conexión a internet (para descargar los navegadores de Playwright la primera vez)

### Pasos

```bash
# 1. Clonar/descomprimir el proyecto y entrar a la carpeta
cd Challenge_ing_rpa_scraping

# 2. Crear y activar entorno virtual
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Instalar el navegador headless que usa Playwright
playwright install chromium

# 5. Copiar la plantilla de configuración y ajustar si es necesario
cp .env.example .env

# 6. Ejecutar el pipeline
python main.py
```

### Salida esperada

El pipeline imprime logs estructurados en consola y genera (según el backend
configurado):
- `src/storage/indicadores.json`, o
- `src/storage/indicadores.db` (SQLite)

Ejemplo de log de una ejecución exitosa:

```
[2026-06-22 00:34:33] [INFO] [runner.py:14]: === INICIANDO PIPELINE DIARIO DE INDICADORES FINANCIEROS ===
[2026-06-22 00:34:33] [INFO] [bcentral_scraper.py:25]: Iniciando navegador automatizado (Playwright)...
[2026-06-22 00:34:34] [INFO] [bcentral_scraper.py:97]: Extracción exitosa en BCCh: UF = 40798.57
[2026-06-22 00:34:34] [INFO] [bcentral_scraper.py:97]: Extracción exitosa en BCCh: Dólar observado = 900.6
[2026-06-22 00:34:34] [INFO] [runner.py:29]: Fase de extracción completada. Resultados: 4 exitosos, 0 fallidos.
[2026-06-22 00:34:34] [INFO] [sqlite_storage.py:83]: Indicadores guardados exitosamente en SQLite. Total registros en histórico: 4
[2026-06-22 00:34:34] [INFO] [runner.py:34]: === PIPELINE FINALIZADO EXITOSAMENTE ===
```

### Verificar los datos guardados

```bash
# Si STORAGE_BACKEND=json
cat src/storage/indicadores.json

# Si STORAGE_BACKEND=sqlite
sqlite3 src/storage/indicadores.db "SELECT * FROM indicadores_financieros;"
```

---

## Configuración (variables de entorno)

| Variable | Default | Descripción |
|---|---|---|
| `ENV` | `development` | Entorno de ejecución (`development` / `production`) |
| `LOG_LEVEL` | `INFO` | Nivel de detalle de logs |
| `URL_BANCO_CENTRAL` | `https://www.bcentral.cl` | URL fuente del scraping |
| `TIMEOUT` | `15` | Segundos de espera para que cargue la página |
| `MAX_RETRIES` | `3` | Reintentos ante timeout de red en la navegación inicial |
| `STORAGE_BACKEND` | `json` | Motor de persistencia: `json` o `sqlite` |
| `OUTPUT_FILE` | `src/storage/indicadores.json` | Ruta de salida si el backend es JSON |
| `SQLITE_DB_PATH` | `src/storage/indicadores.db` | Ruta de la base de datos si el backend es SQLite |

Ver `.env.example` para la plantilla completa comentada.

---

## Decisiones técnicas

### ¿Por qué Playwright y no requests + BeautifulSoup?

La página de inicio del Banco Central de Chile renderiza los valores de UF,
Dólar, Euro y UTM mediante JavaScript del lado del cliente. Una petición
`requests.get()` simple devolvería el HTML inicial sin esos valores
poblados. Playwright controla un navegador real (Chromium headless),
ejecuta el JavaScript de la página y permite esperar (`wait_for_selector`)
a que el contenido dinámico termine de renderizarse antes de leerlo.

> Si en el futuro se agregan fuentes con contenido estático (ej. una tabla
> fija en una página de prensa financiera), se recomienda usar
> `requests + BeautifulSoup` para esas fuentes específicas: es más rápido y
> consume muchos menos recursos que levantar un navegador completo. La
> interfaz `BaseStorage`/scraper está pensada para que convivan ambos
> enfoques sin reescribir el orquestador.

### Esquema de datos validado (Pydantic + Enums)

`IndicadorFinanciero` usa `Enum` para `nombre_indicador`, `fuente_origen` y
`estado_extraccion` en vez de strings libres. Esto evita inconsistencias
silenciosas (ej. `"Dolar"` vs `"Dólar Observado"` vs `"USD"`) que romperían
agrupaciones o reportes sin lanzar ningún error.

Se incluyen dos validadores de negocio:
- `fecha_dato` debe ser una fecha real en formato `DD-MM-YYYY` (no solo un string).
- Si `estado_extraccion == "exitoso"`, el campo `valor` es obligatorio y
  distinto de cero. Si es `"parcial"` o `"fallido"`, `valor` debe ser `None`
  — un dato no confiable no debe reportar un número que aparente serlo.

### Tres estados de extracción, no solo éxito/fallo

- **`exitoso`**: el selector se encontró y el valor se parseó correctamente.
- **`parcial`**: el selector se encontró (el indicador existe en la página),
  pero el texto extraído no se pudo convertir a número — señal de que el
  *formato* cambió, distinto de que el dato *no exista*.
- **`fallido`**: el selector no se encontró, o la navegación falló por
  completo. El detalle queda en `mensaje_error` para trazabilidad.

### Deduplicación por clave natural

Cada registro se identifica por `(fecha_dato, nombre_indicador,
fuente_origen)`. Si el pipeline corre más de una vez el mismo día, el
registro más reciente **sobrescribe** al anterior en vez de duplicarse. En
JSON esto se resuelve indexando en un diccionario antes de escribir; en
SQLite, con un `UNIQUE constraint` y `INSERT OR REPLACE`, delegando la
garantía de unicidad a la base de datos en vez de lógica manual en Python.

### Storage intercambiable (JSON / SQLite)

Ambos backends implementan la misma interfaz `BaseStorage`
(`save_indicadores`, `load_indicadores`). El `runner.py` no conoce el
detalle de implementación; `storage_factory.py` decide cuál instanciar
según `STORAGE_BACKEND` en `.env`. Esto permite, por ejemplo, usar JSON en
desarrollo local y SQLite en un entorno productivo sin tocar código.

### Reintentos acotados a la navegación, no a los selectores

`MAX_RETRIES` solo aplica a la carga inicial de la página
(`page.goto()`), con backoff incremental (2s, 4s, 6s...). Un timeout de red
es una falla transitoria que vale la pena reintentar. La búsqueda de cada
selector individual (UF, Dólar, Euro, UTM) **no** se reintenta: si el HTML
cambió de estructura, reintentar el mismo selector roto no cambia el
resultado, solo demora el diagnóstico del problema real.

### Resiliencia en la carga del histórico

`load_indicadores()` valida cada registro individualmente. Si un registro
antiguo no cumple el schema vigente (por ejemplo, tras una migración de
esquema), se descarta con un `warning` puntual y el resto del histórico se
conserva — en vez de que un solo registro corrupto invalide la carga
completa.

---

## Supuestos

- Se asume que la home de `bcentral.cl` mantiene su estructura de clases
  CSS actual (`.tooltip-wrap`, `p.fs-2`). Un cambio de diseño del sitio
  requeriría actualizar los selectores en `bcentral_scraper.py`.
- Se asume una ejecución **una vez al día**; el mecanismo de deduplicación
  está diseñado para que reintentar manualmente el mismo día sea seguro
  (sobrescribe, no duplica), no para alta frecuencia intradía.
- El valor `0.0` nunca es un valor real válido para ningún indicador
  (UF, Dólar, Euro, UTM siempre son positivos), por lo que se usa como
  señal de "sin dato" en el modelo de validación.
- Las credenciales o configuración sensible se gestionan vía variables de
  entorno y no se versionan (`.env` está en `.gitignore`).

---

## Limitaciones conocidas y alternativas

| Limitación | Alternativa razonable |
|---|---|
| Si el Banco Central agrega un CAPTCHA o bloqueo anti-bot, este scraper no está diseñado para evadirlo (fuera de alcance, según las consideraciones del challenge) | Documentar el bloqueo en logs (`estado_extraccion=fallido`, `mensaje_error` descriptivo) y alertar para revisión manual, en vez de intentar evasión |
| Cambios de estructura HTML (rediseño del sitio) rompen los selectores CSS | El estado `parcial`/`fallido` por indicador, sumado a alertas (ver sección de Monitoreo), permite detectar el problema el mismo día en que ocurre, no días después |
| Dependencia de un único navegador (Chromium) | Playwright soporta Firefox/WebKit como fallback si Chromium presenta problemas específicos de renderizado |
| Un solo indicador HTML por página (no hay API de respaldo permitida por las reglas del challenge) | Para producción real (fuera del alcance de este challenge), se recomendaría evaluar negociar acceso a la API de Estadísticas oficial del Banco Central como fuente primaria, dejando el scraping como mecanismo de respaldo |

---

### Detección temprana de cambios de estructura

Como mejora futura, se recomienda incorporar pruebas automáticas
(smoke tests) que validen diariamente la existencia de los selectores
críticos utilizados por el scraper del Banco Central de Chile.

Por ejemplo:

- UF
- Dólar observado
- Euro
- UTM

Si alguno de estos selectores deja de existir o cambia de ubicación
producto de un rediseño del sitio, la prueba fallará inmediatamente,
permitiendo detectar el problema antes de que impacte la extracción
productiva.

Este mecanismo complementa los estados de extracción
(`parcial` y `fallido`) ya implementados en el pipeline, entregando una
capa adicional de monitoreo preventivo ante cambios estructurales del
HTML fuente.

---

## Propuesta de arquitectura en GCP

Para una ejecución diaria automatizada, sin necesidad de un servidor
corriendo 24/7, se propone una arquitectura *serverless* basada en
Cloud Run Jobs, con un pipeline de CI/CD que despliega automáticamente
cada cambio de código.

### Pipeline de despliegue (CI/CD)

```
┌──────────────┐      ┌───────────────────────┐      ┌────────────────────┐      ┌───────────────────────┐
│   GitHub      │─────▶│  GitHub Actions        │─────▶│  Artifact Registry  │─────▶│  Cloud Run Job          │
│  push a main  │      │  (.github/workflows/   │      │  (imagen Docker)    │      │  (se actualiza con la   │
│               │      │   pipeline.yml)         │      │                     │      │   imagen más reciente)  │
└──────────────┘      └───────────────────────┘      └────────────────────┘      └───────────────────────┘
```

Cada `push` a `main` dispara automáticamente el build de la imagen
Docker, su publicación en Artifact Registry, y la actualización del
Cloud Run Job para que la siguiente ejecución programada use la versión
más reciente del código, sin intervención manual.

Archivos de soporte incluidos en este repositorio:
- **`Dockerfile`**: empaqueta Python + Playwright (Chromium ya instalado,
  usando la imagen base oficial de Playwright) junto con el código del
  pipeline.
- **`.github/workflows/pipeline.yml`**: define el flujo de CI/CD
  (build → push → deploy), con un job adicional de **rollback manual**
  disparable desde la pestaña *Actions* de GitHub
  (`workflow_dispatch`), que vuelve a desplegar la imagen previa del
  Cloud Run Job sin necesidad de un nuevo commit.

> **Nota de implementación:** en equipos con múltiples automatizaciones
> desplegadas en Cloud Run, es común centralizar esta lógica en un
> **workflow reutilizable** compartido entre repositorios (`uses:
> ORG/repo/.github/workflows/py-cr-pipeline.yaml@main`), de forma que
> cada proyecto solo declare sus parámetros propios (nombre de la app,
> puerto, secretos a inyectar) en lugar de repetir los pasos de build y
> deploy en cada repositorio. El workflow incluido aquí se deja
> autocontenido para que sea reproducible sin depender de
> infraestructura privada de una organización específica, pero el
> patrón es equivalente.
>
> Las credenciales de la cuenta de servicio de GCP (`GCP_SA_KEY`) y el
> ID del proyecto (`GCP_PROJECT_ID`) se configuran como **GitHub
> Secrets** a nivel de repositorio u organización, nunca en el código
> del workflow.

> Nota: la primera vez, el Cloud Run Job debe crearse manualmente
> (`gcloud run jobs create`, ver comando de referencia más abajo); el
> pipeline de GitHub Actions solo lo **actualiza** en despliegues
> posteriores (`gcloud run jobs update`).

### Ejecución programada y persistencia

```
┌─────────────────────┐      ┌──────────────────────┐      ┌─────────────────────┐
│   Cloud Scheduler    │─────▶│   Cloud Run Job        │─────▶│  Cloud Storage /      │
│  (cron diario, ej.   │      │  (contenedor con       │      │  Cloud SQL            │
│   08:00 hora Chile)  │      │   Playwright + Python) │      │  (persistencia)       │
└─────────────────────┘      └──────────┬───────────┘      └─────────────────────┘
                                          │
                                          ▼
                                ┌──────────────────────┐
                                │   Cloud Logging        │
                                │   (logs estructurados) │
                                └──────────┬───────────┘
                                          │
                                          ▼
                                ┌──────────────────────┐
                                │ Cloud Monitoring +     │
                                │ Alerting (email/Slack) │
                                └──────────────────────┘
```

### Comandos de referencia (creación inicial)

Estos comandos se ejecutan **una sola vez** para inicializar la
infraestructura; los despliegues posteriores quedan automatizados por
`.github/workflows/pipeline.yml`.

```bash
# 1. Crear el repositorio de imágenes en Artifact Registry
gcloud artifacts repositories create indicadores-financieros-repo \
  --repository-format=docker \
  --location=us-central1

# 2. Build manual inicial (antes de tener el Trigger configurado)
gcloud builds submit --tag \
  us-central1-docker.pkg.dev/PROJECT_ID/indicadores-financieros-repo/indicadores-financieros:v1

# 3. Crear el Cloud Run Job (primera vez)
gcloud run jobs create indicadores-financieros-job \
  --image us-central1-docker.pkg.dev/PROJECT_ID/indicadores-financieros-repo/indicadores-financieros:v1 \
  --region us-central1 \
  --set-env-vars STORAGE_BACKEND=sqlite,LOG_LEVEL=INFO,MAX_RETRIES=3

# 4. Crear el Cloud Scheduler que invoca el Job diariamente (08:00 hora Chile)
gcloud scheduler jobs create http indicadores-financieros-scheduler \
  --schedule="0 8 * * *" \
  --uri="https://us-central1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/PROJECT_ID/jobs/indicadores-financieros-job:run" \
  --http-method=POST \
  --oauth-service-account-email=SERVICE_ACCOUNT@PROJECT_ID.iam.gserviceaccount.com \
  --time-zone="America/Santiago"

# 5. Crear la cuenta de servicio que usará GitHub Actions para desplegar,
#    y otorgarle los permisos mínimos necesarios (Artifact Registry + Cloud Run)
gcloud iam service-accounts create github-actions-deployer \
  --display-name="GitHub Actions Deployer"

gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:github-actions-deployer@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/run.developer"

gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:github-actions-deployer@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

# 6. Generar la clave de esa cuenta de servicio y configurarla como
#    GitHub Secret (Settings > Secrets and variables > Actions):
#      - GCP_SA_KEY: contenido completo del JSON de la clave
#      - GCP_PROJECT_ID: el ID del proyecto GCP
gcloud iam service-accounts keys create key.json \
  --iam-account=github-actions-deployer@PROJECT_ID.iam.gserviceaccount.com
```

A partir de este punto, cualquier `push` a `main` dispara automáticamente
el workflow `.github/workflows/pipeline.yml`, sin necesidad de repetir
estos pasos.

### Justificación de cada componente

- **Cloud Scheduler**: dispara la ejecución diaria mediante un cron job
  (ej. `0 8 * * *`), invocando el Cloud Run Job. No requiere infraestructura
  corriendo en espera.
- **Cloud Run Jobs** (en vez de Cloud Functions): Playwright requiere
  instalar un navegador Chromium completo, lo cual excede cómodamente las
  limitaciones de tamaño/tiempo de ejecución de Cloud Functions. Cloud Run
  Jobs permite empaquetar todo en un contenedor Docker con control total
  del entorno, y solo cobra por el tiempo real de ejecución (segundos al
  día), sin mantener un servicio HTTP siempre activo.
- **Persistencia**:
  - Si se usa `STORAGE_BACKEND=json`: el archivo se sube a un bucket de
    **Cloud Storage** al finalizar la ejecución (el sistema de archivos del
    contenedor es efímero entre ejecuciones).
  - Si se usa `STORAGE_BACKEND=sqlite`: se recomienda migrar a
    **Cloud SQL (PostgreSQL)** para producción real, ya que un archivo
    SQLite local no persiste entre ejecuciones de un Job efímero salvo que
    se monte un volumen externo (ej. Cloud Storage FUSE), lo cual añade
    complejidad innecesaria frente a una base de datos gestionada.
- **Cloud Logging**: los `logger.info/warning/error` ya están en un formato
  estructurado compatible nativamente con Cloud Logging al ejecutarse en
  GCP (stdout se captura automáticamente).
- **Cloud Monitoring + Alerting**: se configuran alertas basadas en
  métricas de logs (log-based metrics), por ejemplo:
  - Si aparece algún registro con `estado_extraccion=fallido` → notificación a Slack/email.
  - Si el Job no se ejecuta en la ventana esperada (ej. no corrió hoy) → alerta de "ejecución ausente".

### Secretos y configuración en GCP

- Las variables de entorno no sensibles (`STORAGE_BACKEND`, `TIMEOUT`,
  `MAX_RETRIES`) se configuran directamente en la definición del Cloud Run
  Job.
- Cualquier credencial sensible futura (ej. credenciales de Cloud SQL, API
  keys de un servicio de alertas como Slack) se almacena en
  **Secret Manager**, nunca en variables de entorno planas ni en el
  código fuente. El Job se configura con permisos IAM mínimos para leer
  únicamente los secretos que necesita (principio de menor privilegio).

> **Nota de implementación:** para Jobs con muchas variables de
> configuración no sensibles, GCP permite cargarlas desde un único
> archivo `--env-vars-file=.env.yaml` en vez de declararlas una por una
> con `--set-env-vars`. Es un patrón común en automatizaciones RPA
> desplegadas en Cloud Run, y mantiene la configuración versionable y
> legible por ambiente (dev/qa/prod), siempre sin incluir secretos reales
> en ese archivo — los secretos siguen yendo a Secret Manager.

---

## Monitoreo, alertas y seguridad

### Monitoreo
- **Logs estructurados** (ya implementado): cada fase del pipeline
  (extracción, persistencia) loguea su resultado con nivel apropiado
  (`INFO` para éxito, `WARNING` para casos parciales, `ERROR`/`CRITICAL`
  para fallos).
- **Resumen ejecutivo por ejecución**: `runner.py` calcula y loguea el
  conteo de indicadores `exitosos` vs `fallidos` en cada corrida, lo cual
  facilita construir un dashboard simple en Cloud Monitoring a partir de
  ese log.

### Alertas (propuesta para producción)
- Alerta crítica si el Job falla por completo (excepción no controlada,
  `sys.exit(1)`).
- Alerta de advertencia si uno o más indicadores quedan en estado
  `fallido` o `parcial`, aunque el pipeline termine "exitosamente" en
  términos de ejecución — un dato faltante es un problema de negocio
  aunque el proceso técnico no haya caído.
- Alerta de "ejecución ausente" si Cloud Scheduler no logra invocar el Job
  en la ventana horaria esperada.

> **Nota de implementación:** en automatizaciones similares (RPA con
> Playwright desplegado en Cloud Run), un patrón habitual es enviar un
> correo de resumen de ejecución (éxito/fallo, cantidad de registros
> procesados) usando un proveedor transaccional como SendGrid, en vez de
> SMTP directo. Esto queda fuera del alcance de este challenge (no es un
> requerimiento mínimo y agregaría una dependencia/credencial externa
> innecesaria para el caso de uso actual), pero es la extensión natural
> si el pipeline pasara a producción real.

### Manejo seguro de credenciales
- Este proyecto, en su forma actual, no requiere credenciales (el
  scraping es sobre contenido público sin autenticación).
- El archivo `.env` real **nunca se versiona** (está en `.gitignore`); se
  provee `.env.example` como plantilla documentada.
- Si en el futuro se incorpora una fuente que requiera autenticación o
  alguna credencial de servicio (ej. credenciales de Cloud SQL, tokens de
  notificación), estas deben gestionarse vía **Secret Manager** en GCP, y
  vía un gestor de secretos local (no en texto plano) en desarrollo.