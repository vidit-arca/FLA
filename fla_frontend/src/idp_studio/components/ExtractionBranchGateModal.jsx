import React, { useState } from 'react';
import { 
  CheckCircle2, 
  AlertCircle, 
  Scale, 
  Sparkles, 
  FileText, 
  ArrowRight, 
  ShieldCheck,
  Building2,
  X
} from 'lucide-react';

export default function ExtractionBranchGateModal({
  isOpen,
  onClose,
  onConfirm,
  formId,
  formName,
  detectedData,
  isExtracting,
  companyId = ""
}) {
  if (!isOpen) return null;

  const detected = detectedData?.detected || {};
  const recommendedBranch = detected.recommended_branch || "Appointment/ Re-appointment in AGM";
  const subReason = detected.sub_reason || "Resignation";
  const confidence = detected.confidence ? Math.round(detected.confidence * 100) : 95;
  const evidenceSnippet = detected.evidence_snippet || "";
  const sectionCited = detected.section_cited || "";

  const [selectedBranch, setSelectedBranch] = useState(recommendedBranch);
  const [selectedSubReason, setSelectedSubReason] = useState(subReason);
  const [cinInput, setCinInput] = useState(companyId);

  const branches = [
    {
      id: "Appointment/ Re-appointment in AGM",
      scenario: "agm_appointment",
      title: "Appointment / Re-appointment in AGM",
      section: "Section 139(1)",
      description: "Standard periodic appointment for 5-year block or single AGM"
    },
    {
      id: "Casual Vacancy",
      scenario: "casual_vacancy",
      title: "Casual Vacancy",
      section: "Section 139(8)",
      description: "Vacancy caused due to resignation, death, or disqualification of auditor"
    },
    {
      id: "Auditor appointed by the Tribunal",
      scenario: "tribunal_order",
      title: "Auditor appointed by Tribunal",
      section: "Section 140(5)",
      description: "Appointment ordered by National Company Law Tribunal (NCLT)"
    },
    {
      id: "Auditor appointed by Central Government",
      scenario: "central_gov",
      title: "Auditor appointed by Central Government",
      section: "Section 139(5)",
      description: "CAG appointment for Government or statutory companies"
    }
  ];

  const handleConfirm = () => {
    const selectedBranchObj = branches.find(b => b.id === selectedBranch) || branches[0];
    onConfirm({
      confirmed_branch: selectedBranch,
      scenario: selectedBranchObj.scenario,
      casual_vacancy_reason: selectedBranch === "Casual Vacancy" ? selectedSubReason : null,
      company_id: cinInput.trim() || "default"
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="bg-slate-900 border border-slate-700/80 rounded-2xl w-full max-w-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        
        {/* Header */}
        <div className="p-5 border-b border-slate-800 bg-slate-850 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-blue-500/10 border border-blue-500/30 text-blue-400">
              <Scale className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-semibold text-white tracking-wide">
                  Confirm Statutory Filing Branch
                </h3>
                <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/30">
                  {formName || "MCA Form"}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Upfront HITL Decision Gate: Verify statutory pathway to prune inactive branches
              </p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-5 overflow-y-auto flex-1 custom-scrollbar">
          
          {/* AI Evidence Recommendation Callout */}
          {evidenceSnippet && (
            <div className="p-4 rounded-xl bg-emerald-950/30 border border-emerald-500/40 relative overflow-hidden">
              <div className="flex items-start gap-3">
                <div className="p-1.5 rounded-lg bg-emerald-500/20 text-emerald-400 mt-0.5">
                  <Sparkles className="w-4 h-4" />
                </div>
                <div className="space-y-1.5 flex-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-emerald-400 uppercase tracking-wider flex items-center gap-1.5">
                      AI Operative Clause Analysis
                      <span className="bg-emerald-500/20 text-emerald-300 px-1.5 py-0.5 rounded text-[10px]">
                        {confidence}% Confidence
                      </span>
                    </span>
                    {sectionCited && (
                      <span className="text-[11px] font-mono font-medium text-emerald-300/80 bg-emerald-900/40 px-2 py-0.5 rounded border border-emerald-500/30">
                        {sectionCited}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-200 italic leading-relaxed border-l-2 border-emerald-500/50 pl-2.5">
                    "{evidenceSnippet}"
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Company Context */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-300 flex items-center gap-1.5">
              <Building2 className="w-3.5 h-3.5 text-slate-400" />
              Company CIN / Scope ID (Optional)
            </label>
            <input
              type="text"
              value={cinInput}
              onChange={(e) => setCinInput(e.target.value)}
              placeholder="e.g. U72200DL2020PTC123456"
              className="w-full px-3 py-2 bg-slate-800/80 border border-slate-700 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
            <p className="text-[11px] text-slate-500">
              Isolates custom letterhead rules strictly to this company's CIN (Zero cross-contamination).
            </p>
          </div>

          {/* Radio Buttons for Branches */}
          <div className="space-y-2.5">
            <label className="text-xs font-medium text-slate-300">
              Select Governing Legal Pathway:
            </label>
            
            <div className="space-y-2">
              {branches.map((b) => {
                const isSelected = selectedBranch === b.id;
                const isAIRecommended = recommendedBranch === b.id;

                return (
                  <div
                    key={b.id}
                    onClick={() => setSelectedBranch(b.id)}
                    className={`p-3.5 rounded-xl border transition-all cursor-pointer flex items-start gap-3.5 ${
                      isSelected
                        ? "bg-blue-600/10 border-blue-500 ring-1 ring-blue-500/50"
                        : "bg-slate-800/50 border-slate-700/80 hover:bg-slate-800 hover:border-slate-600"
                    }`}
                  >
                    <input
                      type="radio"
                      name="filing_branch"
                      checked={isSelected}
                      onChange={() => setSelectedBranch(b.id)}
                      className="mt-1 w-4 h-4 text-blue-600 bg-slate-700 border-slate-600 focus:ring-blue-500"
                    />

                    <div className="flex-1 space-y-1">
                      <div className="flex items-center justify-between">
                        <span className={`text-sm font-medium ${isSelected ? "text-blue-300" : "text-white"}`}>
                          {b.title}
                        </span>
                        <div className="flex items-center gap-1.5">
                          {isAIRecommended && (
                            <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
                              <Sparkles className="w-2.5 h-2.5" /> AI Recommended
                            </span>
                          )}
                          <span className="text-[11px] font-mono text-slate-400 bg-slate-900 px-2 py-0.5 rounded border border-slate-700">
                            {b.section}
                          </span>
                        </div>
                      </div>
                      <p className="text-xs text-slate-400">
                        {b.description}
                      </p>

                      {/* Sub-reason radio for Casual Vacancy */}
                      {isSelected && b.id === "Casual Vacancy" && (
                        <div className="mt-3 pt-3 border-t border-blue-500/20 flex items-center gap-4">
                          <span className="text-xs font-medium text-slate-300">Vacancy Reason:</span>
                          {["Resignation", "Death", "Disqualification"].map((reason) => (
                            <label key={reason} className="flex items-center gap-1.5 text-xs text-slate-200 cursor-pointer">
                              <input
                                type="radio"
                                name="sub_reason"
                                value={reason}
                                checked={selectedSubReason === reason}
                                onChange={(e) => setSelectedSubReason(e.target.value)}
                                className="w-3.5 h-3.5 text-blue-500"
                              />
                              {reason}
                            </label>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-850 flex items-center justify-between">
          <div className="text-xs text-slate-400 flex items-center gap-1.5">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>Prunes 100% of irrelevant branch fields from final form</span>
          </div>

          <div className="flex items-center gap-2.5">
            <button
              onClick={onClose}
              disabled={isExtracting}
              className="px-4 py-2 rounded-xl text-xs font-medium text-slate-300 hover:text-white hover:bg-slate-800 transition"
            >
              Cancel
            </button>
            <button
              onClick={handleConfirm}
              disabled={isExtracting}
              className="px-5 py-2 rounded-xl text-xs font-semibold bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white shadow-lg shadow-blue-500/20 flex items-center gap-2 transition disabled:opacity-50"
            >
              {isExtracting ? (
                <span>Extracting Branch Data...</span>
              ) : (
                <>
                  <span>Confirm & Extract Data</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </>
              )}
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
