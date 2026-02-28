# Instrucciones para desplegar Auditor GEO (Docker Release)

## Requisitos previos

1. Docker instalado y ejecutandose.
2. Docker Compose v2+.

## Archivos necesarios

- `auditor_geo_release.tar`: Archivo con las imagenes Docker precompiladas.
- `docker-compose.release.yml`: Definicion de servicios para produccion.
- `.env`: Archivo de variables de entorno (basado en `.env.example`).

## Pasos para desplegar

1. **Cargar las imagenes Docker:**

   Ejecuta el siguiente comando en la terminal (PowerShell o Bash) donde tengas el archivo `.tar`:

   ```bash
   docker load -i auditor_geo_release.tar
   ```

   Esto cargara `auditor_geo-backend:latest` y `auditor_geo-frontend:latest`.

2. **Configurar variables de entorno:**

   Copia el archivo `.env.example` a `.env` y configura las credenciales (DB, Redis, APIs externas).

   ```bash
   cp .env.example .env
   # Edita .env con tus valores reales
   ```

3. **Iniciar los servicios:**

   Usa el archivo de composicion de release:

   ```bash
   docker compose -f docker-compose.release.yml up -d
   ```

4. **Verificar estado:**

   ```bash
   docker compose -f docker-compose.release.yml ps
   ```

   El backend estara disponible en `http://localhost:8000` y el frontend en `http://localhost:3000`.

## Notas adicionales

- Los volumenes de datos (`postgres_data`, `auditor_reports`) persistiran los datos entre reinicios.
- Si necesitas reiniciar un servicio especifico: `docker compose -f docker-compose.release.yml restart backend`
