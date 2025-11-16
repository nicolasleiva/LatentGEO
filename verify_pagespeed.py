#!/usr/bin/env python3
"""Script de verificación de PageSpeed y PDF"""
import sqlite3
import json
import os
from pathlib import Path

def check_database():
    """Verificar datos en la base de datos"""
    print("=== VERIFICACIÓN DE BASE DE DATOS ===\n")
    
    db_path = "backend/auditor.db"
    if not os.path.exists(db_path):
        db_path = "auditor.db"
    
    if not os.path.exists(db_path):
        print("[X] Base de datos no encontrada")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Últimas 5 auditorías
    cursor.execute("""
        SELECT id, url, status, 
               pagespeed_data IS NOT NULL as has_pagespeed,
               LENGTH(pagespeed_data) as pagespeed_size
        FROM audits 
        ORDER BY id DESC 
        LIMIT 5
    """)
    
    print("Últimas 5 auditorías:")
    print(f"{'ID':<5} {'Status':<12} {'PageSpeed':<12} {'Size':<10} {'URL'}")
    print("-" * 80)
    
    for row in cursor.fetchall():
        audit_id, url, status, has_ps, ps_size = row
        ps_status = "[OK] SI" if has_ps else "[X] NO"
        size_str = f"{ps_size} bytes" if ps_size else "N/A"
        print(f"{audit_id:<5} {status:<12} {ps_status:<12} {size_str:<10} {url[:40]}")
    
    # Verificar reportes PDF
    print("\n=== VERIFICACIÓN DE PDFs ===\n")
    cursor.execute("""
        SELECT a.id, a.url, r.file_path, r.file_size
        FROM audits a
        LEFT JOIN reports r ON a.id = r.audit_id AND r.report_type = 'PDF'
        WHERE a.status = 'completed'
        ORDER BY a.id DESC
        LIMIT 5
    """)
    
    print(f"{'ID':<5} {'PDF':<12} {'Size':<15} {'Path'}")
    print("-" * 80)
    
    for row in cursor.fetchall():
        audit_id, url, pdf_path, pdf_size = row
        pdf_status = "[OK] SI" if pdf_path else "[X] NO"
        exists = "[OK]" if pdf_path and os.path.exists(pdf_path) else "[X]"
        size_str = f"{pdf_size//1024}KB" if pdf_size else "N/A"
        path_str = pdf_path[:50] if pdf_path else "N/A"
        print(f"{audit_id:<5} {pdf_status} {exists:<10} {size_str:<15} {path_str}")
    
    conn.close()

def check_json_files():
    """Verificar archivos JSON de PageSpeed"""
    print("\n=== VERIFICACIÓN DE ARCHIVOS JSON ===\n")
    
    reports_dir = Path("reports")
    if not reports_dir.exists():
        print("[X] Directorio 'reports' no existe")
        return
    
    audit_dirs = sorted([d for d in reports_dir.iterdir() if d.is_dir() and d.name.startswith("audit_")], 
                       key=lambda x: int(x.name.split("_")[1]), reverse=True)[:5]
    
    print(f"{'Audit':<10} {'pagespeed.json':<20} {'Size':<10} {'Keys'}")
    print("-" * 80)
    
    for audit_dir in audit_dirs:
        audit_id = audit_dir.name
        ps_file = audit_dir / "pagespeed.json"
        
        if ps_file.exists():
            size = ps_file.stat().st_size
            try:
                with open(ps_file, 'r') as f:
                    data = json.load(f)
                keys = list(data.keys())
                print(f"{audit_id:<10} [OK] Existe{'':<12} {size//1024}KB{'':<5} {', '.join(keys)}")
            except:
                print(f"{audit_id:<10} [OK] Existe (ERROR){'':<6} {size//1024}KB{'':<5} No se pudo leer")
        else:
            print(f"{audit_id:<10} [X] No existe")

def check_api_key():
    """Verificar API key de PageSpeed"""
    print("\n=== VERIFICACIÓN DE API KEY ===\n")
    
    env_file = Path("backend/.env")
    if not env_file.exists():
        env_file = Path(".env")
    
    if env_file.exists():
        with open(env_file, 'r') as f:
            content = f.read()
            if "GOOGLE_PAGESPEED_API_KEY" in content:
                for line in content.split('\n'):
                    if line.startswith("GOOGLE_PAGESPEED_API_KEY"):
                        key = line.split('=')[1].strip()
                        masked = key[:10] + "..." + key[-4:] if len(key) > 14 else "***"
                        print(f"[OK] GOOGLE_PAGESPEED_API_KEY configurada: {masked}")
            else:
                print("[X] GOOGLE_PAGESPEED_API_KEY no encontrada en .env")
    else:
        print("[X] Archivo .env no encontrado")

def main():
    print("\n" + "="*80)
    print("DIAGNÓSTICO DE PAGESPEED Y PDF")
    print("="*80 + "\n")
    
    check_api_key()
    check_database()
    check_json_files()
    
    print("\n" + "="*80)
    print("DIAGNÓSTICO COMPLETADO")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
