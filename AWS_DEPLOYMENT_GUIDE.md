# 🚀 Guía de Despliegue en AWS

## 1. Preparación de Seguridad

### 1.1 Generar Claves Seguras

```bash
# SECRET_KEY para FastAPI (32 bytes)
python -c "import secrets; print(secrets.token_urlsafe(32))"

# ENCRYPTION_KEY para GitHub (32 bytes base64)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Contraseña BD fuerte
python -c "import secrets; print(secrets.token_urlsafe(24))"
```

### 1.2 Usar AWS Secrets Manager

```bash
# Crear secreto en AWS
aws secretsmanager create-secret \
  --name auditor-geo/prod \
  --secret-string '{
    "DB_PASSWORD": "tu-contraseña-fuerte",
    "SECRET_KEY": "tu-secret-key",
    "ENCRYPTION_KEY": "tu-encryption-key",
    "GITHUB_CLIENT_SECRET": "xxx",
    "AUTH0_CLIENT_SECRET": "xxx"
  }'
```

---

## 2. Configuración de Producción

### 2.1 Variables de Entorno Seguras

**Crear `.env.production`:**

```env
# APP
DEBUG=False
ENVIRONMENT=production
SECRET_KEY=${AWS_SECRET_KEY}

# DATABASE
DATABASE_URL=postgresql+psycopg2://auditor:${DB_PASSWORD}@auditor-db.xxxxx.rds.amazonaws.com:5432/auditor_db

# REDIS
REDIS_URL=redis://auditor-redis.xxxxx.ng.0001.use1.cache.amazonaws.com:6379/0

# CORS - IMPORTANTE: Cambiar a tu dominio
CORS_ORIGINS=https://auditor-geo.com,https://www.auditor-geo.com

# SECURITY
ALLOWED_HOSTS=auditor-geo.com,www.auditor-geo.com
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
SESSION_COOKIE_HTTPONLY=True
CSRF_COOKIE_SECURE=True
CSRF_COOKIE_HTTPONLY=True

# APIs (desde Secrets Manager)
GOOGLE_API_KEY=${GOOGLE_API_KEY}
GEMINI_API_KEY=${GEMINI_API_KEY}
NVIDIA_API_KEY=${NVIDIA_API_KEY}
GITHUB_CLIENT_SECRET=${GITHUB_CLIENT_SECRET}
AUTH0_CLIENT_SECRET=${AUTH0_CLIENT_SECRET}
```

---

## 3. Servicios AWS Necesarios

### 3.1 RDS PostgreSQL

```bash
# Crear instancia RDS
aws rds create-db-instance \
  --db-instance-identifier auditor-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --master-username auditor \
  --master-user-password ${DB_PASSWORD} \
  --allocated-storage 20 \
  --storage-type gp3 \
  --multi-az \
  --backup-retention-period 30 \
  --enable-encryption \
  --storage-encrypted
```

### 3.2 ElastiCache Redis

```bash
# Crear cluster Redis
aws elasticache create-cache-cluster \
  --cache-cluster-id auditor-redis \
  --cache-node-type cache.t3.micro \
  --engine redis \
  --num-cache-nodes 1 \
  --engine-version 7.0 \
  --at-rest-encryption-enabled \
  --transit-encryption-enabled
```

### 3.3 ECR (Container Registry)

```bash
# Crear repositorio
aws ecr create-repository --repository-name auditor-geo/backend
aws ecr create-repository --repository-name auditor-geo/frontend

# Hacer login
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 123456789.dkr.ecr.us-east-1.amazonaws.com

# Pushear imágenes
docker tag auditor-backend:latest 123456789.dkr.ecr.us-east-1.amazonaws.com/auditor-geo/backend:latest
docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/auditor-geo/backend:latest
```

---

## 4. ECS Fargate Deployment

### 4.1 Task Definition

```json
{
  "family": "auditor-backend",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "containerDefinitions": [
    {
      "name": "backend",
      "image": "123456789.dkr.ecr.us-east-1.amazonaws.com/auditor-geo/backend:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "DEBUG",
          "value": "False"
        },
        {
          "name": "ENVIRONMENT",
          "value": "production"
        }
      ],
      "secrets": [
        {
          "name": "DATABASE_URL",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789:secret:auditor-geo/prod:DB_URL::"
        },
        {
          "name": "SECRET_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789:secret:auditor-geo/prod:SECRET_KEY::"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/auditor-backend",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

### 4.2 ECS Service

```bash
aws ecs create-service \
  --cluster auditor-cluster \
  --service-name auditor-backend \
  --task-definition auditor-backend:1 \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx,subnet-yyy],securityGroups=[sg-xxx],assignPublicIp=DISABLED}" \
  --load-balancers targetGroupArn=arn:aws:elasticloadbalancing:...,containerName=backend,containerPort=8000
