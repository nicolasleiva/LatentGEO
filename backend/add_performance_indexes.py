"""
Migración: Agregar índices críticos para performance
Ejecutar: python add_performance_indexes.py
"""
from sqlalchemy import create_engine, text, inspect
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

def add_indexes():
    """Agregar índices para mejorar performance"""
    engine = create_engine(settings.DATABASE_URL)
    
    indexes = [
        # Audits - queries por usuario y fecha
        ("idx_audits_user_created", "audits", ["user_email", "created_at DESC"]),
        ("idx_audits_user_status", "audits", ["user_email", "status"]),
        
        # AuditedPages - N+1 queries
        ("idx_audited_pages_audit", "audited_pages", ["audit_id"]),
        
        # Competitors - listados
        ("idx_competitors_audit", "competitors", ["audit_id"]),
        
        # Reports - búsqueda de PDFs
        ("idx_reports_audit_type", "reports", ["audit_id", "report_type"]),
        
        # Keywords - búsquedas
        ("idx_keywords_audit", "keywords", ["audit_id"]),
        
        # Backlinks - análisis
        ("idx_backlinks_audit", "backlinks", ["audit_id"]),
        
        # RankTracking - tracking temporal
        ("idx_rank_tracking_audit", "rank_trackings", ["audit_id"]),
        
        # LLMVisibility - queries GEO
        ("idx_llm_visibility_audit", "llm_visibilities", ["audit_id"]),
        
        # ScoreHistory - gráficas temporales
        ("idx_score_history_domain_date", "score_history", ["domain", "recorded_at DESC"]),
    ]
    
    inspector = inspect(engine)
    existing_indexes = {}
    
    # Obtener índices existentes por tabla
    for table in inspector.get_table_names():
        existing_indexes[table] = [idx["name"] for idx in inspector.get_indexes(table)]
    
    with engine.connect() as conn:
        created = 0
        skipped = 0
        
        for idx_name, table, columns in indexes:
            # Verificar si la tabla existe
            if table not in inspector.get_table_names():
                logger.warning(f"Tabla {table} no existe, saltando índice {idx_name}")
                skipped += 1
                continue
            
            # Verificar si el índice ya existe
            if idx_name in existing_indexes.get(table, []):
                logger.info(f"Índice {idx_name} ya existe, saltando")
                skipped += 1
                continue
            
            try:
                # Construir SQL según el tipo de BD
                if settings.DATABASE_URL.startswith("sqlite"):
                    # SQLite no soporta DESC en índices, usar solo columnas
                    cols = [c.replace(" DESC", "") for c in columns]
                    sql = f"CREATE INDEX {idx_name} ON {table} ({', '.join(cols)})"
                else:
                    # PostgreSQL soporta CONCURRENTLY
                    sql = f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {idx_name} ON {table} ({', '.join(columns)})"
                
                logger.info(f"Creando índice: {idx_name}")
                conn.execute(text(sql))
                conn.commit()
                created += 1
                logger.info(f"✓ Índice {idx_name} creado")
                
            except Exception as e:
                logger.error(f"Error creando índice {idx_name}: {e}")
                conn.rollback()
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Resumen: {created} índices creados, {skipped} saltados")
        logger.info(f"{'='*60}")
        
        return created, skipped


if __name__ == "__main__":
    print("Agregando índices de performance...")
    created, skipped = add_indexes()
    print(f"\nCompletado: {created} creados, {skipped} saltados")
