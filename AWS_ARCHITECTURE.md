# 🏗️ Arquitectura AWS Recomendada para Auditor GEO

## Diagrama de Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                        INTERNET                                 │
└────────────────────────────┬────────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │   Route 53      │
                    │  (DNS)          │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   CloudFront    │
                    │   + WAF         │
                    │   (CDN)         │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ┌────▼────┐         ┌────▼────┐         ┌────▼────┐
   │   S3    │         │   ALB   │         │ Lambda  │
   │Frontend │         │Backend  │         │ (APIs)  │
   └─────────┘         └────┬────┘         └─────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ┌────▼────┐         ┌────▼────┐         ┌────▼────┐
   │   ECS   │         │   RDS   │         │ Elastic │
   │ Fargate │         │ PostgreSQL       │ Cache   │
   │Backend  │         │ Multi-AZ │         │ Redis  │
   └─────────┘         └─────────┘         └────────┘
        │
   ┌────▼────┐
   │ ECR     │
   │Registry │
   └─────────┘
```

---

## 1. Componentes Principales

### 1.1 Route 53 (DNS)
- **Propósito**: Gestionar dominio y DNS
- **Configuración**:
  - Alias a CloudFront
  - Health checks
  - Failover automático

### 1.2 CloudFront + WAF
- **Propósito**: CDN global + protección
- **Beneficios**:
  - Caché de contenido estático
  - Compresión automática
  - DDoS protection
  - WAF rules personalizadas
  - HTTPS/TLS automático

### 1.3 S3 (Frontend)
- **Propósito**: Hosting estático de Next.js
- **Configuración**:
  - Bucket privado
  - CloudFront como único acceso
  - Versionado habilitado
  - Lifecycle policies

### 1.4 ALB (Application Load Balancer)
- **Propósito**: Distribuir tráfico backend
- **Configuración**:
  - Health checks cada 30s
  - Sticky sessions (opcional)
  - HTTPS listener
  - Target groups por servicio

### 1.5 ECS Fargate
- **Propósito**: Ejecutar contenedores backend
- **Configuración**:
  - 2-4 tasks en paralelo
  - Auto-scaling basado en CPU/memoria
  - Logs en CloudWatch
  - Secrets desde Secrets Manager

### 1.6 RDS PostgreSQL
- **Propósito**: Base de datos relacional
- **Configuración**:
  - Multi-AZ (alta disponibilidad)
  - Automated backups (30 días)
  - Encryption at rest
  - Encryption in transit
  - Read replicas (opcional)

### 1.7 ElastiCache Redis
- **Propósito**: Caché y cola de tareas
- **Configuración**:
  - Cluster mode disabled
  - Automatic failover
  - Encryption at rest
  - Encryption in transit
  - Backup automático

### 1.8 ECR (Elastic Container Registry)
- **Propósito**: Almacenar imágenes Docker
- **Configuración**:
  - Repositorio privado
  - Scan de vulnerabilidades
  - Lifecycle policies

---

## 2. Configuración Detallada por Servicio

### 2.1 RDS PostgreSQL

```bash
# Crear instancia
aws rds create-db-instance \
  --db-instance-identifier auditor-db-prod \
  --db-instance-class db.t3.small \
  --engine postgres \
  --engine-version 16.1 \
  --master-username auditor \
  --master-user-password $(aws secretsmanager get-random-password --query 'RandomPassword' --output text) \
  --allocated-storage 100 \
  --storage-type gp3 \
  --storage-encrypted \
  --kms-key-id arn:aws:kms:us-east-1:ACCOUNT:key/KEY_ID \
  --multi-az \
  --backup-retention-period 30 \
  --backup-window "03:00-04:00" \
  --maintenance-window "sun:04:00-sun:05:00" \
  --enable-cloudwatch-logs-exports postgresql \
  --enable-iam-database-authentication \
  --deletion-protection \
  --db-subnet-group-name auditor-db-subnet \
  --vpc-security-group-ids sg-xxxxxxxx \
  --publicly-accessible false
