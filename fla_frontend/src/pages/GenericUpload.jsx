import { useState, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import axios from 'axios';
import { UploadCloud, File, X, Loader2, Info, ArrowLeft, AlertCircle } from 'lucide-react';
import { MODULES_SCHEMA } from '../config/modulesSchema';

export default function GenericUpload() {
  const { moduleId } = useParams();
  const navigate = useNavigate();
  const [files, setFiles] = useState([]);
  const [previousFlaFile, setPreviousFlaFile] = useState(null);
  const [companyName, setCompanyName] = useState('');
  const [uploading, setUploading] = useState(false);

  const moduleConfig = MODULES_SCHEMA[moduleId];

  if (!moduleConfig) {
    return (
      <div className="flex flex-col items-center justify-center h-[calc(100vh-140px)]">
        <AlertCircle className="w-16 h-16 text-rose-500 mb-4" />
        <h2 className="text-2xl font-bold text-white mb-2">Module Not Found</h2>
      </div>
    );
  }

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    const droppedFiles = Array.from(e.dataTransfer.files);
    setFiles(prev => [...prev, ...droppedFiles]);
  }, []);

  const handleFileChange = (e) => {
    if (e.target.files) {
      setFiles(prev => [...prev, ...Array.from(e.target.files)]);
    }
  };

  const removeFile = (index) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    if (!companyName || files.length === 0) return;

    setUploading(true);
    const formData = new FormData();
    files.forEach(file => {
      formData.append('files', file);
    });

    if (previousFlaFile && moduleConfig.features.hasPreviousYearComparison) {
      formData.append('files', previousFlaFile, `previous_fla_${previousFlaFile.name}`);
    }

    try {
      const res = await axios.post(`http://localhost:8000/api/upload?company_name=${encodeURIComponent(companyName)}&module_type=${moduleConfig.apiType}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      const taskId = res.data.task_id;
      await axios.post(`http://localhost:8000/api/process/${taskId}`);
      navigate(`/m/${moduleId}/task/${taskId}`);
    } catch (error) {
      console.error("Upload failed:", error);
      alert("Failed to upload files. Check console.");
      setUploading(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto h-[calc(100vh-140px)] flex flex-col">
      <div className="flex items-center gap-4 mb-6 shrink-0">
        <button onClick={() => navigate(`/m/${moduleId}`)} className="bg-white/5 hover:bg-white/10 p-2.5 rounded-xl transition-colors border border-white/10 text-slate-400 hover:text-white shadow-sm">
          <ArrowLeft className="w-5 h-5" />
        </button>
        <h1 className="text-4xl font-extrabold text-white tracking-tight drop-shadow-sm">New {moduleConfig.name} Extraction</h1>
      </div>

      <div className="bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-white/10 p-8 shadow-2xl shadow-purple-900/20 flex-1 flex gap-10 min-h-0">

        {/* Left Column */}
        <div className="w-[45%] flex flex-col min-h-0">
          <div className={`mb-6 bg-${moduleConfig.themeColor}-500/10 border border-${moduleConfig.themeColor}-400/20 rounded-xl p-5 flex items-start gap-4 shadow-inner shrink-0`}>
            <Info className={`w-6 h-6 text-${moduleConfig.themeColor}-400 shrink-0 mt-0.5`} />
            <div>
              <h3 className={`text-${moduleConfig.themeColor}-300 font-semibold text-sm tracking-wide uppercase mb-2`}>Required Documents</h3>
              <p className="text-slate-300 text-sm mb-3 leading-relaxed">For a complete extraction, drop these files into the main dropzone:</p>
              <ul className="grid grid-cols-1 gap-y-2 text-sm text-slate-400">
                {moduleConfig.uploadRequirements.map((req, idx) => (
                  <li key={idx} className="flex items-center gap-2">
                    <div className={`w-1.5 h-1.5 rounded-full bg-${moduleConfig.themeColor}-400`}></div>
                    <span className="text-slate-200 font-medium">{req.name} {req.mandatory ? '*' : ''}</span> ({req.type})
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div className="mb-6 shrink-0">
            <label className="block text-sm font-semibold text-slate-300 mb-2">Company Name</label>
            <input
              type="text"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              className="w-full px-5 py-3 bg-[#131B2C]/80 border border-white/10 text-white rounded-xl focus:ring-4 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-[#1A2235] outline-none transition-all shadow-inner"
              placeholder="e.g. Karomi Technologies Pvt Ltd"
            />
          </div>

          <div className="flex-1 overflow-y-auto pr-2 custom-scrollbar">
            {files.length > 0 ? (
              <div>
                <h3 className="text-sm font-semibold text-slate-300 mb-3 flex justify-between">
                  <span>Selected Files ({files.length})</span>
                </h3>
                <ul className="space-y-2">
                  {files.map((file, i) => (
                    <li key={i} className="flex items-center justify-between p-3 bg-[#131B2C]/80 border border-white/10 rounded-lg">
                      <div className="flex items-center gap-3 overflow-hidden">
                        <File className={`w-5 h-5 text-${moduleConfig.themeColor}-400 shrink-0`} />
                        <span className="text-sm font-medium text-slate-300 truncate">{file.name}</span>
                        <span className="text-xs text-slate-400 shrink-0">({(file.size / 1024).toFixed(1)} KB)</span>
                      </div>
                      <button onClick={() => removeFile(i)} className="text-slate-400 hover:text-red-500 transition-colors p-1 shrink-0 ml-2">
                        <X className="w-4 h-4" />
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <div className="h-full border-2 border-dashed border-white/5 rounded-xl flex flex-col items-center justify-center text-slate-500">
                <File className="w-8 h-8 mb-2 opacity-50" />
                <p className="text-sm">No files selected</p>
              </div>
            )}
          </div>
        </div>

        {/* Right Column */}
        <div className="flex-1 flex flex-col min-h-0 gap-6 border-l border-white/10 pl-10">

          <div className="flex-1 flex flex-col min-h-0">
            <label className="block text-sm font-semibold text-slate-300 mb-2">Upload Documents</label>
            <div
              onDrop={handleDrop}
              onDragOver={(e) => e.preventDefault()}
              className="flex-1 group relative border-2 border-dashed border-white/20 rounded-2xl flex flex-col items-center justify-center bg-[#131B2C]/50 hover:bg-[#1A2235] hover:border-primary-400 transition-all cursor-pointer overflow-hidden min-h-[200px]"
              onClick={() => document.getElementById('file-upload').click()}
            >
              <div className="absolute inset-0 bg-gradient-to-br from-primary-100/50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
              <div className="bg-[#1A2235] p-4 border border-white/10 rounded-full shadow-md mb-5 group-hover:scale-110 group-hover:shadow-lg transition-all z-10">
                <UploadCloud className={`w-10 h-10 text-${moduleConfig.themeColor}-400`} />
              </div>
              <p className="text-slate-300 font-medium text-lg">Drag & drop files here</p>
              <p className="text-slate-500 text-sm mt-1">or click to browse</p>
              <input
                id="file-upload"
                type="file"
                multiple
                className="hidden"
                onChange={handleFileChange}
              />
            </div>
          </div>

          {moduleConfig.features.hasPreviousYearComparison && (
            <div className="shrink-0">
              <label className="block text-sm font-semibold text-slate-300 mb-2">Previous Year Data (Optional - for auto comparison)</label>
              {previousFlaFile ? (
                <div className={`flex items-center justify-between p-4 bg-${moduleConfig.themeColor}-500/10 border border-${moduleConfig.themeColor}-500/20 rounded-xl`}>
                  <div className="flex items-center gap-3 truncate">
                    <div className={`bg-${moduleConfig.themeColor}-500/20 p-2 rounded-lg shrink-0`}>
                      <File className={`w-5 h-5 text-${moduleConfig.themeColor}-400`} />
                    </div>
                    <div className="truncate">
                      <p className="text-sm font-semibold text-slate-200 truncate">{previousFlaFile.name}</p>
                      <p className="text-xs text-slate-400">Used for automated mismatch detection</p>
                    </div>
                  </div>
                  <button onClick={(e) => { e.preventDefault(); e.stopPropagation(); setPreviousFlaFile(null); }} className="text-slate-400 hover:text-red-500 transition-colors p-2 bg-white/5 rounded-lg hover:bg-white/10 shrink-0 ml-2 z-30 relative">
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ) : (
                <div
                  onDrop={(e) => { e.preventDefault(); if (e.dataTransfer.files[0]) setPreviousFlaFile(e.dataTransfer.files[0]); }}
                  onDragOver={(e) => e.preventDefault()}
                  className={`group relative border-2 border-dashed border-white/10 rounded-xl p-5 flex flex-col items-center justify-center bg-[#131B2C]/30 hover:bg-[#1A2235] hover:border-${moduleConfig.themeColor}-400/50 transition-all cursor-pointer overflow-hidden`}
                  onClick={() => document.getElementById('prev-file-upload').click()}
                >
                  <div className="flex items-center gap-4">
                    <div className="bg-[#1A2235] p-3 border border-white/10 rounded-full shadow-sm group-hover:scale-110 transition-transform">
                      <File className={`w-6 h-6 text-${moduleConfig.themeColor}-400/70`} />
                    </div>
                    <div className="text-left">
                      <p className="text-slate-300 font-medium text-sm">Select Previous Year Document</p>
                      <p className="text-slate-500 text-xs mt-0.5">.pdf, .xlsx, .md</p>
                    </div>
                  </div>
                  <input
                    id="prev-file-upload"
                    type="file"
                    accept=".pdf,.xlsx,.md"
                    className="hidden"
                    onChange={(e) => { if (e.target.files[0]) setPreviousFlaFile(e.target.files[0]); }}
                  />
                </div>
              )}
            </div>
          )}

          <div className="flex justify-end shrink-0 pt-2">
            <button
              onClick={handleUpload}
              disabled={uploading || !companyName || files.length === 0}
              className={`flex w-full justify-center items-center gap-2 bg-gradient-to-r from-${moduleConfig.themeColor}-500 to-${moduleConfig.themeColor}-700 hover:from-${moduleConfig.themeColor}-400 hover:to-${moduleConfig.themeColor}-600 disabled:from-slate-600 disabled:to-slate-700 disabled:text-slate-400 text-white px-8 py-4 rounded-xl font-bold text-lg shadow-lg shadow-${moduleConfig.themeColor}-500/30 hover:shadow-xl hover:-translate-y-0.5 transition-all`}
            >
              {uploading ? <><Loader2 className="w-5 h-5 animate-spin" /> Uploading...</> : 'Upload & Process'}
            </button>
          </div>

        </div>

      </div>
    </div>
  );
}
