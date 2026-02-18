"""
Generador de Reportes Comparativos HTML
"""
import json
from pathlib import Path
from typing import Dict, List


def generate_html_report(
    all_scores: List[Dict], all_analysis: List[Dict], output_path: Path
) -> None:
    """Genera reporte HTML comparativo."""

    html = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Análisis Comparativo SEO</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f5f5f5; padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #2c3e50; margin-bottom: 30px; text-align: center; }
        h2 { color: #34495e; margin: 30px 0 20px; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #3498db; color: white; font-weight: 600; }
        tr:hover { background: #f8f9fa; }
        .score { font-weight: bold; padding: 5px 10px; border-radius: 5px; }
        .score-high { background: #2ecc71; color: white; }
        .score-medium { background: #f39c12; color: white; }
        .score-low { background: #e74c3c; color: white; }
        .chart-container { margin: 30px 0; padding: 20px; background: #f8f9fa; border-radius: 8px; }
        .analysis-card { background: #fff; border-left: 4px solid #3498db; padding: 20px; margin: 15px 0; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
        .strengths { color: #27ae60; }
        .weaknesses { color: #e74c3c; }
        ul { margin-left: 20px; margin-top: 10px; }
        .url-title { color: #2c3e50; font-weight: 600; margin-bottom: 10px; word-break: break-all; }
        .ranking { font-size: 24px; font-weight: bold; color: #3498db; margin-right: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Análisis Comparativo SEO - Competidores vs Empresa Auditada</h1>
        
        <h2>🏆 Ranking General</h2>
        <table>
            <thead>
                <tr>
                    <th>Posición</th>
                    <th>Sitio Web</th>
                    <th>Puntaje Total</th>
                </tr>
            </thead>
            <tbody>
"""

    sorted_scores = sorted(all_scores, key=lambda x: x["scores"]["total"], reverse=True)
    for i, item in enumerate(sorted_scores, 1):
        score_class = (
            "score-high"
            if item["scores"]["total"] >= 70
            else "score-medium"
            if item["scores"]["total"] >= 50
            else "score-low"
        )
        html += f"""
                <tr>
                    <td><span class="ranking">{i}</span></td>
                    <td>{item['url']}</td>
                    <td><span class="score {score_class}">{item['scores']['total']}/100</span></td>
                </tr>
"""

    html += """
            </tbody>
        </table>
        
        <h2>📈 Comparativa Detallada</h2>
        <table>
            <thead>
                <tr>
                    <th>Sitio Web</th>
                    <th>Estructura</th>
                    <th>Contenido</th>
                    <th>E-E-A-T</th>
                    <th>Schema</th>
                    <th>Total</th>
                </tr>
            </thead>
            <tbody>
"""

    for item in all_scores:
        scores = item["scores"]
        html += f"""
                <tr>
                    <td>{item['url']}</td>
                    <td><span class="score {'score-high' if scores['structure'] >= 70 else 'score-medium' if scores['structure'] >= 50 else 'score-low'}">{scores['structure']}</span></td>
                    <td><span class="score {'score-high' if scores['content'] >= 70 else 'score-medium' if scores['content'] >= 50 else 'score-low'}">{scores['content']}</span></td>
                    <td><span class="score {'score-high' if scores['eeat'] >= 70 else 'score-medium' if scores['eeat'] >= 50 else 'score-low'}">{scores['eeat']}</span></td>
                    <td><span class="score {'score-high' if scores['schema'] >= 70 else 'score-medium' if scores['schema'] >= 50 else 'score-low'}">{scores['schema']}</span></td>
                    <td><span class="score {'score-high' if scores['total'] >= 70 else 'score-medium' if scores['total'] >= 50 else 'score-low'}">{scores['total']}</span></td>
                </tr>
"""

    html += """
            </tbody>
        </table>
        
        <div class="chart-container">
            <canvas id="comparisonChart"></canvas>
        </div>
        
        <h2>💪 Fortalezas y Debilidades</h2>
"""

    for analysis in all_analysis:
        html += f"""
        <div class="analysis-card">
            <div class="url-title">{analysis['url']}</div>
            <div class="strengths">
                <strong>✓ Fortalezas:</strong>
                <ul>
"""
        if analysis["strengths"]:
            for s in analysis["strengths"]:
                html += f"<li>{s}</li>"
        else:
            html += "<li>Ninguna destacada</li>"

        html += """
                </ul>
            </div>
            <div class="weaknesses">
                <strong>✗ Debilidades:</strong>
                <ul>
"""
        if analysis["weaknesses"]:
            for w in analysis["weaknesses"]:
                html += f"<li>{w}</li>"
        else:
            html += "<li>Ninguna crítica</li>"

        html += """
                </ul>
            </div>
        </div>
"""

    # Chart data
    labels = [
        item["url"][:30] + "..." if len(item["url"]) > 30 else item["url"]
        for item in all_scores
    ]
    structure_data = [item["scores"]["structure"] for item in all_scores]
    content_data = [item["scores"]["content"] for item in all_scores]
    eeat_data = [item["scores"]["eeat"] for item in all_scores]
    schema_data = [item["scores"]["schema"] for item in all_scores]

    html += f"""
    </div>
    
    <script>
        const ctx = document.getElementById('comparisonChart').getContext('2d');
        new Chart(ctx, {{
            type: 'bar',
            data: {{
                labels: {json.dumps(labels)},
                datasets: [
                    {{
                        label: 'Estructura',
                        data: {structure_data},
                        backgroundColor: 'rgba(52, 152, 219, 0.7)',
                        borderColor: 'rgba(52, 152, 219, 1)',
                        borderWidth: 1
                    }},
                    {{
                        label: 'Contenido',
                        data: {content_data},
                        backgroundColor: 'rgba(46, 204, 113, 0.7)',
                        borderColor: 'rgba(46, 204, 113, 1)',
                        borderWidth: 1
                    }},
                    {{
                        label: 'E-E-A-T',
                        data: {eeat_data},
                        backgroundColor: 'rgba(155, 89, 182, 0.7)',
                        borderColor: 'rgba(155, 89, 182, 1)',
                        borderWidth: 1
                    }},
                    {{
                        label: 'Schema',
                        data: {schema_data},
                        backgroundColor: 'rgba(241, 196, 15, 0.7)',
                        borderColor: 'rgba(241, 196, 15, 1)',
                        borderWidth: 1
                    }}
                ]
            }},
            options: {{
                responsive: true,
                scales: {{
                    y: {{
                        beginAtZero: true,
                        max: 100
                    }}
                }},
                plugins: {{
                    title: {{
                        display: true,
                        text: 'Comparativa de Puntajes por Categoría',
                        font: {{ size: 18 }}
                    }},
                    legend: {{
                        display: true,
                        position: 'top'
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
