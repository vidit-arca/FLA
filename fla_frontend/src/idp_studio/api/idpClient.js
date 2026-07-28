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
    
    saveRule: async (ruleData) => {
        // ruleData: { template_name, form_field, extracted_key }
        try {
            const response = await axios.post(`${API_BASE_URL}/rules`, ruleData);
            return response.data;
        } catch (error) {
            console.error('Error saving IDP schema rule:', error);
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
    
    extractSpatialRule: async (file, anchorRect, valueRect, page) => {
        try {
            const formData = new FormData();
            formData.append("file", file);
            
            // Anchor coordinates
            formData.append("anchor_x", anchorRect.x);
            formData.append("anchor_y", anchorRect.y);
            formData.append("anchor_w", anchorRect.w);
            formData.append("anchor_h", anchorRect.h);
            
            // Value coordinates
            formData.append("value_x", valueRect.x);
            formData.append("value_y", valueRect.y);
            formData.append("value_w", valueRect.w);
            formData.append("value_h", valueRect.h);
            
            formData.append("page", page);
            
            const response = await axios.post(`${API_BASE_URL}/extract_spatial_rule`, formData, { headers: {'Content-Type': 'multipart/form-data'} });
            return response.data.extracted_data;
        } catch (error) {
            console.error('Error extracting spatial rule:', error);
            throw error;
        }
    }
};