```

**Parámetros importantes:**
- `db.t3.small`: 2 vCPU, 2GB RAM (~$60/mes)
- `gp3`: SSD de alto rendimiento
- `multi-az`: Replicación automática
- `backup-retention-period 30`: 30 días de backups

### 2.2 ElastiCache Redis

```bash
# Crear cluster
aws elasticache create-cache-cluster \
  --cache-cluster-id auditor-redis-prod \
  --cache-node-type cache.t3.small \
  --engine redis \
  --engine-version 7.0 \
  --num-cache-nodes 1 \
  --parameter-group-name default.redis7 \
  --cache-subnet-group-name auditor-cache-subnet \
  --security-group-ids sg-xxxxxxxx \
  --at-rest-encryption-enabled \
  --transit-encryption-enabled \
  --auth-token $(aws secretsmanager get-random-password --query 'RandomPassword' --output text) \
  --automatic-failover-enabled \
  --multi-az \
  --snapshot-retention-limit 5 \
  --snapshot-window "03:00-05:00"
```

**Parámetros importantes:**
- `cache.t3.small`: 2GB RAM (~$30/mes)
- `at-rest-encryption-enabled`: Encriptación en reposo
- `transit-encryption-enabled`: Encriptación en tránsito
- `automatic-failover-enabled`: Failover automático

### 2.3 ECS Fargate

```bash
# Crear cluster
aws ecs create-cluster \
  --cluster-name auditor-prod \
  --cluster-settings name=containerInsights,value=enabled

# Crear task definition
aws ecs register-task-definition \
  --family auditor-backend \
  --network-mode awsvpc \
  --requires-compatibilities FARGATE \
  --cpu 512 \
  --memory 1024 \
  --execution-role-arn arn:aws:iam::ACCOUNT:role/ecsTaskExecutionRole \
  --task-role-arn arn:aws:iam::ACCOUNT:role/ecsTaskRole \
  --container-definitions file://task-definition.json

# Crear servicio
aws ecs create-service \
  --cluster auditor-prod \
  --service-name auditor-backend \
  --task-definition auditor-backend:1 \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx,subnet-yyy],securityGroups=[sg-xxx],assignPublicIp=DISABLED}" \
  --load-balancers targetGroupArn=arn:aws:elasticloadbalancing:...,containerName=backend,containerPort=8000 \
  --deployment-configuration maximumPercent=200,minimumHealthyPercent=100 \
  --enable-ecs-managed-tags
```

**Task Definition (task-definition.json):**

```json
[
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
        "valueFrom": "arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:auditor-geo/prod:DATABASE_URL::"
      },
      {
        "name": "SECRET_KEY",
        "valueFrom": "arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:auditor-geo/prod:SECRET_KEY::"
      }
    ],
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "/ecs/auditor-backend",
        "awslogs-region": "us-east-1",
        "awslogs-stream-prefix": "ecs"
      }
    },
    "healthCheck": {
      "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
      "interval": 30,
      "timeout": 5,
      "retries": 3,
      "startPeriod": 60
    }
  }
]
```

### 2.4 Auto Scaling

```bash
# Crear target para auto-scaling
aws autoscaling create-auto-scaling-target \
  --service-namespace ecs \
  --resource-id service/auditor-prod/auditor-backend \
  --scalable-dimension ecs:service:DesiredCount \
  --min-capacity 2 \
  --max-capacity 10

# Política de escalado por CPU
aws autoscaling put-scaling-policy \
  --policy-name auditor-cpu-scaling \
  --service-namespace ecs \
  --resource-id service/auditor-prod/auditor-backend \
  --scalable-dimension ecs:service:DesiredCount \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration file://scaling-policy.json
```

**scaling-policy.json:**

```json
{
  "TargetValue": 70.0,
  "PredefinedMetricSpecification": {
    "PredefinedMetricType": "ECSServiceAverageCPUUtilization"
  },
  "ScaleOutCooldown": 60,
  "ScaleInCooldown": 300
}
```

### 2.5 ALB (Application Load Balancer)

```bash
# Crear ALB
aws elbv2 create-load-balancer \
  --name auditor-alb \
  --subnets subnet-xxx subnet-yyy \
  --security-groups sg-xxx \
  --scheme internet-facing \
  --type application \
  --ip-address-type ipv4

# Crear target group
aws elbv2 create-target-group \
  --name auditor-backend \
  --protocol HTTP \
  --port 8000 \
  --vpc-id vpc-xxx \
  --health-check-protocol HTTP \
  --health-check-path /health \
  --health-check-interval-seconds 30 \
  --health-check-timeout-seconds 5 \
  --healthy-threshold-count 2 \
  --unhealthy-threshold-count 3

