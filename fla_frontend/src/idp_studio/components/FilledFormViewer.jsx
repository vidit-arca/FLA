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

  // Canonical fields for statutory sequence
  const canonicalFields = [
    { key: 'cin', label: '1. *Corporate Identity Number (CIN)', aliases: ['corporateidentitynumbercin', 'cin', '1 corporateidentitynumbercin'] },
    { key: 'company_name', label: '2(a) *Name of the company', aliases: ['anameofthecompany', 'company_name', '2 anameofthecompany'] },
    { key: 'address', label: '2(b) *Address of registered office', isAddress: true, aliases: ['registered_office_address', 'address', '2b address of registered office'] },
    { key: 'email', label: '2(c) *Email ID of the company', aliases: ['email', 'email_id', '2c email id of the company'] },
    { key: '3a_class_of_companies', label: '3(a) *Whether company falling under Section 139(2)', isToggle: true, options: ['Yes', 'No'] },
    { key: '3b_nature_of_appointment', label: '3(b) *Nature of appointment', isDropdown: true },
    { key: '3b_others_specify', label: '3(b)(i) If Others, please specify', aliases: ['others_specify', '3b others specify'] },
    { key: '3c_appointed_in_agm', label: '3(c) *Whether auditor(s) appointed in AGM', isToggle: true, options: ['Yes', 'No'] },
    { key: '3d_date_of_agm', label: '3(d) If yes, date of AGM (DD/MM/YYYY)', aliases: ['date_of_agm', 'agm_date', '3d date of agm'] },
    { key: 'appointment_date', label: '4(a) *Date of appointment (DD/MM/YYYY)', aliases: ['adateofappointmentddmmyyyy', 'appointment_date', 'date_of_appointment', '4 adateofappointmentddmmyyyy'] },
    { key: '4b_joint_auditors', label: '4(b) *Whether joint auditors have been appointed', isToggle: true, options: ['Yes', 'No'] },
    { key: 'number_of_auditors', label: '4(c) *Number of auditor(s) appointed', aliases: ['cnumberofauditors', 'number_of_auditors', '4c number of auditor(s) appointed'] },
    { key: '4d_auditor_category', label: "4(d) *Category of Auditor", isToggle: true, options: ["Auditor's Firm", "Individual"] },
    { key: 'frn', label: '4(e) *Firm Registration Number (FRN)', aliases: ['efirmregistrationnumber', 'frn', '4 efirmregistrationnumber'] },
    { key: 'auditor_firm_name', label: "4(f) *Name of the auditor's firm", aliases: ['fnameoftheauditorsfirm', 'auditor_firm_name', '4 fnameoftheauditorsfirm'] },
    { key: '4f_pan_auditor_firm', label: "4(f)(i) Income Tax PAN of Auditor's Firm", aliases: ['pan', 'firm_pan', '4f pan of auditor firm'] },
    { key: '4f_address_auditor_firm', label: "4(f)(ii) Address of the Auditor's Firm", aliases: ['auditor_address', 'auditors_firm_address'] },
    { key: '4f_email_auditor_firm', label: "4(f)(ii) *Email ID of the Auditor's Firm", aliases: ['auditor_email', 'auditors_firm_email'] },
    { key: 'auditor_name', label: '4(h) *Name of the auditor', aliases: ['hnameoftheauditor', 'auditor_name', '4 hnameoftheauditor'] },
    { key: 'membership_number', label: '4(i) *Membership Number of Auditor', aliases: ['imembershipnumber', 'membership_number', 'membership', '4i membership number of auditor'] },
    { key: '4i_period_from', label: '4(i) Period of account for which appointed - *From (DD/MM/YYYY)', aliases: ['period_from', 'from_date', 'financial_year_start'] },
    { key: '4i_period_to', label: '4(i) Period of account for which appointed - *To (DD/MM/YYYY)', aliases: ['period_to', 'to_date', 'financial_year_end'] },
    { key: 'number_of_financial_years', label: '4(j) *Number of financial year(s) to which appointment relates', aliases: ['kfinancialyears', 'financial_years', 'number_of_financial_years'] },
    { key: '4k_within_limit_twenty', label: '4(k) *Whether appointment is within limit of 20 companies as per Sec 141(3)(g)', isToggle: true, options: ['Yes', 'No'] },
    { key: '4l_previous_audit_same_co', label: '4(l) Has auditor previously conducted audit in the same company as per Rule 6', isToggle: true, options: ['Yes', 'No'] },
    { key: '5_audit_committee', label: '5. *Recommendation of Audit Committee', isToggle: true, options: ['Yes', 'No', 'Not Applicable'] },
    { key: '6a_casual_vacancy', label: '6(a) *Casual vacancy caused by other than resignation', isToggle: true, options: ['Yes', 'No', 'Not Applicable'] },
  ];

  // Helper: Combine address pieces cleanly
  const getConsolidatedAddress = (data) => {
    if (!data) return '';
    const direct = data['address'] || data['registered_office_address'] || data['2b Address of registered office'] || data['2b address of registered office'];
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

  // Build clean, deduplicated displayData in statutory sequence
  const displayData = {};
  const consumedKeys = new Set();

  canonicalFields.forEach(field => {
    let matchedVal = '';
    
    if (field.isAddress) {
      matchedVal = getConsolidatedAddress(extractedData);
      ['address', 'registered_office_address', 'addressline 1', 'addressline 2', 'addressline_1', 'addressline_2', 'arealocality', 'city', 'pincodezipcode', 'pincode', 'country', 'state'].forEach(k => consumedKeys.add(k));
    } else {
      if (extractedData && extractedData[field.key] !== undefined && extractedData[field.key] !== null) {
        matchedVal = extractedData[field.key];
        consumedKeys.add(field.key);
      } else if (field.aliases) {
        for (const alias of field.aliases) {
          const normAlias = alias.toLowerCase().replace(/[^a-z0-9]/g, '');
          const foundKey = Object.keys(extractedData || {}).find(k => k.toLowerCase().replace(/[^a-z0-9]/g, '') === normAlias);
          if (foundKey && extractedData[foundKey] !== undefined && extractedData[foundKey] !== null) {
            matchedVal = extractedData[foundKey];
            consumedKeys.add(foundKey);
            break;
          }
        }
      }
    }
    displayData[field.key] = matchedVal;
  });

  // Append any genuinely unique custom fields not already mapped into canonical fields
  Object.entries(extractedData || {}).forEach(([k, v]) => {
    const normKey = k.toLowerCase().replace(/[^a-z0-9]/g, '');
    const isConsumed = Array.from(consumedKeys).some(ck => ck.toLowerCase().replace(/[^a-z0-9]/g, '') === normKey);
    if (!isConsumed && displayData[k] === undefined) {
      displayData[k] = v;
    }
  });

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
