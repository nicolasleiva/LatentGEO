# 🔧 Solución de Errores de Memoria (ENOMEM) en Docker

## Problema

**Error:** `ENOMEM: not enough memory, scandir '/app'`

Este error ocurre cuando el contenedor Docker se queda sin memoria disponible. Es común en:
- Desarrollo local con Docker Desktop
- Contenedores con límites de memoria bajos
- Aplicaciones Next.js con muchas dependencias

## Causas

1. **Docker Desktop con poca memoria asignada** (por defecto 2GB, insuficiente para Next.js)
2. **Next.js modo desarrollo** que vigila demasiados archivos
3. **Node.js sin límites de memoria** configurados
4. **Sin optimizaciones de Webpack** para reducir consumo

## Soluciones

### 1. Aumentar Memoria de Docker Desktop (RECOMENDADO)

**Windows:**
1. Abrir Docker Desktop
2. Ir a **Settings** (⚙️) → **Resources** → **Advanced**
3. Aumentar:
   - **Memory**: 4GB o más (recomendado 6-8GB)
   - **Swap**: 2GB o más
   - **CPUs**: 2 o más
4. Aplicar y reiniciar Docker

**macOS:**
1. Docker Desktop → **Settings** → **Resources**
2. Aumentar **Memory** a 4GB+
3. Aplicar y reiniciar

**Linux:**
Docker no tiene límites en Linux, verificar RAM disponible:
```bash
free -h
```

### 2. Usar Docker Compose con Límites de Recursos

```bash
# Usar el docker-compose configurado
docker-compose -f docker-compose.frontend.yml up
```

El archivo incluye:
- Límite de memoria: 2GB
- Límite de CPUs: 1.0
- Node.js optimizado: `--max-old-space-size=1536`

### 3. Build con Límites de Memoria

```bash
# Limitar memoria durante build
docker build \
  --memory=4g \
  --memory-swap=4g \
  --build-arg NODE_OPTIONS="--max-old-space-size=3072" \
  -f Dockerfile.frontend \
  -t auditor-geo-frontend:latest \
  .

# Ejecutar con límites
docker run \
  --memory=2g \
  --memory-swap=2g \
  --cpus=1.0 \
  -p 3000:3000 \
  auditor-geo-frontend:latest
```

### 4. Optimizaciones Aplicadas

Las siguientes optimizaciones ya están implementadas:

#### next.config.mjs
```javascript
// Deshabilitar type checking y eslint durante build (ahorra memoria)
typescript: { ignoreBuildErrors: true },
eslint: { ignoreDuringBuilds: true },

// Webpack optimizado
webpack: (config) => {
  config.optimization = {
    minimize: true,
    removeAvailableModules: true,
    removeEmptyChunks: true,
  }
  return config
}
```

#### Dockerfile
```dockerfile
# NODE_OPTIONS configurado para todas las etapas
ENV NODE_OPTIONS="--max-old-space-size=4096"

# Runtime con límites
ENV NODE_OPTIONS=--max-old-space-size=1536 --optimize-for-size
```

### 5. Verificar Memoria del Sistema

**Verificar memoria disponible:**
```bash
# Linux/macOS
free -h

# Windows (PowerShell)
Get-ComputerInfo | Select-Object TotalPhysicalMemory

# Ver uso de Docker
docker system df
docker stats
```

### 6. Limpiar Recursos de Docker

```bash
# Limpiar todo (CUIDADO: borra volúmenes, imágenes, contenedores)
docker system prune -a --volumes

# Solo builder cache
docker builder prune -f

# Imágenes no utilizadas
docker image prune -f
```

### 7. Monitorear Uso de Memoria

```bash
# Ver uso en tiempo real
docker stats

# Ver logs con timestamps
docker logs -f --timestamps <container_id>

# Ver procesos del contenedor
docker exec <container_id> ps aux
```

## Configuración Recomendada por Entorno

### Desarrollo Local
```yaml
# docker-compose.override.yml
deploy:
  resources:
    limits:
      memory: 3G
      cpus: '2.0'
```

### CI/CD (GitHub Actions, GitLab CI)
```yaml
# Usar runners con más memoria
# GitHub Actions: runs-on: ubuntu-latest-8-cores
# GitLab CI: tag con 'large' o 'memory-optimized'
```

### Producción
```yaml
# Kubernetes/ECS
resources:
  requests:
    memory: "512Mi"
    cpu: "250m"
  limits:
    memory: "1Gi"
    cpu: "500m"
```

## Troubleshooting Avanzado

### Error persiste después de aumentar memoria

1. **Verificar que no hay memory leak:**
   ```bash
   docker exec <container_id> node -e "console.log(process.memoryUsage())"
   ```

2. **Verificar versión de Node.js:**
   ```bash
   docker exec <container_id> node --version
   # Actualizar si es necesario en Dockerfile
   ```

3. **Revisar dependencias:**
   ```bash
   cd frontend
   pnpm why <package-sospechosa>
   ```

### Build exitoso pero runtime falla

Si el build funciona pero al ejecutar da ENOMEM:

```bash
# Ejecutar con modo debug para ver uso de memoria
docker run -e DEBUG=* -e NODE_OPTIONS="--max-old-space-size=1024" <imagen>

# O usar node con inspect
docker run -e NODE_OPTIONS="--inspect=0.0.0.0:9229" <imagen>
```

## Referencias

- [Docker Resource Constraints](https://docs.docker.com/config/containers/resource_constraints/)
- [Node.js Memory Management](https://nodejs.org/docs/latest-v20.x/api/process.html#processmemoryusage)
- [Next.js Memory Optimization](https://nextjs.org/docs/advanced-features/measuring-performance)

## Contacto

Si el problema persiste después de aplicar estas soluciones:
1. Verificar logs completos: `docker logs <container_id> 2>&1 | head -100`
2. Revisar versión de Docker: `docker version`
3. Reportar issue con información de sistema (RAM, Docker version, OS)