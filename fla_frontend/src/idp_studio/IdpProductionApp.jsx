import React, { useState, useEffect } from 'react';
import { 
  UploadCloud, 
  FileText, 
  CheckCircle2, 
  AlertTriangle, 
  Loader2, 
  Download, 
  Table, 
  Layers, 
  ArrowRight, 
  Edit3,
  RefreshCw,
  ExternalLink
} from 'lucide-react';
import { idpClient } from './api/idpClient';

export default function IdpProductionApp() {
  const [templates, setTemplates] = useState([]);
  const [templateName, setTemplateName] = useState('');
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [activeFileIndex, setActiveFileIndex] = useState(0);
  const [isExtracting, setIsExtracting] = useState(false);
  const [filterStatus, setFilterStatus] = useState('all'); // 'all' | 'success' | 'review'

  useEffect(() => {
    fetchTemplates();
  }, []);

  const fetchTemplates = async () => {
    try {
      const data = await idpClient.getTemplates();
      setTemplates(data || []);
      if (data && data.length > 0) {
        setTemplateName(data[0].template_name);
      } else {
        setTemplateName('');
      }
    } catch (err) {
      console.error('Failed to fetch IDP form templates:', err);
    }
  };

  const handleFileUpload = async (e) => {
    if (!templateName) {
      alert("No form schema selected! Please save mappings for your form in IDP Studio first.");
      return;
    }
    const selectedFiles = Array.from(e.target.files);
    if (!selectedFiles || selectedFiles.length === 0) return;


    const newQueue = selectedFiles.map(file => ({
      file: file,
      status: 'loading',
      data: []
    }));

    setUploadedFiles(prev => [...prev, ...newQueue]);
    setActiveFileIndex(0);
    setIsExtracting(true);

    try {
      const batchResults = await idpClient.extractBatchDocuments(selectedFiles, templateName);
      setUploadedFiles(prev => prev.map(item => {
        const res = batchResults.results.find(r => r.filename === item.file.name);
        if (res) {
          return {
            ...item,
            status: res.status,
            data: res.extracted_fields
          };
        }
        return item;
      }));
    } catch (err) {
      console.error('Failed batch extraction:', err);
      alert('Failed to extract data from uploaded documents.');
    } finally {
      setIsExtracting(false);
    }
  };

  const handleCellEdit = (docIndex, fieldIndex, newValue) => {
    setUploadedFiles(prev => {
      const updated = [...prev];
      const doc = { ...updated[docIndex] };
      const fields = [...(doc.data || [])];
      fields[fieldIndex] = { ...fields[fieldIndex], value: newValue };
      doc.data = fields;
      // Once edited by human, upgrade status to success
      doc.status = 'success';
      updated[docIndex] = doc;
      return updated;
    });
  };

  const handleExportExcel = () => {
    if (!uploadedFiles || uploadedFiles.length === 0) return;
    idpClient.exportToExcel(uploadedFiles, `${templateName}_Batch_Extraction_${new Date().toISOString().slice(0,10)}.csv`);
  };

  // Stats calculation
  const totalCount = uploadedFiles.length;
  const greenCount = uploadedFiles.filter(f => f.status === 'success').length;
  const yellowCount = uploadedFiles.filter(f => f.status === 'review').length;

  // Filtered docs for sidebar queue
  const displayedFiles = uploadedFiles.filter(f => {
    if (filterStatus === 'all') return true;
    return f.status === filterStatus;
  });

  const activeDoc = uploadedFiles[activeFileIndex] || null;

  return (
    <div className="flex flex-col w-full h-screen bg-slate-50 dark:bg-[#0B0F19] text-slate-900 dark:text-white overflow-hidden">
      {/* 1. Top Header Bar */}
      <header className="h-16 px-6 bg-white dark:bg-[#111726] border-b border-slate-200 dark:border-white/10 flex items-center justify-between shrink-0 shadow-sm">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center text-white shadow-md shadow-indigo-600/30 font-bold">
            <Layers className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold">IDP Production Extractor</h1>
              <span className="px-2 py-0.5 text-[10px] font-extrabold uppercase tracking-wider rounded-full bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400 border border-emerald-300 dark:border-emerald-500/30">
                End-User Batch Mode
              </span>
            </div>
            <p className="text-xs text-slate-500">100% Automated Document Processing — Zero Mapping Tools</p>
          </div>
        </div>

        {/* Form Selector & Actions */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Form Schema:</span>
            <select
              value={templateName}
              onChange={(e) => setTemplateName(e.target.value)}
              className="px-3 py-1.5 text-xs font-bold rounded-lg bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10 text-slate-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              {templates.length > 0 ? (
                templates.map((t, idx) => (
                  <option key={idx} value={t.template_name}>{t.template_name}</option>
                ))
              ) : (
                <option value="">No mapped forms in DB — Save rules in IDP Studio first</option>
              )}
            </select>
          </div>

          <div className="w-px h-6 bg-slate-200 dark:bg-white/10" />

          <button
            onClick={handleExportExcel}
            disabled={totalCount === 0}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed text-white shadow-sm shadow-emerald-600/20 transition-all"
          >
            <Download className="w-4 h-4" />
            <span>Export to Excel (.csv)</span>
          </button>

          <a
            href="/idp-studio"
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold bg-slate-100 dark:bg-white/5 hover:bg-slate-200 dark:hover:bg-white/10 text-slate-700 dark:text-slate-300 transition-all"
          >
            <span>Schema Studio</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      </header>

      {/* 2. Stats & Filter Banner */}
      <div className="h-12 px-6 bg-slate-100 dark:bg-[#151C2C] border-b border-slate-200 dark:border-white/10 flex items-center justify-between shrink-0 text-xs font-medium">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <span className="text-slate-500 font-semibold">Total Documents:</span>
            <span className="font-bold text-slate-900 dark:text-white">{totalCount}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            <span className="text-slate-500 font-semibold">Ready to Export (✓):</span>
            <span className="font-bold text-emerald-600 dark:text-emerald-400">{greenCount}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-amber-500" />
            <span className="text-slate-500 font-semibold">Needs Review (⚠):</span>
            <span className="font-bold text-amber-600 dark:text-amber-400">{yellowCount}</span>
          </div>
          {isExtracting && (
            <div className="flex items-center gap-2 text-indigo-500 font-bold">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              <span>Processing documents in backend...</span>
            </div>
          )}
        </div>

        {/* Filter Quick Tabs */}
        <div className="flex items-center gap-1 bg-white dark:bg-[#0B0F19] p-1 rounded-lg border border-slate-200 dark:border-white/10">
          <button
            onClick={() => setFilterStatus('all')}
            className={`px-3 py-1 rounded-md transition-all font-bold ${
              filterStatus === 'all'
                ? 'bg-indigo-600 text-white shadow-sm'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900'
            }`}
          >
            All ({totalCount})
          </button>
          <button
            onClick={() => setFilterStatus('success')}
            className={`px-3 py-1 rounded-md transition-all font-bold flex items-center gap-1 ${
              filterStatus === 'success'
                ? 'bg-emerald-600 text-white shadow-sm'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900'
            }`}
          >
            <span>✓ Auto-Approved ({greenCount})</span>
          </button>
          <button
            onClick={() => setFilterStatus('review')}
            className={`px-3 py-1 rounded-md transition-all font-bold flex items-center gap-1 ${
              filterStatus === 'review'
                ? 'bg-amber-600 text-white shadow-sm'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900'
            }`}
          >
            <span>⚠ Review ({yellowCount})</span>
          </button>
        </div>
      </div>

      {/* 3. Main Split View */}
      <div className="flex-1 flex min-h-0">
        {/* Left Panel: Batch Upload Dropzone & Queue */}
        <div className="w-96 border-r border-slate-200 dark:border-white/10 bg-white dark:bg-[#111726] flex flex-col shrink-0">
          {/* Upload Box */}
          <div className="p-4 border-b border-slate-200 dark:border-white/10">
            <label className="flex flex-col items-center justify-center p-6 bg-slate-50 dark:bg-[#1A2234] hover:bg-slate-100 dark:hover:bg-[#202B42] rounded-xl border-2 border-dashed border-slate-300 dark:border-slate-700 cursor-pointer transition-all text-center">
              <UploadCloud className="w-8 h-8 text-indigo-500 mb-2" />
              <span className="text-xs font-bold text-slate-800 dark:text-white">Drag & Drop Batch PDFs</span>
              <span className="text-[11px] text-slate-500 mt-0.5">Upload 1 to 50 documents at once</span>
              <input type="file" className="hidden" accept=".pdf" multiple={true} onChange={handleFileUpload} />
            </label>
          </div>

          {/* Queue List */}
          <div className="flex-1 overflow-y-auto p-3 space-y-2">
            {displayedFiles.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center p-6 text-slate-400">
                <FileText className="w-10 h-10 stroke-1 mb-2 opacity-50" />
                <p className="text-xs">No documents uploaded yet</p>
              </div>
            ) : (
              displayedFiles.map((doc, idx) => {
                const realIndex = uploadedFiles.indexOf(doc);
                const isActive = activeFileIndex === realIndex;
                return (
                  <button
                    key={doc.file.name + idx}
                    onClick={() => setActiveFileIndex(realIndex)}
                    className={`w-full text-left p-3 rounded-xl border transition-all flex items-center justify-between ${
                      isActive
                        ? 'bg-indigo-50 dark:bg-indigo-500/10 border-indigo-500 shadow-sm'
                        : 'bg-white dark:bg-transparent border-slate-200 dark:border-white/10 hover:border-slate-300'
                    }`}
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <FileText className="w-4 h-4 text-slate-500 shrink-0" />
                      <div className="min-w-0">
                        <p className="text-xs font-bold truncate text-slate-900 dark:text-white">{doc.file.name}</p>
                        <p className="text-[10px] text-slate-500 mt-0.5">
                          {doc.data ? `${doc.data.length} fields extracted` : 'Pending...'}
                        </p>
                      </div>
                    </div>

                    {/* Status Badge */}
                    <div className="shrink-0 ml-2">
                      {doc.status === 'success' && (
                        <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400">
                          <CheckCircle2 className="w-3 h-3" /> ✓
                        </span>
                      )}
                      {doc.status === 'review' && (
                        <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-400">
                          <AlertTriangle className="w-3 h-3" /> ⚠ Review
                        </span>
                      )}
                      {doc.status === 'loading' && (
                        <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-indigo-100 dark:bg-indigo-500/20 text-indigo-700 dark:text-indigo-400">
                          <Loader2 className="w-3 h-3 animate-spin" />
                        </span>
                      )}
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* Right Panel: Extracted Results & Inline Editor */}
        <div className="flex-1 flex flex-col bg-white dark:bg-[#1A2234] p-6 overflow-hidden">
          {!activeDoc ? (
            <div className="flex-1 flex flex-col items-center justify-center text-center text-slate-400 max-w-sm mx-auto">
              <div className="w-16 h-16 rounded-2xl bg-slate-100 dark:bg-white/5 flex items-center justify-center mb-4">
                <Table className="w-8 h-8 stroke-1 text-slate-500" />
              </div>
              <h3 className="text-base font-bold text-slate-800 dark:text-white mb-1">No Document Selected</h3>
              <p className="text-xs text-slate-500">Upload multiple balance sheet PDFs on the left to inspect and export their extracted data.</p>
            </div>
          ) : (
            <div className="flex-1 flex flex-col min-h-0">
              {/* Document Header */}
              <div className="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-white/10 shrink-0">
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-lg font-bold text-slate-900 dark:text-white">{activeDoc.file.name}</h2>
                    {activeDoc.status === 'success' ? (
                      <span className="px-2 py-0.5 rounded text-xs font-bold bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400">
                        100% Deterministic Match
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded text-xs font-bold bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-400">
                        Needs Quick Human Verification
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-500 mt-1">
                    Click any yellow table cell below to correct or verify extracted values inline.
                  </p>
                </div>
              </div>

              {/* Data Table */}
              <div className="flex-1 overflow-y-auto mt-4 border border-slate-200 dark:border-white/10 rounded-xl">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-slate-50 dark:bg-[#111726] border-b border-slate-200 dark:border-white/10 text-xs font-bold uppercase text-slate-500">
                      <th className="p-3.5 w-12 text-center">#</th>
                      <th className="p-3.5">Extracted Form Field (Key)</th>
                      <th className="p-3.5">Value (Click to Edit)</th>
                      <th className="p-3.5 w-32 text-center">Confidence Flag</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 dark:divide-white/10 text-sm">
                    {(activeDoc.data || []).map((field, fIdx) => (
                      <tr 
                        key={fIdx} 
                        className={`transition-colors ${
                          activeDoc.status === 'review' 
                            ? 'bg-amber-50/50 dark:bg-amber-500/5 hover:bg-amber-100/50' 
                            : 'hover:bg-slate-50 dark:hover:bg-white/5'
                        }`}
                      >
                        <td className="p-3.5 text-center text-xs font-bold text-slate-400">{fIdx + 1}</td>
                        <td className="p-3.5 font-bold uppercase text-xs text-slate-700 dark:text-slate-300">
                          {field.key}
                        </td>
                        <td className="p-3.5 font-bold text-slate-900 dark:text-white">
                          <input
                            type="text"
                            value={field.value || ''}
                            onChange={(e) => handleCellEdit(activeFileIndex, fIdx, e.target.value)}
                            className="w-full bg-transparent border-b border-dashed border-slate-300 dark:border-slate-700 focus:border-indigo-500 focus:outline-none py-1 px-1.5 rounded transition-colors font-bold text-base"
                            placeholder="Type value..."
                          />
                        </td>
                        <td className="p-3.5 text-center">
                          {activeDoc.status === 'success' ? (
                            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400">
                              ✓ Verified
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-400">
                              ⚠ Check
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
