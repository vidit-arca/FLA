import React, { useRef, useState, useMemo, useEffect } from 'react';
import { LayoutDashboard, UploadCloud, Loader2, Save, CornerDownRight, Filter, AlertCircle, Sparkles, CheckCircle2 } from 'lucide-react';
import { idpClient } from '../api/idpClient';

export default function FormTemplateViewer({ 
  templateId, 
  onTemplateChange, 
  templates, 
  currentSchema, 
  rules, 
  selectedExtractedData, 
  onLinkField, 
  onDeleteRule, 
  onTemplateUploaded, 
  onSaveMappings, 
  isSavingMappings,
  activeSelections: externalSelections = null,
  onOptionSelect = null
}) {
  const fileInputRef = useRef(null);
  const [isUploading, setIsUploading] = useState(false);
  // Internal state fallback if external selections not provided
  const [internalSelections, setInternalSelections] = useState({});
  const activeSelections = externalSelections || internalSelections;
  const [showAllFields, setShowAllFields] = useState(false);

  // When schema changes, reset selections and log to console for debugging
  useEffect(() => {
    if (!externalSelections) {
      setInternalSelections({});
    }
    if (currentSchema?.fields?.length > 0) {
      const deps = currentSchema.fields.filter(f => f.depends_on);
      console.log(`[IDP] Schema: ${currentSchema.fields.length} fields, ${deps.length} conditional`, deps.map(f => `${f.id} → ${f.depends_on?.field}==${f.depends_on?.value}`));
    }
  }, [currentSchema]);

  const handleFileUpload = async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      
      setIsUploading(true);
      try {
          const res = await idpClient.uploadTemplate(file);
          alert(`✓ Successfully ingested ${res.fields ? res.fields.length : 0} fields from Instruction Kit!`);
          if (onTemplateUploaded) await onTemplateUploaded();
          if (res.template_name) onTemplateChange(res.template_name);
      } catch (err) {
          console.error("Failed to upload instruction kit", err);
          alert("Failed to parse template. Make sure it's a valid MCA Instruction Kit PDF.");
      } finally {
          setIsUploading(false);
          if (fileInputRef.current) fileInputRef.current.value = "";
      }
  };

  const fields = currentSchema?.fields || [];

  const handleOptionSelect = (fieldId, optionValue) => {
    if (!externalSelections) {
      setInternalSelections(prev => ({
        ...prev,
        [fieldId]: optionValue
      }));
    }
    if (onOptionSelect) {
      onOptionSelect(fieldId, optionValue);
    }
  };

  // hasConditionalFields: true if ANY field has a depends_on, controls UI toggle
  const hasConditionalFields = useMemo(() => fields.some(f => !!f.depends_on), [fields]);

  // Evaluate whether a field is conditionally visible (memoized and robust)
  const isFieldVisible = useMemo(() => {
    return (field) => {
      if (showAllFields) return true;
      if (!field || !field.depends_on) return true;

      const { field: parentId, operator, value } = field.depends_on;
      if (!parentId) return true;

      // Check active selections for parent
      let parentVal = activeSelections[parentId];
      if (parentVal === undefined) {
        // Fallback matching by key/id substring
        for (const [k, v] of Object.entries(activeSelections)) {
          if (k === parentId || parentId.includes(k) || k.includes(parentId)) {
            parentVal = v;
            break;
          }
        }
      }

      // If still not in activeSelections, check mapped rules
      if (parentVal === undefined) {
        const parentRule = (rules || []).find(r => 
          r.form_field === parentId || r.form_field?.includes(parentId) || parentId.includes(r.form_field)
        );
        if (parentRule && parentRule.extracted_key) {
          parentVal = parentRule.extracted_key;
        }
      }

      // If parent has no value yet, default to hiding dependent child
      if (parentVal === undefined || parentVal === null || parentVal === '') {
        return false;
      }

      const currentStr = String(parentVal).trim().toLowerCase();
      const targetStr = String(value || '').trim().toLowerCase();

      if (operator === 'equals') {
        return currentStr === targetStr || currentStr.includes(targetStr) || targetStr.includes(currentStr);
      }
      if (operator === 'in' && Array.isArray(value)) {
        return value.map(v => String(v).toLowerCase()).includes(currentStr);
      }
      if (operator === 'exists') {
        return !!parentVal;
      }
      return true;
    };
  }, [activeSelections, showAllFields, rules]);

  // Group fields hierarchically: dependent child fields appear IMMEDIATELY below their parent!
  const hierarchicalFields = useMemo(() => {
    if (!fields || !Array.isArray(fields)) return [];

    const fieldMap = new Map();
    fields.forEach(f => {
      if (f.id) fieldMap.set(f.id, f);
      if (f.name) fieldMap.set(f.name, f);
      if (f.key) fieldMap.set(f.key, f);
    });

    const parentMap = new Map();
    const roots = [];

    fields.forEach(f => {
      const parentId = f.depends_on?.field;
      if (parentId) {
        let realParentId = parentId;
        if (!fieldMap.has(parentId)) {
          for (const [k, v] of fieldMap.entries()) {
            if (k === parentId || k.includes(parentId) || parentId.includes(k)) {
              realParentId = v.id || v.name || v.key;
              break;
            }
          }
        }
        if (!parentMap.has(realParentId)) {
          parentMap.set(realParentId, []);
        }
        parentMap.get(realParentId).push(f);
      } else {
        roots.push(f);
      }
    });

    const result = [];
    const addNode = (node, depth = 0) => {
      result.push({ ...node, _depth: depth });
      const nodeKeys = [node.id, node.name, node.key].filter(Boolean);
      let children = [];
      for (const nk of nodeKeys) {
        if (parentMap.has(nk)) {
          children = parentMap.get(nk);
          break;
        }
      }
      children.forEach(child => {
        if (isFieldVisible(child)) {
          addNode(child, depth + 1);
        }
      });
    };

    // Root fields (no depends_on) always shown
    roots.forEach(root => {
      addNode(root, 0);
    });

    return result;
  }, [fields, isFieldVisible]);

  const getTypeBadge = (type) => {
    switch ((type || '').toLowerCase()) {
      case 'radio':
        return <span className="text-[0.6rem] font-bold px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30">RADIO</span>;
      case 'select':
        return <span className="text-[0.6rem] font-bold px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30">SELECT</span>;
      case 'date':
        return <span className="text-[0.6rem] font-bold px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">DATE</span>;
      case 'number':
        return <span className="text-[0.6rem] font-bold px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">NUMBER</span>;
      case 'file':
        return <span className="text-[0.6rem] font-bold px-1.5 py-0.5 rounded bg-pink-500/20 text-pink-300 border border-pink-500/30">ATTACHMENT</span>;
      default:
        return <span className="text-[0.6rem] font-bold px-1.5 py-0.5 rounded bg-slate-500/20 text-slate-300 border border-slate-500/30">TEXT</span>;
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
        <p className="text-xs text-slate-400 mt-1 font-medium line-clamp-2">
          {currentSchema?.governing_law ? (
            <span className="text-indigo-400 font-semibold">{currentSchema.governing_law}</span>
          ) : (
            "Select or upload an official MCA Instruction Kit to populate form schema."
          )}
        </p>
        
        <div className="mt-4 flex flex-col gap-2.5">
            <button 
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploading}
                className="w-full p-2.5 bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 hover:bg-indigo-500/20 rounded-lg transition-colors flex items-center justify-center gap-2 font-medium disabled:opacity-50 text-xs shadow-sm"
                title="Upload official MCA Instruction Kit PDF"
            >
                {isUploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <UploadCloud className="w-4 h-4" />}
                {isUploading ? "Ingesting Instruction Kit..." : "Upload MCA Instruction Kit"}
            </button>
            <input 
                type="file" 
                ref={fileInputRef} 
                onChange={handleFileUpload} 
                accept=".pdf" 
                className="hidden" 
            />

            {/* Filter Toggle for Dynamic Branching */}
            {hasConditionalFields && (
              <div className="flex items-center justify-between px-2 py-1.5 bg-black/20 rounded-lg border border-white/5 text-[0.7rem]">
                <span className="text-slate-400 flex items-center gap-1.5">
                  <Filter className="w-3 h-3 text-indigo-400" />
                  <span>Dynamic View:</span>
                </span>
                <button
                  onClick={() => setShowAllFields(!showAllFields)}
                  className={`px-2 py-0.5 rounded-md font-semibold transition-colors text-[0.65rem] ${
                    showAllFields 
                      ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' 
                      : 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30'
                  }`}
                >
                  {showAllFields ? 'Showing All Fields' : 'Active Branch Only'}
                </button>
              </div>
            )}
        </div>

        {/* SAVE FORM MAPPINGS ACTION BUTTON */}
        {onSaveMappings && (
          <button
            onClick={onSaveMappings}
            disabled={isSavingMappings || (rules?.length || 0) === 0}
            className="w-full mt-3 py-2 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/20 rounded-lg font-semibold flex justify-center items-center gap-2 transition-colors disabled:opacity-50 text-xs"
          >
            {isSavingMappings ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Saving Mappings...</span>
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

      <div className="flex-1 overflow-y-auto p-4 space-y-2.5">
        {!currentSchema && (
            <div className="flex flex-col items-center justify-center text-center p-8 mt-10">
                <div className="w-12 h-12 bg-indigo-500/10 text-indigo-400 rounded-xl flex items-center justify-center mb-4 border border-indigo-500/20">
                    <UploadCloud className="w-6 h-6" />
                </div>
                <h4 className="text-sm font-bold text-white mb-2">No Form Loaded</h4>
                <p className="text-xs text-slate-400">
                    Upload an <strong>MCA Instruction Kit PDF</strong> above to auto-generate the complete validated form schema with dynamic branching.
                </p>
            </div>
        )}

        {currentSchema && fields.length === 0 && (
            <div className="flex flex-col items-center justify-center text-center p-8 mt-10">
                <div className="w-12 h-12 bg-amber-500/10 text-amber-400 rounded-xl flex items-center justify-center mb-4 border border-amber-500/20">
                    <AlertCircle className="w-6 h-6" />
                </div>
                <h4 className="text-sm font-bold text-white mb-2">Empty Template</h4>
                <p className="text-xs text-slate-400">
                    No fields found in template. Re-upload the Instruction Kit PDF.
                </p>
            </div>
        )}

        {hierarchicalFields.map(field => {
          const rule = (rules || []).find(r => r.form_field === field.id);
          const isMapped = !!rule;
          const activeChoice = activeSelections[field.id];
          const isNoSelected = (activeChoice && String(activeChoice).toLowerCase() === 'no') || (rule && String(rule.extracted_value || rule.extracted_key).toLowerCase() === 'no');
          const isSatisfied = isMapped || isNoSelected;
          const isLinkable = selectedExtractedData && !rule && !isNoSelected;
          const depth = field._depth || 0;
          const isDependent = depth > 0;

          return (
            <div 
              key={field.id}
              onClick={() => {
                  if (isLinkable) onLinkField(field.id);
              }}
              style={{ marginLeft: depth > 0 ? `${depth * 18}px` : undefined }}
              className={`p-3 rounded-xl border transition-all duration-200 relative ${
                isDependent ? 'border-l-4 border-l-indigo-500 bg-indigo-500/[0.03]' : ''
              } ${
                isSatisfied 
                  ? 'border-emerald-500/30 bg-emerald-500/5' 
                  : isLinkable 
                      ? 'border-indigo-400 cursor-pointer bg-indigo-500/10 shadow-[0_0_15px_rgba(99,102,241,0.2)] transform scale-[1.01]' 
                      : 'border-white/5 bg-black/10'
              }`}
            >
              <div className="flex flex-col gap-1.5">
                {/* Header line: Canonical number, label, type badge */}
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5 overflow-hidden">
                    {isDependent && (
                      <CornerDownRight className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                    )}
                    {field.canonical_no && (
                      <span className="text-[0.65rem] font-mono font-bold px-1.5 py-0.5 rounded bg-white/10 text-slate-200 shrink-0">
                        {field.canonical_no}
                      </span>
                    )}
                    <label className={`text-xs font-bold uppercase tracking-wider truncate ${
                      isSatisfied ? 'text-emerald-400' : isLinkable ? 'text-indigo-400' : 'text-slate-200'
                    }`} title={field.label}>
                      {field.label}
                    </label>
                  </div>
                  {getTypeBadge(field.type)}
                </div>

                {/* Conditional Dependency Tag */}
                {isDependent && field.depends_on && (
                  <div className="text-[0.65rem] text-indigo-300/90 bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20 w-fit flex items-center gap-1">
                    <Sparkles className="w-2.5 h-2.5 text-indigo-400" />
                    <span>Revealed by: {field.depends_on.value}</span>
                  </div>
                )}

                {/* Interactive Radio / Select Option Pills */}
                {field.options && field.options.length > 0 && (
                  <div className="mt-1 flex flex-wrap gap-1.5 pt-0.5">
                    {field.options.map(opt => {
                      const isSelected = activeChoice === opt;
                      return (
                        <button
                          key={opt}
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleOptionSelect(field.id, opt);
                          }}
                          className={`text-[0.7rem] px-2.5 py-1 rounded-md font-medium transition-all ${
                            isSelected 
                              ? 'bg-indigo-600 text-white font-bold shadow-md ring-2 ring-indigo-400' 
                              : 'bg-black/40 hover:bg-white/10 text-slate-300 border border-white/5'
                          }`}
                        >
                          {opt}
                        </button>
                      );
                    })}
                  </div>
                )}
                
                {/* Mapped State or Unmapped Action Slot */}
                {rule ? (
                    <div className="mt-1.5 flex items-center justify-between bg-black/30 p-2 rounded-lg border border-white/5">
                        <div className="flex flex-col overflow-hidden">
                            <div className="flex items-center gap-1.5 mb-0.5 flex-wrap">
                                <span className="text-[0.65rem] text-slate-400">Linked to:</span>
                                {rule.scope_type === 'COMPANY' ? (
                                    <span className="text-[0.6rem] font-bold px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                                        Company ({rule.scope_id})
                                    </span>
                                ) : rule.scope_type === 'SCENARIO' ? (
                                    <span className="text-[0.6rem] font-bold px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30">
                                        Scenario ({rule.scope_id})
                                    </span>
                                ) : (
                                    <span className="text-[0.6rem] font-bold px-1.5 py-0.5 rounded bg-slate-500/20 text-slate-300 border border-slate-500/30">
                                        Global
                                    </span>
                                )}
                                {rule.source === 'markdown_ast' ? (
                                    <span className="text-[0.6rem] font-bold px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400">
                                        DOM ({Math.round((rule.confidence || 0.98) * 100)}%)
                                    </span>
                                ) : (
                                    <span className="text-[0.6rem] font-bold px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-400">
                                        Spatial ({Math.round((rule.confidence || 0.85) * 100)}%)
                                    </span>
                                )}
                            </div>

                            <span className="text-xs font-medium text-slate-200 truncate" title={rule.extracted_key}>
                              "{rule.extracted_key}"
                            </span>
                        </div>
                        <button 
                            onClick={(e) => { e.stopPropagation(); onDeleteRule(rule.rule_id); }}
                            className="text-xs text-red-400 hover:text-red-300 font-medium px-2 py-1 transition-colors"
                        >
                            Unlink
                        </button>
                    </div>
                ) : isNoSelected ? (
                    <div className="mt-1.5 flex items-center justify-between bg-slate-800/40 p-2 rounded-lg border border-slate-700/60">
                        <div className="flex items-center gap-2">
                            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                            <span className="text-xs font-bold text-slate-200">
                                Selected: <span className="text-white font-mono bg-slate-700 px-1.5 py-0.5 rounded">No</span>
                            </span>
                            <span className="text-[0.65rem] text-slate-400 bg-slate-800/80 px-2 py-0.5 rounded font-medium border border-slate-700">
                                No document mapping required
                            </span>
                        </div>
                    </div>
                ) : (
                    <div className="bg-black/20 border border-white/5 rounded-lg p-1.5 min-h-[32px] flex items-center justify-center mt-1">
                        <span className="text-xs italic text-slate-500 font-medium">
                            {isLinkable ? 'Click to link selected text' : (String(activeChoice).toLowerCase() === 'yes' ? 'Requires document mapping (Select text from document)' : 'Unmapped')}
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
