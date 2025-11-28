import requests
import sys

# Token obtenido de la BD (lo vimos en el paso anterior, pero no lo tengo en texto plano)
# Así que usaré el endpoint del backend para auditar, pero con logging extra.

# Mejor opción: Usar el token que ya está en la BD.
# Voy a asumir que puedo leerlo de la BD.

import psycopg2

def get_token():
    try:
        conn = psycopg2.connect("postgresql://auditor:auditor_password@localhost:5432/auditor_db")
        cur = conn.cursor()
        cur.execute("SELECT access_token FROM github_connections WHERE id = '950f7afc-fa8d-4baf-9bef-cd00c780f05c'")
        token = cur.fetchone()[0]
        conn.close()
        return token
    except Exception as e:
        print(f"Error DB: {e}")
        return None

# Como no puedo conectar a la BD desde fuera del contenedor fácilmente sin instalar dependencias,
# voy a usar un script que corra DENTRO del contenedor backend.

print("Este script debe correr dentro del contenedor backend")
