import json
import sys
import io
from pathlib import Path

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def calculate_scores(audit_data):
    scores = {}
    
    # Structure Score (0-100)
    structure = audit_data.get('structure', {})
    structure_score = 0
    structure_score += 25 if structure.get('h1_check', {}).get('status') == 'pass' else 0
    structure_score += 25 if len(structure.get('header_hierarchy', {}).get('issues', [])) == 0 else 0
    structure_score += structure.get('semantic_html', {}).get('score_percent', 0) * 0.5
    scores['structure'] = round(structure_score, 1)
    
    # Content Score (0-100)
    content = audit_data.get('content', {})
    content_score = 0
    content_score += max(0, 100 - content.get('fragment_clarity', {}).get('score', 0) * 5)
    content_score += content.get('conversational_tone', {}).get('score', 0) * 10
    content_score += 25 if content.get('question_targeting', {}).get('status') == 'pass' else 0
    content_score += 25 if content.get('inverted_pyramid_style', {}).get('status') == 'pass' else 0
    scores['content'] = round(content_score / 2, 1)
    
    # E-E-A-T Score (0-100)
    eeat = audit_data.get('eeat', {})
    eeat_score = 0
    eeat_score += 25 if eeat.get('author_presence', {}).get('status') == 'pass' else 0
    eeat_score += min(25, eeat.get('citations_and_sources', {}).get('external_links', 0) * 0.5)
    eeat_score += 25 if len(eeat.get('content_freshness', {}).get('dates_found', [])) > 0 else 0
    trans = eeat.get('transparency_signals', {})
    eeat_score += 25 * sum([trans.get('about', False), trans.get('contact', False), trans.get('privacy', False)]) / 3
    scores['eeat'] = round(eeat_score, 1)
    
    # Schema Score (0-100)
    schema = audit_data.get('schema', {})
    schema_score = 0
    schema_score += 50 if schema.get('schema_presence', {}).get('status') == 'present' else 0
    schema_score += min(50, len(schema.get('schema_types', [])) * 25)
    scores['schema'] = round(schema_score, 1)
    
    # Total Score
    scores['total'] = round((scores['structure'] + scores['content'] + scores['eeat'] + scores['schema']) / 4, 1)
    
    return scores

def identify_strengths_weaknesses(scores, url):
    strengths = []
    weaknesses = []
    
    for category, score in scores.items():
        if category == 'total':
            continue
        if score >= 70:
            strengths.append(f"{category.upper()}: {score}/100")
        elif score < 50:
            weaknesses.append(f"{category.upper()}: {score}/100")
    
    return {
        'url': url,
        'strengths': strengths,
        'weaknesses': weaknesses
    }

def generate_comparison_table(all_scores):
    print("\n" + "="*100)
    print("TABLA COMPARATIVA DE PUNTAJES")
    print("="*100)
    print(f"{'Sitio':<50} {'Estructura':<12} {'Contenido':<12} {'E-E-A-T':<12} {'Schema':<12} {'TOTAL':<12}")
    print("-"*100)
    
    for item in all_scores:
        url = item['url'][:47] + "..." if len(item['url']) > 50 else item['url']
        scores = item['scores']
        print(f"{url:<50} {scores['structure']:<12} {scores['content']:<12} {scores['eeat']:<12} {scores['schema']:<12} {scores['total']:<12}")
    
    print("="*100)

def generate_ranking(all_scores):
    sorted_scores = sorted(all_scores, key=lambda x: x['scores']['total'], reverse=True)
    
    print("\n" + "="*100)
    print("RANKING GENERAL")
    print("="*100)
    
    for i, item in enumerate(sorted_scores, 1):
        url = item['url']
        total = item['scores']['total']
        print(f"{i}. {url} - {total}/100")
    
    print("="*100)

def generate_strengths_weaknesses_report(all_analysis):
    print("\n" + "="*100)
    print("FORTALEZAS Y DEBILIDADES POR COMPETIDOR")
    print("="*100)
    
    for analysis in all_analysis:
        print(f"\n{analysis['url']}")
        print("-"*100)
        print("FORTALEZAS:")
        if analysis['strengths']:
            for s in analysis['strengths']:
                print(f"  + {s}")
        else:
            print("  - Ninguna destacada")
        
        print("\nDEBILIDADES:")
        if analysis['weaknesses']:
            for w in analysis['weaknesses']:
                print(f"  - {w}")
        else:
            print("  - Ninguna critica")
        print()

def generate_html_report(all_scores, all_analysis, output_path):
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
    
    sorted_scores = sorted(all_scores, key=lambda x: x['scores']['total'], reverse=True)
    for i, item in enumerate(sorted_scores, 1):
        score_class = 'score-high' if item['scores']['total'] >= 70 else 'score-medium' if item['scores']['total'] >= 50 else 'score-low'
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
        scores = item['scores']
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
        if analysis['strengths']:
            for s in analysis['strengths']:
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
        if analysis['weaknesses']:
            for w in analysis['weaknesses']:
                html += f"<li>{w}</li>"
        else:
            html += "<li>Ninguna crítica</li>"
        
        html += """
                </ul>
            </div>
        </div>
"""
    
    # Chart data
    labels = [item['url'][:30] + '...' if len(item['url']) > 30 else item['url'] for item in all_scores]
    structure_data = [item['scores']['structure'] for item in all_scores]
    content_data = [item['scores']['content'] for item in all_scores]
    eeat_data = [item['scores']['eeat'] for item in all_scores]
    schema_data = [item['scores']['schema'] for item in all_scores]
    
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
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

def main():
    if len(sys.argv) < 2:
        print("Uso: python comparative_analysis.py <ruta_al_json>")
        sys.exit(1)
    
    json_path = Path(sys.argv[1])
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    all_scores = []
    all_analysis = []
    
    # Analizar empresa auditada
    target = data.get('target_audit', {})
    target_scores = calculate_scores(target)
    target_url = target.get('url', 'Empresa Auditada')
    all_scores.append({'url': target_url, 'scores': target_scores})
    all_analysis.append(identify_strengths_weaknesses(target_scores, target_url))
    
    # Analizar competidores
    for comp in data.get('competitor_audits', []):
        comp_scores = calculate_scores(comp)
        comp_url = comp.get('url', 'Desconocido')
        all_scores.append({'url': comp_url, 'scores': comp_scores})
        all_analysis.append(identify_strengths_weaknesses(comp_scores, comp_url))
    
    # Generar reportes
    generate_comparison_table(all_scores)
    generate_ranking(all_scores)
    generate_strengths_weaknesses_report(all_analysis)
    
    # Generar reporte HTML
    output_dir = json_path.parent
    html_path = output_dir / 'comparative_report.html'
    generate_html_report(all_scores, all_analysis, html_path)
    
    print(f"\n✅ Reporte HTML generado: {html_path}")
    
    # Guardar JSON con scores
    json_output = output_dir / 'comparative_scores.json'
    with open(json_output, 'w', encoding='utf-8') as f:
        json.dump({'scores': all_scores, 'analysis': all_analysis}, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Datos JSON generados: {json_output}")

if __name__ == '__main__':
    main()
