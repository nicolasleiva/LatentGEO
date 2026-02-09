#!/usr/bin/env python3
"""
Script para crear secretos en AWS Secrets Manager de forma segura.
Ejecutar con: python create_aws_secrets.py
"""

import json
import subprocess
import secrets
import base64
import os

def generate_secret_key():
    return secrets.token_urlsafe(32)

def generate_encryption_key():
    return base64.urlsafe_b64encode(os.urandom(32)).decode()

def generate_db_password():
    return secrets.token_urlsafe(24)

def create_aws_secret():
    # Generar claves seguras
    secret_key = generate_secret_key()
    encryption_key = generate_encryption_key()
    db_password = generate_db_password()

    print("🔐 Generando claves seguras para producción...")
    print(f"SECRET_KEY: {secret_key}")
    print(f"ENCRYPTION_KEY: {encryption_key}")
    print(f"DB_PASSWORD: {db_password}")
    print("\n⚠️  IMPORTANTE: Guarda estos valores de forma segura. No los compartas.")
    print("   Los necesitarás para configurar tu aplicación en AWS.\n")

    # Estructura del secreto
    secret_data = {
        "SECRET_KEY": secret_key,
        "ENCRYPTION_KEY": encryption_key,
        "DB_PASSWORD": db_password,
        "GEMINI_API_KEY": "REEMPLAZA_CON_TU_GEMINI_API_KEY",
        "GOOGLE_API_KEY": "REEMPLAZA_CON_TU_GOOGLE_API_KEY",
        "GOOGLE_PAGESPEED_API_KEY": "REEMPLAZA_CON_TU_PAGESPEED_API_KEY",
        "NVIDIA_API_KEY": "REEMPLAZA_CON_TU_NVIDIA_API_KEY",
        "NV_API_KEY_CODE": "REEMPLAZA_CON_TU_NV_CODE_KEY",
        "NV_API_KEY_ANALYSIS": "REEMPLAZA_CON_TU_NV_ANALYSIS_KEY",
        "GITHUB_CLIENT_ID": "REEMPLAZA_CON_TU_GITHUB_CLIENT_ID",
        "GITHUB_CLIENT_SECRET": "REEMPLAZA_CON_TU_GITHUB_CLIENT_SECRET",
        "GITHUB_WEBHOOK_SECRET": "REEMPLAZA_CON_TU_GITHUB_WEBHOOK_SECRET",
        "AUTH0_SECRET": "REEMPLAZA_CON_TU_AUTH0_SECRET",
        "AUTH0_CLIENT_ID": "REEMPLAZA_CON_TU_AUTH0_CLIENT_ID",
        "AUTH0_CLIENT_SECRET": "REEMPLAZA_CON_TU_AUTH0_CLIENT_SECRET"
    }

    # Crear comando AWS CLI
    secret_string = json.dumps(secret_data, indent=2)
    cmd = [
        "aws", "secretsmanager", "create-secret",
        "--name", "auditor-geo/prod",
        "--description", "Secretos de producción para Auditor GEO",
        "--secret-string", secret_string
    ]

    print("🚀 Creando secreto en AWS Secrets Manager...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("✅ Secreto creado exitosamente: auditor-geo/prod")
        print("📋 ARN del secreto:", json.loads(result.stdout)["ARN"])
    except subprocess.CalledProcessError as e:
        print("❌ Error al crear el secreto:")
        print(e.stderr)
        return False

    return True

if __name__ == "__main__":
    print("🔒 Configuración de Secretos para Producción en AWS")
    print("=" * 50)

    # Verificar si AWS CLI está instalado
    try:
        subprocess.run(["aws", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ AWS CLI no está instalado. Instálalo desde: https://aws.amazon.com/cli/")
        exit(1)

    # Verificar credenciales AWS
    try:
        subprocess.run(["aws", "sts", "get-caller-identity"], capture_output=True, check=True)
    except subprocess.CalledProcessError:
        print("❌ No tienes credenciales AWS configuradas o válidas.")
        print("   Configura tus credenciales con: aws configure")
        exit(1)

    create_aws_secret()

    print("\n📝 Próximos pasos:")
    print("1. Reemplaza los valores 'REEMPLAZA_CON_TU_*' con tus claves reales")
    print("2. Actualiza el secreto con: aws secretsmanager update-secret --secret-id auditor-geo/prod --secret-string '...'")
    print("3. Configura tu ECS Task Definition para usar estos secretos")
    print("4. Asegúrate de que tu aplicación tenga permisos IAM para acceder a Secrets Manager")