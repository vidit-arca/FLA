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
  Info,
  Search,
  X,
  Zap,
  Rows,
  Columns as ColumnsIcon
} from 'lucide-react';

const KEYWORDS_MAP = [
  { pattern: /contribution|partner.*capital/i, headPattern: /contribution/i },
  { pattern: /reserve|surplus|retained.*earnings/i, headPattern: /reserves/i },
  { pattern: /secured\s*loan|borrowing.*secured/i, headPattern: /secured loans/i },
  { pattern: /unsecured\s*loan|borrowing.*unsecured/i, headPattern: /unsecured loans/i },
  { pattern: /short.*term.*borrow/i, headPattern: /short-term/i },
  { pattern: /trade\s*payable|creditor|sundry.*creditor/i, headPattern: /trade payables/i },
  { pattern: /other.*liabilit/i, headPattern: /other liabilities/i },
  { pattern: /total.*liabilit/i, headPattern: /total liabilities/i },
  { pattern: /gross.*fixed.*asset|gross.*block|property.*plant/i, headPattern: /gross fixed assets/i },
  { pattern: /depreciation|amortisation/i, headPattern: /depreciation/i },
  { pattern: /net.*fixed.*asset|net.*block/i, headPattern: /net fixed assets/i },
  { pattern: /investment/i, headPattern: /investments/i },
  { pattern: /inventor|stock/i, headPattern: /inventories/i },
  { pattern: /trade.*receivable|debtor|sundry.*debtor/i, headPattern: /trade receivables/i },
  { pattern: /cash|bank/i, headPattern: /cash and bank/i },
  { pattern: /loans.*advance/i, headPattern: /loans and advances/i },
  { pattern: /other.*asset/i, headPattern: /other assets/i },
  { pattern: /total.*asset/i, headPattern: /total assets/i },
  { pattern: /turnover|revenue.*operation|sales|gross.*revenue/i, headPattern: /turnover/i },
  { pattern: /other.*income/i, headPattern: /other income/i },
  { pattern: /total.*revenue|total.*income/i, headPattern: /total revenue/i },
  { pattern: /purchase|cost.*goods|cost.*material/i, headPattern: /purchases/i },
  { pattern: /personnel|employee.*benefit|salaries|wage/i, headPattern: /personnel/i },
  { pattern: /admin|other.*exp/i, headPattern: /administrative/i },
  { pattern: /total.*exp/i, headPattern: /total expenses/i },
  { pattern: /profit.*before.*tax|pbt/i, headPattern: /profit.*before/i },
  { pattern: /provision.*tax|tax.*expense/i, headPattern: /provision for tax/i },
  { pattern: /profit.*after.*tax|pat|net.*profit/i, headPattern: /profit.*after/i }
];

