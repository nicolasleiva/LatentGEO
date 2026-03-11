# ✅ Checklist de Despliegue a AWS

## Fase 0: Estabilización Preproducción (Bloqueante, sin deploy)

> No avanzar a staging/producción hasta completar esta fase.

### Gate técnico obligatorio
- [ ] `pnpm --dir frontend lint`
- [ ] `pnpm --dir frontend run format:check`
- [ ] `pnpm --dir frontend run type-check`
- [ ] `pnpm --dir frontend test:ci`
- [ ] `STRICT_BUILD=1 pnpm --dir frontend build`
- [ ] `python -m ruff check backend/app`
- [ ] `python -m mypy backend/app --ignore-missing-imports --show-error-codes`
- [ ] `python -m bandit -r backend/app -q`
- [ ] `pytest -q backend/tests -m "not integration and not live"`

### Smoke externa mínima (bloqueante)
- [ ] Definir `SMOKE_BASE_URL` (entorno objetivo)
- [ ] Definir `SMOKE_BEARER_TOKEN`
- [ ] Ejecutar `pytest -q backend/tests/test_release_smoke_external.py`
- [ ] Verificar:
  - [ ] `GET /health` = 200
  - [ ] `GET /docs` = 404
  - [ ] `GET /api/v1/webhooks/health` = 200
  - [ ] `GET /api/v1/geo/content-templates` con token = 200
  - [ ] `GET /api/v1/geo/content-templates` sin token = 401/403 (no 404/5xx)

### Gate estricto de release
- [ ] `OPENAPI_DOCS_ENABLED=false`
- [ ] `PDF_ALLOW_DETERMINISTIC_FALLBACK=false`
- [ ] `WEB_CONCURRENCY` definido explícitamente
- [ ] `PERF_AUTH_EMAIL` definido
- [ ] `PERF_AUTH_PASSWORD` definido
- [ ] Ejecutar `pnpm --dir frontend quality:web:full`
- [ ] Ejecutar `pnpm --dir frontend perf:e2e`
- [ ] Ejecutar `pnpm --dir frontend release:smoke:e2e`
- [ ] Ejecutar `RUN_INTEGRATION_TESTS=1 RUN_LIVE_E2E=1 pytest -q backend/tests/test_live_plataforma5_agent1_pdf.py -s`

---

## Fase 1: Preparación (Semana 1)

