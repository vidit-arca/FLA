import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { AlertCircle, CheckCircle, FileText, Check, ChevronRight, Save, X, ArrowRight, ShieldAlert } from 'lucide-react';

const DUMMY_FLAGS = [
  {
    id: "RULE_0",
    particulars: "Whether audit report has the following fields: Opinion of the Auditor, Basis of Opinion, Emphasis of matter...",
    source: "Auditors report",
    status: "Failed",
    user_value: null,
    reason: "Value is missing in extraction."
  },
  {
    id: "RULE_1",
    particulars: "whether CARO/Companies (Auditor's Report) Order is as per format given in Annual Filing > SAMPLE CARO",
    source: "Auditors report",
    status: "Failed",
    user_value: "No",
    reason: "Validation check failed (No)."
  },
  {
    id: "RULE_2",
    particulars: "whether Schedule III is as per format in Annual Filing > SAMPLE SCHEDULE III",
    source: "financials",
    status: "Failed",
    user_value: null,
    reason: "Value is missing in extraction."
  },
  {
    id: "RULE_8",
    particulars: "Whether the Authorised Capital is mentioned correctly as per MCA (Including Face Value of the shares)",
    source: "financials + Input sheet",
    status: "Failed",
    user_value: "No",
    reason: "Validation check failed (No)."
  }
];

const STEPS = [
  { id: 1, title: 'Common Errors' },
  { id: 2, title: 'Compliance & RPT Review' },
  { id: 3, title: 'Final Attachments' }
];

