import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  ArrowLeft, 
  CheckCircle2, 
  AlertCircle, 
  FileText, 
  Check, 
  X, 
  Edit2, 
  Save, 
  Maximize2 
} from 'lucide-react';

const TaskReviewView = () => {
  const { taskId } = useParams();
  const navigate = useNavigate();

  // Dummy extracted data for the task
  const [fields, setFields] = useState([
    { id: 1, key: 'Company Name', value: 'Reliance Industries Ltd.', confidence: 98, status: 'approved' },
    { id: 2, key: 'CIN Number', value: 'L17110MH1973PLC019786', confidence: 95, status: 'approved' },
    { id: 3, key: 'Reporting Year', value: '2023-2024', confidence: 99, status: 'approved' },
    { id: 4, key: 'Net Worth', value: 'INR 45,000 Cr', confidence: 65, status: 'flagged' },
    { id: 5, key: 'Total FDI Received', value: 'USD 1.2 Billion', confidence: 72, status: 'flagged' },
    { id: 6, key: 'Director Signature', value: 'Present', confidence: 88, status: 'pending' },
  ]);

  const [editingFieldId, setEditingFieldId] = useState(null);
  const [editValue, setEditValue] = useState('');

  const handleApprove = (id) => {
    setFields(fields.map(f => f.id === id ? { ...f, status: 'approved' } : f));
  };

  const handleReject = (id) => {
    setFields(fields.map(f => f.id === id ? { ...f, status: 'rejected' } : f));
  };

  const startEditing = (field) => {
    setEditingFieldId(field.id);
    setEditValue(field.value);
  };

  const saveEdit = (id) => {
    setFields(fields.map(f => f.id === id ? { ...f, value: editValue, status: 'approved', confidence: 100 } : f));
    setEditingFieldId(null);
  };

  return (
    <div className="h-screen flex flex-col bg-[#0B0F19] text-slate-200 overflow-hidden animate-fade-in">
      
      {/* Top Navigation Bar */}
      <div className="h-16 border-b border-white/10 flex items-center justify-between px-6 bg-[#0F1523]/90 backdrop-blur-md shrink-0">
        <div className="flex items-center gap-4">
          <button 
            onClick={() => window.location.href = '/review'}
            className="p-2 rounded-lg hover:bg-white/5 text-slate-400 hover:text-white transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div className="h-6 w-px bg-white/10"></div>
          <div>
            <h1 className="text-sm font-semibold text-white flex items-center gap-3">
              Task Validation
              <span className="px-2 py-0.5 rounded text-xs font-mono bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                {taskId || 'TSK-9901'}
              </span>
            </h1>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span className="flex items-center gap-2 text-sm font-medium text-amber-400 bg-amber-500/10 px-3 py-1.5 rounded-lg border border-amber-500/20">
            <AlertCircle className="w-4 h-4" /> 2 Fields Require Review
          </span>
        </div>
      </div>

      {/* Main Split Workspace */}
      <div className="flex-1 flex overflow-hidden">
        
        {/* Left Pane: Document Viewer */}
        <div className="flex-1 border-r border-white/10 flex flex-col bg-black/20">
          {/* Viewer Toolbar */}
          <div className="h-12 border-b border-white/5 flex items-center justify-between px-4 bg-[#1A2235]/40">
            <div className="flex items-center gap-2 text-sm text-slate-400 font-medium">
              <FileText className="w-4 h-4" />
              source_document_v2.pdf
            </div>
            <button className="p-1.5 hover:bg-white/10 rounded-md text-slate-400 transition-colors">
              <Maximize2 className="w-4 h-4" />
            </button>
          </div>
          
          {/* Viewer Content Placeholder */}
          <div className="flex-1 p-6 flex items-center justify-center overflow-auto">
            <div className="w-full max-w-2xl h-[800px] bg-white rounded shadow-2xl flex flex-col items-center justify-center text-slate-400 border border-slate-200">
              <FileText className="w-16 h-16 mb-4 text-slate-300" />
              <p className="text-lg font-medium text-slate-500">Document Preview</p>
              <p className="text-sm text-slate-400 mt-2">Original PDF renders here</p>
            </div>
          </div>
        </div>

        {/* Right Pane: Extracted Data */}
        <div className="w-[450px] flex flex-col bg-[#0F1523]/50 shrink-0">
          
          {/* Pane Header */}
          <div className="p-5 border-b border-white/10">
            <h2 className="text-lg font-semibold text-white">Extracted Data</h2>
            <p className="text-sm text-slate-400 mt-1">Review AI predictions against the document.</p>
          </div>

          {/* Fields List */}
          <div className="flex-1 overflow-y-auto p-5 space-y-4 hide-scrollbar">
            {fields.map((field) => (
              <div 
                key={field.id} 
                className={`p-4 rounded-xl border transition-all ${
                  field.status === 'flagged' 
                    ? 'bg-rose-500/5 border-rose-500/30 shadow-[0_0_15px_rgba(244,63,94,0.05)]' 
                    : field.status === 'approved'
                      ? 'bg-emerald-500/5 border-emerald-500/20'
                      : 'bg-white/5 border-white/10 hover:border-indigo-500/30'
                }`}
              >
                <div className="flex justify-between items-start mb-2">
                  <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">{field.key}</span>
                  <div className="flex items-center gap-1.5">
                    <div className={`w-2 h-2 rounded-full ${field.confidence < 80 ? 'bg-rose-500' : field.confidence < 90 ? 'bg-amber-400' : 'bg-emerald-500'}`}></div>
                    <span className="text-xs font-mono text-slate-500">{field.confidence}%</span>
                  </div>
                </div>

                {editingFieldId === field.id ? (
                  <div className="flex gap-2 mt-2">
                    <input 
                      type="text" 
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      className="flex-1 bg-black/40 border border-indigo-500/50 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    />
                    <button 
                      onClick={() => saveEdit(field.id)}
                      className="p-1.5 bg-indigo-500 hover:bg-indigo-600 rounded-lg text-white transition-colors"
                    >
                      <Save className="w-4 h-4" />
                    </button>
                    <button 
                      onClick={() => setEditingFieldId(null)}
                      className="p-1.5 bg-white/10 hover:bg-white/20 rounded-lg text-white transition-colors"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ) : (
                  <div className="flex justify-between items-end mt-1">
                    <span className="text-base font-medium text-white">{field.value}</span>
                    
                    <div className="flex gap-1">
                      {field.status !== 'approved' && (
                        <button 
                          onClick={() => handleApprove(field.id)}
                          className="p-1.5 hover:bg-emerald-500/20 text-slate-400 hover:text-emerald-400 rounded-md transition-colors"
                          title="Approve"
                        >
                          <Check className="w-4 h-4" />
                        </button>
                      )}
                      <button 
                        onClick={() => startEditing(field)}
                        className="p-1.5 hover:bg-indigo-500/20 text-slate-400 hover:text-indigo-400 rounded-md transition-colors"
                        title="Edit Value"
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                )}
                
                {field.status === 'flagged' && !editingFieldId && (
                  <p className="text-xs text-rose-400 mt-3 flex items-center gap-1">
                    <AlertCircle className="w-3 h-3" /> Low confidence score. Please verify manually.
                  </p>
                )}
              </div>
            ))}
          </div>

          {/* Action Footer */}
          <div className="p-5 border-t border-white/10 bg-[#0F1523]">
            <button className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-medium shadow-lg shadow-indigo-500/20 transition-all flex items-center justify-center gap-2">
              <CheckCircle2 className="w-5 h-5" /> Submit Validated Data
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TaskReviewView;
