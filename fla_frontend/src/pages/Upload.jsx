import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { UploadCloud, File, X, Loader2 } from 'lucide-react';

export default function Upload() {
  const [files, setFiles] = useState([]);
  const [companyName, setCompanyName] = useState('');
  const [uploading, setUploading] = useState(false);
  const navigate = useNavigate();

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

    try {
      // POST upload
      const res = await axios.post(`http://localhost:8000/api/upload?company_name=${encodeURIComponent(companyName)}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      const taskId = res.data.task_id;
      
      // Trigger processing immediately after upload
      await axios.post(`http://localhost:8000/api/process/${taskId}`);
      
      // Navigate to task view to watch progress
      navigate(`/task/${taskId}`);
    } catch (error) {
      console.error("Upload failed:", error);
      alert("Failed to upload files. Check console.");
      setUploading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-4xl font-extrabold text-white mb-8 tracking-tight drop-shadow-sm">New Extraction</h1>
      
      <div className="bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-white/10 p-10 shadow-2xl shadow-purple-900/20">
        
        <div className="mb-6">
          <label className="block text-sm font-semibold text-slate-300 mb-2">Company Name</label>
          <input 
            type="text" 
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
            className="w-full px-5 py-3 bg-[#131B2C]/80 border border-white/10 text-white rounded-xl focus:ring-4 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-[#1A2235] outline-none transition-all shadow-inner"
            placeholder="e.g. Karomi Technologies Pvt Ltd"
          />
        </div>

        <div className="mb-6">
          <label className="block text-sm font-semibold text-slate-300 mb-2">Upload Documents</label>
          <div 
            onDrop={handleDrop}
            onDragOver={(e) => e.preventDefault()}
            className="group relative border-2 border-dashed border-white/20 rounded-2xl p-12 flex flex-col items-center justify-center bg-[#131B2C]/50 hover:bg-[#1A2235] hover:border-primary-400 transition-all cursor-pointer overflow-hidden"
            onClick={() => document.getElementById('file-upload').click()}
          >
            <div className="absolute inset-0 bg-gradient-to-br from-primary-100/50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
            <div className="bg-[#1A2235] p-4 border border-white/10 rounded-full shadow-md mb-5 group-hover:scale-110 group-hover:shadow-lg transition-all z-10">
              <UploadCloud className="w-10 h-10 text-indigo-400" />
            </div>
            <p className="text-slate-300 font-medium text-lg">Drag & drop files here</p>
            <p className="text-slate-500 text-sm mt-1">or click to browse</p>
            <p className="text-slate-400 text-xs mt-4">Supports .pdf, .md, .xlsx</p>
            <input 
              id="file-upload" 
              type="file" 
              multiple 
              className="hidden" 
              onChange={handleFileChange}
            />
          </div>
        </div>

        {files.length > 0 && (
          <div className="mb-8">
            <h3 className="text-sm font-semibold text-slate-300 mb-3">Selected Files ({files.length})</h3>
            <ul className="space-y-2">
              {files.map((file, i) => (
                <li key={i} className="flex items-center justify-between p-3 bg-[#131B2C]/80 border border-white/10 rounded-lg">
                  <div className="flex items-center gap-3">
                    <File className="w-5 h-5 text-indigo-400" />
                    <span className="text-sm font-medium text-slate-300">{file.name}</span>
                    <span className="text-xs text-slate-400">({(file.size / 1024).toFixed(1)} KB)</span>
                  </div>
                  <button onClick={() => removeFile(i)} className="text-slate-400 hover:text-red-500 transition-colors p-1">
                    <X className="w-4 h-4" />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="flex justify-end">
          <button 
            onClick={handleUpload}
            disabled={uploading || !companyName || files.length === 0}
            className="flex items-center gap-2 bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-400 hover:to-purple-500 disabled:from-slate-400 disabled:to-slate-400 text-white px-8 py-3.5 rounded-xl font-bold text-lg shadow-lg shadow-primary-500/30 hover:shadow-xl hover:shadow-primary-500/40 hover:-translate-y-0.5 transition-all"
          >
            {uploading ? <><Loader2 className="w-5 h-5 animate-spin" /> Uploading...</> : 'Upload & Process'}
          </button>
        </div>

      </div>
    </div>
  );
}
