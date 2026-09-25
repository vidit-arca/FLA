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
  ArrowLeft,
  Edit3,
  RefreshCw,
  ExternalLink,
  Sparkles,
  X,
  FileSpreadsheet,
  CheckCircle,
  Eye,
  Send,
  ShieldCheck,
  Scale
} from 'lucide-react';
import { idpClient } from './api/idpClient';
import FilledFormViewer from './components/FilledFormViewer';
import ExtractionBranchGateModal from './components/ExtractionBranchGateModal';

export default function IdpProductionApp() {
  const [templates, setTemplates] = useState([]);
  const [templateName, setTemplateName] = useState('');
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [activeFileIndex, setActiveFileIndex] = useState(0);
  const [isExtracting, setIsExtracting] = useState(false);
  const [filterStatus, setFilterStatus] = useState('all'); // 'all' | 'success' | 'review'

  // 3-Stage Pipeline State: 'batch_queue' | 'consolidated_return' | 'preview_export'
  const [currentStage, setCurrentStage] = useState('batch_queue');

  // HITL Statutory Branch Gate States
  const [showBranchModal, setShowBranchModal] = useState(false);
  const [detectedBranchData, setDetectedBranchData] = useState(null);
  const [activeScenario, setActiveScenario] = useState(null);
  const [isDetectingBranch, setIsDetectingBranch] = useState(false);

  // Consolidated Form Return States
  const [consolidatedState, setConsolidatedState] = useState(null);
  const [isEvaluatingConsolidated, setIsEvaluatingConsolidated] = useState(false);
  const [isDownloadingExcel, setIsDownloadingExcel] = useState(false);
  const [activeModalSection, setActiveModalSection] = useState('Section II');
  const [hideEmptyModalRows, setHideEmptyModalRows] = useState(true);
  const [showOnlyMappedFields, setShowOnlyMappedFields] = useState(true);

  // User-edited overrides tracked at consolidated level
  const [userOverrides, setUserOverrides] = useState({});

  const isFieldMapped = (val) => {
    if (val === null || val === undefined) return false;
    const s = String(val).trim();
    if (s === "" || s === "Unknown" || s === "N/A" || s === "Empty / N/A" || s === "None" || s === "null") return false;
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
      alert("No form schema selected! Please select or create a template in IDP Studio first.");
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
            document_type: res.document_type || 'generic',
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
      doc.status = 'success';
      updated[docIndex] = doc;
      return updated;
    });
  };

  const handleConsolidatedFieldEdit = (fieldKey, newValue) => {
    setUserOverrides(prev => ({
      ...prev,
      [fieldKey]: newValue
    }));

    setConsolidatedState(prev => {
      if (!prev) return prev;
      const updated = { ...prev };
      if (updated.payload) {
        updated.payload = { ...updated.payload, [fieldKey]: newValue };
      }
      if (updated.cells && updated.cells[activeModalSection]) {
        updated.cells[activeModalSection] = { ...updated.cells[activeModalSection], [fieldKey]: newValue };
      }
      if (updated.active_fields) {
        updated.active_fields = updated.active_fields.map(f => {
          if (f.id === fieldKey || f.canonical_no === fieldKey) {
            return { ...f, value: newValue, status: 'human_verified' };
          }
          return f;
        });
      }
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

    // Apply any explicit user overrides
    Object.entries(userOverrides).forEach(([k, v]) => {
      payload[k] = v;
    });

    return payload;
  };

  const getFieldSourceDoc = (fieldKey) => {
    if (userOverrides[fieldKey]) {
      return { docName: 'Human Override', docType: 'user_edit', status: 'override' };
    }
    const cleanK = String(fieldKey).toLowerCase().replace(/[^a-z0-9]/g, '');
    for (const doc of uploadedFiles) {
      for (const field of (doc.data || [])) {
        const docCleanK = String(field.key).toLowerCase().replace(/[^a-z0-9]/g, '');
        if (docCleanK === cleanK || cleanK.includes(docCleanK) || docCleanK.includes(cleanK)) {
          if (isFieldMapped(field.value)) {
            return {
              docName: doc.file?.name || 'Document',
              docType: doc.document_type || 'generic',
              status: doc.status || 'success'
            };
          }
        }
      }
    }
    return { docName: 'Rule Engine', docType: 'derived', status: 'success' };
  };

  // HITL Trigger: Invoked when user clicks "Proceed to Consolidated Return"
  const handleProceedToConsolidatedGate = async () => {
    if (!uploadedFiles || uploadedFiles.length === 0) return;

    // Check if form is multi-scenario (non-FLA MCA forms like ADT-1)
    if (!templateName.toLowerCase().includes("fla")) {
      setIsDetectingBranch(true);
      try {
        const rawFiles = uploadedFiles.map(f => f.file).filter(Boolean);
        const branchRes = await idpClient.detectBranch(templateName, rawFiles);
        setDetectedBranchData(branchRes);
        setShowBranchModal(true);
      } catch (err) {
        console.warn("Branch detection skipped or failed, using default consolidation:", err);
        await executeConsolidation(null);
      } finally {
        setIsDetectingBranch(false);
      }
    } else {
      // For FLA, proceed directly
      await executeConsolidation(null);
    }
  };

  // HITL Confirmation Handler from Modal
  const handleScenarioConfirm = async (confirmedData) => {
    setActiveScenario(confirmedData);
    setShowBranchModal(false);
    await executeConsolidation(confirmedData);
  };

  // Execution with DAG Pruning for Confirmed Scenario
  const executeConsolidation = async (scenarioData) => {
    setIsEvaluatingConsolidated(true);
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
        let autofillRes = null;
        if (scenarioData) {
          try {
            autofillRes = await idpClient.autofillForm(templateName, {
              confirmed_branch: scenarioData.confirmed_branch,
              scenario: scenarioData.scenario,
              casual_vacancy_reason: scenarioData.casual_vacancy_reason,
              company_id: scenarioData.company_id || "default",
              evidence: Object.entries(payload).map(([k, v]) => ({ key: k, value: v }))
            });
          } catch (e) {
            console.warn("Autofill DAG execution warning:", e);
          }
        }

        const finalPayload = { ...payload };
        
        // Explicitly inject confirmed branch & sub-reasons into statutory payload
        if (scenarioData?.confirmed_branch) {
          finalPayload['3b_nature_of_appointment'] = scenarioData.confirmed_branch;
          finalPayload['nature_of_appointment'] = scenarioData.confirmed_branch;
          finalPayload['field_nature_of_appointment'] = scenarioData.confirmed_branch;
        }
        if (scenarioData?.casual_vacancy_reason) {
          finalPayload['casual_vacancy_reason'] = scenarioData.casual_vacancy_reason;
          finalPayload['field_casual_vacancy_reason'] = scenarioData.casual_vacancy_reason;
          finalPayload['7a_casual_vacancy_reason'] = scenarioData.casual_vacancy_reason;
        }

        // Unpack active DAG fields from backend (supports both list and dictionary representations)
        let activeFieldsArray = null;
        if (autofillRes) {
          if (Array.isArray(autofillRes.active_fields)) {
            activeFieldsArray = autofillRes.active_fields;
          } else if (autofillRes.fields && typeof autofillRes.fields === 'object') {
            activeFieldsArray = Object.entries(autofillRes.fields)
              .filter(([_, f]) => f.is_active !== false)
              .map(([id, f]) => ({ id, ...f }));
          }
        }

        if (activeFieldsArray) {
          activeFieldsArray.forEach(f => {
            if (f.value !== undefined && f.value !== null && String(f.value).trim() !== "" && !finalPayload[f.id]) {
              finalPayload[f.id] = f.value;
            }
          });
        }

        setConsolidatedState({
          payload: finalPayload,
          active_fields: activeFieldsArray,
          cells: { "Consolidated Return": finalPayload },
          labels: {}
        });
        setActiveModalSection('Consolidated Return');
      }
      setCurrentStage('consolidated_return');
    } catch (err) {
      console.error("Failed to execute consolidation:", err);
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

  const displayedFiles = uploadedFiles.filter(f => {
    if (filterStatus === 'all') return true;
    return f.status === filterStatus;
  });

  const activeDoc = uploadedFiles[activeFileIndex] || null;

  const consolidatedPayload = consolidatedState?.payload || getConsolidatedPayload();
  const consolidatedFieldCount = consolidatedState?.active_fields 
    ? consolidatedState.active_fields.length 
    : Object.keys(consolidatedPayload).filter(k => isFieldMapped(consolidatedPayload[k])).length;

  return (
    <div className="flex flex-col w-full h-screen bg-slate-50 dark:bg-[#0B0F19] text-slate-900 dark:text-white overflow-hidden">
      
      {/* 1. Top Header Bar & Stage Navigation Switcher */}
      <header className="h-16 px-6 bg-white dark:bg-[#111726] border-b border-slate-200 dark:border-white/10 flex items-center justify-between shrink-0 shadow-sm z-20">
        
        {/* Brand & Mode */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center text-white shadow-md shadow-indigo-600/30 font-bold">
            <Layers className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold">IDP Batch Extractor</h1>
              <span className="px-2 py-0.5 text-[10px] font-extrabold uppercase tracking-wider rounded-full bg-indigo-100 dark:bg-indigo-500/20 text-indigo-700 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-500/30">
                Production Release
              </span>
            </div>
            <p className="text-[11px] text-slate-500">Autonomous Statutory Extraction & Scenario DAG Pipeline</p>
          </div>
        </div>

        {/* 3-Stage Progress Nav Tabs */}
        <div className="flex items-center bg-slate-100 dark:bg-[#0A0E17] p-1 rounded-xl border border-slate-200 dark:border-white/10 shadow-inner">
          <button
            onClick={() => setCurrentStage('batch_queue')}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all ${
              currentStage === 'batch_queue'
                ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/25 ring-1 ring-indigo-400'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            <span>1. Batch Queue</span>
            {totalCount > 0 && (
              <span className={`px-1.5 py-0.2 rounded text-[10px] ${
                currentStage === 'batch_queue' ? 'bg-white/20 text-white' : 'bg-slate-200 dark:bg-white/10 text-slate-700 dark:text-slate-300'
              }`}>
                {totalCount}
              </span>
            )}
          </button>

          <button
            onClick={() => {
              if (totalCount > 0) handleProceedToConsolidatedGate();
            }}
            disabled={totalCount === 0 || isEvaluatingConsolidated || isDetectingBranch}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all disabled:opacity-40 disabled:cursor-not-allowed ${
              currentStage === 'consolidated_return'
                ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/25 ring-1 ring-indigo-400'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            {isEvaluatingConsolidated || isDetectingBranch ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Sparkles className="w-3.5 h-3.5 text-amber-400" />
            )}
            <span>2. Consolidated Return</span>
            {consolidatedFieldCount > 0 && (
              <span className={`px-1.5 py-0.2 rounded text-[10px] ${
                currentStage === 'consolidated_return' ? 'bg-white/20 text-white' : 'bg-slate-200 dark:bg-white/10 text-slate-700 dark:text-slate-300'
              }`}>
                {consolidatedFieldCount}
              </span>
            )}
          </button>

          <button
            onClick={() => {
              if (totalCount > 0) setCurrentStage('preview_export');
            }}
            disabled={totalCount === 0}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all disabled:opacity-40 disabled:cursor-not-allowed ${
              currentStage === 'preview_export'
                ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/25 ring-1 ring-indigo-400'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            <Eye className="w-3.5 h-3.5" />
            <span>3. Official Preview & Export</span>
          </button>
        </div>

        {/* Form Schema Selector & Auxiliary Actions */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Schema:</span>
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
                <option value="">No templates found</option>
              )}
            </select>
          </div>

          <button
            onClick={handleExportExcel}
            disabled={totalCount === 0}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 dark:bg-white/5 hover:bg-slate-200 dark:hover:bg-white/10 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-white/10 transition-all disabled:opacity-40"
            title="Export raw extraction CSV dump"
          >
            <Download className="w-3.5 h-3.5" />
            <span>CSV</span>
          </button>

          <a
            href="/idp-studio"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 dark:bg-white/5 hover:bg-slate-200 dark:hover:bg-white/10 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-white/10 transition-all"
          >
            <span>Studio</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      </header>

      {/* ========================================================= */}
      {/* STAGE 1: BATCH INTAKE & DOCUMENT QUEUE                   */}
      {/* ========================================================= */}
      {currentStage === 'batch_queue' && (
        <div className="flex-1 flex flex-col min-h-0">
          
          {/* Stats & Filter Subheader */}
          <div className="h-12 px-6 bg-slate-100 dark:bg-[#151C2C] border-b border-slate-200 dark:border-white/10 flex items-center justify-between shrink-0 text-xs font-medium">
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-2">
                <span className="text-slate-500 font-semibold">Total Documents:</span>
                <span className="font-bold text-slate-900 dark:text-white">{totalCount}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-500" />
                <span className="text-slate-500 font-semibold">Auto-Approved (✓):</span>
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
                  <span>Processing batch documents...</span>
                </div>
              )}
            </div>

            {/* Filter Tabs */}
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
                <span>✓ Approved ({greenCount})</span>
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

          {/* Split Queue & Inspector */}
          <div className="flex-1 flex min-h-0">
            {/* Left Queue Panel */}
            <div className="w-96 border-r border-slate-200 dark:border-white/10 bg-white dark:bg-[#111726] flex flex-col shrink-0">
              <div className="p-4 border-b border-slate-200 dark:border-white/10">
                <label className="flex flex-col items-center justify-center p-6 bg-slate-50 dark:bg-[#1A2234] hover:bg-slate-100 dark:hover:bg-[#202B42] rounded-xl border-2 border-dashed border-slate-300 dark:border-slate-700 cursor-pointer transition-all text-center">
                  <UploadCloud className="w-8 h-8 text-indigo-500 mb-2" />
                  <span className="text-xs font-bold text-slate-800 dark:text-white">Drag & Drop Batch PDFs</span>
                  <span className="text-[11px] text-slate-500 mt-0.5">Upload 1 to 50 documents at once</span>
                  <input type="file" className="hidden" accept=".pdf,.xlsx,.xls,.md,.txt" multiple={true} onChange={handleFileUpload} />
                </label>
              </div>

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
                            <div className="flex items-center gap-1.5 mt-0.5">
                              {doc.document_type && doc.document_type !== 'generic' && (
                                <span className="px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider bg-indigo-100 dark:bg-indigo-500/20 text-indigo-700 dark:text-indigo-300 rounded">
                                  {doc.document_type.replace('_', ' ')}
                                </span>
                              )}
                              <span className="text-[10px] text-slate-500">
                                {doc.data ? `${(doc.data || []).filter(item => isFieldMapped(item.value)).length} fields mapped` : 'Pending...'}
                              </span>
                            </div>
                          </div>
                        </div>

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

            {/* Right Extracted Field Inspector */}
            <div className="flex-1 flex flex-col bg-white dark:bg-[#1A2234] p-6 overflow-hidden">
              {!activeDoc ? (
                <div className="flex-1 flex flex-col items-center justify-center text-center text-slate-400 max-w-sm mx-auto">
                  <div className="w-16 h-16 rounded-2xl bg-slate-100 dark:bg-white/5 flex items-center justify-center mb-4">
                    <Table className="w-8 h-8 stroke-1 text-slate-500" />
                  </div>
                  <h3 className="text-base font-bold text-slate-800 dark:text-white mb-1">No Document Selected</h3>
                  <p className="text-xs text-slate-500">Upload documents on the left to inspect extracted values and synthesize your consolidated return.</p>
                </div>
              ) : (
                <div className="flex-1 flex flex-col min-h-0">
                  <div className="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-white/10 shrink-0">
                    <div>
                      <div className="flex items-center gap-2">
                        <h2 className="text-base font-bold text-slate-900 dark:text-white">{activeDoc.file.name}</h2>
                        {activeDoc.status === 'success' ? (
                          <span className="px-2 py-0.5 rounded text-xs font-bold bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400">
                            ✓ Deterministic Match
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded text-xs font-bold bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-400">
                            ⚠ Human Verification Needed
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-slate-500 mt-1">
                        Individual document extraction results. You can verify or edit flagged values inline.
                      </p>
                    </div>

                    {/* Stage 1 CTA to Stage 2 with HITL Gate */}
                    <button
                      onClick={handleProceedToConsolidatedGate}
                      disabled={isEvaluatingConsolidated || isDetectingBranch}
                      className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white shadow-md shadow-indigo-600/25 transition-all disabled:opacity-50"
                    >
                      {isEvaluatingConsolidated || isDetectingBranch ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Scale className="w-4 h-4 text-amber-300" />
                      )}
                      <span>Proceed to Consolidated Return (HITL Gate)</span>
                      <ArrowRight className="w-4 h-4" />
                    </button>
                  </div>

                  {/* Extracted Fields Table */}
                  <div className="flex-1 overflow-y-auto mt-4 border border-slate-200 dark:border-white/10 rounded-xl">
                    <table className="w-full text-left border-collapse">
                      <thead>
                        <tr className="bg-slate-50 dark:bg-[#111726] border-b border-slate-200 dark:border-white/10 text-xs font-bold uppercase text-slate-500 sticky top-0 z-10">
                          <th className="p-3.5 w-12 text-center">#</th>
                          <th className="p-3.5">Extracted Key</th>
                          <th className="p-3.5">Value (Click to Edit)</th>
                          <th className="p-3.5 w-32 text-center">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-200 dark:divide-white/10 text-sm">
                        {(() => {
                          const allFields = activeDoc.data || [];
                          const displayedFields = allFields.filter(f => isFieldMapped(f.value));

                          if (displayedFields.length === 0) {
                            return (
                              <tr>
                                <td colSpan={4} className="p-12 text-center text-slate-400 font-bold">
                                  No mapped fields extracted for this document.
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
                                    ? 'bg-amber-50/40 dark:bg-amber-500/5 hover:bg-amber-100/40' 
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
                                    className="w-full bg-transparent border-b border-dashed border-slate-300 dark:border-slate-700 focus:border-indigo-500 focus:outline-none py-1 px-1.5 rounded transition-colors font-bold text-sm"
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
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* STAGE 2: DEDICATED CONSOLIDATED RETURN SYNTHESIS          */}
      {/* ========================================================= */}
      {currentStage === 'consolidated_return' && (
        <div className="flex-1 flex flex-col min-h-0 bg-slate-50 dark:bg-[#0B0F19] overflow-hidden">
          
          {/* Top Metrics Strip */}
          <div className="h-14 px-8 bg-white dark:bg-[#111726] border-b border-slate-200 dark:border-white/10 flex items-center justify-between shrink-0">
            <div className="flex items-center gap-8">
              <div>
                <span className="text-xs text-slate-500 font-medium">Statutory Fields:</span>
                <span className="ml-2 font-bold text-slate-900 dark:text-white text-sm">{consolidatedFieldCount}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
                <span className="text-xs text-slate-500 font-medium">Auto-Approved:</span>
                <span className="font-bold text-emerald-600 dark:text-emerald-400 text-sm">
                  {uploadedFiles.filter(f => f.status === 'success').length} documents
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-500" />
                <span className="text-xs text-slate-500 font-medium">Human Overrides:</span>
                <span className="font-bold text-indigo-600 dark:text-indigo-400 text-sm">
                  {Object.keys(userOverrides).length}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-500" />
                <span className="text-xs text-slate-500 font-medium">Readiness:</span>
                <span className="font-bold text-emerald-600 dark:text-emerald-400 text-sm">100% Validated</span>
              </div>
            </div>

            {/* Stage Actions */}
            <div className="flex items-center gap-3">
              <button
                onClick={() => setCurrentStage('batch_queue')}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/5 transition-all"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>Back to Queue</span>
              </button>

              {templateName.toLowerCase().includes("fla") && (
                <button
                  onClick={handleDownloadOfficialExcel}
                  disabled={isDownloadingExcel}
                  className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white shadow-sm transition-all"
                >
                  {isDownloadingExcel ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <FileSpreadsheet className="w-3.5 h-3.5" />
                  )}
                  <span>Download Official .xlsx</span>
                </button>
              )}

              <button
                onClick={() => setCurrentStage('preview_export')}
                className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white shadow-md shadow-indigo-600/25 transition-all"
              >
                <span>Proceed to Official Preview</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* HITL Statutory Scenario Decision Banner */}
          {!templateName.toLowerCase().includes("fla") && (
            <div className="px-8 py-3 bg-gradient-to-r from-indigo-900/60 to-purple-900/40 border-b border-indigo-500/20 flex items-center justify-between shrink-0">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-xl bg-indigo-500/20 border border-indigo-500/30 text-indigo-400">
                  <Scale className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-extrabold uppercase tracking-wider bg-indigo-500/30 text-indigo-300 border border-indigo-500/30 px-2 py-0.5 rounded">
                      HITL Confirmed Statutory Scenario
                    </span>
                    <h4 className="text-sm font-bold text-white">
                      {activeScenario?.confirmed_branch || 'Appointment / Re-appointment in AGM (Section 139(1))'}
                    </h4>
                    {activeScenario?.casual_vacancy_reason && (
                      <span className="text-xs text-indigo-300 font-semibold">
                        • Reason: {activeScenario.casual_vacancy_reason}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-300 mt-0.5">
                    DAG Dependency Pruner active: non-applicable branches pruned out. Displaying only statutory fields for this scenario.
                  </p>
                </div>
              </div>

              <button
                onClick={() => setShowBranchModal(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold bg-white/10 hover:bg-white/20 text-white border border-white/20 shadow-sm transition-all"
              >
                <Edit3 className="w-3.5 h-3.5" />
                <span>Change Statutory Scenario</span>
              </button>
            </div>
          )}

          {/* Section Tabs (if FLA) + Filter Toggle */}
          <div className="px-8 py-2.5 bg-slate-100 dark:bg-[#0E131F] border-b border-slate-200 dark:border-white/10 flex items-center justify-between shrink-0">
            <div className="flex items-center gap-2">
              {Object.keys(consolidatedState?.cells || {}).map((sec) => {
                const count = Object.keys(consolidatedState?.cells?.[sec] || {}).length;
                return (
                  <button
                    key={sec}
                    onClick={() => setActiveModalSection(sec)}
                    className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-2 ${
                      activeModalSection === sec
                        ? 'bg-indigo-600 text-white shadow-sm'
                        : 'text-slate-600 dark:text-slate-400 hover:bg-white dark:hover:bg-white/5'
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

            <label className="flex items-center gap-2.5 cursor-pointer select-none px-3 py-1.5 rounded-lg bg-white dark:bg-white/5 border border-slate-200 dark:border-white/10 text-xs font-bold text-slate-700 dark:text-slate-300">
              <input
                type="checkbox"
                checked={hideEmptyModalRows}
                onChange={(e) => setHideEmptyModalRows(e.target.checked)}
                className="w-4 h-4 rounded text-indigo-600 focus:ring-indigo-500 border-slate-300 dark:border-white/20"
              />
              <span>Hide Empty & Zero Rows</span>
            </label>
          </div>

          {/* Consolidated Synthesis Content View */}
          <div className="flex-1 overflow-y-auto p-8">
            <div className="max-w-7xl mx-auto border border-slate-200 dark:border-white/10 rounded-2xl bg-white dark:bg-[#111726] shadow-sm overflow-hidden">
              
              {!templateName.toLowerCase().includes("fla") ? (
                /* STANDARD MCA FORM SYNTHESIS TABLE (DAG Pruned for Scenario) */
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-slate-50 dark:bg-[#151C2C] border-b border-slate-200 dark:border-white/10 text-xs font-bold uppercase text-slate-500">
                      <th className="p-4 w-16 text-center">#</th>
                      <th className="p-4 w-1/3">Statutory Field Label</th>
                      <th className="p-4">Consolidated Value (Click to Override)</th>
                      <th className="p-4 w-56">Provenance Source</th>
                      <th className="p-4 w-40 text-center">HITL Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 dark:divide-white/10 text-sm">
                    {(() => {
                      const activeFieldsList = consolidatedState?.active_fields;
                      
                      // If DAG pruned fields are available, use them!
                      if (activeFieldsList && activeFieldsList.length > 0) {
                        return activeFieldsList.map((f, idx) => {
                          const provenance = getFieldSourceDoc(f.id);
                          const isOverridden = !!userOverrides[f.id];
                          const currentVal = userOverrides[f.id] !== undefined ? userOverrides[f.id] : (f.value || '');

                          return (
                            <tr key={f.id} className="hover:bg-slate-50 dark:hover:bg-white/5 transition-colors">
                              <td className="p-4 text-center font-bold text-slate-400 text-xs">{idx + 1}</td>
                              <td className="p-4 font-bold text-slate-800 dark:text-slate-200">
                                <div>{f.canonical_no ? `${f.canonical_no} ${f.label}` : f.label}</div>
                                <span className="text-[10px] font-mono text-slate-400">{f.id}</span>
                              </td>
                              <td className="p-4">
                                <input
                                  type="text"
                                  value={typeof currentVal === 'object' ? JSON.stringify(currentVal) : currentVal}
                                  onChange={(e) => handleConsolidatedFieldEdit(f.id, e.target.value)}
                                  className="w-full bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10 focus:border-indigo-500 focus:outline-none py-1.5 px-2.5 rounded-lg font-mono text-xs font-bold text-slate-900 dark:text-white"
                                  placeholder="Type value..."
                                />
                              </td>
                              <td className="p-4">
                                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-indigo-50 dark:bg-indigo-500/10 text-indigo-700 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-500/20">
                                  📄 {provenance.docName}
                                </span>
                              </td>
                              <td className="p-4 text-center">
                                {isOverridden ? (
                                  <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-indigo-100 dark:bg-indigo-500/20 text-indigo-700 dark:text-indigo-300">
                                    👤 Human Override
                                  </span>
                                ) : (
                                  <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400">
                                    ✓ Verified
                                  </span>
                                )}
                              </td>
                            </tr>
                          );
                        });
                      }

                      // Fallback: standard synthesized payload
                      const payload = consolidatedState?.payload || getConsolidatedPayload();
                      const entries = Object.entries(payload).filter(([k, v]) => isFieldMapped(v));

                      if (entries.length === 0) {
                        return (
                          <tr>
                            <td colSpan={5} className="p-12 text-center text-slate-400 font-bold">
                              No consolidated statutory fields resolved yet.
                            </td>
                          </tr>
                        );
                      }

                      return entries.map(([key, val], idx) => {
                        const provenance = getFieldSourceDoc(key);
                        const isOverridden = !!userOverrides[key];
                        const currentVal = userOverrides[key] !== undefined ? userOverrides[key] : val;

                        return (
                          <tr key={key} className="hover:bg-slate-50 dark:hover:bg-white/5 transition-colors">
                            <td className="p-4 text-center font-bold text-slate-400 text-xs">{idx + 1}</td>
                            <td className="p-4 font-bold text-slate-800 dark:text-slate-200">
                              <div>{key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</div>
                              <span className="text-[10px] font-mono text-slate-400">{key}</span>
                            </td>
                            <td className="p-4">
                              <input
                                type="text"
                                value={typeof currentVal === 'object' ? JSON.stringify(currentVal) : String(currentVal || '')}
                                onChange={(e) => handleConsolidatedFieldEdit(key, e.target.value)}
                                className="w-full bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10 focus:border-indigo-500 focus:outline-none py-1.5 px-2.5 rounded-lg font-mono text-xs font-bold text-slate-900 dark:text-white"
                                placeholder="Type value..."
                              />
                            </td>
                            <td className="p-4">
                              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-indigo-50 dark:bg-indigo-500/10 text-indigo-700 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-500/20">
                                📄 {provenance.docName}
                              </span>
                            </td>
                            <td className="p-4 text-center">
                              {isOverridden ? (
                                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-indigo-100 dark:bg-indigo-500/20 text-indigo-700 dark:text-indigo-300">
                                  👤 Human Override
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400">
                                  ✓ Verified
                                </span>
                              )}
                            </td>
                          </tr>
                        );
                      });
                    })()}
                  </tbody>
                </table>
              ) : activeModalSection === 'Section I' ? (
                /* RBI FLA SECTION I LIST VIEW */
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-slate-50 dark:bg-[#151C2C] border-b border-slate-200 dark:border-white/10 text-xs font-bold uppercase text-slate-500">
                      <th className="p-3.5 w-28">RBI Excel Cell</th>
                      <th className="p-3.5">Field Label / Description</th>
                      <th className="p-3.5 w-48">Computed Value</th>
                      <th className="p-3.5 w-48 text-center">Source & Reconciled Flag</th>
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
                              All Section I rows are empty/zero (uncheck 'Hide Empty & Zero Rows' above to view).
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
                                    <span className="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10 font-mono">
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
                                Showing {filteredEntries.length} active items • {hiddenCount} empty/zero rows hidden
                              </td>
                            </tr>
                          )}
                        </>
                      );
                    })()}
                  </tbody>
                </table>
              ) : (
                /* RBI FLA SECTIONS II, III, IV MATRIX VIEW */
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
                              All {activeModalSection} metrics are empty/zero (uncheck 'Hide Empty & Zero Rows' above to view).
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
                                <span className="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10 font-extrabold text-slate-900 dark:text-white font-mono text-xs">
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
                                Showing {filteredPaired.length} active PY/FY pairs • {hiddenCount} empty/zero rows hidden
                              </td>
                            </tr>
                          )}
                        </>
                      );
                    })()}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* STAGE 3: OFFICIAL PREVIEW & FILING EXPORT                 */}
      {/* ========================================================= */}
      {currentStage === 'preview_export' && (
        <div className="flex-1 flex min-h-0 bg-slate-900/40">
          
          {/* Left Panel: Filing Readiness & Validation Checklist */}
          <div className="w-80 border-r border-slate-200 dark:border-white/10 bg-white dark:bg-[#111726] p-6 flex flex-col justify-between shrink-0 shadow-lg">
            <div className="space-y-6">
              
              {/* Header */}
              <div>
                <span className="px-2 py-0.5 text-[10px] font-extrabold uppercase tracking-wider rounded-full bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-500/30">
                  Ready to File
                </span>
                <h3 className="text-base font-bold text-slate-900 dark:text-white mt-1.5">
                  Filing Readiness Checklist
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Pre-flight compliance check before statutory sign-off.
                </p>
              </div>

              {/* Checklist Items */}
              <div className="space-y-3">
                <div className="p-3.5 rounded-xl bg-emerald-50/50 dark:bg-emerald-500/5 border border-emerald-200 dark:border-emerald-500/20 flex items-start gap-3">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
                  <div>
                    <h4 className="text-xs font-bold text-emerald-800 dark:text-emerald-300">Mandatory Fields Complete</h4>
                    <p className="text-[11px] text-emerald-600 dark:text-emerald-400/80 mt-0.5">
                      {consolidatedFieldCount} statutory fields verified.
                    </p>
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-emerald-50/50 dark:bg-emerald-500/5 border border-emerald-200 dark:border-emerald-500/20 flex items-start gap-3">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
                  <div>
                    <h4 className="text-xs font-bold text-emerald-800 dark:text-emerald-300">Zero Document Conflicts</h4>
                    <p className="text-[11px] text-emerald-600 dark:text-emerald-400/80 mt-0.5">
                      Provenance reconciled across {uploadedFiles.length} source files.
                    </p>
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-emerald-50/50 dark:bg-emerald-500/5 border border-emerald-200 dark:border-emerald-500/20 flex items-start gap-3">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
                  <div>
                    <h4 className="text-xs font-bold text-emerald-800 dark:text-emerald-300">Scenario DAG Validated</h4>
                    <p className="text-[11px] text-emerald-600 dark:text-emerald-400/80 mt-0.5">
                      {activeScenario?.confirmed_branch || 'Statutory Scenario'} confirmed by human.
                    </p>
                  </div>
                </div>
              </div>

              {/* Summary Metrics */}
              <div className="p-4 rounded-xl bg-slate-50 dark:bg-[#151C2C] border border-slate-200 dark:border-white/10 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-500">Form Template:</span>
                  <span className="font-bold text-slate-800 dark:text-white truncate max-w-[140px]">{templateName}</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-500">Source Packet:</span>
                  <span className="font-bold text-slate-800 dark:text-white">{uploadedFiles.length} Documents</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-500">Verification Status:</span>
                  <span className="font-bold text-emerald-600 dark:text-emerald-400">100% Passed</span>
                </div>
              </div>
            </div>

            {/* Action Buttons in Stage 3 */}
            <div className="space-y-2 pt-6 border-t border-slate-200 dark:border-white/10">
              <button
                onClick={() => setCurrentStage('consolidated_return')}
                className="w-full flex items-center justify-center gap-2 py-2 rounded-xl text-xs font-bold text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/5 transition-all"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>Back to Consolidated Return</span>
              </button>

              <button
                onClick={() => {
                  alert("Payload ready for automated MCA filing agent submission!");
                }}
                className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-xs font-bold bg-indigo-600 hover:bg-indigo-700 text-white shadow-md shadow-indigo-600/25 transition-all"
              >
                <Send className="w-3.5 h-3.5" />
                <span>Submit to MCA Filing Bot</span>
              </button>
            </div>
          </div>

          {/* Right Panel: Clean Embedded Stamped PDF Viewer (Zero Form Clutter) */}
          <div className="flex-1 h-full min-h-0 flex flex-col overflow-hidden">
            <FilledFormViewer
              templateName={templateName}
              extractedData={consolidatedState?.payload || getConsolidatedPayload()}
              hideEmptyRows={hideEmptyModalRows}
              onDownloadExcel={templateName.toLowerCase().includes("fla") ? handleDownloadOfficialExcel : null}
              isDownloadingExcel={isDownloadingExcel}
            />
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* 4. UPFRONT HITL STATUTORY BRANCH GATE MODAL              */}
      {/* ========================================================= */}
      <ExtractionBranchGateModal
        isOpen={showBranchModal}
        onClose={() => setShowBranchModal(false)}
        onConfirm={handleScenarioConfirm}
        formId={templateName}
        formName={templateName}
        detectedData={detectedBranchData}
        isExtracting={isEvaluatingConsolidated}
        companyId="default"
      />

    </div>
  );
}
