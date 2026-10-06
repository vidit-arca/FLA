import React, { useRef, useState } from 'react';
import { LayoutDashboard, UploadCloud, Loader2, Save } from 'lucide-react';
import { idpClient } from '../api/idpClient';

export default function FormTemplateViewer({ templateId, onTemplateChange, templates, currentSchema, rules, selectedExtractedData, onLinkField, onDeleteRule, onTemplateUploaded, onSaveMappings, isSavingMappings }) {
  
  const fileInputRef = useRef(null);
  const [isUploading, setIsUploading] = useState(false);

  const handleFileUpload = async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      
      setIsUploading(true);
      try {
          const res = await idpClient.uploadTemplate(file);
          alert(`✓ Successfully extracted ${res.fields.length} field labels from PDF!`);
          if (onTemplateUploaded) await onTemplateUploaded();
          onTemplateChange(res.template_name); // Switch to the newly uploaded template
      } catch (err) {
          console.error("Failed to upload template", err);
          alert("Failed to upload template. Make sure it's a valid PDF file.");
      } finally {
          setIsUploading(false);
          if (fileInputRef.current) fileInputRef.current.value = "";
      }
  };

  return (
    <div className="w-full h-full bg-transparent flex flex-col shrink-0">
      <div className="p-5 border-b border-white/5 bg-white/5 relative">
        <button 
          onClick={() => window.close()}
          className="absolute top-5 right-5 text-slate-400 hover:text-white transition-colors"
          title="Exit Studio"
        >
          <LayoutDashboard className="w-4 h-4" />
        </button>
        <h2 className="text-lg font-bold text-white pr-6">Form Template</h2>
        <p className="text-xs text-slate-400 mt-1 font-medium">Select a target form template to map extracted PDF values to.</p>
        
        <div className="mt-4 flex flex-col gap-3">
            <button 
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploading}
                className="w-full p-2.5 bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 hover:bg-indigo-500/20 rounded-lg transition-colors flex items-center justify-center gap-2 font-medium disabled:opacity-50"
                title="Upload new form template PDF"
            >
                {isUploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <UploadCloud className="w-4 h-4" />}
                {isUploading ? "Uploading Template..." : "Upload New Form Template"}
            </button>
            <input 
                type="file" 
                ref={fileInputRef} 
                onChange={handleFileUpload}
                accept=".pdf" 
                className="hidden" 
            />
        </div>

          {/* SAVE FORM MAPPINGS ACTION BUTTON */}
          {onSaveMappings && (
            <button
              onClick={onSaveMappings}
              disabled={isSavingMappings || (rules?.length || 0) === 0}
              className="w-full mt-3 py-2 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/20 rounded-lg font-semibold flex justify-center items-center gap-2 transition-colors disabled:opacity-50"
            >
              {isSavingMappings ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Saving...</span>
                </>
              ) : (
                <>
                  <Save className="w-4 h-4" />
                  <span>Save Form Mappings ({rules ? rules.length : 0})</span>
                </>
              )}
            </button>
          )}
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {!currentSchema && (
            <div className="flex flex-col items-center justify-center text-center p-8 mt-10">
                <div className="w-12 h-12 bg-indigo-50 dark:bg-indigo-500/10 text-indigo-500 rounded-xl flex items-center justify-center mb-4">
                    <UploadCloud className="w-6 h-6" />
                </div>
                <h4 className="text-sm font-bold text-slate-900 dark:text-white mb-2">No Template Found</h4>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                    Click the upload icon above to upload a <strong>PDF form</strong> — the left-side field labels will be extracted automatically.
                </p>
            </div>
        )}
        {currentSchema && currentSchema.fields.length === 0 && (
            <div className="flex flex-col items-center justify-center text-center p-8 mt-10">
                <div className="w-12 h-12 bg-amber-50 dark:bg-amber-500/10 text-amber-500 rounded-xl flex items-center justify-center mb-4">
                    <UploadCloud className="w-6 h-6" />
                </div>
                <h4 className="text-sm font-bold text-slate-900 dark:text-white mb-2">Empty Template</h4>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                    No field labels could be extracted from the uploaded PDF. Ensure the PDF has readable left-side labels.
                </p>
            </div>
        )}
        {currentSchema && currentSchema.fields.map(field => {
          const rule = rules.find(r => r.form_field === field.id);
          const isMapped = !!rule;
          const isLinkable = selectedExtractedData && !rule;
          
          return (
            <div 
              key={field.id}
              onClick={() => {
                  if (isLinkable) onLinkField(field.id);
              }}
              className={`p-4 rounded-xl border transition-all duration-200 ${
                isMapped 
                  ? 'border-emerald-500/30 bg-emerald-500/5' 
                  : isLinkable 
                      ? 'border-indigo-400 cursor-pointer bg-indigo-500/10 shadow-[0_0_15px_rgba(99,102,241,0.2)] transform scale-[1.02]'
                      : 'border-white/5 bg-black/10'
              }`}
            >
              <div className="flex flex-col gap-1">
                <label className={`text-xs font-bold uppercase tracking-wider block ${
                  isMapped ? 'text-emerald-400' : isLinkable ? 'text-indigo-400' : 'text-slate-400'
                }`}>
                  {field.label}
                </label>
                
                {rule ? (
                    <div className="mt-2 flex items-center justify-between bg-black/20 p-2 rounded border border-white/5">
                        <div className="flex flex-col overflow-hidden">
                            <div className="flex items-center gap-1.5 mb-0.5">
                                <span className="text-[0.65rem] text-slate-400">Linked to:</span>
                                {rule.source === 'markdown_ast' ? (
                                    <span className="text-[0.6rem] font-bold px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400">
                                        Markdown ({Math.round((rule.confidence || 0.98) * 100)}%)
                                    </span>
                                ) : (
                                    <span className="text-[0.6rem] font-bold px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400">
                                        Spatial ({Math.round((rule.confidence || 0.85) * 100)}%)
                                    </span>
                                )}
                            </div>
                            <span className="text-sm font-medium text-slate-200 truncate" title={rule.extracted_key}>"{rule.extracted_key}"</span>
                        </div>
                        <button 
                            onClick={(e) => { e.stopPropagation(); onDeleteRule(rule.rule_id); }}
                            className="text-xs text-red-400 hover:text-red-300 font-medium px-2 py-1"
                        >
                            Unlink
                        </button>
                    </div>

                ) : (
                    <div className="bg-black/30 border border-white/5 rounded-lg p-2.5 min-h-[40px] flex items-center justify-center">
                        <span className="text-sm italic text-slate-500 font-medium">
                            {isLinkable ? 'Click to link selected data' : 'Unmapped'}
                        </span>
                    </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