```

---

## 5. Frontend en S3 + CloudFront

### 5.1 Build Next.js para Producción

```bash
cd frontend
npm run build
npm run export  # Para sitio estático
```

### 5.2 Subir a S3

```bash
# Crear bucket
aws s3 mb s3://auditor-geo-frontend --region us-east-1

# Subir archivos
aws s3 sync ./out s3://auditor-geo-frontend --delete

# Configurar como sitio web
aws s3 website s3://auditor-geo-frontend --index-document index.html --error-document 404.html
```

### 5.3 CloudFront Distribution

```bash
# Crear distribución
aws cloudfront create-distribution \
  --origin-domain-name auditor-geo-frontend.s3.us-east-1.amazonaws.com \
  --default-root-object index.html \
  --viewer-protocol-policy redirect-to-https
```

---

## 6. WAF (Web Application Firewall)

```bash
# Crear Web ACL
aws wafv2 create-web-acl \
  --name auditor-geo-waf \
  --scope CLOUDFRONT \
  --default-action Block={} \
  --rules file://waf-rules.json \
  --visibility-config SampledRequestsEnabled=true,CloudWatchMetricsEnabled=true,MetricName=auditor-geo-waf
```

---

## 7. Monitoreo y Logs

### 7.1 CloudWatch

```bash
# Crear log group
aws logs create-log-group --log-group-name /auditor-geo/backend
aws logs create-log-group --log-group-name /auditor-geo/frontend

# Crear alarmas
aws cloudwatch put-metric-alarm \
  --alarm-name auditor-backend-cpu \
  --alarm-description "Alert if CPU > 80%" \
  --metric-name CPUUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold
```

### 7.2 X-Ray para Tracing

```python
# En backend/app/main.py
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all

patch_all()
xray_recorder.configure(service='auditor-geo-backend')
```

---

## 8. CI/CD con GitHub Actions

**Crear `.github/workflows/deploy.yml`:**

```yaml
name: Deploy to AWS

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      
      - name: Build and push backend
        run: |
          docker build -f Dockerfile.backend -t auditor-backend:latest .
          aws ecr get-login-password | docker login --username AWS --password-stdin ${{ secrets.ECR_REGISTRY }}
          docker tag auditor-backend:latest ${{ secrets.ECR_REGISTRY }}/auditor-geo/backend:latest
          docker push ${{ secrets.ECR_REGISTRY }}/auditor-geo/backend:latest
      
      - name: Update ECS service
        run: |
          aws ecs update-service \
            --cluster auditor-cluster \
            --service auditor-backend \
            --force-new-deployment
```

---

## 9. Checklist de Seguridad

- [ ] Cambiar todas las contraseñas por defecto
- [ ] Habilitar MFA en AWS
- [ ] Usar Secrets Manager para credenciales
- [ ] Habilitar encryption en RDS y ElastiCache
- [ ] Configurar Security Groups restrictivos
- [ ] Habilitar VPC Flow Logs
- [ ] Configurar WAF rules
- [ ] Habilitar CloudTrail para auditoría
- [ ] Configurar backup automático
- [ ] Usar HTTPS/TLS en todo
- [ ] Implementar rate limiting
- [ ] Validar CORS correctamente
- [ ] Usar IAM roles en lugar de access keys

---

## 10. Costos Estimados (Mensual)

| Servicio | Tier | Costo |
|----------|------|-------|
| RDS PostgreSQL | db.t3.micro | ~$30 |
| ElastiCache Redis | cache.t3.micro | ~$20 |
| ECS Fargate | 2x 512 CPU, 1GB RAM | ~$40 |
| ALB | 1 Load Balancer | ~$16 |
| CloudFront | 100GB/mes | ~$10 |
| S3 | 10GB storage | ~$0.25 |
| **TOTAL** | | **~$116/mes** |

*Nota: Usa AWS Free Tier si es tu primer año*

---

## 11. Próximos Pasos

1. Crear cuenta AWS
2. Generar claves seguras
3. Crear Secrets Manager
4. Provisionar RDS y ElastiCache
5. Crear ECR repositories
6. Pushear imágenes Docker
7. Crear ECS cluster y services
8. Configurar CloudFront
9. Configurar dominio en Route53
10. Implementar CI/CD

¡Listo para producción! 🚀