export default function AOC4TaskView() {
  const { taskId } = useParams();
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(1);
  const [activeFlagId, setActiveFlagId] = useState(DUMMY_FLAGS[0].id);
  const [resolvedFlags, setResolvedFlags] = useState({});

  const activeFlag = DUMMY_FLAGS.find(f => f.id === activeFlagId);

  const handleResolve = (e) => {
    e.preventDefault();
    setResolvedFlags(prev => ({ ...prev, [activeFlagId]: true }));
    
    // Auto-select next unresolved flag
    const nextUnresolved = DUMMY_FLAGS.find(f => f.id !== activeFlagId && !resolvedFlags[f.id]);
    if (nextUnresolved) {
      setActiveFlagId(nextUnresolved.id);
    }
  };

  const progress = (Object.keys(resolvedFlags).length / DUMMY_FLAGS.length) * 100;

  return (
    <div className="flex flex-col h-[calc(100vh-5rem)]">
      {/* Header & Wizard Stepper */}
      <div className="bg-[#131B2C] border border-slate-700/50 rounded-2xl p-6 shadow-xl mb-6 flex flex-col gap-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-3">
              <ShieldAlert className="w-6 h-6 text-indigo-400" />
              AOC4 Compliance Wizard
            </h1>
            <p className="text-slate-400 mt-1 text-sm">Task ID: {taskId} • Reviewing extracted compliance data</p>
          </div>
          
          <div className="flex items-center gap-4">
            <div className="text-right">
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-1">Step {currentStep} Progress</p>
              <p className="text-lg font-bold text-white">{Math.round(progress)}%</p>
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
        <div className="flex items-center w-full max-w-3xl mx-auto">
          {STEPS.map((step, idx) => (
            <React.Fragment key={step.id}>
              <div className={`flex flex-col items-center gap-2 relative z-10 ${currentStep === step.id ? 'opacity-100' : 'opacity-50'}`}>
                <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold border-2 transition-colors
                  ${currentStep > step.id ? 'bg-emerald-500 border-emerald-500 text-white' : 
                    currentStep === step.id ? 'bg-indigo-500/20 border-indigo-500 text-indigo-400 shadow-[0_0_15px_rgba(99,102,241,0.2)]' : 
                    'bg-slate-800 border-slate-700 text-slate-500'}`}
                >
                  {currentStep > step.id ? <Check className="w-5 h-5" /> : step.id}
                </div>
                <span className={`text-xs font-semibold whitespace-nowrap ${currentStep === step.id ? 'text-indigo-400' : 'text-slate-400'}`}>
                  {step.title}
                </span>
              </div>
              {idx < STEPS.length - 1 && (
                <div className="flex-1 h-0.5 mx-4 bg-slate-800 relative top-[-10px]">
                  <div 
                    className="absolute top-0 left-0 h-full bg-emerald-500 transition-all duration-500"
                    style={{ width: currentStep > step.id ? '100%' : '0%' }}
                  />
                </div>
              )}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex flex-col lg:flex-row gap-6 flex-1 min-h-0">
        
        {/* Left Panel: Flags List */}
        <div className="w-full lg:w-1/3 flex flex-col bg-[#1A2235] border border-slate-700 rounded-xl shadow-xl overflow-hidden h-full">
          <div className="p-4 border-b border-slate-700 bg-[#131B2C] flex items-center justify-between">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <AlertCircle className="w-5 h-5 text-rose-400" />
              Common Errors ({DUMMY_FLAGS.length - Object.keys(resolvedFlags).length})
            </h3>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-[#131B2C]/50 hide-scrollbar">
            {DUMMY_FLAGS.map((flag) => {
              const isResolved = resolvedFlags[flag.id];
              const isActive = activeFlagId === flag.id;
              const isMissing = flag.reason.includes('missing');
              
              const cardColor = isResolved 
                ? 'border-emerald-500/20 bg-emerald-500/5 opacity-60' 
                : isActive 
                  ? 'border-indigo-500/50 bg-indigo-500/10 shadow-[0_0_15px_rgba(99,102,241,0.15)]'
                  : isMissing
                    ? 'border-amber-500/30 bg-amber-500/10'
                    : 'border-rose-500/30 bg-rose-500/10';
              
              const iconColor = isResolved ? 'text-emerald-400' : isMissing ? 'text-amber-400' : 'text-rose-400';
              
              return (
                <div 
                  key={flag.id} 
                  onClick={() => setActiveFlagId(flag.id)}
                  className={`p-4 rounded-xl border ${cardColor} transition-all cursor-pointer hover:-translate-y-0.5 flex flex-col gap-2`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-2">
                      {isResolved ? <CheckCircle className={`w-4 h-4 ${iconColor}`} /> : <AlertCircle className={`w-4 h-4 ${iconColor}`} />}
                      <span className={`text-xs font-bold uppercase tracking-wider ${iconColor}`}>
                        {isResolved ? 'Resolved' : isMissing ? 'Missing Value' : 'Validation Failed'}
                      </span>
                    </div>
                    <span className="text-[10px] px-2 py-0.5 rounded bg-black/30 text-slate-400 border border-white/5 whitespace-nowrap">
                      {flag.source}
                    </span>
                  </div>
                  
                  <p className="text-sm text-slate-200 font-medium line-clamp-2 mt-1 leading-snug">
                    {flag.particulars}
                  </p>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Panel: Resolution Form */}
        <div className="flex-1 flex flex-col bg-[#1A2235] border border-slate-700 rounded-xl shadow-xl overflow-hidden h-full">
          <div className="p-4 border-b border-slate-700 bg-[#131B2C]">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <FileText className="w-5 h-5 text-indigo-400" />
              Resolve Issue
            </h3>
          </div>
          
          <div className="flex-1 overflow-y-auto p-8 bg-[#0F1523]">
            {activeFlag ? (
              <form onSubmit={handleResolve} className="max-w-2xl mx-auto space-y-6">
                
                <div className="p-6 rounded-xl bg-slate-800/50 border border-slate-700 space-y-4">
                  <div>
                    <label className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-2 block">Rule / Particulars</label>
                    <p className="text-lg text-white font-medium">{activeFlag.particulars}</p>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4 pt-4 border-t border-slate-700">
                    <div>
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1 block">Expected Source</label>
                      <span className="inline-flex items-center px-2.5 py-1 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 text-sm font-semibold">
                        {activeFlag.source}
                      </span>
                    </div>
                    <div>
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1 block">Extracted Value</label>
                      <span className="inline-flex items-center px-2.5 py-1 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20 text-sm font-semibold">
                        {activeFlag.user_value || 'None / Missing'}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="space-y-4 pt-4">
                  <div>
                    <label className="block text-sm font-semibold text-slate-300 mb-2">
                      Corrected Value (Yes/No/NA)
                    </label>
                    <select 
                      className="w-full bg-[#131B2C] border border-slate-700 text-white rounded-xl px-4 py-3 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-colors"
                      defaultValue={activeFlag.user_value === 'No' ? 'No' : ''}
                      required
                    >
                      <option value="" disabled>Select a value...</option>
                      <option value="Yes">Yes</option>
                      <option value="No">No</option>
                      <option value="NA">NA</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-semibold text-slate-300 mb-2">
                      Auditor / Resolution Comments
                    </label>
                    <textarea 
                      className="w-full bg-[#131B2C] border border-slate-700 text-white rounded-xl px-4 py-3 h-32 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-colors resize-none placeholder-slate-600"
                      placeholder="Enter explanation or manual verification details here..."
                      required
                    ></textarea>
                  </div>
                </div>

                <div className="flex items-center justify-end gap-4 pt-6 mt-6 border-t border-slate-700/50">
                  <button 
                    type="button" 
                    className="px-6 py-2.5 rounded-xl font-semibold text-slate-300 hover:text-white hover:bg-slate-800 transition-colors flex items-center gap-2"
                  >
                    <X className="w-4 h-4" />
                    Cancel
                  </button>
                  <button 
                    type="submit" 
                    className="px-6 py-2.5 rounded-xl font-semibold text-white bg-indigo-500 hover:bg-indigo-600 shadow-lg shadow-indigo-500/25 transition-all flex items-center gap-2"
                  >
                    <Save className="w-4 h-4" />
                    Save & Mark Resolved
                  </button>
                </div>

              </form>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-slate-500 gap-4">
                <CheckCircle className="w-16 h-16 text-emerald-500/20" />
                <p className="text-lg font-medium">All flags resolved or none selected.</p>
              </div>
            )}
          </div>
          
          {/* Next Step Action Bar */}
          {progress === 100 && (
            <div className="p-4 bg-emerald-500/10 border-t border-emerald-500/20 flex items-center justify-between">
              <p className="text-emerald-400 font-medium">All common errors resolved! Ready for Compliance Review.</p>
              <button 
                onClick={() => setCurrentStep(2)}
                className="px-5 py-2 rounded-lg font-semibold text-white bg-emerald-500 hover:bg-emerald-600 shadow-lg shadow-emerald-500/25 transition-all flex items-center gap-2"
              >
                Proceed to Step 2
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
