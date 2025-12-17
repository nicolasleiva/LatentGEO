'use client';

import { Clock, AlertTriangle } from 'lucide-react';

interface AuditProgressIndicatorProps {
  progress: number;
  status: string;
  hasTimedOut: boolean;
}

export function AuditProgressIndicator({
  progress,
  status,
  hasTimedOut,
}: AuditProgressIndicatorProps) {
  if (status === 'completed') return null;

  const getProgressMessage = () => {
    if (status === 'pending' && progress === 0) {
      return '⏳ Configurando auditoría...';
    }
    if (progress < 33) return '1/3: Analizando tu página';
    if (progress < 66) return '2/3: Analizando competidores';
    if (progress < 100) return '3/3: Generando reporte con IA (esto puede tardar 1-2 minutos)';
    return null;
  };

  return (
    <>
      <div className="mt-8">
        <div className="flex justify-between mb-2 text-sm text-muted-foreground">
          <span className="font-medium flex items-center gap-2">
            <Clock className="w-4 h-4" />
            {getProgressMessage()}
          </span>
          <span className="font-semibold">{progress}%</span>
        </div>
        <div className="w-full bg-muted rounded-full h-2 overflow-hidden">
          <div
            className="bg-gradient-to-r from-blue-500 to-purple-500 h-full rounded-full transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {hasTimedOut && (
        <div className="mt-4 p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-xl flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-yellow-200">
            <p className="font-medium mb-1">El análisis está tardando más de lo normal</p>
            <p className="text-xs text-yellow-300/80">Te avisaremos por email cuando esté listo.</p>
          </div>
        </div>
      )}
    </>
  );
}
