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
  ExternalLink,
  Sparkles,
  X,
  Calculator,
  FileSpreadsheet
} from 'lucide-react';
import { idpClient } from './api/idpClient';

export default function IdpProductionApp() {
  const [templates, setTemplates] = useState([]);
  const [templateName, setTemplateName] = useState('');
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [activeFileIndex, setActiveFileIndex] = useState(0);
  const [isExtracting, setIsExtracting] = useState(false);
  const [filterStatus, setFilterStatus] = useState('all'); // 'all' | 'success' | 'review'

  // Consolidated Form Return Modal States
  const [showConsolidatedModal, setShowConsolidatedModal] = useState(false);
  const [consolidatedState, setConsolidatedState] = useState(null);
  const [isEvaluatingConsolidated, setIsEvaluatingConsolidated] = useState(false);
  const [isDownloadingExcel, setIsDownloadingExcel] = useState(false);
  const [activeModalSection, setActiveModalSection] = useState('Section II');
  const [hideEmptyModalRows, setHideEmptyModalRows] = useState(true);
  const [showOnlyMappedFields, setShowOnlyMappedFields] = useState(true);

  const isFieldMapped = (val) => {
    if (val === null || val === undefined) return false;
    const s = String(val).trim();
    if (s === "" || s === "Unknown" || s === "N/A" || s === "Empty / N/A" || s === "None" || s === "null") return false;
    // Reject values that are suspiciously short labels (likely a field label was extracted as value)
    // e.g. "CIN No", "Corporate Office", "Name" — if value matches extracted_key it's wrong
    return true;
  };

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

  const CELL_LABELS = {
    "Section I": {
      "C3": "Filing Year",
      "C4": "Name of the Indian Company",
      "C5": "PAN Number",
      "C6": "CIN Number",
      "C7": "Name of the Contact Person",
      "C8": "Telephone No. (with extension)",
      "C9": "Mobile Number",
      "C10": "E-Mail ID (Head of the institution)",
      "C11": "E-Mail of Contact Person",
      "C12": "Designation",
      "C13": "Website (if any)",
      "C14": "Closing Date of Reference Period",
      "C15": "State / Union Territory",
      "C16": "Whether Company is Listed (Yes/No)",
      "C17": "Whether Company is a Technical/Management Consultant",
      "C21": "Activity Code (NIC 2008)",
      "C22": "Group / Subsidiary Status",
      "C23": "Whether Company is a Startup",
      "C26": "Auditor Firm Name",
      "C27": "Auditor Firm Registration Number",
      "C28": "Auditor Contact Number",
      "C32": "Listed Market Price per Share",
      "C33": "Face Value per Equity Share (INR)",
      "C35": "Overseas Direct Investment (ODI) Status",
      "C36": "Foreign Currency Loans / Trade Credit Status",
      "C37": "Foreign Direct Investment (FDI) Status"
    },
    "Section II": {
      "D5": "Total Paid-up Capital PY (Shares)",
      "E5": "Total Paid-up Capital FY (Shares)",
      "F5": "Total Paid-up Capital PY (Amount in Lakhs)",
      "G5": "Total Paid-up Capital FY (Amount in Lakhs)",
      "D6": "Total Equity & Participating Pref PY (Shares)",
      "E6": "Total Equity & Participating Pref FY (Shares)",
      "F6": "Total Equity & Participating Pref PY (Amount in Lakhs)",
      "G6": "Total Equity & Participating Pref FY (Amount in Lakhs)",
      "D7": "Ordinary Equity Shares PY (Count)",
      "E7": "Ordinary Equity Shares FY (Count)",
      "F7": "Ordinary Equity Amount PY (Amount in Lakhs)",
      "G7": "Ordinary Equity Amount FY (Amount in Lakhs)",
      "D8": "Participating Preference Shares PY (Count)",
      "E8": "Participating Preference Shares FY (Count)",
      "F8": "Participating Preference Amount PY (Amount in Lakhs)",
      "G8": "Participating Preference Amount FY (Amount in Lakhs)",
      "D9": "Non-Participating Preference Shares PY (Count)",
      "E9": "Non-Participating Preference Shares FY (Count)",
      "F9": "Non-Participating Preference Amount PY (Amount in Lakhs)",
      "G9": "Non-Participating Preference Amount FY (Amount in Lakhs)",
      "F11": "Total Non-Resident Holdings PY (Amount in Lakhs)",
      "G11": "Total Non-Resident Holdings FY (Amount in Lakhs)",
      "F24": "Non-Resident Shareholding Percentage PY (%)",
      "G24": "Non-Resident Shareholding Percentage FY (%)",
      "F27": "Profit After Tax PY (Amount in Lakhs)",
      "G27": "Profit After Tax FY (Amount in Lakhs)",
      "F30": "Retained Profit PY (Amount in Lakhs)",
      "G30": "Retained Profit FY (Amount in Lakhs)",
      "F32": "Reserves & Surplus PY (Amount in Lakhs)",
      "G32": "Reserves & Surplus FY (Amount in Lakhs)",
      "F34": "Net Worth PY (Amount in Lakhs)",
      "G34": "Net Worth FY (Amount in Lakhs)",
      "F39": "Domestic Purchases PY (Amount in Lakhs)",
      "G39": "Domestic Purchases FY (Amount in Lakhs)",
      "F40": "Imports PY (Amount in Lakhs)",
      "G40": "Imports FY (Amount in Lakhs)",
      "F41": "Total Purchases PY (Domestic + Imports)",
      "G41": "Total Purchases FY (Domestic + Imports)"
    },
    "Section III": {
      "D70": "Unrelated Trade Credit PY (Amount in Lakhs)",
      "E70": "Unrelated Trade Credit FY (Amount in Lakhs)",
      "D71": "Unrelated Loans PY (Amount in Lakhs)",
      "E71": "Unrelated Loans FY (Amount in Lakhs)",
      "D72": "Unrelated Currency & Deposits PY (Amount in Lakhs)",
      "E72": "Unrelated Currency & Deposits FY (Amount in Lakhs)",
      "D73": "Unrelated Other Liabilities PY (Amount in Lakhs)",
      "E73": "Unrelated Other Liabilities FY (Amount in Lakhs)",
      "D74": "Unrelated Total Liabilities PY (Amount in Lakhs)",
      "E74": "Unrelated Total Liabilities FY (Amount in Lakhs)"
    },
    "Section IV": {
      "D26": "DIE 1 Equity Capital & Reserves PY (in Foreign Currency)",
      "E26": "DIE 1 Equity Capital & Reserves FY (in Foreign Currency)",
      "D27": "DIE 1 Face Value of Equity Held PY (in Foreign Currency)",
      "E27": "DIE 1 Face Value of Equity Held FY (in Foreign Currency)",
      "D28": "DIE 1 Other Reserves PY (in Foreign Currency)",
      "E28": "DIE 1 Other Reserves FY (in Foreign Currency)",
      "D30": "DIE 1 Net Worth PY (in Foreign Currency)",
      "E30": "DIE 1 Net Worth FY (in Foreign Currency)",
      "D31": "DIE 1 Exchange Rate PY (INR per FC)",
      "E31": "DIE 1 Exchange Rate FY (INR per FC)",
      "D39": "DIE 1 Equity Capital PY (INR Lakhs)",
      "E39": "DIE 1 Equity Capital FY (INR Lakhs)",
      "D96": "Unrelated Trade Credit PY (Claims in Lakhs)",
      "E96": "Unrelated Trade Credit FY (Claims in Lakhs)",
      "D100": "Unrelated Total Claims PY (Amount in Lakhs)",
      "E100": "Unrelated Total Claims FY (Amount in Lakhs)"
    }
  };

  const getConsolidatedPayload = () => {
    const payload = {};
    const KEY_MAP = {
      "pannumber": "pan_number",
      "cinnumber": "cin_number",
      "contactperson": "contact_name",
      "nameofthecontactperson": "contact_name",
      "telephonenowithextension": "telephone",
      "mobileno": "mobile_number",
      "emailheadofinstitution": "email_id",
      "emailofcontactperson": "email_contact",
      "designation": "designation",
      "websiteifany": "website",
      "nameoftheindiancompany": "company_name",
      "companyname": "company_name",
      "closingdate": "closing_date",
      "whethercompanyislisted": "listed_status"
    };

    uploadedFiles.forEach(doc => {
      (doc.data || []).forEach(field => {
        const val = field.value;
        if (val && val !== "Unknown" && val !== "N/A" && val !== "") {
          payload[field.key] = val;
          // Clean alphanumeric key
          const cleanK = String(field.key).toLowerCase().replace(/[^a-z0-9]/g, '');
          for (const [pattern, targetField] of Object.entries(KEY_MAP)) {
            if (cleanK.includes(pattern)) {
              payload[targetField] = val;
              break;
            }
          }
          if (cleanK.includes("paidupcapitalpy") || cleanK.includes("totalequitypy")) {
            payload["equity_amount_lakhs_py"] = val;
          } else if (cleanK.includes("paidupcapital") || cleanK.includes("totalequity")) {
            payload["equity_amount_lakhs_fy"] = val;
          }
        }
      });
    });
    return payload;
  };

  const handlePreviewConsolidated = async () => {
    if (!uploadedFiles || uploadedFiles.length === 0) return;
    setIsEvaluatingConsolidated(true);
    setShowConsolidatedModal(true);
    try {
      const payload = getConsolidatedPayload();
      if (templateName.toLowerCase().includes("fla")) {
        const res = await idpClient.testFlaEngine(payload);
        setConsolidatedState({
          payload: payload,
          cells: res?.computed_state || {},
          labels: res?.cell_labels || {}
        });
        setActiveModalSection('Section I');
      } else {
        setConsolidatedState({
          payload: payload,
          cells: { "Consolidated Return": payload },
          labels: {}
        });
        setActiveModalSection('Consolidated Return');
      }
    } catch (err) {
      console.error("Failed to evaluate consolidated payload:", err);
    } finally {
      setIsEvaluatingConsolidated(false);
    }
  };

  const handleDownloadOfficialExcel = async () => {
    if (!uploadedFiles || uploadedFiles.length === 0) return;
    setIsDownloadingExcel(true);
    try {
      const payload = getConsolidatedPayload();
      await idpClient.generateExcel(payload);
    } catch (err) {
      console.error("Failed to generate official Excel:", err);
      alert("Failed to generate official Excel file.");
    } finally {
      setIsDownloadingExcel(false);
    }
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
            onClick={handlePreviewConsolidated}
            disabled={totalCount === 0 || isEvaluatingConsolidated}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 disabled:opacity-50 disabled:cursor-not-allowed text-white shadow-md shadow-indigo-600/25 transition-all"
          >
            {isEvaluatingConsolidated ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Sparkles className="w-4 h-4 text-amber-300" />
            )}
            <span>Preview Consolidated Return</span>
          </button>

          <button
            onClick={handleDownloadOfficialExcel}
            disabled={totalCount === 0 || isDownloadingExcel}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed text-white shadow-sm shadow-emerald-600/20 transition-all"
          >
            {isDownloadingExcel ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <FileSpreadsheet className="w-4 h-4" />
            )}
            <span>Download RBI Excel (.xlsx)</span>
          </button>

          <button
            onClick={handleExportExcel}
            disabled={totalCount === 0}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-semibold bg-slate-100 dark:bg-white/5 hover:bg-slate-200 dark:hover:bg-white/10 text-slate-700 dark:text-slate-300 transition-all"
            title="Export raw batch extraction CSV dump"
          >
            <Download className="w-3.5 h-3.5" />
            <span>CSV Dump</span>
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
              <input type="file" className="hidden" accept=".pdf,.xlsx,.xls,.md,.txt" multiple={true} onChange={handleFileUpload} />
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
                          {doc.data ? `${(doc.data || []).filter(item => isFieldMapped(item.value)).length} fields mapped` : 'Pending...'}
                        </p>
                      </div>
                    </div>

                    {/* Status Badge */}
                    <div className="shrink-0 ml-2">
                      {doc.status === 'success' && (
                        <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400">
                          <CheckCircle2 className="w-3 h-3" /> Approved
                        </span>
                      )}
                      {doc.status === 'review' && (
                        <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-400">
                          <AlertTriangle className="w-3 h-3" /> Review
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
                  <div className="flex items-center justify-between mt-2">
                    <p className="text-xs text-slate-500">
                      Click any yellow table cell below to correct or verify extracted values inline.
                    </p>
                    <label className="flex items-center gap-2 cursor-pointer bg-slate-100 dark:bg-white/5 hover:bg-slate-200 dark:hover:bg-white/10 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-white/10 transition-colors text-xs font-bold text-slate-700 dark:text-slate-300">
                      <input
                        type="checkbox"
                        checked={showOnlyMappedFields}
                        onChange={(e) => setShowOnlyMappedFields(e.target.checked)}
                        className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 w-3.5 h-3.5"
                      />
                      Show Only Fields Mapped in This Document
                    </label>
                  </div>
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
                    {(() => {
                      const allFields = activeDoc.data || [];
                      // Always show only real extracted fields — filter out Unknown/null/empty
                      const displayedFields = allFields.filter(f => isFieldMapped(f.value));

                      if (displayedFields.length === 0) {
                        return (
                          <tr>
                            <td colSpan={4} className="p-12 text-center text-slate-400 font-bold">
                              {allFields.length === 0
                                ? "No fields extracted for this document."
                                : "No active fields mapped from this document (uncheck 'Show Only Fields Mapped in This Document' above to view unmapped template fields)."}
                            </td>
                          </tr>
                        );
                      }

                      return displayedFields.map((field, idx) => {
                        const fIdx = allFields.indexOf(field);
                        return (
                          <tr 
                            key={fIdx} 
                            className={`transition-colors ${
                              activeDoc.status === 'review' 
                                ? 'bg-amber-50/50 dark:bg-amber-500/5 hover:bg-amber-100/50' 
                                : 'hover:bg-slate-50 dark:hover:bg-white/5'
                            }`}
                          >
                            <td className="p-3.5 text-center text-xs font-bold text-slate-400">{idx + 1}</td>
                            <td className="p-3.5 font-bold uppercase text-xs text-slate-700 dark:text-slate-300">
                              {field.key}
                            </td>
                            <td className="p-3.5 font-bold text-slate-900 dark:text-white">
                              <input
                                type="text"
                                value={typeof field.value === 'object' ? JSON.stringify(field.value) : (field.value || '')}
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
                        );
                      });
                    })()}
                  </tbody>
                </table>
              </div>

              {(() => {
                const allFields = activeDoc.data || [];
                const mappedCount = allFields.filter(f => isFieldMapped(f.value)).length;
                const hiddenCount = allFields.length - mappedCount;
                return (
                  <div className="mt-2 flex items-center justify-between text-xs font-bold text-slate-500 px-2 shrink-0">
                    <span>Showing {showOnlyMappedFields ? mappedCount : allFields.length} of {allFields.length} template fields</span>
                    {showOnlyMappedFields && hiddenCount > 0 && (
                      <span className="text-indigo-600 dark:text-indigo-400">
                        {hiddenCount} unmapped/empty fields hidden • Uncheck toggle above to view all
                      </span>
                    )}
                  </div>
                );
              })()}
            </div>
          )}
        </div>
      </div>

      {/* 3. Consolidated RBI FLA Form Return Preview Modal */}
      {showConsolidatedModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-6 animate-in fade-in duration-200">
          <div className="bg-white dark:bg-[#111726] border border-slate-200 dark:border-white/10 rounded-2xl w-full max-w-5xl h-[85vh] flex flex-col shadow-2xl overflow-hidden">
            
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-slate-200 dark:border-white/10 flex items-center justify-between shrink-0 bg-slate-50 dark:bg-[#151C2C]">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-600 to-purple-600 flex items-center justify-center text-white shadow-md font-bold">
                  <Table className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-base font-bold text-slate-900 dark:text-white">{templateName} Consolidated Return</h2>
                    <span className="px-2 py-0.5 text-[10px] font-extrabold uppercase tracking-wider rounded-full bg-indigo-100 dark:bg-indigo-500/20 text-indigo-700 dark:text-indigo-400 border border-indigo-300 dark:border-indigo-500/30">
                      Multi-Document Packet
                    </span>
                  </div>
                  <p className="text-xs text-slate-500">
                    Combined values picked across {uploadedFiles.length} uploaded source documents • Evaluated by IDP Extraction Engine
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <button
                  onClick={async () => {
                    try {
                      const mapped_data = getConsolidatedPayload();
                      await idpClient.generatePreviewPdf({ template_name: templateName, mapped_data });
                    } catch (e) {
                      alert("Failed to generate PDF preview.");
                    }
                  }}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold bg-purple-600 hover:bg-purple-700 text-white shadow-sm transition-all"
                >
                  <FileText className="w-4 h-4" />
                  <span>Preview Stamped PDF</span>
                </button>

                {templateName.toLowerCase().includes("fla") && (
                  <button
                    onClick={handleDownloadOfficialExcel}
                    disabled={isDownloadingExcel}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white shadow-sm transition-all"
                  >
                    {isDownloadingExcel ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <FileSpreadsheet className="w-4 h-4" />
                    )}
                    <span>Download Official RBI .xlsx</span>
                  </button>
                )}

                <button
                  onClick={() => setShowConsolidatedModal(false)}
                  className="p-2 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/5 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Modal Sub-Header: Section Navigation Tabs & Hide Empty Toggle */}
            <div className="px-6 py-2.5 bg-white dark:bg-[#0E131F] border-b border-slate-200 dark:border-white/10 flex items-center justify-between shrink-0">
              <div className="flex items-center gap-2">
                {Object.keys(consolidatedState?.cells || {}).map((sec) => {
                  const count = Object.keys(consolidatedState?.cells?.[sec] || {}).length;
                  return (
                    <button
                      key={sec}
                      onClick={() => setActiveModalSection(sec)}
                      className={`px-4 py-2 rounded-lg text-xs font-bold transition-all flex items-center gap-2 ${
                        activeModalSection === sec
                          ? 'bg-indigo-600 text-white shadow-sm'
                          : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-white/5'
                      }`}
                    >
                      <span>{sec}</span>
                      {count > 0 && (
                        <span className={`px-1.5 py-0.2 rounded text-[10px] font-extrabold ${
                          activeModalSection === sec
                            ? 'bg-white/20 text-white'
                            : 'bg-slate-200 dark:bg-white/10 text-slate-700 dark:text-slate-300'
                        }`}>
                          {count}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>

              {/* Toggle Switch: Hide Empty / Zero Rows */}
              <label className="flex items-center gap-2.5 cursor-pointer select-none px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10 hover:bg-slate-200/50 dark:hover:bg-white/10 transition-colors">
                <input
                  type="checkbox"
                  checked={hideEmptyModalRows}
                  onChange={(e) => setHideEmptyModalRows(e.target.checked)}
                  className="w-4 h-4 rounded text-indigo-600 focus:ring-indigo-500 border-slate-300 dark:border-white/20"
                />
                <span className="text-xs font-bold text-slate-700 dark:text-slate-300">
                  Hide Empty & Zero Rows
                </span>
              </label>
            </div>

            {/* Modal Body: Table of Cells for Active Section */}
            <div className="flex-1 overflow-y-auto p-6 bg-slate-50/50 dark:bg-[#0B0F19]">
              <div className="border border-slate-200 dark:border-white/10 rounded-xl bg-white dark:bg-[#111726] shadow-sm overflow-hidden">
                {activeModalSection === 'Section I' ? (
                  /* SECTION I: 4-Column List View */
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-slate-50 dark:bg-[#151C2C] border-b border-slate-200 dark:border-white/10 text-xs font-bold uppercase text-slate-500">
                        <th className="p-3.5 w-28">RBI Excel Cell</th>
                        <th className="p-3.5">Field Label / Description</th>
                        <th className="p-3.5 w-48">Computed Value</th>
                        <th className="p-3.5 w-44 text-center">Source & Reconciled Flag</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200 dark:divide-white/10 text-sm">
                      {(() => {
                        const allEntries = Object.entries(consolidatedState?.cells?.[activeModalSection] || {});
                        allEntries.sort(([cA], [cB]) => {
                          const getRow = (code) => {
                            const num = parseInt(String(code).replace(/[^0-9]/g, ''), 10);
                            return isNaN(num) ? 99999 : num;
                          };
                          const rA = getRow(cA);
                          const rB = getRow(cB);
                          if (rA !== rB) return rA - rB;
                          return String(cA).localeCompare(String(cB));
                        });
                        const isActiveVal = (v) => v !== null && v !== "" && v !== "Empty / N/A" && v !== "Unknown" && Number(v) !== 0;
                        const filteredEntries = hideEmptyModalRows ? allEntries.filter(([, v]) => isActiveVal(v)) : allEntries;
                        const hiddenCount = allEntries.length - filteredEntries.length;

                        if (filteredEntries.length === 0) {
                          return (
                            <tr>
                              <td colSpan={4} className="p-12 text-center text-slate-400 font-bold">
                                {allEntries.length === 0 ? "No computed cells found for Section I." : "All Section I rows are empty/zero (uncheck 'Hide Empty & Zero Rows' above to view)."}
                              </td>
                            </tr>
                          );
                        }

                        return (
                          <>
                            {filteredEntries.map(([cellCode, val], idx) => {
                              const label = consolidatedState?.labels?.[activeModalSection]?.[cellCode] || CELL_LABELS[activeModalSection]?.[cellCode] || `Cell ${cellCode}`;
                              const isMapped = CELL_LABELS[activeModalSection]?.[cellCode] !== undefined;
                              return (
                                <tr key={idx} className="hover:bg-slate-50 dark:hover:bg-white/5 transition-colors">
                                  <td className="p-3.5 font-extrabold text-xs text-indigo-600 dark:text-indigo-400">
                                    [{cellCode}]
                                  </td>
                                  <td className="p-3.5 font-bold text-slate-700 dark:text-slate-200">
                                    {label}
                                  </td>
                                  <td className="p-3.5 font-extrabold text-slate-900 dark:text-white">
                                    {val === null || val === "" ? (
                                      <span className="text-slate-400 font-normal italic">Empty / N/A</span>
                                    ) : (
                                      <span className="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10">
                                        {String(val)}
                                      </span>
                                    )}
                                  </td>
                                  <td className="p-3.5 text-center">
                                    {isMapped ? (
                                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-indigo-100 dark:bg-indigo-500/20 text-indigo-700 dark:text-indigo-400">
                                        📄 Packet Source
                                      </span>
                                    ) : (
                                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400">
                                        🧮 RuleEngine
                                      </span>
                                    )}
                                  </td>
                                </tr>
                              );
                            })}
                            {hideEmptyModalRows && hiddenCount > 0 && (
                              <tr className="bg-slate-50/50 dark:bg-[#151C2C]/50 text-xs text-slate-500">
                                <td colSpan={4} className="p-2.5 text-center italic">
                                  Showing {filteredEntries.length} active items • {hiddenCount} empty/zero rows hidden (uncheck toggle above to view all)
                                </td>
                              </tr>
                            )}
                          </>
                        );
                      })()}
                    </tbody>
                  </table>
                ) : ['Section II', 'Section III', 'Section IV'].includes(activeModalSection) ? (
                  /* SECTION II, III, IV: Side-by-Side PY vs. FY Matrix View */
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-slate-50 dark:bg-[#151C2C] border-b border-slate-200 dark:border-white/10 text-xs font-bold uppercase text-slate-500">
                        <th className="p-3.5 w-32">RBI Excel Cells</th>
                        <th className="p-3.5">Field Label / Metric Description</th>
                        <th className="p-3.5 w-44 text-center">Previous Year (PY)</th>
                        <th className="p-3.5 w-44 text-center">Financial Year (FY)</th>
                        <th className="p-3.5 w-40 text-center">Source Flag</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200 dark:divide-white/10 text-sm">
                      {(() => {
                        const cellsObj = consolidatedState?.cells?.[activeModalSection] || {};
                        const labelsObj = consolidatedState?.labels?.[activeModalSection] || {};
                        const paired = [];
                        const seenCells = new Set();
                        const allCodes = Object.keys(cellsObj);

                        const getCleanPairLabel = (code, rawLabel) => {
                          let l = String(rawLabel || '');
                          if (l.includes('Shares')) {
                            l = l.replace(/\bPY\s*Shares\b/gi, '(Shares Count)').replace(/\bFY\s*Shares\b/gi, '(Shares Count)');
                          }
                          l = l.replace(/\bPY\b/g, '').replace(/\bFY\b/g, '').replace(/\(\s*\)/g, '').replace(/\s+/g, ' ').trim();
                          return l || code;
                        };

                        const getFyPartner = (pyCode) => {
                          if (!pyCode || pyCode.length < 2) return null;
                          const col = pyCode.charAt(0);
                          const rNum = pyCode.slice(1);
                          if (isNaN(Number(rNum))) return null;
                          const r = Number(rNum);

                          if (activeModalSection === 'Section II') {
                            if (col === 'D') return 'E' + rNum;
                            if (col === 'F') return 'G' + rNum;
                          } else if (activeModalSection === 'Section III') {
                            if (pyCode === 'C41') return 'D41';
                            if (col === 'D' && r >= 44) return 'E' + rNum;
                          } else if (activeModalSection === 'Section IV') {
                            if (pyCode === 'E19') return 'F19';
                            if (col === 'D' && r >= 26) return 'E' + rNum;
                          }
                          return null;
                        };

                        // 1. Pair up verified PY/FY items
                        allCodes.forEach((code) => {
                          const fyCode = getFyPartner(code);
                          if (fyCode && (cellsObj[fyCode] !== undefined || cellsObj[code] !== undefined)) {
                            if (!seenCells.has(code) && !seenCells.has(fyCode)) {
                              seenCells.add(code);
                              seenCells.add(fyCode);
                              const pyVal = cellsObj[code];
                              const fyVal = cellsObj[fyCode];
                              const rawLabel = labelsObj[code] || CELL_LABELS[activeModalSection]?.[code] || `Row ${code.slice(1)}`;
                              const cleanLabel = getCleanPairLabel(code, rawLabel);
                              const isMapped = CELL_LABELS[activeModalSection]?.[code] !== undefined || CELL_LABELS[activeModalSection]?.[fyCode] !== undefined;

                              paired.push({
                                pyCell: code,
                                fyCell: fyCode,
                                label: cleanLabel,
                                pyVal: pyVal,
                                fyVal: fyVal,
                                isMapped: isMapped
                              });
                            }
                          }
                        });

                        // 2. Standalone cells (not a PY/FY pair)
                        allCodes.forEach((code) => {
                          if (!seenCells.has(code)) {
                            seenCells.add(code);
                            const val = cellsObj[code];
                            const rawLabel = labelsObj[code] || CELL_LABELS[activeModalSection]?.[code] || `Row ${code.slice(1)}`;
                            const isMapped = CELL_LABELS[activeModalSection]?.[code] !== undefined;

                            paired.push({
                              pyCell: code,
                              fyCell: 'N/A',
                              label: rawLabel,
                              pyVal: val,
                              fyVal: null,
                              isMapped: isMapped
                            });
                          }
                        });

                        // Sort paired by Excel row number (ascending), then column letter
                        paired.sort((a, b) => {
                          const getRow = (code) => {
                            if (!code || code === '-') return 99999;
                            const num = parseInt(String(code).replace(/[^0-9]/g, ''), 10);
                            return isNaN(num) ? 99999 : num;
                          };
                          const rA = getRow(a.pyCell);
                          const rB = getRow(b.pyCell);
                          if (rA !== rB) return rA - rB;
                          return String(a.pyCell).localeCompare(String(b.pyCell));
                        });

                        const isActiveVal = (v) => v !== null && v !== "" && v !== "Empty / N/A" && v !== "Unknown" && Number(v) !== 0;
                        const filteredPaired = hideEmptyModalRows
                          ? paired.filter((item) => isActiveVal(item.pyVal) || isActiveVal(item.fyVal))
                          : paired;
                        const hiddenCount = paired.length - filteredPaired.length;

                        if (filteredPaired.length === 0) {
                          return (
                            <tr>
                              <td colSpan={5} className="p-12 text-center text-slate-400 font-bold">
                                {paired.length === 0
                                  ? `No computed metrics found for ${activeModalSection}.`
                                  : `All ${activeModalSection} metrics are empty/zero (uncheck 'Hide Empty & Zero Rows' above to view).`}
                              </td>
                            </tr>
                          );
                        }

                        return (
                          <>
                            {filteredPaired.map((item, idx) => {
                              const formatVal = (v) => {
                                if (v === null || v === "" || v === undefined) {
                                  return <span className="text-slate-400 font-normal italic">Empty / N/A</span>;
                                }
                                return (
                                  <span className="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10 font-extrabold text-slate-900 dark:text-white">
                                    {String(v)}
                                  </span>
                                );
                              };

                              return (
                                <tr key={idx} className="hover:bg-slate-50 dark:hover:bg-white/5 transition-colors">
                                  <td className="p-3.5 font-extrabold text-xs text-indigo-600 dark:text-indigo-400">
                                    [{item.pyCell} / {item.fyCell}]
                                  </td>
                                  <td className="p-3.5 font-bold text-slate-700 dark:text-slate-200">
                                    {item.label}
                                  </td>
                                  <td className="p-3.5 text-center">
                                    {formatVal(item.pyVal)}
                                  </td>
                                  <td className="p-3.5 text-center">
                                    {formatVal(item.fyVal)}
                                  </td>
                                  <td className="p-3.5 text-center">
                                    {item.isMapped ? (
                                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-indigo-100 dark:bg-indigo-500/20 text-indigo-700 dark:text-indigo-400">
                                        📄 Packet Source
                                      </span>
                                    ) : (
                                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400">
                                        🧮 RuleEngine
                                      </span>
                                    )}
                                  </td>
                                </tr>
                              );
                            })}
                            {hideEmptyModalRows && hiddenCount > 0 && (
                              <tr className="bg-slate-50/50 dark:bg-[#151C2C]/50 text-xs text-slate-500">
                                <td colSpan={5} className="p-2.5 text-center italic">
                                  Showing {filteredPaired.length} active PY/FY pairs • {hiddenCount} empty/zero rows hidden (uncheck toggle above to view all {paired.length} items)
                                </td>
                              </tr>
                            )}
                          </>
                        );
                      })()}
                    </tbody>
                  </table>
                ) : (
                  /* GENERIC FORM: Simple Consolidated Key-Value List */
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-slate-50 dark:bg-[#151C2C] border-b border-slate-200 dark:border-white/10 text-xs font-bold uppercase text-slate-500">
                        <th className="p-3.5 w-16">#</th>
                        <th className="p-3.5">Consolidated Form Field</th>
                        <th className="p-3.5">Consolidated Extracted Value</th>
                        <th className="p-3.5 w-40 text-center">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200 dark:divide-white/10 text-sm">
                      {(() => {
                        const payload = consolidatedState?.cells?.[activeModalSection] || {};
                        const entries = Object.entries(payload);
                        if (entries.length === 0) {
                          return (
                            <tr>
                              <td colSpan={4} className="p-12 text-center text-slate-400 font-bold">
                                No consolidated values extracted for this form.
                              </td>
                            </tr>
                          );
                        }
                        const cleanFieldKey = (rawKey) => {
                          if (!rawKey) return "";
                          let s = String(rawKey).replace(/^field_/, "");
                          // Add space between numbers and letters
                          s = s.replace(/([0-9]+)([a-zA-Z]+)/g, "$1 $2").replace(/([a-zA-Z]+)([0-9]+)/g, "$1 $2");
                          return s.replace(/_/g, " ").toUpperCase();
                        };
                        return entries.map(([key, val], idx) => (
                          <tr key={idx} className="hover:bg-slate-50 dark:hover:bg-white/5 transition-colors">
                            <td className="p-3.5 text-slate-400 font-bold text-xs">{idx + 1}</td>
                            <td className="p-3.5 font-bold uppercase text-slate-700 dark:text-slate-300">
                              {cleanFieldKey(key)}
                            </td>
                            <td className="p-3.5 font-extrabold text-slate-900 dark:text-white">
                              <div className="py-1 px-3 rounded-lg bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10 font-bold text-slate-900 dark:text-white max-w-xl whitespace-pre-wrap break-words inline-block text-sm leading-relaxed">
                                {String(val)}
                              </div>
                            </td>
                            <td className="p-3.5 text-center">
                              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-indigo-100 dark:bg-indigo-500/20 text-indigo-700 dark:text-indigo-400">
                                📄 Consolidated
                              </span>
                            </td>
                          </tr>
                        ));
                      })()}
                    </tbody>
                  </table>
                )}
              </div>
            </div>

          </div>
        </div>
      )}
    </div>
  );
}
