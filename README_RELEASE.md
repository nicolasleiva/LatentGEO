# Instrucciones de Despliegue (Release)

## Requisitos
1. Docker instalado.
2. Docker Compose v2+.

## Archivos necesarios
- `auditor_geo_release.tar` (imagenes backend/frontend)
- `docker-compose.yml` (stack estandar)
- `.env` (basado en `.env.example`)

## Pasos

1. Cargar imagenes:
```bash
docker load -i auditor_geo_release.tar
```

2. Configurar entorno:
```bash
cp .env.example .env
# editar .env con credenciales reales
```

3. Levantar servicios:
```bash
docker compose up -d
```

4. Verificar estado:
```bash
docker compose ps
```

Servicios:
- Backend: `http://localhost:8000`
- Frontend: `http://localhost:3000`

## Notas
- Para desarrollo con hot reload usar `docker-compose.dev.yml`.
- Comando de reinicio backend:
```bash
docker compose restart backend
```