# Crear listener HTTPS
aws elbv2 create-listener \
  --load-balancer-arn arn:aws:elasticloadbalancing:... \
  --protocol HTTPS \
  --port 443 \
  --certificates CertificateArn=arn:aws:acm:... \
  --default-actions Type=forward,TargetGroupArn=arn:aws:elasticloadbalancing:...
```

### 2.6 CloudFront Distribution

```bash
# Crear distribución
aws cloudfront create-distribution \
  --distribution-config file://cloudfront-config.json
```

**cloudfront-config.json:**

```json
{
  "CallerReference": "auditor-geo-prod",
  "Comment": "Auditor GEO Production",
  "Enabled": true,
  "Origins": {
    "Quantity": 2,
    "Items": [
      {
        "Id": "S3-frontend",
        "DomainName": "auditor-geo-frontend.s3.us-east-1.amazonaws.com",
        "S3OriginConfig": {
          "OriginAccessIdentity": "origin-access-identity/cloudfront/ABCDEFG"
        }
      },
      {
        "Id": "ALB-backend",
        "DomainName": "auditor-alb-123456.us-east-1.elb.amazonaws.com",
        "CustomOriginConfig": {
          "HTTPPort": 80,
          "HTTPSPort": 443,
          "OriginProtocolPolicy": "https-only",
          "OriginSSLProtocols": {
            "Quantity": 1,
            "Items": ["TLSv1.2"]
          }
        }
      }
    ]
  },
  "DefaultCacheBehavior": {
    "TargetOriginId": "S3-frontend",
    "ViewerProtocolPolicy": "redirect-to-https",
    "AllowedMethods": {
      "Quantity": 2,
      "Items": ["GET", "HEAD"]
    },
    "CachePolicyId": "658327ea-f89d-4fab-a63d-7e88639e58f6"
  },
  "CacheBehaviors": [
    {
      "PathPattern": "/api/*",
      "TargetOriginId": "ALB-backend",
      "ViewerProtocolPolicy": "https-only",
      "AllowedMethods": {
        "Quantity": 7,
        "Items": ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
      },
      "CachePolicyId": "4135ea3d-c35d-46eb-81d7-reeSJmXQQpQ"
    }
  ],
  "WebACLId": "arn:aws:wafv2:us-east-1:ACCOUNT:global/webacl/auditor-geo/xxx"
}
```

---

## 3. Seguridad en Capas

### Capa 1: WAF (Web Application Firewall)

```bash
# Crear Web ACL
aws wafv2 create-web-acl \
  --name auditor-geo-waf \
  --scope CLOUDFRONT \
  --default-action Block={} \
  --rules file://waf-rules.json \
  --visibility-config SampledRequestsEnabled=true,CloudWatchMetricsEnabled=true,MetricName=auditor-geo-waf
```

**waf-rules.json:**

```json
[
  {
    "Name": "AWSManagedRulesCommonRuleSet",
    "Priority": 0,
    "Statement": {
      "ManagedRuleGroupStatement": {
        "VendorName": "AWS",
        "Name": "AWSManagedRulesCommonRuleSet"
      }
    },
    "OverrideAction": {
      "None": {}
    },
    "VisibilityConfig": {
      "SampledRequestsEnabled": true,
      "CloudWatchMetricsEnabled": true,
      "MetricName": "AWSManagedRulesCommonRuleSetMetric"
    }
  },
  {
    "Name": "RateLimitRule",
    "Priority": 1,
    "Statement": {
      "RateBasedStatement": {
        "Limit": 2000,
        "AggregateKeyType": "IP"
      }
    },
    "Action": {
      "Block": {}
    },
    "VisibilityConfig": {
      "SampledRequestsEnabled": true,
      "CloudWatchMetricsEnabled": true,
      "MetricName": "RateLimitRuleMetric"
    }
  }
]
```

### Capa 2: Security Groups

```bash
# ALB Security Group
aws ec2 create-security-group \
  --group-name auditor-alb-sg \
  --description "ALB for Auditor GEO" \
  --vpc-id vpc-xxx

# Permitir HTTPS desde internet
aws ec2 authorize-security-group-ingress \
  --group-id sg-alb \
  --protocol tcp \
  --port 443 \
  --cidr 0.0.0.0/0

