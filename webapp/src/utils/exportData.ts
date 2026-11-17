import JSZip from 'jszip';
import { saveAs } from 'file-saver';
import * as XLSX from 'xlsx';
import type { Project, CPMResult, TestCase } from '../types';

/**
 * Exports a pure data .ZIP bundle containing:
 * - proyecto.json (re-importable into the app)
 * - tabla_cpm_pert.csv (standard RFC4180 CSV)
 * - resultados.xlsx (Excel workbook with computed schedule and metrics)
 * - casos_prueba.json (test suite and edge cases)
 */
export async function exportProjectZip(
  project: Project,
  cpmResult: CPMResult | null,
  testCases: TestCase[]
): Promise<void> {
  const zip = new JSZip();

  // 1. proyecto.json
  const projectJson = JSON.stringify(project, null, 2);
  zip.file('proyecto.json', projectJson);

  // 2. casos_prueba.json
  const testCasesJson = JSON.stringify(testCases, null, 2);
  zip.file('casos_prueba.json', testCasesJson);

  // 3. tabla_cpm_pert.csv
  if (cpmResult && cpmResult.rows.length > 0) {
    const csvHeaders = [
      'Codigo',
      'Actividad',
      'Predecesoras',
      'Optimista (a)',
      'Mas Probable (m)',
      'Pesimista (b)',
      'Tiempo Esperado (te)',
      'Varianza',
      'Desviacion (sigma)',
      'ES',
      'EF',
      'LS',
      'LF',
      'Holgura Total',
      'Holgura Libre',
      'Es Critica',
      'Costo',
    ];

    const csvRows = cpmResult.rows.map((row) => [
      `"${row.code}"`,
      `"${row.name.replace(/"/g, '""')}"`,
      `"${row.predecessors.join(', ')}"`,
      row.optimistic,
      row.mostLikely,
      row.pessimistic,
      row.te.toFixed(2),
      row.variance.toFixed(4),
      row.sigma.toFixed(4),
      row.es.toFixed(2),
      row.ef.toFixed(2),
      row.ls.toFixed(2),
      row.lf.toFixed(2),
      row.totalSlack.toFixed(2),
      row.freeSlack.toFixed(2),
      row.isCritical ? 'SI' : 'NO',
      row.cost,
    ]);

    const csvContent = [csvHeaders.join(','), ...csvRows.map((r) => r.join(','))].join('\r\n');
    zip.file('tabla_cpm_pert.csv', csvContent);

    // 4. resultados.xlsx using SheetJS
    try {
      const wb = XLSX.utils.book_new();

      // Sheet 1: Tabla de Actividades y Tiempos
      const wsData = [
        csvHeaders,
        ...cpmResult.rows.map((row) => [
          row.code,
          row.name,
          row.predecessors.join(', '),
          row.optimistic,
          row.mostLikely,
          row.pessimistic,
          row.te,
          row.variance,
          row.sigma,
          row.es,
          row.ef,
          row.ls,
          row.lf,
          row.totalSlack,
          row.freeSlack,
          row.isCritical ? 'SI' : 'NO',
          row.cost,
        ]),
      ];
      const wsActivities = XLSX.utils.aoa_to_sheet(wsData);
      XLSX.utils.book_append_sheet(wb, wsActivities, 'Actividades PERT-CPM');

      // Sheet 2: Métricas del Proyecto
      const metricsData = [
        ['Métrica', 'Valor'],
        ['Nombre del Proyecto', project.name || 'Sin título'],
        ['Duración Total Esperada (días)', cpmResult.duration],
        ['Varianza de la Ruta Crítica', cpmResult.variance],
        ['Desviación Estándar (σ)', cpmResult.sigma],
        ['Actividades Críticas', cpmResult.criticalActivities.join(', ')],
        ['Ruta Crítica Secuencial', cpmResult.criticalPath.join(' -> ')],
        ['Costo Total Estimado', project.activities.reduce((s, a) => s + (a.cost || 0), 0)],
        ['Fecha de Cálculo', new Date().toISOString()],
      ];
      const wsMetrics = XLSX.utils.aoa_to_sheet(metricsData);
      XLSX.utils.book_append_sheet(wb, wsMetrics, 'Resumen Ejecutivo');

      const xlsxBuffer = XLSX.write(wb, { bookType: 'xlsx', type: 'array' });
      zip.file('resultados.xlsx', xlsxBuffer);
    } catch (err) {
      console.warn('Could not generate xlsx file, continuing with csv:', err);
    }
  }

  // Generate and download ZIP
  const blob = await zip.generateAsync({ type: 'blob' });
  const filename = `${(project.name || 'proyecto').toLowerCase().replace(/[^a-z0-9]+/g, '_')}_pert_cpm_datos.zip`;
  saveAs(blob, filename);
}
