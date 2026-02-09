#!/bin/bash
# Script para crear secretos en AWS Secrets Manager
# Ejecutar con: bash create_aws_secrets.sh

# Generar claves seguras
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
ENCRYPTION_KEY=$(python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())")
DB_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")

echo "Generando secretos seguros..."
echo "SECRET_KEY: $SECRET_KEY"
echo "ENCRYPTION_KEY: $ENCRYPTION_KEY"
echo "DB_PASSWORD: $DB_PASSWORD"

# Crear secreto en AWS Secrets Manager
aws secretsmanager create-secret \
  --name auditor-geo/prod \
  --description "Secretos de producción para Auditor GEO" \
  --secret-string "{
    \"SECRET_KEY\": \"$SECRET_KEY\",
    \"ENCRYPTION_KEY\": \"$ENCRYPTION_KEY\",
    \"DB_PASSWORD\": \"$DB_PASSWORD\",
    \"GEMINI_API_KEY\": \"tu_gemini_key_aqui\",
    \"GOOGLE_API_KEY\": \"tu_google_key_aqui\",
    \"GOOGLE_PAGESPEED_API_KEY\": \"tu_pagespeed_key_aqui\",
    \"NVIDIA_API_KEY\": \"tu_nvidia_key_aqui\",
    \"NV_API_KEY_CODE\": \"tu_nv_code_key_aqui\",
    \"NV_API_KEY_ANALYSIS\": \"tu_nv_analysis_key_aqui\",
    \"GITHUB_CLIENT_ID\": \"tu_github_client_id\",
    \"GITHUB_CLIENT_SECRET\": \"tu_github_client_secret\",
    \"GITHUB_WEBHOOK_SECRET\": \"tu_github_webhook_secret\",
    \"AUTH0_SECRET\": \"tu_auth0_secret\",
    \"AUTH0_CLIENT_ID\": \"tu_auth0_client_id\",
    \"AUTH0_CLIENT_SECRET\": \"tu_auth0_client_secret\"
  }"

echo "Secreto creado en AWS Secrets Manager: auditor-geo/prod"
echo "IMPORTANTE: Anota estos valores de forma segura y no los compartas."