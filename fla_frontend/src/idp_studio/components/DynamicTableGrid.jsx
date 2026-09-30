import React, { useState, useEffect } from 'react';
import { 
  Table, 
  Plus, 
  Trash2, 
  Download, 
  Upload, 
  FileSpreadsheet, 
  Lock, 
  Link2, 
  Check, 
  ChevronDown, 
  ChevronUp,
  Sparkles,
  Info
} from 'lucide-react';

export default function DynamicTableGrid({
  field,
  value,
  onChange,
  selectedExtractedData = null,
  onLinkColumn = null,
  rules = [],
  repeatCount = null,
  onRepeatCountChange = null
}) {
  const [isExpanded, setIsExpanded] = useState(true);
  const archetype = field.table_archetype || 'web_dynamic_grid';
  const columns = field.columns || [];
  const minRows = field.min_rows || 1;
  const maxRows = field.max_rows || (archetype === 'excel_utility_bridge' ? 50 : 10);
  const isExcelBridge = archetype === 'excel_utility_bridge';

  // Helper to construct a clean default row
  const createDefaultRow = (index) => {
    const row = {};
    columns.forEach(col => {
      if (col.readonly && col.default_pattern) {
        row[col.key] = col.default_pattern.replace('{index}', index + 1);
      } else if (col.type === 'number') {
        row[col.key] = col.min || 1;
      } else if (col.type === 'select' && col.options && col.options.length > 0) {
        row[col.key] = col.options[0];
      } else {
        row[col.key] = '';
      }
    });
    return row;
  };

  // Initialize or synchronize rows
  const [rows, setRows] = useState(() => {
    if (Array.isArray(value) && value.length > 0) {
      return value;
    }
    const initialCount = Math.max(minRows, Number(repeatCount) || 1);
    return Array.from({ length: initialCount }, (_, i) => createDefaultRow(i));
  });

  // Sync rows if repeatCount from parent changes externally
  useEffect(() => {
    if (repeatCount !== null && repeatCount !== undefined) {
      const targetCount = Math.max(minRows, Math.min(maxRows, Number(repeatCount) || 1));
      setRows(prev => {
        if (prev.length === targetCount) return prev;
        if (prev.length < targetCount) {
          const needed = targetCount - prev.length;
          const newRows = Array.from({ length: needed }, (_, i) => createDefaultRow(prev.length + i));
          const updated = [...prev, ...newRows];
          if (onChange) onChange(updated);
          return updated;
        } else {
          const updated = prev.slice(0, targetCount);
          if (onChange) onChange(updated);
          return updated;
        }
      });
    }
  }, [repeatCount]);

  const handleCellChange = (rowIndex, colKey, val) => {
    const updated = rows.map((r, i) => {
      if (i === rowIndex) {
        return { ...r, [colKey]: val };
      }
      return r;
    });
    setRows(updated);
    if (onChange) onChange(updated);
  };

  const handleAddRow = () => {
    if (rows.length >= maxRows) return;
    const newRow = createDefaultRow(rows.length);
    const updated = [...rows, newRow];
    setRows(updated);
    if (onChange) onChange(updated);
    if (onRepeatCountChange) onRepeatCountChange(updated.length);
  };

  const handleDeleteRow = (index) => {
    if (rows.length <= minRows) return;
    const updated = rows.filter((_, i) => i !== index).map((r, i) => {
      // Re-number readonly sequence keys like SBO1, SBO2...
      const patched = { ...r };
      columns.forEach(col => {
        if (col.readonly && col.default_pattern) {
          patched[col.key] = col.default_pattern.replace('{index}', i + 1);
        }
      });
      return patched;
    });
    setRows(updated);
    if (onChange) onChange(updated);
    if (onRepeatCountChange) onRepeatCountChange(updated.length);
  };

  const handleExportExcel = () => {
    // Generate CSV / TSV as simple Excel-compatible download
    const headers = columns.map(c => c.label).join('\t');
    const dataRows = rows.map(r => columns.map(c => r[c.key] || '').join('\t')).join('\n');
    const content = `${headers}\n${dataRows}`;
    const blob = new Blob([content], { type: 'application/vnd.ms-excel' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${field.id.split('.').pop()}_template.xls`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  // Find column-level mapping rules
  const getColRule = (colKey) => {
    const targetKey = `${field.id}[].${colKey}`;
    return (rules || []).find(r => r.form_field === targetKey || r.form_field?.endsWith(`.${colKey}`));
  };

  return (
    <div className="mt-3 rounded-xl border border-emerald-500/30 bg-emerald-500/[0.02] dark:bg-emerald-950/[0.1] overflow-hidden shadow-sm">
      {/* Header bar */}
      <div 
        onClick={() => setIsExpanded(!isExpanded)}
        className="px-3 py-2 bg-emerald-500/10 dark:bg-emerald-500/15 border-b border-emerald-500/20 flex items-center justify-between cursor-pointer hover:bg-emerald-500/15 transition-colors"
      >
        <div className="flex items-center gap-2">
          <FileSpreadsheet className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
          <span className="text-xs font-bold text-emerald-900 dark:text-emerald-200 uppercase tracking-wider">
            {isExcelBridge ? 'Excel Utility Table' : 'Dynamic Table Grid'}
          </span>
          <span className="text-[0.65rem] font-bold px-1.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-700 dark:text-emerald-300">
            {rows.length} {rows.length === 1 ? 'Row' : 'Rows'}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {isExcelBridge && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                handleExportExcel();
              }}
              className="text-[0.65rem] px-2 py-0.5 rounded bg-emerald-600 hover:bg-emerald-700 text-white font-semibold flex items-center gap-1 transition-colors shadow-xs"
              title="Download Excel spreadsheet template"
            >
              <Download className="w-3 h-3" />
              <span>.XLS Template</span>
            </button>
          )}

          <button type="button" className="text-emerald-700 dark:text-emerald-300 p-0.5">
            {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Table Content */}
      {isExpanded && (
        <div className="p-2.5">
          {/* Instructions banner */}
          <div className="mb-2 text-[0.68rem] text-slate-500 dark:text-slate-400 flex items-center justify-between">
            <span className="flex items-center gap-1">
              <Info className="w-3 h-3 text-emerald-500" />
              <span>Fill each row directly or click column badges to link document extraction.</span>
            </span>
            <span className="font-mono text-[0.62rem]">
              Limits: {minRows}–{maxRows} rows
            </span>
          </div>

          {/* Responsive Table Scroll Container */}
          <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-white/10 bg-white dark:bg-black/30 shadow-inner">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-slate-50 dark:bg-white/5 border-b border-slate-200 dark:border-white/10 text-[0.68rem] text-slate-600 dark:text-slate-300 font-semibold">
                  <th className="py-2 px-2.5 w-12 text-center">#</th>
                  {columns.map(col => {
                    const colRule = getColRule(col.key);
                    const isColMappable = selectedExtractedData && onLinkColumn;
                    return (
                      <th key={col.key} className="py-2 px-2.5 min-w-[140px]">
                        <div className="flex flex-col gap-0.5">
                          <div className="flex items-center justify-between gap-1">
                            <span className="truncate" title={col.label}>{col.label}</span>
                            {col.canonical_no && (
                              <span className="text-[0.6rem] font-mono font-bold px-1 rounded bg-slate-200 dark:bg-white/10 text-slate-700 dark:text-slate-300">
                                {col.canonical_no}
                              </span>
                            )}
                          </div>

                          {/* Column Mapping Slot */}
                          {colRule ? (
                            <span className="text-[0.6rem] text-emerald-600 dark:text-emerald-400 font-bold flex items-center gap-0.5">
                              <Check className="w-2.5 h-2.5" />
                              <span className="truncate" title={colRule.extracted_key}>
                                {colRule.extracted_key}
                              </span>
                            </span>
                          ) : isColMappable ? (
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                onLinkColumn(`${field.id}[].${col.key}`);
                              }}
                              className="text-[0.6rem] px-1.5 py-0.5 rounded bg-indigo-50 hover:bg-indigo-100 dark:bg-indigo-500/20 text-indigo-600 dark:text-indigo-400 font-bold flex items-center gap-1 transition-all border border-indigo-200 dark:border-indigo-500/30 w-fit"
                              title={`Link column '${col.label}' to '${selectedExtractedData.key}'`}
                            >
                              <Link2 className="w-2.5 h-2.5" />
                              <span>Map Column</span>
                            </button>
                          ) : null}
                        </div>
                      </th>
                    );
                  })}
                  <th className="py-2 px-2 w-10 text-center">Act</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-white/5">
                {rows.map((row, rIdx) => (
                  <tr key={rIdx} className="hover:bg-slate-50/80 dark:hover:bg-white/[0.02] transition-colors">
                    <td className="py-2 px-2.5 text-center font-mono font-bold text-[0.68rem] text-slate-400">
                      {row[columns[0]?.key]?.startsWith?.('SBO') ? row[columns[0]?.key] : rIdx + 1}
                    </td>

                    {columns.map(col => {
                      const isReadonly = col.readonly;
                      const cellVal = row[col.key] ?? '';

                      if (isReadonly) {
                        return (
                          <td key={col.key} className="py-1.5 px-2.5">
                            <span className="inline-flex items-center gap-1 px-2 py-1 rounded bg-slate-100 dark:bg-white/5 text-slate-600 dark:text-slate-300 font-mono text-[0.7rem] font-bold border border-slate-200 dark:border-white/10">
                              <Lock className="w-2.5 h-2.5 text-slate-400" />
                              {cellVal}
                            </span>
                          </td>
                        );
                      }

                      if (col.type === 'select' && col.options && col.options.length > 0) {
                        return (
                          <td key={col.key} className="py-1.5 px-2.5">
                            <select
                              value={cellVal}
                              onChange={(e) => handleCellChange(rIdx, col.key, e.target.value)}
                              className="w-full text-xs py-1 px-2 rounded-md border border-slate-200 dark:border-white/10 bg-white dark:bg-black/40 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                            >
                              {col.options.map(opt => (
                                <option key={opt} value={opt}>{opt}</option>
                              ))}
                            </select>
                          </td>
                        );
                      }

                      return (
                        <td key={col.key} className="py-1.5 px-2.5">
                          <input
                            type={col.type === 'number' ? 'number' : 'text'}
                            value={cellVal}
                            min={col.min}
                            max={col.max}
                            onChange={(e) => handleCellChange(rIdx, col.key, e.target.value)}
                            placeholder={`Enter ${col.label}...`}
                            className="w-full text-xs py-1 px-2 rounded-md border border-slate-200 dark:border-white/10 bg-white dark:bg-black/40 text-slate-800 dark:text-slate-200 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                          />
                        </td>
                      );
                    })}

                    <td className="py-1.5 px-2 text-center">
                      <button
                        type="button"
                        onClick={() => handleDeleteRow(rIdx)}
                        disabled={rows.length <= minRows}
                        className="p-1 rounded text-slate-400 hover:text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-500/10 transition-colors disabled:opacity-30 disabled:hover:bg-transparent disabled:hover:text-slate-400"
                        title={rows.length <= minRows ? `Minimum ${minRows} row required` : 'Delete row'}
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Table Footer Controls */}
          <div className="mt-2.5 flex items-center justify-between">
            <button
              type="button"
              onClick={handleAddRow}
              disabled={rows.length >= maxRows}
              className="text-xs py-1.5 px-3 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 font-bold flex items-center gap-1.5 border border-emerald-500/20 transition-all disabled:opacity-40 disabled:cursor-not-allowed shadow-xs"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Add Row</span>
            </button>

            <span className="text-[0.65rem] text-slate-400 dark:text-slate-500">
              {rows.length} of {maxRows} maximum rows
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