# ECS Security Group
aws ec2 create-security-group \
  --group-name auditor-ecs-sg \
  --description "ECS for Auditor GEO" \
  --vpc-id vpc-xxx

# Permitir tráfico desde ALB
aws ec2 authorize-security-group-ingress \
  --group-id sg-ecs \
  --protocol tcp \
  --port 8000 \
  --source-group sg-alb

# RDS Security Group
aws ec2 create-security-group \
  --group-name auditor-rds-sg \
  --description "RDS for Auditor GEO" \
  --vpc-id vpc-xxx

# Permitir tráfico desde ECS
aws ec2 authorize-security-group-ingress \
  --group-id sg-rds \
  --protocol tcp \
  --port 5432 \
  --source-group sg-ecs
```

### Capa 3: VPC y Subnets

```bash
# Crear VPC
aws ec2 create-vpc --cidr-block 10.0.0.0/16

# Crear subnets privadas para ECS, RDS, Redis
aws ec2 create-subnet \
  --vpc-id vpc-xxx \
  --cidr-block 10.0.1.0/24 \
  --availability-zone us-east-1a

aws ec2 create-subnet \
  --vpc-id vpc-xxx \
  --cidr-block 10.0.2.0/24 \
  --availability-zone us-east-1b

# Crear subnet pública para ALB
aws ec2 create-subnet \
  --vpc-id vpc-xxx \
  --cidr-block 10.0.100.0/24 \
  --availability-zone us-east-1a
```

---

## 4. Monitoreo y Alertas

### CloudWatch Dashboards

```bash
# Crear dashboard
aws cloudwatch put-dashboard \
  --dashboard-name auditor-geo-prod \
  --dashboard-body file://dashboard.json
```

### Alarmas Críticas

```bash
# CPU alta en ECS
aws cloudwatch put-metric-alarm \
  --alarm-name auditor-ecs-cpu-high \
  --alarm-description "Alert if ECS CPU > 80%" \
  --metric-name CPUUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions arn:aws:sns:us-east-1:ACCOUNT:auditor-alerts

# Memoria alta en ECS
aws cloudwatch put-metric-alarm \
  --alarm-name auditor-ecs-memory-high \
  --alarm-description "Alert if ECS Memory > 80%" \
  --metric-name MemoryUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions arn:aws:sns:us-east-1:ACCOUNT:auditor-alerts

# RDS CPU alta
aws cloudwatch put-metric-alarm \
  --alarm-name auditor-rds-cpu-high \
  --alarm-description "Alert if RDS CPU > 80%" \
  --metric-name CPUUtilization \
  --namespace AWS/RDS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions arn:aws:sns:us-east-1:ACCOUNT:auditor-alerts
```

---

## 5. Costos Estimados (Mensual)

| Servicio | Configuración | Costo |
|----------|---------------|-------|
| RDS PostgreSQL | db.t3.small, Multi-AZ | $120 |
| ElastiCache Redis | cache.t3.small | $50 |
| ECS Fargate | 2x 512 CPU, 1GB RAM | $60 |
| ALB | 1 Load Balancer | $16 |
| CloudFront | 100GB/mes | $10 |
| S3 | 10GB storage | $0.25 |
| Secrets Manager | 1 secreto | $0.40 |
| CloudWatch Logs | 10GB/mes | $5 |
| **TOTAL** | | **~$261/mes** |

*Nota: Usar AWS Free Tier si es tu primer año (12 meses gratis para muchos servicios)*

---

## 6. Pasos de Implementación

1. **Semana 1**: Crear VPC, Subnets, Security Groups
2. **Semana 2**: Provisionar RDS y ElastiCache
3. **Semana 3**: Crear ECR y pushear imágenes
4. **Semana 4**: Configurar ECS Fargate y ALB
5. **Semana 5**: Configurar CloudFront y S3
6. **Semana 6**: Implementar WAF y monitoreo
7. **Semana 7**: Testing y optimización
8. **Semana 8**: Go live

---

## 7. Referencias

- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)
- [ECS Best Practices](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/best_practices.html)
- [RDS Best Practices](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_BestPractices.html)
- [CloudFront Best Practices](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/best-practices-content-delivery.html)
