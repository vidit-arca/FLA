import React, { useState, useEffect } from 'react';
import * as XLSX from 'xlsx';
import axios from 'axios';
import { Save, Loader2, AlertCircle } from 'lucide-react';

export default function ExcelViewer({ taskId }) {
  const [workbook, setWorkbook] = useState(null);
  const [activeSheet, setActiveSheet] = useState(0);
  const [edits, setEdits] = useState({});
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchExcel();
  }, [taskId]);

  const fetchExcel = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`http://localhost:8000/api/download/${taskId}`, {
        responseType: 'arraybuffer'
      });
      const data = new Uint8Array(res.data);
      const wb = XLSX.read(data, { type: 'array' });
      setWorkbook(wb);
      
      // Select Section I or the first sheet by default
      const defaultSheetIdx = wb.SheetNames.findIndex(n => n.includes("Section"));
      setActiveSheet(defaultSheetIdx >= 0 ? defaultSheetIdx : 0);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCellEdit = (sheetName, rowIndex, colIndex, value) => {
    const cellRef = XLSX.utils.encode_cell({ r: rowIndex, c: colIndex });
    setEdits(prev => ({
      ...prev,
      [`${sheetName}!${cellRef}`]: { sheet: sheetName, cell: cellRef, value: value }
    }));
  };

  const handleSave = async () => {
    const updatePayload = Object.values(edits);
    if (updatePayload.length === 0) return;

    setSaving(true);
    try {
      await axios.post(`http://localhost:8000/api/update-excel/${taskId}`, updatePayload);
      setEdits({});
      // Refresh to get latest data
      await fetchExcel();
    } catch (err) {
      console.error(err);
      alert("Failed to save Excel updates");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="flex justify-center p-12"><Loader2 className="w-8 h-8 animate-spin text-indigo-400" /></div>;
  }

  if (!workbook) {
    return <div className="p-8 text-center text-red-500"><AlertCircle className="w-10 h-10 mx-auto mb-2"/> Failed to load Excel file.</div>;
  }

  const currentSheetName = workbook.SheetNames[activeSheet];
  const worksheet = workbook.Sheets[currentSheetName];
  // Convert sheet to a 2D array representing rows and columns
  const rawRows = XLSX.utils.sheet_to_json(worksheet, { header: 1, defval: "" });
  const maxCols = Math.max(...rawRows.map(r => r.length), 0);
  const htmlRows = rawRows.map(r => {
    const newRow = [...r];
    while(newRow.length < maxCols) newRow.push("");
    return newRow;
  });

  return (
    <div className="flex flex-col bg-[#1A2235] border border-slate-700 rounded-xl shadow-sm overflow-hidden font-sans">
      
      {/* Tabs */}
      <div className="flex overflow-x-auto border-b border-slate-700 bg-[#131B2C]">
        {workbook.SheetNames.map((name, idx) => (
          <button
            key={name}
            onClick={() => setActiveSheet(idx)}
            className={`px-6 py-3 text-sm font-medium whitespace-nowrap transition-colors outline-none
              ${activeSheet === idx 
                ? 'border-b-2 border-indigo-500 text-indigo-300 bg-[#1A2235]' 
                : 'text-slate-400 hover:text-slate-300 hover:bg-[#1e293b]'}`}
          >
            {name}
          </button>
        ))}
      </div>

      {/* Action Bar */}
      <div className="p-3 bg-[#1A2235] border-b border-slate-700 flex justify-between items-center">
        <div className="text-sm text-slate-400 px-3">
          {Object.keys(edits).length > 0 ? (
            <span className="text-amber-600 font-medium">{Object.keys(edits).length} unsaved changes</span>
          ) : (
            <span>All changes saved</span>
          )}
        </div>
        <button 
          onClick={handleSave}
          disabled={saving || Object.keys(edits).length === 0}
          className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-300 text-white px-4 py-2 rounded-lg font-medium text-sm transition-colors"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          Sync to File
        </button>
      </div>

      {/* Spreadsheet Grid */}
      <div className="overflow-auto max-h-[600px] w-full">
        <table className="border-collapse w-full">
          <thead>
            <tr>
              <th className="bg-[#1e293b] border border-slate-700 p-1 w-10 sticky top-0 left-0 z-20"></th>
              {htmlRows[0] && htmlRows[0].map((_, colIdx) => (
                <th key={colIdx} className="bg-[#1e293b] border border-slate-700 p-1 font-normal text-xs text-slate-400 sticky top-0 z-10 min-w-[120px]">
                  {XLSX.utils.encode_col(colIdx)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {htmlRows.map((row, rowIdx) => (
              <tr key={rowIdx}>
                <td className="bg-[#1e293b] border border-slate-700 p-1 text-center text-xs text-slate-400 sticky left-0 z-10 w-10">
                  {rowIdx + 1}
                </td>
                {row.map((cellValue, colIdx) => {
                  const cellRef = XLSX.utils.encode_cell({ r: rowIdx, c: colIdx });
                  const editKey = `${currentSheetName}!${cellRef}`;
                  const isEdited = edits[editKey] !== undefined;
                  const displayValue = isEdited ? edits[editKey].value : cellValue;

                  return (
                    <td key={colIdx} className="border border-slate-700 p-0 relative group">
                      <input 
                        type="text"
                        value={displayValue}
                        onChange={(e) => handleCellEdit(currentSheetName, rowIdx, colIdx, e.target.value)}
                        className={`w-full h-full px-2 py-1.5 text-sm outline-none transition-colors
                          ${isEdited ? 'bg-indigo-900/40 text-indigo-300' : 'bg-transparent text-slate-200'}
                          focus:ring-2 focus:ring-primary-500 focus:bg-[#1A2235] focus:z-10 relative
                        `}
                      />
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