export default function DynamicTableGrid({
  field,
  value,
  onChange,
  selectedExtractedData = null,
  onLinkColumn = null,
  onLinkCell = null,
  onDeleteRule = null,
  rules = [],
  extractedData = [],
  repeatCount = null,
  onRepeatCountChange = null
}) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [showPreviousYear, setShowPreviousYear] = useState(true);
  const [pickerState, setPickerState] = useState(null); // { type: 'row'|'column'|'cell', rowIndex, colKey, title, head }
  const [pickerSearch, setPickerSearch] = useState('');

  const archetype = field.table_archetype || 'web_dynamic_grid';
  const rawColumns = field.columns || [];
  const columns = rawColumns.filter(c => showPreviousYear || c.key !== 'previous_year');
  const minRows = field.min_rows || 1;
  const maxRows = field.max_rows || (archetype === 'excel_utility_bridge' ? 50 : 10);
  const isExcelBridge = archetype === 'excel_utility_bridge';
  const isFinancialMatrix = archetype === 'financial_matrix';

  // Helper to construct a clean default row
  const createDefaultRow = (index) => {
    const row = {};
    columns.forEach(col => {
      if (col.readonly && col.default_pattern) {
        row[col.key] = col.default_pattern.replace('{index}', index + 1);
      } else if (col.type === 'number') {
        row[col.key] = '';
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
    if (Array.isArray(field.default_rows) && field.default_rows.length > 0) {
      return field.default_rows;
    }
    const initialCount = Math.max(minRows, Number(repeatCount) || 1);
    return Array.from({ length: initialCount }, (_, i) => createDefaultRow(i));
  });

  // Find cell-level mapping rule
  const getCellRule = (rIdx, colKey, row) => {
    const targetKey = `${field.id}[${rIdx}].${colKey}`;
    return (rules || []).find(r => 
      r.form_field === targetKey || 
      r.form_field?.endsWith(`[${rIdx}].${colKey}`)
    );
  };

  // Synchronize rows with cell rules
  useEffect(() => {
    if (!rules || rules.length === 0) return;
    setRows(prev => {
      let changed = false;
      const updated = prev.map((r, rIdx) => {
        let rowChanged = false;
        const newRow = { ...r };
        columns.forEach(col => {
          if (!col.readonly) {
            const rule = getCellRule(rIdx, col.key, r);
            if (rule && rule.extracted_value !== undefined && rule.extracted_value !== null) {
              const ruleVal = rule.extracted_value;
              if (newRow[col.key] !== ruleVal) {
                newRow[col.key] = ruleVal;
                rowChanged = true;
              }
            }
          }
        });
        if (rowChanged) changed = true;
        return rowChanged ? newRow : r;
      });
      if (changed) {
        if (onChange) onChange(updated);
        return updated;
      }
      return prev;
    });
  }, [rules]);

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

  const handleCellLink = (rowIndex, colKey, explicitData = null) => {
    const dataToLink = explicitData || selectedExtractedData;
    if (!dataToLink) return;
    const targetKey = `${field.id}[${rowIndex}].${colKey}`;
    if (onLinkCell) {
      onLinkCell(targetKey, dataToLink);
    }
    handleCellChange(rowIndex, colKey, dataToLink.value);
  };

  // Find column-level mapping rules
  const getColRule = (colKey) => {
    const targetKey = `${field.id}[].${colKey}`;
    return (rules || []).find(r => r.form_field === targetKey || r.form_field?.endsWith(`.${colKey}`));
  };

  // Row-level rules and helpers
  const getRowRules = (rIdx, row) => {
    return columns
      .filter(c => !c.readonly)
      .map(c => ({ col: c, rule: getCellRule(rIdx, c.key, row) }))
      .filter(x => !!x.rule);
  };

  const handleRowQuickMap = (rIdx, row) => {
    if (selectedExtractedData) {
      // Map to current_year by default, or whichever column is currently empty
      const targetCol = (row.current_year === '' || row.current_year === null || row.current_year === undefined)
        ? 'current_year'
        : 'previous_year';
      handleCellLink(rIdx, targetCol, selectedExtractedData);
    } else {
      setPickerSearch('');
      setPickerState({
        type: 'row',
        rowIndex: rIdx,
        title: `Map Row: ${row.financial_head || `Row #${rIdx + 1}`}`,
        head: row.financial_head || ''
      });
    }
  };

  const handleRowUnlink = (rIdx, row) => {
    const rowRules = getRowRules(rIdx, row);
    rowRules.forEach(({ rule }) => {
      if (onDeleteRule) onDeleteRule(rule.rule_id);
    });
  };

  const handleRowAutoMatch = (rIdx, row) => {
    const head = row.financial_head || '';
    if (!head || !extractedData || extractedData.length === 0) return;
    
    const km = KEYWORDS_MAP.find(k => k.headPattern.test(head));
    if (!km) return;
    
    const matched = extractedData.filter(item => km.pattern.test(item.key));
    if (matched.length > 0) {
      const cyMatch = matched.find(item => !/prev|prior|last.*year|py/i.test(item.key)) || matched[0];
      if (cyMatch) {
        handleCellLink(rIdx, 'current_year', cyMatch);
      }
      const pyMatch = matched.find(item => /prev|prior|last.*year|py/i.test(item.key));
      if (pyMatch) {
        handleCellLink(rIdx, 'previous_year', pyMatch);
      }
    }
  };

  // Column-level mapping handler
  const handleColumnQuickMap = (colKey, colLabel) => {
    if (selectedExtractedData) {
      if (onLinkColumn) {
        onLinkColumn(`${field.id}[].${colKey}`, selectedExtractedData);
      }
    } else {
      setPickerSearch('');
      setPickerState({
        type: 'column',
        colKey,
        title: `Map Entire Column: ${colLabel}`
      });
    }
  };

  const handleColumnAutoMatch = (colKey) => {
    if (!extractedData || extractedData.length === 0) return;
    const isPy = colKey === 'previous_year';
    let matchCount = 0;
    const updatedRows = [...rows];

    rows.forEach((row, rIdx) => {
      const head = row.financial_head || '';
      for (const km of KEYWORDS_MAP) {
        if (km.headPattern.test(head)) {
          const matched = extractedData.filter(item => km.pattern.test(item.key));
          if (matched.length > 0) {
            const targetMatch = isPy 
              ? matched.find(item => /prev|prior|last.*year|py/i.test(item.key))
              : (matched.find(item => !/prev|prior|last.*year|py/i.test(item.key)) || matched[0]);
            if (targetMatch && targetMatch.value !== undefined && targetMatch.value !== null) {
              const numVal = typeof targetMatch.value === 'number' ? targetMatch.value : String(targetMatch.value).replace(/[^\d.-]/g, '');
              if (numVal !== '') {
                const finalVal = Number(numVal) || numVal;
                updatedRows[rIdx] = { ...updatedRows[rIdx], [colKey]: finalVal };
                if (onLinkCell) {
                  onLinkCell(`${field.id}[${rIdx}].${colKey}`, targetMatch);
                }
                matchCount++;
              }
            }
          }
          break;
        }
      }
    });

    if (matchCount > 0) {
      setRows(updatedRows);
      if (onChange) onChange(updatedRows);
    }
  };

  // Auto-Map All rows and columns
  const handleAutoMap = (e) => {
    e?.stopPropagation();
    if (!extractedData || extractedData.length === 0) return;

    let matchCount = 0;
    const updatedRows = [...rows];

    rows.forEach((row, rIdx) => {
      const head = row.financial_head || '';
      for (const km of KEYWORDS_MAP) {
        if (km.headPattern.test(head)) {
          const matchedItems = extractedData.filter(item => km.pattern.test(item.key));
          if (matchedItems.length > 0) {
            // Find Current Year Match (exclude explicit prior/prev tags)
            const cyMatch = matchedItems.find(item => !/prev|prior|last.*year|py/i.test(item.key)) || matchedItems[0];
            if (cyMatch && cyMatch.value !== undefined && cyMatch.value !== null) {
              const rawVal = cyMatch.value;
              const numVal = typeof rawVal === 'number' ? rawVal : String(rawVal).replace(/[^\d.-]/g, '');
              if (numVal !== '') {
                const finalVal = Number(numVal) || numVal;
                updatedRows[rIdx] = { ...updatedRows[rIdx], current_year: finalVal };
                if (onLinkCell) {
                  onLinkCell(`${field.id}[${rIdx}].current_year`, cyMatch);
                }
                matchCount++;
              }
            }

            // Find Previous Year Match (explicit prior/prev tags)
            const pyMatch = matchedItems.find(item => /prev|prior|last.*year|py/i.test(item.key));
            if (pyMatch && pyMatch.value !== undefined && pyMatch.value !== null) {
              const rawVal = pyMatch.value;
              const numVal = typeof rawVal === 'number' ? rawVal : String(rawVal).replace(/[^\d.-]/g, '');
              if (numVal !== '') {
                const finalVal = Number(numVal) || numVal;
                updatedRows[rIdx] = { ...updatedRows[rIdx], previous_year: finalVal };
                if (onLinkCell) {
                  onLinkCell(`${field.id}[${rIdx}].previous_year`, pyMatch);
                }
                matchCount++;
              }
            }
          }
          break;
        }
      }
    });

    if (matchCount > 0) {
      setRows(updatedRows);
      if (onChange) onChange(updatedRows);
    }
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

  const mappedCellCount = rows.reduce((acc, r, rIdx) => {
    return acc + columns.filter(c => !c.readonly && !!getCellRule(rIdx, c.key, r)).length;
  }, 0);

  const mappedRowCount = rows.filter((r, rIdx) => getRowRules(rIdx, r).length > 0).length;

  // Filter extractedData for Quick-Pick modal
  const filteredExtractedData = (extractedData || []).filter(item => {
    if (!pickerSearch.trim()) return true;
    const s = pickerSearch.toLowerCase();
    return (item.key || '').toLowerCase().includes(s) || String(item.value || '').toLowerCase().includes(s);
  });

  const recommendedMatches = pickerState?.head ? (extractedData || []).filter(item => {
    const km = KEYWORDS_MAP.find(k => k.headPattern.test(pickerState.head));
    return km ? km.pattern.test(item.key) : false;
  }) : [];

  return (
    <div className="mt-3 rounded-xl border border-emerald-500/30 bg-emerald-500/[0.02] dark:bg-emerald-950/[0.1] overflow-hidden shadow-sm relative">
      {/* Header bar */}
      <div 
        onClick={() => setIsExpanded(!isExpanded)}
        className="px-3 py-2 bg-emerald-500/10 dark:bg-emerald-500/15 border-b border-emerald-500/20 flex items-center justify-between cursor-pointer hover:bg-emerald-500/15 transition-colors"
      >
        <div className="flex items-center gap-2 flex-wrap">
          <FileSpreadsheet className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
          <span className="text-xs font-bold text-emerald-900 dark:text-emerald-200 uppercase tracking-wider">
            {isFinancialMatrix ? 'Financial Statement Matrix (Part B)' : (isExcelBridge ? 'Excel Utility Table' : 'Dynamic Table Grid')}
          </span>
          <span className="text-[0.65rem] font-bold px-1.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-700 dark:text-emerald-300">
            {rows.length} {rows.length === 1 ? 'Row' : 'Rows'}
          </span>
          {mappedRowCount > 0 && (
            <span className="text-[0.65rem] font-bold px-1.5 py-0.5 rounded-full bg-emerald-600 text-white flex items-center gap-1 shadow-xs">
              <Check className="w-2.5 h-2.5" />
              <span>{mappedRowCount}/{rows.length} Rows Mapped</span>
            </span>
          )}
          {mappedCellCount > 0 && (
            <span className="text-[0.65rem] font-bold px-1.5 py-0.5 rounded-full bg-indigo-600 text-white flex items-center gap-1 shadow-xs">
              <span>{mappedCellCount} Cells</span>
            </span>
          )}
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* Comparative Toggle */}
          {isFinancialMatrix && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setShowPreviousYear(prev => !prev);
              }}
              className={`text-[0.65rem] px-2 py-1 rounded-md font-semibold flex items-center gap-1 border transition-colors shadow-xs ${
                showPreviousYear
                  ? 'bg-emerald-500/20 text-emerald-800 dark:text-emerald-300 border-emerald-500/30 hover:bg-emerald-500/30'
                  : 'bg-slate-100 dark:bg-white/10 text-slate-600 dark:text-slate-400 border-slate-300 dark:border-white/10 hover:bg-slate-200'
              }`}
              title="Toggle Previous Year comparative figures column"
            >
              <span>{showPreviousYear ? 'Comparative: Prev Year ON' : 'Show Prev Year'}</span>
            </button>
          )}

          {/* Auto-Map All */}
          {isFinancialMatrix && extractedData && extractedData.length > 0 && (
            <button
              type="button"
              onClick={handleAutoMap}
              className="text-[0.65rem] px-2.5 py-1 rounded-md bg-indigo-600 hover:bg-indigo-700 text-white font-bold flex items-center gap-1.5 transition-colors shadow-xs"
              title="Automatically map and populate all matching financial heads from extracted document data"
            >
              <Sparkles className="w-3 h-3 text-amber-300" />
              <span>Auto-Map All</span>
            </button>
          )}

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
          <div className="mb-2 text-[0.68rem] text-slate-500 dark:text-slate-400 flex items-center justify-between flex-wrap gap-1">
            <span className="flex items-center gap-1">
              <Info className="w-3 h-3 text-emerald-500 shrink-0" />
              <span>
                {isFinancialMatrix 
                  ? 'Map figures Row-wise, Column-wise, or Cell-wise directly from extracted document evidence.' 
                  : 'Fill each row directly or click column badges to link document extraction.'}
              </span>
            </span>
            <div className="flex items-center gap-2">
              {selectedExtractedData && (
                <span className="text-[0.62rem] px-1.5 py-0.5 rounded bg-indigo-100 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300 font-bold border border-indigo-200 dark:border-indigo-800">
                  Ready to link: "{selectedExtractedData.key}"
                </span>
              )}
              <span className="font-mono text-[0.62rem]">
                Limits: {minRows}–{maxRows} rows
              </span>
            </div>
          </div>

          {/* Responsive Table Scroll Container */}
          <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-white/10 bg-white dark:bg-black/30 shadow-inner">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-slate-50 dark:bg-white/5 border-b border-slate-200 dark:border-white/10 text-[0.68rem] text-slate-600 dark:text-slate-300 font-semibold">
                  <th className="py-2.5 px-2.5 w-12 text-center">#</th>
                  {columns.map(col => {
                    const colRule = getColRule(col.key);
                    const isReadonly = col.readonly;

                    return (
                      <th key={col.key} className="py-2.5 px-3 min-w-[170px] align-top">
                        <div className="flex flex-col gap-1.5">
                          <div className="flex items-center justify-between gap-1">
                            <span className="font-bold text-slate-800 dark:text-slate-100 truncate" title={col.label}>
                              {col.label}
                            </span>
                            {col.canonical_no && (
                              <span className="text-[0.6rem] font-mono font-bold px-1 rounded bg-slate-200 dark:bg-white/10 text-slate-700 dark:text-slate-300">
                                {col.canonical_no}
                              </span>
                            )}
                          </div>

                          {/* Column-Wise Mapping Controls */}
                          {!isReadonly && (
                            <div className="flex items-center gap-1.5 flex-wrap pt-0.5">
                              {colRule ? (
                                <div className="flex items-center justify-between w-full text-[0.62rem] text-emerald-700 dark:text-emerald-300 font-bold bg-emerald-500/15 px-2 py-0.5 rounded border border-emerald-500/30">
                                  <span className="flex items-center gap-1 truncate" title={colRule.extracted_key}>
                                    <ColumnsIcon className="w-2.5 h-2.5 shrink-0 text-emerald-600 dark:text-emerald-400" />
                                    <span className="truncate">Col: {colRule.extracted_key}</span>
                                  </span>
                                  {onDeleteRule && (
                                    <button
                                      type="button"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        onDeleteRule(colRule.rule_id);
                                      }}
                                      className="ml-1 text-slate-400 hover:text-red-500 font-bold"
                                      title="Unlink column"
                                    >
                                      ×
                                    </button>
                                  )}
                                </div>
                              ) : (
                                <div className="flex items-center gap-1 flex-wrap">
                                  {/* Map Column Action */}
                                  <button
                                    type="button"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleColumnQuickMap(col.key, col.label);
                                    }}
                                    className={`text-[0.6rem] px-2 py-0.5 rounded font-bold flex items-center gap-1 transition-all border ${
                                      selectedExtractedData 
                                        ? 'bg-indigo-600 hover:bg-indigo-700 text-white border-indigo-700 ring-2 ring-indigo-400 shadow-xs' 
                                        : 'bg-indigo-50 hover:bg-indigo-100 dark:bg-indigo-500/20 text-indigo-700 dark:text-indigo-300 border-indigo-200 dark:border-indigo-500/30'
                                    }`}
                                    title={selectedExtractedData ? `Map entire column to "${selectedExtractedData.key}"` : `Map entire column`}
                                  >
                                    <ColumnsIcon className="w-2.5 h-2.5" />
                                    <span>
                                      {selectedExtractedData ? `Map Col to "${selectedExtractedData.key.slice(0, 10)}..."` : 'Map Column'}
                                    </span>
                                  </button>

                                  {/* Auto-Match Column Action */}
                                  {extractedData && extractedData.length > 0 && (
                                    <button
                                      type="button"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handleColumnAutoMatch(col.key);
                                      }}
                                      className="text-[0.6rem] px-1.5 py-0.5 rounded bg-amber-50 hover:bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-300 font-bold flex items-center gap-0.5 transition-all border border-amber-200 dark:border-amber-500/30"
                                      title={`Auto-match extracted values for column ${col.label}`}
                                    >
                                      <Zap className="w-2.5 h-2.5" />
                                      <span>Auto-Col</span>
                                    </button>
                                  )}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      </th>
                    );
                  })}
                  {!isFinancialMatrix && <th className="py-2.5 px-2 w-10 text-center">Act</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-white/5">
                {rows.map((row, rIdx) => {
                  const rowRules = getRowRules(rIdx, row);
                  const isRowMapped = rowRules.length > 0;
                  const activeColCount = columns.filter(c => !c.readonly).length;

                  return (
                    <tr key={rIdx} className="hover:bg-slate-50/80 dark:hover:bg-white/[0.02] transition-colors">
                      <td className="py-2.5 px-2.5 text-center font-mono font-bold text-[0.68rem] text-slate-400">
                        {row[columns[0]?.key]?.startsWith?.('SBO') ? row[columns[0]?.key] : rIdx + 1}
                      </td>

                      {columns.map(col => {
                        const isReadonly = col.readonly;
                        const cellVal = row[col.key] ?? '';

                        if (isReadonly) {
                          return (
                            <td key={col.key} className="py-2 px-3 align-top min-w-[200px]">
                              <div className="flex flex-col gap-1.5">
                                <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded bg-slate-100 dark:bg-white/5 text-slate-700 dark:text-slate-200 font-medium text-[0.72rem] border border-slate-200 dark:border-white/10 leading-snug">
                                  <Lock className="w-3 h-3 text-slate-400 shrink-0" />
                                  <span>{cellVal}</span>
                                </span>

                                {/* Row-Wise Mapping Action Bar */}
                                {isFinancialMatrix && (
                                  <div className="flex items-center gap-1.5 flex-wrap">
                                    {isRowMapped ? (
                                      <div className="flex items-center gap-1">
                                        <span className="text-[0.6rem] font-bold px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-800 dark:text-emerald-300 border border-emerald-500/30 flex items-center gap-0.5">
                                          <Check className="w-2.5 h-2.5 text-emerald-600" />
                                          <span>Row: {rowRules.length}/{activeColCount} Mapped</span>
                                        </span>
                                        <button
                                          type="button"
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            handleRowUnlink(rIdx, row);
                                          }}
                                          className="text-[0.6rem] text-slate-400 hover:text-rose-500 font-medium px-1"
                                          title="Unlink all mapped cells in this row"
                                        >
                                          Unlink
                                        </button>
                                      </div>
                                    ) : (
                                      <div className="flex items-center gap-1">
                                        <button
                                          type="button"
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            handleRowQuickMap(rIdx, row);
                                          }}
                                          className={`text-[0.6rem] px-2 py-0.5 rounded font-bold flex items-center gap-1 transition-all border ${
                                            selectedExtractedData 
                                              ? 'bg-indigo-600 hover:bg-indigo-700 text-white border-indigo-700 ring-2 ring-indigo-400 shadow-xs' 
                                              : 'bg-slate-100 hover:bg-slate-200 dark:bg-white/5 dark:hover:bg-white/10 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-white/10'
                                          }`}
                                          title={selectedExtractedData ? `Map "${selectedExtractedData.key}" to this row` : 'Map this row'}
                                        >
                                          <Rows className="w-2.5 h-2.5" />
                                          <span>{selectedExtractedData ? 'Link to Row' : 'Map Row'}</span>
                                        </button>

                                        {extractedData && extractedData.length > 0 && (
                                          <button
                                            type="button"
                                            onClick={(e) => {
                                              e.stopPropagation();
                                              handleRowAutoMatch(rIdx, row);
                                            }}
                                            className="text-[0.6rem] px-1.5 py-0.5 rounded bg-amber-50 hover:bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-300 font-bold flex items-center gap-0.5 border border-amber-200 dark:border-amber-500/30 transition-all"
                                            title="Auto-match document figures for this row"
                                          >
                                            <Zap className="w-2.5 h-2.5" />
                                            <span>Match</span>
                                          </button>
                                        )}
                                      </div>
                                    )}
                                  </div>
                                )}
                              </div>
                            </td>
                          );
                        }

                        if (col.type === 'select' && col.options && col.options.length > 0) {
                          return (
                            <td key={col.key} className="py-2 px-3 align-top">
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

                        const cellRule = getCellRule(rIdx, col.key, row);
                        const isCellLinkable = !!selectedExtractedData;
                        const isMapped = !!cellRule;

                        return (
                          <td key={col.key} className="py-2 px-3 align-top min-w-[160px]">
                            <div className="flex flex-col gap-1">
                              <div 
                                onClick={() => {
                                  if (isCellLinkable) {
                                    handleCellLink(rIdx, col.key);
                                  }
                                }}
                                className={`relative rounded-md transition-all ${
                                  isCellLinkable 
                                    ? 'ring-2 ring-indigo-400 bg-indigo-50/50 dark:bg-indigo-950/30 cursor-pointer shadow-xs' 
                                    : isMapped 
                                      ? 'ring-1 ring-emerald-500/50 bg-emerald-500/[0.03]' 
                                      : ''
                                }`}
                              >
                                <input
                                  type={col.type === 'number' ? 'number' : 'text'}
                                  value={cellVal}
                                  min={col.min}
                                  max={col.max}
                                  onChange={(e) => handleCellChange(rIdx, col.key, e.target.value)}
                                  placeholder={
                                    isCellLinkable 
                                      ? `Click to map "${selectedExtractedData.key}"...` 
                                      : (col.key === 'current_year' 
                                          ? '₹ 0 (Click or Auto-Map)' 
                                          : (col.key === 'previous_year' ? '₹ 0 (Prior Year)' : `Enter ${col.label}...`))
                                  }
                                  className={`w-full text-xs py-1.5 px-2.5 rounded-md border bg-white dark:bg-black/40 text-slate-800 dark:text-slate-200 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-emerald-500 ${
                                    isMapped 
                                      ? 'border-emerald-500/60 font-bold text-emerald-950 dark:text-emerald-200' 
                                      : isCellLinkable 
                                        ? 'border-indigo-400 dark:border-indigo-500 text-indigo-900 dark:text-indigo-200 cursor-pointer' 
                                        : 'border-slate-200 dark:border-white/10'
                                  }`}
                                />

                                {/* Subtle Quick Map button when unmapped and no global selection */}
                                {!isMapped && !selectedExtractedData && extractedData && extractedData.length > 0 && (
                                  <button
                                    type="button"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setPickerSearch('');
                                      setPickerState({
                                        type: 'cell',
                                        rowIndex: rIdx,
                                        colKey: col.key,
                                        title: `Map Cell: ${row.financial_head || `Row ${rIdx + 1}`} (${col.label})`,
                                        head: row.financial_head || ''
                                      });
                                    }}
                                    className="absolute right-1.5 top-1/2 -translate-y-1/2 opacity-0 hover:opacity-100 group-hover:opacity-100 focus:opacity-100 text-[0.6rem] px-1 py-0.5 rounded bg-slate-100 hover:bg-indigo-50 text-slate-500 hover:text-indigo-600 border border-slate-200 transition-opacity"
                                    title="Pick extracted value for this cell"
                                  >
                                    <Link2 className="w-2.5 h-2.5" />
                                  </button>
                                )}
                              </div>

                              {/* Mapped Evidence Badge */}
                              {isMapped && (
                                <div className="flex items-center justify-between text-[0.6rem] text-emerald-700 dark:text-emerald-300 font-bold bg-emerald-500/15 px-1.5 py-0.5 rounded border border-emerald-500/20">
                                  <span className="flex items-center gap-1 truncate" title={cellRule.extracted_key}>
                                    <Link2 className="w-2.5 h-2.5 shrink-0 text-emerald-600 dark:text-emerald-400" />
                                    <span className="truncate">{cellRule.extracted_key}</span>
                                  </span>
                                  {onDeleteRule && (
                                    <button
                                      type="button"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        onDeleteRule(cellRule.rule_id);
                                      }}
                                      className="ml-1 text-slate-400 hover:text-red-500 font-bold leading-none"
                                      title="Unlink cell"
                                    >
                                      ×
                                    </button>
                                  )}
                                </div>
                              )}
                            </div>
                          </td>
                        );
                      })}

                      {!isFinancialMatrix && (
                        <td className="py-2 px-2 text-center align-middle">
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
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Table Footer Controls */}
          {!isFinancialMatrix && (
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
          )}
        </div>
      )}

      {/* Quick-Pick Modal for Row-wise, Column-wise, and Cell-wise mapping */}
      {pickerState && (
        <div 
          onClick={() => setPickerState(null)}
          className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center z-50 p-4"
        >
          <div 
            onClick={(e) => e.stopPropagation()}
            className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-white/10 rounded-2xl w-full max-w-md shadow-2xl overflow-hidden flex flex-col max-h-[85vh] animate-in fade-in zoom-in-95 duration-150"
          >
            {/* Modal Header */}
            <div className="px-4 py-3 border-b border-slate-200 dark:border-white/10 flex items-center justify-between bg-slate-50 dark:bg-white/5">
              <div className="flex items-center gap-2">
                <Link2 className="w-4 h-4 text-indigo-500" />
                <span className="text-xs font-bold text-slate-800 dark:text-white truncate max-w-[320px]">
                  {pickerState.title}
                </span>
              </div>
              <button
                type="button"
                onClick={() => setPickerState(null)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-1 rounded-md"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Search Input */}
            <div className="p-3 border-b border-slate-100 dark:border-white/5">
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={pickerSearch}
                  onChange={(e) => setPickerSearch(e.target.value)}
                  placeholder="Search extracted values or keys..."
                  autoFocus
                  className="w-full text-xs py-1.5 pl-8 pr-3 rounded-lg border border-slate-200 dark:border-white/10 bg-white dark:bg-black/30 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
              </div>
            </div>

            {/* List of Extracted Candidates */}
            <div className="p-3 overflow-y-auto space-y-2 flex-1">
              {/* Recommended Matches */}
              {recommendedMatches.length > 0 && !pickerSearch && (
                <div className="mb-3">
                  <div className="text-[0.65rem] font-bold text-indigo-600 dark:text-indigo-400 uppercase tracking-wider mb-1.5 flex items-center gap-1">
                    <Sparkles className="w-3 h-3" />
                    <span>Recommended Matches for this Head</span>
                  </div>
                  <div className="space-y-1.5">
                    {recommendedMatches.map((item, idx) => (
                      <div
                        key={`rec_${idx}`}
                        onClick={() => {
                          if (pickerState.type === 'row') {
                            handleCellLink(pickerState.rowIndex, 'current_year', item);
                          } else if (pickerState.type === 'column') {
                            if (onLinkColumn) onLinkColumn(`${field.id}[].${pickerState.colKey}`, item);
                          } else if (pickerState.type === 'cell') {
                            handleCellLink(pickerState.rowIndex, pickerState.colKey, item);
                          }
                          setPickerState(null);
                        }}
                        className="p-2 rounded-lg border border-indigo-200 dark:border-indigo-500/30 bg-indigo-50/50 dark:bg-indigo-950/20 hover:bg-indigo-100 dark:hover:bg-indigo-900/40 cursor-pointer transition-colors flex items-center justify-between"
                      >
                        <div className="flex flex-col min-w-0 pr-2">
                          <span className="text-[0.68rem] font-bold text-indigo-950 dark:text-indigo-200 truncate">{item.key}</span>
                          <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">₹ {item.value}</span>
                        </div>
                        <span className="text-[0.6rem] font-bold px-2 py-0.5 rounded bg-indigo-600 text-white shrink-0">
                          Select
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* All Extracted Items */}
              <div className="text-[0.65rem] font-bold text-slate-400 uppercase tracking-wider mb-1">
                {recommendedMatches.length > 0 && !pickerSearch ? 'All Document Extracted Items' : 'Extracted Document Data'}
              </div>

              {filteredExtractedData.length === 0 ? (
                <div className="p-4 text-center text-xs text-slate-400">
                  No extracted values match your search.
                </div>
              ) : (
                filteredExtractedData.map((item, idx) => (
                  <div
                    key={`all_${idx}`}
                    onClick={() => {
                      if (pickerState.type === 'row') {
                        handleCellLink(pickerState.rowIndex, 'current_year', item);
                      } else if (pickerState.type === 'column') {
                        if (onLinkColumn) onLinkColumn(`${field.id}[].${pickerState.colKey}`, item);
                      } else if (pickerState.type === 'cell') {
                        handleCellLink(pickerState.rowIndex, pickerState.colKey, item);
                      }
                      setPickerState(null);
                    }}
                    className="p-2 rounded-lg border border-slate-200 dark:border-white/5 bg-white dark:bg-black/20 hover:bg-slate-50 dark:hover:bg-white/5 hover:border-slate-300 cursor-pointer transition-colors flex items-center justify-between shadow-2xs"
                  >
                    <div className="flex flex-col min-w-0 pr-2">
                      <span className="text-[0.68rem] font-bold text-slate-700 dark:text-slate-200 truncate">{item.key}</span>
                      <span className="text-xs font-semibold text-slate-900 dark:text-white">₹ {item.value}</span>
                    </div>
                    <span className="text-[0.6rem] font-bold px-2 py-0.5 rounded bg-slate-100 hover:bg-indigo-600 text-slate-600 hover:text-white transition-colors shrink-0">
                      Link
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
