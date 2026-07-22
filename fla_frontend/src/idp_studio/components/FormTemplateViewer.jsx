import React, { useRef, useState } from 'react';
import { LayoutDashboard, UploadCloud, Loader2 } from 'lucide-react';
import { idpClient } from '../api/idpClient';

export default function FormTemplateViewer({ templateId, onTemplateChange, templates, currentSchema, rules, selectedExtractedData, onLinkField, onDeleteRule, onTemplateUploaded }) {
  
  const fileInputRef = useRef(null);
  const [isUploading, setIsUploading] = useState(false);

  const handleFileUpload = async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      
      setIsUploading(true);
      try {
          const res = await idpClient.uploadTemplate(file);
          alert(`Successfully parsed ${res.fields.length} fields from Excel!`);
          if (onTemplateUploaded) await onTemplateUploaded();
          onTemplateChange(res.template_name); // Switch to the newly uploaded template
      } catch (err) {
          console.error("Failed to upload template", err);
          alert("Failed to upload template. Make sure it's a valid Excel file.");
      } finally {
          setIsUploading(false);
          if (fileInputRef.current) fileInputRef.current.value = "";
      }
  };

  return (
    <div className="w-80 h-full bg-white dark:bg-[#1A2234] border-r border-slate-200 dark:border-white/10 flex flex-col shrink-0">
      <div className="p-5 border-b border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 relative">
        <button 
          onClick={() => window.close()}
          className="absolute top-5 right-5 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition-colors"
          title="Exit Studio"
        >
          <LayoutDashboard className="w-4 h-4" />
        </button>
        <h2 className="text-lg font-bold text-slate-800 dark:text-white pr-6">Form Template</h2>
        <p className="text-xs text-slate-500 mt-1">Select a target form template to map extracted PDF values to.</p>
        
        <div className="mt-4">
          <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Target Form Schema</label>
          <div className="flex gap-2">
              <select 
                value={templateId}
                onChange={(e) => onTemplateChange(e.target.value)}
                className="flex-1 bg-white dark:bg-[#0F1523] border border-slate-200 dark:border-white/10 rounded-lg px-3 py-2 text-sm text-slate-700 dark:text-slate-300 focus:outline-none focus:border-indigo-500 cursor-pointer"
              >
                {templates && templates.map(schema => (
                    <option key={schema.template_id} value={schema.template_name}>{schema.template_name}</option>
                ))}
                {(!templates || templates.length === 0) && (
                    <option value="">No templates found</option>
                )}
              </select>
              
              <button 
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isUploading}
                  className="px-3 py-2 bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-500/20 rounded-lg hover:bg-indigo-100 dark:hover:bg-indigo-500/20 transition-colors flex items-center justify-center"
                  title="Upload New Excel Schema"
              >
                  {isUploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <UploadCloud className="w-4 h-4" />}
              </button>
              <input 
                  type="file" 
                  ref={fileInputRef} 
                  onChange={handleFileUpload} 
                  accept=".xlsx, .xls" 
                  className="hidden" 
              />
          </div>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {!currentSchema && (
            <div className="flex flex-col items-center justify-center text-center p-8 mt-10">
                <div className="w-12 h-12 bg-indigo-50 dark:bg-indigo-500/10 text-indigo-500 rounded-xl flex items-center justify-center mb-4">
                    <UploadCloud className="w-6 h-6" />
                </div>
                <h4 className="text-sm font-bold text-slate-900 dark:text-white mb-2">No Template Found</h4>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                    Click the upload icon above to upload an Excel (.xlsx) file containing your target form fields.
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
                    The uploaded Excel file didn't contain any recognizable fields.
                </p>
            </div>
        )}
        {currentSchema && currentSchema.fields.map(field => {
          const rule = rules.find(r => r.form_field === field.id);
          const canLink = selectedExtractedData && !rule;
          
          return (
            <div 
              key={field.id}
              onClick={() => {
                  if (canLink) onLinkField(field.id);
              }}
              className={`p-3 rounded-lg border transition-all ${
                rule 
                  ? 'bg-emerald-50/50 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/30' 
                  : canLink 
                      ? 'bg-indigo-50 dark:bg-indigo-500/10 border-indigo-300 dark:border-indigo-500/50 cursor-pointer hover:shadow-md'
                      : 'bg-white dark:bg-transparent border-slate-200 dark:border-white/10'
              }`}
            >
              <div className="flex flex-col gap-1">
                <span className="text-xs font-semibold text-slate-500 uppercase">{field.label}</span>
                
                {rule ? (
                    <div className="mt-2 flex items-center justify-between bg-white dark:bg-[#0B0F19] p-2 rounded border border-emerald-100 dark:border-emerald-500/20">
                        <div className="flex flex-col overflow-hidden">
                            <span className="text-[0.65rem] text-slate-400">Linked to PDF Key:</span>
                            <span className="text-sm font-medium text-slate-700 dark:text-slate-300 truncate" title={rule.extracted_key}>"{rule.extracted_key}"</span>
                        </div>
                        <button 
                            onClick={(e) => { e.stopPropagation(); onDeleteRule(rule.rule_id); }}
                            className="text-xs text-red-500 hover:text-red-700 font-medium px-2 py-1"
                        >
                            Unlink
                        </button>
                    </div>
                ) : (
                    <div className="h-8 border border-dashed border-slate-300 dark:border-slate-600 rounded flex items-center justify-center mt-1 bg-slate-50 dark:bg-white/5">
                        <span className="text-xs text-slate-400 font-medium italic">
                            {canLink ? 'Click to link selected data' : 'Unmapped'}
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
