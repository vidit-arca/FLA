import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { 
  AlertCircle, CheckCircle, FileText, Check, Save, X, ArrowRight,
  ShieldAlert, FileSpreadsheet, Loader2, MessageSquare,
  CheckSquare, XOctagon, FileBadge, Clock, RefreshCw, ChevronRight, Download
} from 'lucide-react';
import ExcelViewer from '../components/ExcelViewer';

const STEPS = [
  { id: 1, title: 'Common Errors' },
  { id: 2, title: 'Compliance Review' },
  { id: 3, title: 'RPT & Loans Review' }
];

export default function AOC4TaskView() {
  const { taskId } = useParams();
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(1);
  const [task, setTask] = useState(null);
  const [loading, setLoading] = useState(true);
  
  const [allFlags, setAllFlags] = useState([]);
  const [failedFlags, setFailedFlags] = useState([]);
  
  const [activeFlagId, setActiveFlagId] = useState(null);
  const [resolvedFlags, setResolvedFlags] = useState({});
  const [showExcelPreview, setShowExcelPreview] = useState(false);

  useEffect(() => {
    let interval = null;
    
    const fetchTask = async () => {
      try {
        const res = await axios.get(`http://localhost:8000/api/tasks/${taskId}`);
        setTask(res.data);
        
        if (res.data.status === 'completed' || res.data.status === 'review_needed') {
          clearInterval(interval);
          setLoading(false);
          
          if (res.data.extracted_data && res.data.extracted_data.flags) {
            const flags = res.data.extracted_data.flags;
            setAllFlags(flags);
            
            const failed = flags.filter(f => f.status === 'Failed' || f.status === 'Manual');
            setFailedFlags(failed);
            if (failed.length > 0 && !activeFlagId) {
              setActiveFlagId(failed[0].rule_id);
            }
          }
        } else if (res.data.status === 'error') {
          clearInterval(interval);
          setLoading(false);
        }
      } catch (err) {
        console.error(err);
        clearInterval(interval);
        setLoading(false);
      }
    };

    fetchTask();
    interval = setInterval(fetchTask, 2000);
    return () => clearInterval(interval);
  }, [taskId]);

  const getFlagsForStep = (flags, step) => flags.filter(f => {
    if (step === 1) return f.source !== 'Compliance Engine' && f.source !== 'RPT & Loans Engine';
    if (step === 2) return f.source === 'Compliance Engine';
    if (step === 3) return f.source === 'RPT & Loans Engine';
    return true;
  });

  const stepAllFlags = getFlagsForStep(allFlags, currentStep);
  const stepFailedFlags = getFlagsForStep(failedFlags, currentStep);

  const activeFlag = stepFailedFlags.find(f => f.rule_id === activeFlagId);

  const handleResolve = (e) => {
    e.preventDefault();
    setResolvedFlags(prev => ({ ...prev, [activeFlagId]: true }));
    
    // Auto-select next unresolved flag
    const nextUnresolved = stepFailedFlags.find(f => f.rule_id !== activeFlagId && !resolvedFlags[f.rule_id]);
    if (nextUnresolved) {
      setActiveFlagId(nextUnresolved.rule_id);
    }
  };

  const totalChecks = allFlags.length || 0;
  const totalFailed = failedFlags.length || 0;
  const manualResolved = Object.keys(resolvedFlags).length;
  
  const pendingCount = totalFailed - manualResolved;
  const resolvedCount = totalChecks - pendingCount; // Auto-passed + Manually resolved
  
  const progress = totalChecks === 0 ? 100 : (resolvedCount / totalChecks) * 100;
  
  // Get unique sources
  const uniqueSources = [...new Set(allFlags.map(f => f.source))].length;

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-[calc(100vh-5rem)]">
        <Loader2 className="w-12 h-12 text-indigo-500 animate-spin mb-4" />
        <h2 className="text-xl font-bold text-slate-900 dark:text-white">Extracting & Validating AOC4...</h2>
        <p className="text-slate-600 dark:text-slate-400 mt-2">This may take a few minutes depending on the document size.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-5rem)] overflow-hidden gap-4">
      {/* Header & Wizard Stepper */}
      <div className="bg-white dark:bg-[#131B2C] border border-slate-300 dark:border-slate-700/50 rounded-2xl p-5 shadow-xl flex flex-col gap-4 flex-shrink-0">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-4">
              <h1 className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight flex items-center gap-3">
                <ShieldAlert className="w-6 h-6 text-indigo-400" />
                AOC4 Compliance Wizard
              </h1>
              <button 
                onClick={() => setShowExcelPreview(!showExcelPreview)}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-semibold transition-colors border ${showExcelPreview ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' : 'bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-300 dark:border-slate-700 hover:bg-slate-700'}`}
              >
                <FileSpreadsheet className="w-4 h-4" />
                {showExcelPreview ? 'Hide Excel' : 'Preview Excel'}
              </button>
            </div>
            <p className="text-slate-600 dark:text-slate-400 mt-1 text-sm">Task ID: {taskId} • Reviewing extracted compliance data</p>
          </div>
          
          <div className="flex items-center gap-4 w-64">
            <div className="text-right flex-1">
              <p className="text-[10px] font-bold text-slate-600 dark:text-slate-400 uppercase tracking-widest mb-1">Step {currentStep} Progress</p>
              <p className="text-lg font-bold text-slate-900 dark:text-white leading-none">{Math.round(progress)}%</p>
            </div>
            <div className="w-32 h-2.5 bg-slate-800 rounded-full overflow-hidden">
              <div 
                className="h-full bg-indigo-500 rounded-full transition-all duration-500" 
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        </div>

        {/* Stepper */}
        <div className="flex items-center w-full max-w-2xl mx-auto">
          {STEPS.map((step, idx) => (
            <React.Fragment key={step.id}>
              <div className={`flex flex-col items-center gap-2 relative z-10 ${currentStep === step.id ? 'opacity-100' : 'opacity-50'}`}>
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold border-2 transition-colors
                  ${currentStep > step.id ? 'bg-emerald-500 border-emerald-500 text-slate-900 dark:text-white' : 
                    currentStep === step.id ? 'bg-indigo-500 border-indigo-500 text-slate-900 dark:text-white shadow-[0_0_15px_rgba(99,102,241,0.3)]' : 
                    'bg-slate-800 border-slate-300 dark:border-slate-700 text-slate-500'}`}
                >
                  {currentStep > step.id ? <Check className="w-4 h-4" /> : step.id}
                </div>
                <span className={`text-[11px] font-semibold uppercase tracking-wider whitespace-nowrap ${currentStep === step.id ? 'text-indigo-400' : 'text-slate-600 dark:text-slate-400'}`}>
                  {step.title}
                </span>
              </div>
              {idx < STEPS.length - 1 && (
                <div className="flex-1 h-[1px] mx-4 bg-slate-800 relative top-[-10px]">
                  <div 
                    className="absolute top-0 left-0 h-full bg-indigo-500 transition-all duration-500"
                    style={{ width: currentStep > step.id ? '100%' : '0%' }}
                  />
                </div>
              )}
            </React.Fragment>
          ))}
        </div>
        
        {/* Step Navigation Controls */}
        <div className="flex items-center justify-between mt-2 pt-4 border-t border-slate-300 dark:border-slate-700/50">
           <button 
             onClick={() => {
                const prev = Math.max(1, currentStep - 1);
                setCurrentStep(prev);
                const prevFailed = getFlagsForStep(failedFlags, prev);
                if (prevFailed.length > 0) setActiveFlagId(prevFailed[0].rule_id);
             }}
             disabled={currentStep === 1}
             className={`px-4 py-1.5 rounded-lg text-sm font-bold transition-colors ${currentStep === 1 ? 'opacity-50 cursor-not-allowed bg-slate-200 dark:bg-slate-800 text-slate-500' : 'bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-300 dark:hover:bg-slate-700'}`}
           >
             Previous Step
           </button>
           {currentStep < 3 ? (
              <button 
                onClick={() => {
                   const next = currentStep + 1;
                   setCurrentStep(next);
                   const nextFailed = getFlagsForStep(failedFlags, next);
                   if (nextFailed.length > 0) setActiveFlagId(nextFailed[0].rule_id);
                }}
                className="px-4 py-1.5 rounded-lg text-sm font-bold transition-colors flex items-center gap-2 bg-indigo-500 text-white hover:bg-indigo-600 shadow-lg shadow-indigo-500/20"
              >
                {currentStep === 1 ? 'Next Step: Compliance Review' : 'Next Step: RPT & Loans Review'}
                <ArrowRight className="w-4 h-4" />
              </button>
            ) : (
              <button 
                onClick={() => window.open(`http://localhost:8000/api/download/${taskId}`, '_blank')}
                disabled={progress < 100}
                className={`px-4 py-1.5 rounded-lg text-sm font-bold transition-colors flex items-center gap-2 ${progress < 100 ? 'opacity-50 cursor-not-allowed bg-slate-200 dark:bg-slate-800 text-slate-500' : 'bg-emerald-500 text-white hover:bg-emerald-600 shadow-lg shadow-emerald-500/20'}`}
              >
                {progress < 100 ? 'Resolve all flags to download' : 'Download Final Excel'}
                <Download className="w-4 h-4" />
              </button>
            )}
        </div>
        
      </div>

      {/* Main 3-Column Layout */}
      <div className="flex gap-4 flex-1 min-h-0">
        
        {/* Left Column: Common Errors List */}
        <div className="w-[300px] flex flex-col bg-white dark:bg-[#131B2C] border border-slate-300 dark:border-slate-700/50 rounded-xl shadow-lg overflow-hidden h-full flex-shrink-0">
          <div className="p-4 border-b border-slate-300 dark:border-slate-700/50 flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-400" />
              {currentStep === 1 ? 'Common Errors' : 'Compliance Checks'}
            </h3>
            <span className="bg-rose-500/20 text-rose-400 text-xs font-bold px-2 py-0.5 rounded-full">
              {stepFailedFlags.length}
            </span>
          </div>
          
          <div className="flex-1 overflow-y-auto p-3 space-y-2 hide-scrollbar">
            {stepFailedFlags.map((flag) => {
              const isResolved = resolvedFlags[flag.rule_id];
              const isActive = activeFlagId === flag.rule_id;
              
              return (
                <div 
                  key={flag.rule_id} 
                  onClick={() => setActiveFlagId(flag.rule_id)}
                  className={`p-3 rounded-xl border transition-all cursor-pointer group flex flex-col gap-2 relative overflow-hidden
                    ${isResolved ? 'border-emerald-500/20 bg-emerald-500/5 opacity-60' : 
                      isActive ? 'border-indigo-500 bg-indigo-500/10' : 'border-slate-300 dark:border-slate-700/50 bg-white dark:bg-[#1A2235] hover:border-slate-600'}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-1.5">
                      {isResolved ? <CheckCircle className="w-3.5 h-3.5 text-emerald-400" /> : <AlertCircle className="w-3.5 h-3.5 text-rose-400" />}
                      <span className={`text-[10px] font-bold uppercase tracking-wider ${isResolved ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {isResolved ? 'Resolved' : 'Validation Failed'}
                      </span>
                    </div>
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-300 dark:border-slate-700 truncate max-w-[80px]">
                      {flag.source}
                    </span>
                  </div>
                  
                  <p className="text-xs text-slate-700 dark:text-slate-300 font-medium line-clamp-2 leading-relaxed">
                    {flag.particulars}
                  </p>
                  
                  {isActive && !isResolved && (
                    <div className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <ChevronRight className="w-4 h-4 text-indigo-400" />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          <div className="p-3 border-t border-slate-300 dark:border-slate-700/50 bg-slate-100 dark:bg-[#0F1523]">
             <button className="w-full text-xs font-semibold text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:text-white flex items-center justify-center gap-1 transition-colors">
               View All Errors <ChevronRight className="w-3 h-3" />
             </button>
          </div>
        </div>

        {/* Middle Column: Resolve Issue Form */}
        <div className="w-[360px] flex flex-col bg-white dark:bg-[#1A2235] border border-slate-300 dark:border-slate-700/50 rounded-xl shadow-lg overflow-hidden h-full flex-shrink-0">
          <div className="p-4 border-b border-slate-300 dark:border-slate-700/50 bg-white dark:bg-[#131B2C]">
            <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <FileText className="w-4 h-4 text-indigo-400" />
              Resolve Issue
            </h3>
          </div>
          
          <div className="flex-1 overflow-y-auto p-5">
            {activeFlag ? (
              <form onSubmit={handleResolve} className="flex flex-col h-full space-y-6">
                
                <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-300 dark:border-slate-700/50 shadow-inner">
                  <div className="mb-4">
                    <label className="text-[10px] font-bold text-slate-600 dark:text-slate-400 uppercase tracking-widest mb-1.5 block">Rule / Particulars</label>
                    <p className="text-sm text-slate-800 dark:text-slate-200 font-medium leading-relaxed">{activeFlag.particulars}</p>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-3 pt-3 border-t border-slate-300 dark:border-slate-700/50">
                    <div>
                      <label className="text-[10px] font-bold text-slate-600 dark:text-slate-400 uppercase tracking-widest mb-1 block">Expected Source</label>
                      <span className="inline-flex items-center px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 text-xs font-semibold">
                        {activeFlag.source}
                      </span>
                    </div>
                    <div>
                      <label className="text-[10px] font-bold text-slate-600 dark:text-slate-400 uppercase tracking-widest mb-1 block">Extracted Value</label>
                      <span className={`inline-flex items-center px-2 py-0.5 rounded border text-xs font-semibold ${!activeFlag.user_value || activeFlag.user_value === 'No' || activeFlag.user_value.includes('Missing') ? 'bg-rose-500/10 text-rose-400 border-rose-500/20' : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'}`}>
                        {activeFlag.user_value || 'None / Missing'}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="space-y-4">
                  <div>
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
                      Corrected Value (Yes/No/NA)
                    </label>
                    <div className="relative">
                      <select 
                        className="w-full bg-white dark:bg-[#131B2C] border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-colors appearance-none"
                        defaultValue={
                          (activeFlag.source === 'Compliance Engine' || activeFlag.source === 'RPT & Loans Engine')
                            ? activeFlag.user_value || ''
                            : (['Yes', 'No', 'NA'].includes(activeFlag.user_value) ? activeFlag.user_value : 'No')
                        }
                        required
                      >
                        <option value="" disabled>Select a value...</option>
                        {(activeFlag.source === 'Compliance Engine' || activeFlag.source === 'RPT & Loans Engine') ? (
                          <>
                            {activeFlag.user_value && !['Applicable', 'Not Applicable', 'Yes, It is a Small Company', 'No', 'Missing Data'].includes(activeFlag.user_value) && (
                              <option value={activeFlag.user_value}>{activeFlag.user_value}</option>
                            )}
                            <option value="Applicable">Applicable</option>
                            <option value="Not Applicable">Not Applicable</option>
                            <option value="Yes, It is a Small Company">Yes, Small Co</option>
                            <option value="No">No</option>
                            <option value="Missing Data">Missing Data</option>
                          </>
                        ) : (
                          <>
                            <option value="Yes">Yes</option>
                            <option value="No">No</option>
                            <option value="NA">NA</option>
                          </>
                        )}
                      </select>
                      <ChevronRight className="w-4 h-4 text-slate-600 dark:text-slate-400 absolute right-3 top-3 pointer-events-none rotate-90" />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
                      Auditor / Resolution Comments
                    </label>
                    <textarea 
                      className="w-full bg-white dark:bg-[#131B2C] border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white rounded-lg px-3 py-2.5 h-28 text-sm focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-colors resize-none placeholder-slate-600"
                      placeholder="Enter explanation or manual verification details here..."
                    ></textarea>
                  </div>
                </div>

                <div className="mt-auto pt-4 flex items-center justify-between">
                  <button 
                    type="button" 
                    className="px-4 py-2 rounded-lg text-xs font-bold text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:text-white hover:bg-slate-800 transition-colors flex items-center gap-1.5"
                  >
                    <X className="w-3.5 h-3.5" />
                    Cancel
                  </button>
                  <button 
                    type="submit" 
                    className="px-5 py-2 rounded-lg text-xs font-bold text-slate-900 dark:text-white bg-indigo-500 hover:bg-indigo-600 shadow-[0_0_15px_rgba(99,102,241,0.3)] transition-all flex items-center gap-1.5"
                  >
                    <Save className="w-3.5 h-3.5" />
                    Save & Mark Resolved
                  </button>
                </div>

              </form>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-slate-500 gap-3">
                <CheckCircle className="w-12 h-12 text-emerald-500/20" />
                <p className="text-sm font-medium">All flags resolved!</p>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Full Compliance Sheet */}
        <div className="flex-1 flex flex-col bg-white dark:bg-[#131B2C] border border-slate-300 dark:border-slate-700/50 rounded-xl shadow-lg overflow-hidden h-full min-w-[500px]">
          <div className="border-b border-slate-300 dark:border-slate-700/50 flex items-center justify-between px-2 bg-white dark:bg-[#1A2235]">
            <div className="flex items-center gap-2">
              <div className="px-4 py-3 text-xs font-bold uppercase tracking-wider border-b-2 border-indigo-500 text-indigo-400">
                {STEPS.find(s => s.id === currentStep)?.title}
              </div>
            </div>
            <button 
              onClick={() => window.open(`http://localhost:8000/api/download/${taskId}`, '_blank')}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold text-slate-700 dark:text-slate-300 border border-slate-300 dark:border-slate-700 hover:bg-slate-800 transition-colors mr-2"
            >
              <Download className="w-3.5 h-3.5" />
              Download Excel
            </button>
          </div>
          
          <div className="flex-1 overflow-auto bg-slate-100 dark:bg-[#0F1523] hide-scrollbar">
            <table className="w-full text-left border-collapse">
              <thead className="bg-white dark:bg-[#1A2235] sticky top-0 z-10 shadow-md">
                <tr>
                  <th className="py-3 px-4 text-[10px] font-bold text-slate-600 dark:text-slate-400 uppercase tracking-widest border-b border-slate-300 dark:border-slate-700/50">S.No</th>
                  <th className="py-3 px-4 text-[10px] font-bold text-slate-600 dark:text-slate-400 uppercase tracking-widest border-b border-slate-300 dark:border-slate-700/50">Particulars</th>
                  <th className="py-3 px-4 text-[10px] font-bold text-slate-600 dark:text-slate-400 uppercase tracking-widest border-b border-slate-300 dark:border-slate-700/50">Expected Source</th>
                  <th className="py-3 px-4 text-[10px] font-bold text-slate-600 dark:text-slate-400 uppercase tracking-widest border-b border-slate-300 dark:border-slate-700/50">Extracted Value</th>
                  <th className="py-3 px-4 text-[10px] font-bold text-slate-600 dark:text-slate-400 uppercase tracking-widest border-b border-slate-300 dark:border-slate-700/50">Corrected Value</th>
                  <th className="py-3 px-4 text-[10px] font-bold text-slate-600 dark:text-slate-400 uppercase tracking-widest border-b border-slate-300 dark:border-slate-700/50">Status</th>
                  <th className="py-3 px-4 text-[10px] font-bold text-slate-600 dark:text-slate-400 uppercase tracking-widest border-b border-slate-300 dark:border-slate-700/50 text-center">Comments</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50">
                {stepAllFlags.map((flag, idx) => {
                  const isFailed = flag.status === 'Failed' || flag.status === 'Manual';
                  const isResolved = resolvedFlags[flag.rule_id];
                  const statusBadge = (!isFailed || isResolved) 
                    ? <span className="inline-flex px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Resolved</span>
                    : <span className="inline-flex px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/10 text-rose-400 border border-rose-500/20">Pending</span>;

                  // Trim particulars for UI
                  const trimmedPart = flag.particulars.length > 50 ? flag.particulars.substring(0, 50) + '...' : flag.particulars;
                  
                  return (
                    <tr key={flag.rule_id} className="hover:bg-slate-800/20 transition-colors">
                      <td className="py-2.5 px-4 text-xs text-slate-500 font-medium">{idx + 1}</td>
                      <td className="py-2.5 px-4 text-xs text-slate-700 dark:text-slate-300 font-medium max-w-[200px] truncate" title={flag.particulars}>{trimmedPart}</td>
                      <td className="py-2.5 px-4 text-xs text-slate-600 dark:text-slate-400">{flag.source}</td>
                      <td className="py-2.5 px-4">
                        <span className={`text-xs font-bold ${!flag.user_value || flag.user_value === 'No' || flag.user_value.includes('Missing') ? 'text-rose-400' : 'text-emerald-400'}`}>
                          {flag.user_value || 'No'}
                        </span>
                      </td>
                      <td className="py-2.5 px-4">
                        <div className="relative w-[110px]">
                          <select 
                            className="w-full bg-white dark:bg-[#1A2235] border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 text-[11px] rounded px-2 py-1 appearance-none focus:outline-none focus:border-indigo-500"
                            value={resolvedFlags[flag.rule_id] ? 'Yes' : (
                               (flag.source === 'Compliance Engine' || flag.source === 'RPT & Loans Engine')
                                 ? flag.user_value || ''
                                 : (['Yes', 'No', 'NA'].includes(flag.user_value) ? flag.user_value : 'No')
                            )}
                            onChange={(e) => {
                              setResolvedFlags(prev => ({ ...prev, [flag.rule_id]: true }));
                            }}
                          >
                            {(flag.source === 'Compliance Engine' || flag.source === 'RPT & Loans Engine') ? (
                              <>
                                {flag.user_value && !['Applicable', 'Not Applicable', 'Yes, It is a Small Company', 'No', 'Missing Data'].includes(flag.user_value) && (
                                  <option value={flag.user_value}>{flag.user_value}</option>
                                )}
                                <option value="Applicable">Applicable</option>
                                <option value="Not Applicable">Not Applicable</option>
                                <option value="Yes, It is a Small Company">Yes, Small Co</option>
                                <option value="No">No</option>
                                <option value="Missing Data">Missing Data</option>
                              </>
                            ) : (
                              <>
                                <option value="Yes">Yes</option>
                                <option value="No">No</option>
                                <option value="NA">NA</option>
                              </>
                            )}
                          </select>
                          <ChevronRight className="w-3 h-3 text-slate-500 absolute right-1.5 top-1.5 pointer-events-none rotate-90" />
                        </div>
                      </td>
                      <td className="py-2.5 px-4">{statusBadge}</td>
                      <td className="py-2.5 px-4 text-center">
                        <button className="text-slate-500 hover:text-indigo-400 transition-colors">
                          <MessageSquare className="w-3.5 h-3.5 mx-auto" />
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>

      </div>

      {/* Bottom KPIs Dashboard */}
      <div className="grid grid-cols-5 gap-4 flex-shrink-0">
        <div className="bg-white dark:bg-[#131B2C] border border-slate-300 dark:border-slate-700/50 rounded-xl p-4 flex items-center gap-4 shadow-lg">
          <div className="w-10 h-10 rounded-lg bg-slate-800 flex items-center justify-center">
            <CheckSquare className="w-5 h-5 text-slate-600 dark:text-slate-400" />
          </div>
          <div>
            <p className="text-[10px] font-bold text-slate-600 dark:text-slate-400 uppercase tracking-widest mb-0.5">Total Checks</p>
            <p className="text-xl font-bold text-slate-900 dark:text-white leading-none">{totalChecks}</p>
            <p className="text-[10px] text-slate-500 mt-1">Total compliance checks</p>
          </div>
        </div>
        
        <div className="bg-white dark:bg-[#131B2C] border border-slate-300 dark:border-slate-700/50 rounded-xl p-4 flex items-center gap-4 shadow-lg">
          <div className="w-10 h-10 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
            <CheckCircle className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <p className="text-[10px] font-bold text-slate-600 dark:text-slate-400 uppercase tracking-widest mb-0.5">Resolved</p>
            <p className="text-xl font-bold text-slate-900 dark:text-white leading-none">{resolvedCount}</p>
            <p className="text-[10px] text-emerald-400 mt-1 font-medium">{totalChecks > 0 ? ((resolvedCount/totalChecks)*100).toFixed(1) : 100}% completed</p>
          </div>
        </div>
        
        <div className="bg-white dark:bg-[#131B2C] border border-slate-300 dark:border-slate-700/50 rounded-xl p-4 flex items-center gap-4 shadow-lg">
          <div className="w-10 h-10 rounded-lg bg-rose-500/10 border border-rose-500/20 flex items-center justify-center">
            <XOctagon className="w-5 h-5 text-rose-400" />
          </div>
          <div>
            <p className="text-[10px] font-bold text-slate-600 dark:text-slate-400 uppercase tracking-widest mb-0.5">Pending</p>
            <p className="text-xl font-bold text-slate-900 dark:text-white leading-none">{pendingCount}</p>
            <p className="text-[10px] text-rose-400 mt-1 font-medium">{totalChecks > 0 ? ((pendingCount/totalChecks)*100).toFixed(1) : 0}% remaining</p>
          </div>
        </div>
        
        <div className="bg-white dark:bg-[#131B2C] border border-slate-300 dark:border-slate-700/50 rounded-xl p-4 flex items-center gap-4 shadow-lg">
          <div className="w-10 h-10 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
            <FileBadge className="w-5 h-5 text-indigo-400" />
          </div>
          <div>
            <p className="text-[10px] font-bold text-slate-600 dark:text-slate-400 uppercase tracking-widest mb-0.5">Sources</p>
            <p className="text-xl font-bold text-slate-900 dark:text-white leading-none">{uniqueSources}</p>
            <p className="text-[10px] text-slate-500 mt-1">Audit, Financials, Other</p>
          </div>
        </div>
        
        <div className="bg-white dark:bg-[#131B2C] border border-slate-300 dark:border-slate-700/50 rounded-xl p-4 flex items-center gap-4 shadow-lg">
          <div className="w-10 h-10 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center">
            <Clock className="w-5 h-5 text-purple-400" />
          </div>
          <div>
            <p className="text-[10px] font-bold text-slate-600 dark:text-slate-400 uppercase tracking-widest mb-0.5">Last Updated</p>
            <p className="text-xl font-bold text-slate-900 dark:text-white leading-none">Just now</p>
            <p className="text-[10px] text-purple-400 mt-1 font-medium">Auto-saved</p>
          </div>
        </div>
      </div>
      
    </div>
  );
}
