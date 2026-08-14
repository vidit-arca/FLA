import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api/idp';

export const idpClient = {
    getRules: async (templateName) => {
        try {
            const response = await axios.get(`${API_BASE_URL}/rules/${templateName}`);
            return response.data;
        } catch (error) {
            console.error('Error fetching IDP schema rules:', error);
            throw error;
        }
    },
    
    saveRuleWithDom: async (ruleData, pdfFile) => {
        try {
            const formData = new FormData();
            formData.append("template_name", ruleData.template_name);
            formData.append("form_field", ruleData.form_field);
            formData.append("extracted_key", ruleData.extracted_key);
            if (ruleData.spatial_meta) {
                formData.append("spatial_meta", JSON.stringify(ruleData.spatial_meta));
            }
            if (pdfFile) {
                formData.append("file", pdfFile);
            }
            const response = await axios.post(`${API_BASE_URL}/rules_with_dom`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });
            return response.data;
        } catch (error) {
            console.error('Error saving rule with DOM learning:', error);
            throw error;
        }
    },
    
    saveRulesBatch: async (templateName, mappedRules, pdfFile) => {
        try {
            const formData = new FormData();
            formData.append("template_name", templateName);
            formData.append("rules_json", JSON.stringify(mappedRules));
            if (pdfFile) {
                formData.append("file", pdfFile);
            }
            const response = await axios.post(`${API_BASE_URL}/rules_batch_save`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });
            return response.data;
        } catch (error) {
            console.error('Error saving batch rules:', error);
            throw error;
        }
    },

    testFlaEngine: async (extractedDataPayload) => {
        try {
            const response = await axios.post(`${API_BASE_URL}/test_fla_engine`, extractedDataPayload);
            return {
                computed_state: response.data.computed_state,
                cell_labels: response.data.cell_labels
            };
        } catch (error) {
            console.error('Error testing FLA engine:', error);
            throw error;
        }
    },

    generateExcel: async (extractedDataPayload) => {
        try {
            const response = await axios.post(`${API_BASE_URL}/generate_excel`, extractedDataPayload, {
                responseType: 'blob'
            });
            const blob = new Blob([response.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', 'FLA_Return_Populated.xlsx');
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);
            return true;
        } catch (error) {
            console.error('Error generating Excel from IDP mappings:', error);
            throw error;
        }
    },

    generatePreviewPdf: async (payload) => {
        try {
            const response = await axios.post(`${API_BASE_URL}/generate_preview_pdf`, payload, {
                responseType: 'blob'
            });
            const file = new Blob([response.data], { type: 'application/pdf' });
            const fileURL = URL.createObjectURL(file);
            window.open(fileURL, '_blank');
        } catch (error) {
            console.error('Error generating Preview PDF:', error);
            throw error;
        }
    },

    deleteRule: async (ruleId) => {

        try {
            const response = await axios.delete(`${API_BASE_URL}/rules/${ruleId}`);
            return response.data;
        } catch (error) {
            console.error('Error deleting IDP schema rule:', error);
            throw error;
        }
    },
    
    processDocument: async (file) => {
        try {
            const formData = new FormData();
            formData.append("file", file);
            const response = await axios.post(`${API_BASE_URL}/process_document`, formData, { headers: {'Content-Type': 'multipart/form-data'} });
            return response.data;
        } catch (error) {
            console.error('Error processing document OCR:', error);
            throw error;
        }
    },

    extractDocument: async (file) => {

        try {
            const formData = new FormData();
            formData.append("file", file);
            const response = await axios.post(`${API_BASE_URL}/extract`, formData, { headers: {'Content-Type': 'multipart/form-data'} });
            return response.data.extracted_data;
        } catch (error) {
             console.error('Error extracting document:', error);
             throw error;
        }
    },
    
    extractBatchDocuments: async (files, templateName = "FLA") => {
        try {
            const formData = new FormData();
            files.forEach(file => {
                formData.append("files", file);
            });
            formData.append("template_name", templateName);
            const response = await axios.post(`${API_BASE_URL}/extract/batch`, formData, { headers: {'Content-Type': 'multipart/form-data'} });
            return response.data;
        } catch (error) {
             console.error('Error extracting batch documents:', error);
             throw error;
        }
    },
    
    exportToExcel: (batchResults, filename = 'IDP_Batch_Export.csv') => {
        if (!batchResults || batchResults.length === 0) return;
        
        const allKeysSet = new Set();
        batchResults.forEach(doc => {
            (doc.data || []).forEach(field => {
                if (field.key) allKeysSet.add(field.key);
            });
        });
        const headers = ['Document Name', 'Status', ...Array.from(allKeysSet)];
        
        const rows = batchResults.map(doc => {
            const fieldMap = {};
            (doc.data || []).forEach(field => {
                fieldMap[field.key] = field.value || '';
            });
            return [
                `"${doc.file.name}"`,
                `"${doc.status.toUpperCase()}"`,
                ...Array.from(allKeysSet).map(key => `"${(fieldMap[key] || '').replace(/"/g, '""')}"`)
            ];
        });
        
        const csvContent = [headers.map(h => `"${h}"`).join(','), ...rows.map(r => r.join(','))].join('\n');
        const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', filename);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    },
    
    getTemplates: async () => {

        try {
            const response = await axios.get(`${API_BASE_URL}/templates`);
            return response.data;
        } catch (error) {
            console.error('Error fetching templates:', error);
            throw error;
        }
    },
    
    uploadTemplate: async (file) => {
        try {
            const formData = new FormData();
            formData.append("file", file);
            const response = await axios.post(`${API_BASE_URL}/templates/upload`, formData, { headers: {'Content-Type': 'multipart/form-data'} });
            return response.data;
        } catch (error) {
            console.error('Error uploading template:', error);
            throw error;
        }
    },
    
    getStructuredDocument: async (filename) => {
        try {
            const response = await axios.get(`${API_BASE_URL}/structured_document/${filename}`);
            return response.data.structured_document;
        } catch (error) {
            console.error('Error fetching structured document:', error);
            throw error;
        }
    }
};
