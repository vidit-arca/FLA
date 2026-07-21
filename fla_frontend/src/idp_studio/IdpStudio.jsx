import React, { useState, useEffect } from 'react';
import PdfCanvas from './components/PdfCanvas';
import FormTemplateViewer from './components/FormTemplateViewer';
import ExtractedDataSidebar from './components/ExtractedDataSidebar';
import { idpClient } from './api/idpClient';
import { LayoutDashboard } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export default function IdpStudio() {
  const navigate = useNavigate();
  const [rules, setRules] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [templateName, setTemplateName] = useState("");
  const [currentSchema, setCurrentSchema] = useState(null);
  
  // Extraction State
  const [extractedData, setExtractedData] = useState([]);
  const [isExtracting, setIsExtracting] = useState(false);
  const [isExtractingRegion, setIsExtractingRegion] = useState(false);
  const [selectedExtractedData, setSelectedExtractedData] = useState(null);
  const [pdfFile, setPdfFile] = useState(null);

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

  const handleDocumentUpload = async (file) => {
      setPdfFile(file);
      if (!file) {
          setExtractedData([]);
          setSelectedExtractedData(null);
          return;
      }
      
      setIsExtracting(true);
      setSelectedExtractedData(null);
      
      try {
          const data = await idpClient.extractDocument(file);
          setExtractedData(data);
      } catch (err) {
          console.error("Failed to extract document", err);
          alert("Failed to auto-extract document values.");
      } finally {
          setIsExtracting(false);
      }
  };

  const handleRegionSelect = async (pageNumber, anchorRect, valueRect) => {
      if (!pdfFile) return;
      setIsExtractingRegion(true);
      try {
          const newData = await idpClient.extractSpatialRule(pdfFile, anchorRect, valueRect, pageNumber);
          setExtractedData(prev => [...prev, ...newData]);
      } catch (err) {
          console.error("Failed to extract spatial rule", err);
          alert("Failed to extract data from the selected spatial rule.");
      } finally {
          setIsExtractingRegion(false);
      }
  };

  const handleLinkField = async (formFieldId) => {
    if (!selectedExtractedData) return;
    
    try {
      await idpClient.saveRule({
        template_name: templateName,
        form_field: formFieldId,
        extracted_key: selectedExtractedData.key,
        spatial_meta: selectedExtractedData._spatial_meta
      });
      setSelectedExtractedData(null); // Reset after saving
      fetchRules(); // Refresh list
    } catch (err) {
      console.error("Failed to save rule", err);
      alert("Failed to link field. Ensure backend is running.");
    }
  };

  const handleDeleteRule = async (ruleId) => {
    try {
      await idpClient.deleteRule(ruleId);
      fetchRules();
    } catch (err) {
      console.error("Failed to delete rule", err);
    }
  };

  return (
    <div className="flex w-full h-screen overflow-hidden bg-slate-50 dark:bg-[#0B0F19]">
      {/* Far Left Panel: Form Template Viewer */}
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
      />

      {/* Middle Panel: Document Canvas */}
      <div className="flex-1 p-6 pt-16 flex flex-col min-w-[500px]">
        <div className="mb-4 text-center">
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center justify-center gap-3">
            IDP Schema Mapping Studio
            <span className="px-2.5 py-1 rounded-md bg-indigo-100 dark:bg-indigo-500/20 text-indigo-700 dark:text-indigo-400 text-xs uppercase tracking-wider font-bold">
              Schema Mode
            </span>
          </h1>
          <p className="text-sm text-slate-500 mt-1">Upload a PDF. Select an extracted value on the right, and link it to the form on the left.</p>
        </div>
        
        <div className="flex-1 min-h-0 bg-white dark:bg-[#1A2234] rounded-2xl border border-slate-200 dark:border-white/10 shadow-sm p-4">
          <PdfCanvas 
            onDocumentUpload={handleDocumentUpload} 
            onRegionSelect={handleRegionSelect}
            isExtractingRegion={isExtractingRegion}
          />
        </div>
      </div>

      {/* Far Right Panel: Extracted Data */}
      <ExtractedDataSidebar 
          extractedData={extractedData}
          isExtracting={isExtracting}
          selectedExtractedData={selectedExtractedData}
          setSelectedExtractedData={setSelectedExtractedData}
          rules={rules}
      />
    </div>
  );
}
