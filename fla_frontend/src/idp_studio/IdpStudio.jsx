import React, { useState, useEffect } from 'react';
import PdfCanvas from './components/PdfCanvas';
import FormTemplateViewer from './components/FormTemplateViewer';
import ExtractedDataSidebar from './components/ExtractedDataSidebar';
import StructuredDocumentViewer from './components/StructuredDocumentViewer';
import { idpClient } from './api/idpClient';
import { LayoutDashboard, CheckCircle, AlertCircle, Cpu, X, Database, Loader2, Download } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export default function IdpStudio() {
  const navigate = useNavigate();
  
  // 3-Step Wizard State
  const [currentStep, setCurrentStep] = useState('extract'); // 'extract' | 'map' | 'preview'
  
  const [rules, setRules] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [templateName, setTemplateName] = useState("");
  const [currentSchema, setCurrentSchema] = useState(null);
  
  // Test FLA Logic State
  const [testFlaResult, setTestFlaResult] = useState(null);
  const [isTestingFla, setIsTestingFla] = useState(false);
  const [isGeneratingExcel, setIsGeneratingExcel] = useState(false);

  // Extraction State
  const [extractedData, setExtractedData] = useState([]);
  const [isExtracting, setIsExtracting] = useState(false);
  const [showPdfPanel, setShowPdfPanel] = useState(false);
  const [selectedExtractedData, setSelectedExtractedData] = useState(null);
  const [pdfFile, setPdfFile] = useState(null);

  // Multi-Document Batch State
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [activeFileIndex, setActiveFileIndex] = useState(0);

  useEffect(() => {
    if (uploadedFiles && uploadedFiles.length > 0 && uploadedFiles[activeFileIndex]) {
      setPdfFile(uploadedFiles[activeFileIndex].file);
      setExtractedData(uploadedFiles[activeFileIndex].data || []);
    } else {
      setPdfFile(null);
      setExtractedData([]);
    }
  }, [uploadedFiles, activeFileIndex]);


  useEffect(() => {
    fetchTemplates();
  }, []);

  useEffect(() => {
    if (templateName) {
      fetchRules();
      const schema = templates.find(t => t.template_name === templateName);
      if (schema) {
          try {
              let parsedFields = [];
              if (typeof schema.fields_json === 'string') {
                  parsedFields = JSON.parse(schema.fields_json);
              } else {
                  parsedFields = schema.fields_json;
              }
              
              setCurrentSchema({
                  id: schema.template_name,
                  name: schema.template_name,
                  fields: parsedFields
              });
          } catch (e) {
              console.error("Failed to parse fields_json for schema", schema.template_name, e);
              setCurrentSchema({
                  id: schema.template_name,
                  name: schema.template_name,
                  fields: []
              });
          }
      } else {
          setCurrentSchema(null);
      }
    } else {
        setCurrentSchema(null);
    }
  }, [templateName, templates]);

  const fetchTemplates = async () => {
    try {
        const data = await idpClient.getTemplates();
        setTemplates(data);
        if (data.length > 0 && !templateName) {
            setTemplateName(data[0].template_name);
        }
    } catch (err) {
        console.error("Failed to fetch templates", err);
    }
  };

  const fetchRules = async () => {
    try {
      const data = await idpClient.getRules(templateName);
      setRules(data);
    } catch (err) {
      console.error("Failed to fetch rules", err);
    }
  };

  const handleDocumentUpload = async (filesInput) => {
      if (!filesInput || (Array.isArray(filesInput) && filesInput.length === 0)) {
          setUploadedFiles([]);
          setPdfFile(null);
          setExtractedData([]);
          setSelectedExtractedData(null);
          return;
      }
      
      const fileArray = Array.isArray(filesInput) ? filesInput : [filesInput];

      const newQueue = fileArray.map(file => ({
          file: file,
          status: 'loading',
          data: []
      }));
      
      setUploadedFiles(prev => [...prev, ...newQueue]);
      setActiveFileIndex(0);
      setIsExtracting(true);
      setSelectedExtractedData(null);

      try {
          for (let i = 0; i < fileArray.length; i++) {
              const currentFile = fileArray[i];
              try {
                  await idpClient.processDocument(currentFile);
                  setUploadedFiles(prev => prev.map(item => 
                      item.file.name === currentFile.name ? { ...item, status: 'ready' } : item
                  ));
              } catch (fileErr) {
                  console.error(`Failed to process document OCR for ${currentFile.name}`, fileErr);
                  alert(`Server Error processing ${currentFile.name}: ${fileErr.response?.data?.detail || fileErr.message}`);
                  setUploadedFiles(prev => prev.map(item => 
                      item.file.name === currentFile.name ? { ...item, status: 'error' } : item
                  ));
              }
          }
      } finally {
          setIsExtracting(false);
      }
  };

  const handleSelectDocument = (index) => {
      setActiveFileIndex(index);
      setSelectedExtractedData(null);
  };


  const handlePairExtracted = (file, pair) => {
      if (!file || !pair) return;
      
      const newData = {
          key: pair.key.substring(0, 120),
          value: pair.value,
          source: "ai_cell_selection"
      };
      
      setExtractedData(prev => [...prev, newData]);
  };

  const [isSavingMappings, setIsSavingMappings] = useState(false);

  const handleLinkField = (formFieldId) => {
    if (!selectedExtractedData) return;

    const newRule = {
      rule_id: `temp_${Date.now()}`,
      template_name: templateName,
      form_field: formFieldId,
      extracted_key: selectedExtractedData.key,
      extracted_value: selectedExtractedData.value,
      spatial_meta: selectedExtractedData._spatial_meta
    };

    setRules(prev => {
      const filtered = prev.filter(r => r.form_field !== formFieldId);
      return [...filtered, newRule];
    });
    setSelectedExtractedData(null);
  };

  const handleSaveAllMappings = async () => {
    if (!rules || rules.length === 0) {
      alert("No mapped fields to save! Please map fields first using the Map to Form step.");
      return;
    }

    setIsSavingMappings(true);
    try {
      const res = await idpClient.saveRulesBatch(templateName, rules, pdfFile);
      alert(`✓ Successfully saved ${res.saved_count} form rules and learned DOM structural paths for '${templateName}'!`);
      await fetchRules();
    } catch (err) {
      console.error("Failed to save rules batch", err);
      alert("Failed to save form mappings. Ensure backend is running.");
    } finally {
      setIsSavingMappings(false);
    }
  };

  const handleTestFla = async () => {
    const payload = {};
    if (currentSchema && currentSchema.fields) {
        currentSchema.fields.forEach(field => {
            const rule = rules.find(r => r.form_field === field.id);
            if (rule) {
                const extractedItem = extractedData.find(e => e.key === rule.extracted_key);
                if (extractedItem) {
                    payload[field.id] = extractedItem.value;
                } else {
                    payload[field.id] = rule.extracted_key;
                }
            }
        });
    }

    if (Object.keys(payload).length === 0) {
        alert("No mapped fields to test! Please map fields first.");
        return;
    }

    setIsTestingFla(true);
    try {
        const result = await idpClient.testFlaEngine(payload);
        setTestFlaResult(result);
    } catch (err) {
        console.error("Failed to test FLA engine", err);
        alert("Failed to run FLA Logic Engine. Ensure backend is running.");
    } finally {
        setIsTestingFla(false);
    }
  };

  const handleGenerateExcel = async () => {
    const payload = {};
    if (currentSchema && currentSchema.fields) {
        currentSchema.fields.forEach(field => {
            const rule = rules.find(r => r.form_field === field.id);
            if (rule) {
                const extractedItem = extractedData.find(e => e.key === rule.extracted_key);
                if (extractedItem) {
                    payload[field.id] = extractedItem.value;
                } else {
                    payload[field.id] = rule.extracted_key;
                }
            }
        });
    }

    if (Object.keys(payload).length === 0) {
        alert("No mapped fields to generate Excel from! Please map fields first.");
        return;
    }

    setIsGeneratingExcel(true);
    try {
        await idpClient.generateExcel(payload);
        alert("✓ Successfully generated and downloaded FLA Return Populated.xlsx!");
    } catch (err) {
        console.error("Failed to generate Excel", err);
        alert("Failed to generate populated Excel. Ensure backend is running.");
    } finally {
        setIsGeneratingExcel(false);
    }
  };

  const handleDeleteRule = async (ruleId) => {
    try {
      if (!ruleId.startsWith('temp_')) {
        await idpClient.deleteRule(ruleId);
      }
      setRules(prev => prev.filter(r => r.rule_id !== ruleId));
    } catch (err) {
      console.error("Failed to delete rule", err);
    }
  };

  const renderTopBar = () => (
    <div className="absolute top-0 left-0 right-0 h-16 bg-[#0F172A]/80 backdrop-blur-md border-b border-white/5 flex items-center justify-between px-6 z-10 shadow-sm">
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-3 text-lg font-bold text-white tracking-wide border-r border-white/10 pr-6">
          <LayoutDashboard className="w-5 h-5 text-indigo-400" />
          IDP Studio
        </div>
        
        {/* Global Target Form Selector */}
        <div className="flex items-center gap-3">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Target Form:</span>
          <select 
            value={templateName}
            onChange={(e) => setTemplateName(e.target.value)}
            className="appearance-none bg-black/20 border border-white/10 text-indigo-300 text-sm font-semibold rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 block px-3 py-1.5 min-w-[200px] cursor-pointer"
          >
            {templates && templates.map(schema => (
                <option key={schema.template_id} value={schema.template_name} className="bg-[#1E293B] text-white">
                    {schema.template_name}
                </option>
            ))}
            {(!templates || templates.length === 0) && (
                <option value="">No templates found</option>
            )}
          </select>
        </div>
      </div>
      
      <div className="flex items-center bg-black/20 rounded-lg p-1 border border-white/5 absolute left-1/2 transform -translate-x-1/2">
        <button 
          onClick={() => setCurrentStep('extract')}
          className={`px-4 py-1.5 rounded-md text-sm font-semibold transition-all duration-200 ${currentStep === 'extract' ? 'bg-indigo-500/20 shadow-lg text-indigo-300 border border-indigo-500/30' : 'text-slate-400 hover:text-slate-200 hover:bg-white/5 border border-transparent'}`}
        >
          1. Extract Data
        </button>
        <button 
          onClick={() => setCurrentStep('map')}
          className={`px-4 py-1.5 rounded-md text-sm font-semibold transition-all duration-200 ${currentStep === 'map' ? 'bg-indigo-500/20 shadow-lg text-indigo-300 border border-indigo-500/30' : 'text-slate-400 hover:text-slate-200 hover:bg-white/5 border border-transparent'}`}
        >
          2. Map to Form
        </button>
        <button 
          onClick={() => setCurrentStep('preview')}
          className={`px-4 py-1.5 rounded-md text-sm font-semibold transition-all duration-200 ${currentStep === 'preview' ? 'bg-indigo-500/20 shadow-lg text-indigo-300 border border-indigo-500/30' : 'text-slate-400 hover:text-slate-200 hover:bg-white/5 border border-transparent'}`}
        >
          3. Preview & Save
        </button>
      </div>
      <div className="w-[120px] flex justify-end">
        {currentStep === 'preview' && (
          <button 
            onClick={handleSaveAllMappings}
            disabled={isSavingMappings}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-md text-sm font-medium transition-colors disabled:opacity-50"
          >
            {isSavingMappings ? "Saving..." : "Save Data"}
          </button>
        )}
      </div>
    </div>
  );

  return (
    <div className="flex flex-col w-full h-screen overflow-hidden bg-[#0B1120] relative pt-16">
      {renderTopBar()}

      <div className="flex flex-1 overflow-hidden w-full h-full bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-slate-900 via-[#0B1120] to-[#0B1120]">
        
        {/* Step 1: Extract Data */}
        {currentStep === 'extract' && (
          <>
            <div className="flex-1 p-8 flex flex-col min-w-[500px]">
              <div className="mb-6 text-center">
                <h1 className="text-3xl font-extrabold text-white tracking-tight flex items-center justify-center gap-3">
                  Data Extraction
                </h1>
                <p className="text-sm text-slate-400 mt-2 font-medium">Upload a PDF and select cells to extract key-value pairs.</p>
              </div>
              
              <div className="flex-1 min-h-0 flex gap-6">
                <div className="flex-1 bg-[#1E293B]/80 backdrop-blur-xl rounded-2xl border border-white/10 shadow-2xl overflow-hidden flex flex-col">
                  <div className="p-4 border-b border-white/5 bg-white/5 flex justify-between items-center">
                      <span className="text-sm font-bold tracking-wide text-slate-200">Structured Document</span>
                      <button 
                          onClick={() => setShowPdfPanel(!showPdfPanel)}
                          className="text-xs px-4 py-2 bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 rounded-md font-semibold hover:bg-indigo-500/20 transition-all"
                      >
                          {showPdfPanel ? "Hide Original PDF" : "Show Original PDF"}
                      </button>
                  </div>
                  <div className="flex-1 overflow-hidden">
                      {uploadedFiles[activeFileIndex]?.status === 'error' ? (
                          <div className="flex flex-col items-center justify-center h-full text-center p-8 bg-black/20">
                              <div className="w-12 h-12 bg-red-500/10 text-red-400 rounded-xl flex items-center justify-center mb-4">
                                  <AlertCircle className="w-6 h-6" />
                              </div>
                              <h4 className="text-sm font-bold text-white mb-2">Processing Failed</h4>
                              <p className="text-xs text-slate-400">
                                  The server encountered an error while processing this document (e.g. GPU out of memory). Please clear server memory and upload again.
                              </p>
                          </div>
                      ) : (
                          <StructuredDocumentViewer pdfFile={pdfFile} onPairExtracted={handlePairExtracted} />
                      )}
                  </div>
                </div>
                
                {showPdfPanel && (
                    <div className="w-1/2 bg-white dark:bg-[#1A2234] rounded-2xl border border-slate-200 dark:border-white/10 shadow-sm p-4 overflow-hidden">
                        <PdfCanvas 
                          onDocumentUpload={handleDocumentUpload} 
                          onRegionSelect={() => {}} 
                          isExtractingRegion={false}
                          uploadedFiles={uploadedFiles}
                          activeFileIndex={activeFileIndex}
                          onSelectDocument={handleSelectDocument}
                        />
                    </div>
                )}
              </div>
            </div>
            
            <div className="w-[400px] bg-[#1E293B]/50 border-l border-white/5 shadow-2xl">
              <ExtractedDataSidebar 
                  extractedData={extractedData}
                  isExtracting={isExtracting}
                  selectedExtractedData={selectedExtractedData}
                  setSelectedExtractedData={setSelectedExtractedData}
                  rules={rules}
              />
            </div>
          </>
        )}

        {/* Step 2: Map to Form */}
        {currentStep === 'map' && (
          <div className="flex-1 p-8 flex flex-col items-center">
            <div className="mb-8 text-center">
                <h1 className="text-3xl font-extrabold text-white tracking-tight flex items-center justify-center gap-3">
                  Map Extracted Data
                </h1>
                <p className="text-sm text-slate-400 mt-2 font-medium">Link your extracted values (right) to the target schema fields (left).</p>
            </div>
            <div className="flex-1 w-full max-w-6xl flex gap-8 justify-center min-h-0 pb-8">
              <div className="flex-1 rounded-2xl shadow-2xl border border-white/10 overflow-hidden bg-[#1E293B]/80 backdrop-blur-xl">
                <FormTemplateViewer 
                    templateId={templateName}
                    onTemplateChange={setTemplateName}
                    templates={templates}
                    currentSchema={currentSchema}
                    rules={rules}
                    selectedExtractedData={selectedExtractedData}
                    onLinkField={handleLinkField}
                    onDeleteRule={handleDeleteRule}
                    onTemplateUploaded={fetchTemplates}
                    onSaveMappings={handleSaveAllMappings}
                    isSavingMappings={isSavingMappings}
                />
              </div>
              
              <div className="flex-1 rounded-2xl shadow-2xl border border-white/10 overflow-hidden bg-[#1E293B]/80 backdrop-blur-xl">
                <ExtractedDataSidebar 
                    extractedData={extractedData}
                    isExtracting={isExtracting}
                    selectedExtractedData={selectedExtractedData}
                    setSelectedExtractedData={setSelectedExtractedData}
                    rules={rules}
                />
              </div>
            </div>
          </div>
        )}

        {/* Step 3: Preview */}
        {currentStep === 'preview' && (
          <div className="flex-1 p-8 flex flex-col items-center min-h-0">
            <div className="mb-6 text-center mt-2 shrink-0">
                <h1 className="text-4xl font-extrabold text-white tracking-tight">
                  Final Review
                </h1>
                <p className="text-slate-400 mt-2 font-medium">Verify your mapped data before committing to the database.</p>
            </div>
            
            <div className="bg-[#1E293B]/80 backdrop-blur-xl rounded-3xl shadow-2xl border border-white/10 p-8 w-full max-w-3xl mb-4 relative flex flex-col flex-1 min-h-0">
                <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 shrink-0"></div>
                <div className="flex items-center justify-between mb-6 pb-6 border-b border-white/5 shrink-0">
                    <div>
                        <h2 className="text-xl font-bold text-white flex items-center gap-2">
                            <LayoutDashboard className="w-6 h-6 text-indigo-400" />
                            {templateName || "Document"} Schema
                        </h2>
                        <p className="text-sm text-slate-400 mt-1">Ready for submission</p>
                    </div>
                    <div className="bg-indigo-500/10 text-indigo-300 px-5 py-2.5 rounded-full text-sm font-bold border border-indigo-500/20 shadow-inner">
                        {rules.length} / {currentSchema?.fields?.length || 0} Fields Mapped
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto pr-2 space-y-3 mb-6 custom-scrollbar">
                    {currentSchema?.fields?.map(field => {
                        const mapping = rules.find(r => r.form_field === field.id);
                        return (
                            <div key={field.id} className="flex items-center justify-between p-4 rounded-xl transition-colors hover:bg-slate-50 dark:hover:bg-white/5 border border-transparent hover:border-slate-100 dark:hover:border-white/5">
                                <div className="flex items-center gap-3">
                                    <div className={`w-2 h-2 rounded-full ${mapping ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'bg-slate-300 dark:bg-slate-600'}`}></div>
                                    <span className={`text-sm font-semibold ${mapping ? 'text-slate-700 dark:text-slate-200' : 'text-slate-500'}`}>
                                        {field.label}
                                    </span>
                                </div>
                                {mapping ? (
                                    <div className="text-right">
                                        <span className="inline-block text-slate-900 dark:text-white font-mono bg-indigo-50 dark:bg-indigo-900/20 px-4 py-2 rounded-lg border border-indigo-100 dark:border-indigo-500/20 text-sm">
                                            {extractedData.find(e => e.key === mapping.extracted_key)?.value || mapping.extracted_key}
                                        </span>
                                    </div>
                                ) : (
                                    <span className="text-slate-400 italic text-sm px-4 py-2 bg-slate-50 dark:bg-white/5 rounded-lg border border-dashed border-slate-200 dark:border-white/10">
                                        Unmapped
                                    </span>
                                )}
                            </div>
                        );
                    })}
                </div>
                
                <button 
                    onClick={handleSaveAllMappings}
                    disabled={isSavingMappings}
                    className="w-full py-4 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white rounded-2xl font-bold flex justify-center items-center gap-3 transition-all transform hover:scale-[1.01] active:scale-[0.99] disabled:opacity-50 disabled:hover:scale-100 shadow-xl shadow-indigo-500/25 text-lg shrink-0"
                >
                    {isSavingMappings ? "Saving to Database..." : "Confirm & Save to Database"}
                    {!isSavingMappings && <CheckCircle className="w-6 h-6" />}
                </button>
                
                {/* TEST FLA LOGIC BUTTON */}
                <button 
                    onClick={handleTestFla}
                    disabled={isTestingFla || isGeneratingExcel}
                    className="w-full mt-4 py-3 bg-[#0F172A] hover:bg-black/40 border border-indigo-500/30 hover:border-indigo-400 text-indigo-300 rounded-2xl font-bold flex justify-center items-center gap-3 transition-all transform hover:scale-[1.01] active:scale-[0.99] disabled:opacity-50 disabled:hover:scale-100 text-md shrink-0"
                >
                    {isTestingFla ? <Loader2 className="w-5 h-5 animate-spin" /> : <Cpu className="w-5 h-5" />}
                    {isTestingFla ? "Testing Logic..." : "Test Legacy FLA Logic"}
                </button>

                {/* GENERATE FINAL EXCEL BUTTON */}
                <button 
                    onClick={handleGenerateExcel}
                    disabled={isGeneratingExcel || isTestingFla}
                    className="w-full mt-3 py-3 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white rounded-2xl font-bold flex justify-center items-center gap-3 transition-all transform hover:scale-[1.01] active:scale-[0.99] disabled:opacity-50 disabled:hover:scale-100 shadow-lg shadow-emerald-500/20 text-md shrink-0"
                >
                    {isGeneratingExcel ? <Loader2 className="w-5 h-5 animate-spin" /> : <Download className="w-5 h-5" />}
                    {isGeneratingExcel ? "Generating Excel..." : "Generate Final Excel (.xlsx)"}
                </button>
            </div>
          </div>
        )}

      </div>
      
      {/* TEST FLA RESULT MODAL */}
      {testFlaResult && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-8">
            <div className="bg-[#1E293B] border border-white/10 rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in duration-200">
                <div className="px-6 py-4 border-b border-white/10 bg-black/20 flex items-center justify-between">
                    <h3 className="text-xl font-bold text-white flex items-center gap-3">
                        <Cpu className="w-6 h-6 text-indigo-400" />
                        FLA Engine Computation Results
                    </h3>
                    <button onClick={() => setTestFlaResult(null)} className="text-slate-400 hover:text-white transition-colors">
                        <X className="w-6 h-6" />
                    </button>
                </div>
                <div className="p-6 overflow-y-auto bg-[#0F172A] custom-scrollbar text-sm font-mono text-emerald-400">
                    <pre className="whitespace-pre-wrap">{JSON.stringify(testFlaResult, null, 2)}</pre>
                </div>
                <div className="px-6 py-4 border-t border-white/10 bg-black/20 flex justify-end">
                    <button onClick={() => setTestFlaResult(null)} className="px-6 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-lg transition-colors">
                        Close
                    </button>
                </div>
            </div>
        </div>
      )}

    </div>
  );
}