### Seguridad
- [ ] Generar SECRET_KEY segura
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
- [ ] Generar ENCRYPTION_KEY
  ```bash
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```
- [ ] Generar contraseña BD fuerte
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(24))"
  ```
- [ ] Crear cuenta AWS
- [ ] Habilitar MFA en AWS
- [ ] Crear IAM user para CI/CD
- [ ] Crear IAM roles para ECS

### Configuración
- [ ] Copiar `.env.production` a `.env`
- [ ] Actualizar variables de entorno
- [ ] Cambiar CORS_ORIGINS a tu dominio
- [ ] Cambiar ALLOWED_HOSTS
- [ ] Revisar docker-compose.yml (estandar) y docker-compose.dev.yml (desarrollo)
- [ ] Revisar Dockerfiles

### Dominio
- [ ] Registrar dominio (Route53 o registrador externo)
- [ ] Crear hosted zone en Route53
- [ ] Solicitar certificado SSL en ACM
- [ ] Validar certificado

---

## Fase 2: Infraestructura AWS (Semana 2-3)

### VPC y Networking
- [ ] Crear VPC (10.0.0.0/16)
- [ ] Crear subnets privadas (2 AZs)
- [ ] Crear subnets públicas (2 AZs)
- [ ] Crear Internet Gateway
- [ ] Crear NAT Gateway
- [ ] Configurar route tables

### Security Groups
- [ ] Crear SG para ALB
  - [ ] Permitir 443 desde 0.0.0.0/0
  - [ ] Permitir 80 desde 0.0.0.0/0 (redirect a 443)
- [ ] Crear SG para ECS
  - [ ] Permitir 8000 desde SG ALB
- [ ] Crear SG para RDS
  - [ ] Permitir 5432 desde SG ECS
- [ ] Crear SG para ElastiCache
  - [ ] Permitir 6379 desde SG ECS

### RDS PostgreSQL
- [ ] Crear DB subnet group
- [ ] Crear instancia RDS
  - [ ] db.t3.small
  - [ ] Multi-AZ habilitado
  - [ ] Encryption habilitado
  - [ ] Backup retention 30 días
  - [ ] Automated backups habilitados
- [ ] Crear parámetro group personalizado
- [ ] Crear opción group (si es necesario)
- [ ] Anotar endpoint de RDS

### ElastiCache Redis
- [ ] Crear cache subnet group
- [ ] Crear cluster Redis
  - [ ] cache.t3.small
  - [ ] Encryption at rest habilitado
  - [ ] Encryption in transit habilitado
  - [ ] Automatic failover habilitado
  - [ ] Backup habilitado
- [ ] Anotar endpoint de Redis

### Secrets Manager
- [ ] Crear secreto para credenciales
  ```bash
  aws secretsmanager create-secret \
    --name auditor-geo/prod \
    --secret-string '{
      "DATABASE_URL": "postgresql+psycopg2://auditor:PASSWORD@endpoint:5432/auditor_db",
      "SECRET_KEY": "tu-secret-key",
      "ENCRYPTION_KEY": "tu-encryption-key",
      "REDIS_URL": "redis://endpoint:6379/0"
    }'
  ```
- [ ] Crear secreto para APIs
- [ ] Crear secreto para GitHub
- [ ] Crear secreto para Auth0

---

## Fase 3: Contenedores (Semana 3-4)

### ECR
- [ ] Crear repositorio para backend
- [ ] Crear repositorio para frontend
- [ ] Configurar scan de vulnerabilidades
- [ ] Configurar lifecycle policies

### Build y Push
- [ ] Hacer login en ECR
  ```bash
  aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ACCOUNT.dkr.ecr.us-east-1.amazonaws.com
  ```
- [ ] Build backend
  ```bash
  docker build -f Dockerfile.backend -t auditor-backend:latest .
  ```
- [ ] Tag backend
  ```bash
  docker tag auditor-backend:latest ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/auditor-geo/backend:latest
  ```
- [ ] Push backend
  ```bash
  docker push ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/auditor-geo/backend:latest
  ```
- [ ] Build frontend
  ```bash
  docker build -f Dockerfile.frontend -t auditor-frontend:latest .
  ```
- [ ] Tag frontend
- [ ] Push frontend

### ECS
- [ ] Crear ECS cluster
- [ ] Crear CloudWatch log groups
  - [ ] /ecs/auditor-backend
  - [ ] /ecs/auditor-frontend
- [ ] Crear IAM role para ECS task execution
- [ ] Crear IAM role para ECS task
- [ ] Crear task definition para backend
- [ ] Crear task definition para frontend
- [ ] Crear servicio backend
- [ ] Crear servicio frontend

---

## Fase 4: Load Balancing (Semana 4)

### ALB
- [ ] Crear Application Load Balancer
- [ ] Crear target group para backend
  - [ ] Health check: /health
  - [ ] Interval: 30s
  - [ ] Timeout: 5s
- [ ] Registrar targets (ECS tasks)
- [ ] Crear listener HTTPS
  - [ ] Certificado ACM
  - [ ] Forward a target group
- [ ] Crear listener HTTP
  - [ ] Redirect a HTTPS
- [ ] Anotar DNS del ALB

---

## Fase 5: CDN y Frontend (Semana 5)

### S3
- [ ] Crear bucket para frontend
  - [ ] Nombre: auditor-geo-frontend
  - [ ] Bloquear acceso público
  - [ ] Versionado habilitado
- [ ] Crear bucket policy para CloudFront
- [ ] Crear Origin Access Identity (OAI)

### CloudFront
- [ ] Crear distribución
  - [ ] Origin 1: S3 (frontend)
  - [ ] Origin 2: ALB (backend)
- [ ] Configurar behaviors
  - [ ] Default: S3 (GET, HEAD)
  - [ ] /api/*: ALB (todos los métodos)
- [ ] Configurar cache policies
- [ ] Habilitar compression
- [ ] Habilitar HTTP/2
- [ ] Anotar domain name de CloudFront

### Route 53
- [ ] Crear alias record
  - [ ] Name: auditor-geo.com
  - [ ] Type: A
  - [ ] Alias to CloudFront distribution
- [ ] Crear alias record para www
- [ ] Verificar DNS propagation

---

## Fase 6: Seguridad (Semana 5-6)

### WAF
- [ ] Crear Web ACL
- [ ] Agregar AWS Managed Rules
  - [ ] Common Rule Set
  - [ ] Known Bad Inputs
  - [ ] SQL Injection Protection
  - [ ] XSS Protection
- [ ] Agregar Rate Limiting Rule
  - [ ] 2000 requests por 5 minutos
- [ ] Agregar IP Reputation List
- [ ] Asociar WAF a CloudFront

### Certificados
- [ ] Validar certificado ACM
- [ ] Configurar auto-renewal
- [ ] Verificar en CloudFront

### Secrets
- [ ] Verificar que todas las credenciales están en Secrets Manager
- [ ] Verificar que ECS puede acceder a Secrets Manager
- [ ] Rotar credenciales de BD

---

## Fase 7: Monitoreo (Semana 6)

### CloudWatch
- [ ] Crear log groups
- [ ] Crear dashboard
  - [ ] ECS CPU/Memory
  - [ ] RDS CPU/Connections
  - [ ] Redis CPU/Memory
  - [ ] ALB requests/errors
  - [ ] CloudFront requests/errors

### Alarmas
- [ ] ECS CPU > 80%
- [ ] ECS Memory > 80%
- [ ] RDS CPU > 80%
- [ ] RDS Storage > 80%
- [ ] Redis CPU > 80%
- [ ] ALB Target Unhealthy
- [ ] RDS Replication Lag > 1s

### SNS
- [ ] Crear SNS topic para alertas
- [ ] Suscribir email
- [ ] Suscribir Slack (opcional)

### X-Ray
- [ ] Habilitar X-Ray en ECS
- [ ] Configurar sampling rules
- [ ] Crear service map

---

## Fase 8: Auto Scaling (Semana 6)

### ECS Auto Scaling
- [ ] Crear auto scaling target
  - [ ] Min: 2 tasks
  - [ ] Max: 10 tasks
- [ ] Crear scaling policy por CPU
  - [ ] Target: 70%
  - [ ] Scale out cooldown: 60s
  - [ ] Scale in cooldown: 300s
- [ ] Crear scaling policy por memoria
  - [ ] Target: 80%

### RDS Auto Scaling
- [ ] Habilitar storage auto scaling
  - [ ] Max: 1000 GB
  - [ ] Threshold: 80%

---

## Fase 9: Backup y Disaster Recovery (Semana 7)

### RDS
- [ ] Verificar backup retention (30 días)
- [ ] Crear snapshot manual
- [ ] Probar restore desde snapshot
- [ ] Crear read replica (opcional)

### S3
- [ ] Habilitar versioning
- [ ] Crear lifecycle policy
  - [ ] Delete old versions después de 90 días
- [ ] Habilitar MFA delete (opcional)

### Disaster Recovery Plan
- [ ] Documentar RTO (Recovery Time Objective)
- [ ] Documentar RPO (Recovery Point Objective)
- [ ] Crear runbook de recuperación
- [ ] Probar recuperación mensualmente

---

## Fase 10: Testing (Semana 7-8)

### Funcionalidad
- [ ] Probar login
- [ ] Probar auditorías
- [ ] Probar reportes
- [ ] Probar integraciones (GitHub, etc)
- [ ] Probar APIs

### Performance
- [ ] Load testing con 1000 usuarios
- [ ] Verificar response time < 2s
- [ ] Verificar CPU < 70%
- [ ] Verificar memoria < 80%

### Seguridad
- [ ] OWASP ZAP scan
- [ ] Verificar HTTPS en todo
- [ ] Verificar headers de seguridad
- [ ] Verificar CORS restrictivo
- [ ] Verificar rate limiting
- [ ] Verificar validación de entrada

### Disponibilidad
- [ ] Simular fallo de AZ
- [ ] Simular fallo de instancia RDS
- [ ] Simular fallo de instancia Redis
- [ ] Verificar failover automático

---

## Fase 11: CI/CD (Semana 8)

### GitHub Actions
- [ ] Crear workflow para build
- [ ] Crear workflow para push a ECR
- [ ] Crear workflow para deploy a ECS
- [ ] Crear workflow para tests
- [ ] Crear workflow para security scan

### Secrets en GitHub
- [ ] AWS_ACCESS_KEY_ID
- [ ] AWS_SECRET_ACCESS_KEY
- [ ] ECR_REGISTRY

---

## Fase 12: Go Live (Semana 8)

### Pre-Launch
- [ ] Revisar todos los checklist anteriores
- [ ] Hacer backup de BD
- [ ] Notificar al equipo
- [ ] Preparar rollback plan

### Launch
- [ ] Cambiar DNS a CloudFront
- [ ] Monitorear logs
- [ ] Monitorear métricas
- [ ] Estar disponible para issues

### Post-Launch
- [ ] Monitorear por 24 horas
- [ ] Recopilar feedback
- [ ] Optimizar basado en métricas
- [ ] Documentar lecciones aprendidas

---

## Fase 13: Post-Launch (Semana 9+)

### Mantenimiento
- [ ] Revisar logs diariamente
- [ ] Revisar métricas semanalmente
- [ ] Actualizar dependencias mensualmente
- [ ] Hacer security audits trimestralmente

### Optimización
- [ ] Analizar CloudFront cache hit ratio
- [ ] Optimizar RDS queries
- [ ] Optimizar Redis usage
- [ ] Reducir costos

### Escalabilidad
- [ ] Monitorear crecimiento
- [ ] Planificar para 10x crecimiento
- [ ] Considerar multi-region (si es necesario)

---

## Notas Importantes

### Credenciales
- ❌ NUNCA commitear `.env.production`
- ✅ Usar AWS Secrets Manager
- ✅ Rotar credenciales cada 90 días
- ✅ Usar IAM roles en lugar de access keys

### Costos
- 💰 Presupuestar ~$300/mes
- 💰 Usar AWS Free Tier si es posible
- 💰 Configurar billing alerts
- 💰 Revisar costos mensualmente

### Seguridad
- 🔒 Habilitar MFA en AWS
- 🔒 Usar VPC privadas
- 🔒 Usar Security Groups restrictivos
- 🔒 Habilitar encryption en todo
- 🔒 Usar WAF
- 🔒 Hacer security audits

### Disponibilidad
- 🚀 Multi-AZ para RDS
- 🚀 Auto-scaling para ECS
- 🚀 CloudFront para caché
- 🚀 Health checks en ALB
- 🚀 Backup automático

---

## Contactos Útiles

- AWS Support: https://console.aws.amazon.com/support/
- AWS Status: https://status.aws.amazon.com/
- AWS Documentation: https://docs.aws.amazon.com/
- AWS Forums: https://forums.aws.amazon.com/

---

## Recursos

- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)
- [AWS Security Best Practices](https://aws.amazon.com/security/best-practices/)
- [AWS Pricing Calculator](https://calculator.aws/)
- [AWS Architecture Center](https://aws.amazon.com/architecture/)

---

## Strict Release Gate (workflow_dispatch)

### Variables requeridas
- [ ] `SMOKE_BASE_URL` (obligatoria, debe iniciar con `http://` o `https://`)

### Secrets opcionales
- [ ] `SMOKE_BEARER_TOKEN` (obligatoria en gate estricto; se usa para validar endpoints protegidos)

### Resultado esperado
- [ ] Backend local determinista verde (`pytest -q backend/tests -m "not integration and not live"`)
- [ ] Smoke externa mínima verde (`pytest -q backend/tests/test_release_smoke_external.py`)
- [ ] Frontend strict verde (`lint`, `format:check`, `type-check`, `test:ci`, `build` con `STRICT_BUILD=1`)
- [ ] Sin deploy automático en esta etapa
