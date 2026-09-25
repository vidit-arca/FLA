import React, { useState, useEffect } from 'react';
import { 
  FileText, 
  Download, 
  FileSpreadsheet, 
  ShieldCheck, 
  RefreshCw,
  Loader2,
  Eye,
  AlertCircle
} from 'lucide-react';
import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api/idp';

export default function FilledFormViewer({ 
  templateName = 'Form', 
  extractedData = {}, 
  hideEmptyRows = false,
  onDownloadExcel = null,
  isDownloadingExcel = false
}) {
  const [pdfBlobUrl, setPdfBlobUrl] = useState(null);
  const [isLoadingPdf, setIsLoadingPdf] = useState(true);
  const [pdfError, setPdfError] = useState(null);

  // Helper: Combine address pieces cleanly if address parts exist
  const getConsolidatedAddress = (data) => {
    if (!data) return '';
    const direct = data['address'] || data['registered_office_address'] || data['registered_address'];
    if (direct && String(direct).length > 15) return direct;
    
    const pieces = [
      data['addressline 1'] || data['addressline_1'] || data['addressline1'],
      data['addressline 2'] || data['addressline_2'] || data['addressline2'] || data['arealocality'],
      data['city'],
      data['state'],
      data['pincodezipcode'] || data['pincode'] || data['zipcode'],
      data['country']
    ].filter(Boolean).map(s => String(s).trim()).filter(s => s && s.toLowerCase() !== 'unknown' && s.toLowerCase() !== 'null');
    
    const unique = [];
    pieces.forEach(p => {
      if (!unique.some(u => u.toLowerCase() === p.toLowerCase())) unique.push(p);
    });
    return unique.join(', ') || direct || '';
  };

  // Build clean dynamic payload directly from extractedData (ZERO hardcoded fields)
  const displayData = { ...(extractedData || {}) };
  const consolidatedAddr = getConsolidatedAddress(extractedData);
  if (consolidatedAddr && !displayData['address'] && !displayData['registered_office_address']) {
    displayData['address'] = consolidatedAddr;
  }

  const fieldCount = Object.keys(displayData).length;

  useEffect(() => {
    if (templateName) {
      generatePdfPreview();
    }
    return () => {
      if (pdfBlobUrl) {
        URL.revokeObjectURL(pdfBlobUrl);
      }
    };
  }, [templateName, fieldCount]);

  const generatePdfPreview = async () => {
    if (!templateName) return;
    setIsLoadingPdf(true);
    setPdfError(null);
    try {
      const response = await axios.post(`${API_BASE_URL}/generate_preview_pdf`, {
        template_name: templateName,
        mapped_data: displayData
      }, {
        responseType: 'blob'
      });

      const file = new Blob([response.data], { type: 'application/pdf' });
      const url = URL.createObjectURL(file);
      setPdfBlobUrl(url);
    } catch (err) {
      console.error('Failed to generate official PDF preview:', err);
      const errMsg = err?.response?.data?.detail || err?.message || 'Could not render official PDF template.';
      setPdfError(String(errMsg));
    } finally {
      setIsLoadingPdf(false);
    }
  };

  const handleDownloadPdf = () => {
    if (!pdfBlobUrl) return;
    const a = document.createElement('a');
    a.href = pdfBlobUrl;
    a.download = `${templateName}_Filled_Return.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  return (
    <div className="flex flex-col h-full bg-slate-100 dark:bg-[#0B0F19] text-slate-900 dark:text-slate-100 font-sans">
      
      {/* Top Header Bar */}
      <div className="px-6 py-3 bg-white dark:bg-[#111726] border-b border-slate-200 dark:border-white/10 flex items-center justify-between shrink-0 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-200 dark:border-indigo-500/30 rounded-lg text-indigo-700 dark:text-indigo-400 text-xs font-bold">
            <Eye className="w-3.5 h-3.5" />
            <span>Official Stamped Filing Preview</span>
          </div>

          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/30 rounded-full text-emerald-700 dark:text-emerald-400 text-xs font-bold">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>{templateName}</span>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2">
          <button
            onClick={generatePdfPreview}
            disabled={isLoadingPdf}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold bg-slate-100 dark:bg-white/5 hover:bg-slate-200 dark:hover:bg-white/10 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-white/10 shadow-sm transition-all disabled:opacity-50"
            title="Re-render stamped PDF preview"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoadingPdf ? 'animate-spin' : ''}`} />
            <span>Refresh Preview</span>
          </button>

          <button
            onClick={handleDownloadPdf}
            disabled={!pdfBlobUrl || isLoadingPdf}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-bold bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm transition-all disabled:opacity-50"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Download Official PDF</span>
          </button>

          {onDownloadExcel && (
            <button
              onClick={onDownloadExcel}
              disabled={isDownloadingExcel}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm transition-all disabled:opacity-50"
            >
              <FileSpreadsheet className="w-3.5 h-3.5" />
              <span>Download Excel</span>
            </button>
          )}
        </div>
      </div>

      {/* Main View Area: Pure High-Fidelity Embedded PDF View */}
      <div className="flex-1 h-full min-h-0 p-3 flex justify-center bg-slate-900/40">
        <div className="w-full h-full min-h-[680px] bg-white dark:bg-[#111726] border border-slate-300 dark:border-white/10 rounded-xl shadow-2xl overflow-hidden flex flex-col relative">
          {isLoadingPdf && (
            <div className="absolute inset-0 z-20 bg-white/80 dark:bg-[#111726]/80 backdrop-blur-sm flex flex-col items-center justify-center gap-3">
              <Loader2 className="w-8 h-8 text-indigo-600 animate-spin" />
              <p className="text-sm font-bold text-slate-700 dark:text-slate-200">
                Rendering official {templateName} filing preview...
              </p>
            </div>
          )}

          {pdfError ? (
            <div className="flex-1 flex flex-col items-center justify-center p-12 text-center">
              <div className="w-12 h-12 rounded-full bg-amber-50 dark:bg-amber-500/10 text-amber-500 flex items-center justify-center mb-3">
                <AlertCircle className="w-6 h-6" />
              </div>
              <h4 className="text-base font-bold text-slate-900 dark:text-white mb-1">
                Could Not Load Template PDF
              </h4>
              <p className="text-xs text-slate-500 max-w-sm mb-4">
                {pdfError}
              </p>
              <div className="flex items-center gap-3">
                <button
                  onClick={generatePdfPreview}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-bold transition-all flex items-center gap-2"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>Retry Preview</span>
                </button>
              </div>
            </div>
          ) : pdfBlobUrl ? (
            <iframe
              src={`${pdfBlobUrl}#toolbar=1&navpanes=1&view=FitH`}
              className="w-full h-full min-h-[680px] flex-1 border-0 bg-white"
              title={`${templateName} Official Filled Form`}
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}
