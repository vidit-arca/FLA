import { useState } from 'react';
import { UploadCloud, FileSpreadsheet, CheckCircle, AlertCircle, RefreshCw, FileText } from 'lucide-react';

export default function ComparisonPlatform() {
  const [selectedModule, setSelectedModule] = useState('fla');
  const [sourceFile, setSourceFile] = useState(null);
  const [targetFile, setTargetFile] = useState(null);
  const [isComparing, setIsComparing] = useState(false);
  const [results, setResults] = useState(null);

  const modules = [
    { id: 'fla', name: 'FLA Comparison Module' },
    { id: 'aoc', name: 'AOC Comparison Module' }
  ];

  const handleCompare = async () => {
    if (!sourceFile || !targetFile) return;
    
    setIsComparing(true);
    setResults(null);
    
    const formData = new FormData();
    formData.append('source_file', sourceFile);
    formData.append('target_file', targetFile);

    try {
      // Assuming API is running on localhost:8000 like the rest of the app
      const response = await fetch(`http://localhost:8000/api/platform-compare/${selectedModule}`, {
        method: 'POST',
        body: formData,
      });
      
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Comparison failed');
      }
      
      setResults(data.results);
    } catch (error) {
      console.error(error);
      alert(error.message);
    } finally {
      setIsComparing(false);
    }
  };

  return (
    <div className="animate-fade-in space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Comparison Platform</h1>
          <p className="text-slate-400 mt-1">Analyze and compare your datasets seamlessly across different modules.</p>
        </div>
      </div>

      <div className="bg-[#131B2C] border border-white/5 rounded-2xl p-6 shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500/5 rounded-full blur-[80px] pointer-events-none" />
        
        <div className="relative z-10 space-y-8">
          {/* Module Selection */}
          <div className="space-y-3">
            <label className="text-sm font-semibold text-slate-300 uppercase tracking-wider">Select Comparison Module</label>
            <div className="relative w-full md:w-1/2">
              <select 
                value={selectedModule}
                onChange={(e) => setSelectedModule(e.target.value)}
                className="w-full appearance-none bg-[#0B0F19] border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all cursor-pointer"
              >
                {modules.map(m => (
                  <option key={m.id} value={m.id}>{m.name}</option>
                ))}
              </select>
              <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path></svg>
              </div>
            </div>
          </div>

          {/* Upload Areas */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            
            {/* Source Data Upload */}
            <div className="space-y-2">
              <div className="flex justify-between items-center px-1">
                <span className="text-sm font-medium text-slate-300">Source Data</span>
                {sourceFile && <span className="text-xs text-indigo-400 font-medium flex items-center gap-1"><CheckCircle className="w-3 h-3"/> Uploaded</span>}
              </div>
              <label className={`flex flex-col items-center justify-center w-full h-48 border-2 border-dashed rounded-2xl cursor-pointer transition-all duration-200 ${sourceFile ? 'border-indigo-500/50 bg-indigo-500/5' : 'border-white/10 hover:border-indigo-500/30 hover:bg-white/5 bg-[#0B0F19]'}`}>
                <div className="flex flex-col items-center justify-center pt-5 pb-6 text-center px-4">
                  <UploadCloud className={`w-10 h-10 mb-3 ${sourceFile ? 'text-indigo-400' : 'text-slate-500'}`} />
                  <p className="mb-2 text-sm text-slate-300 font-medium">
                    {sourceFile ? sourceFile.name : 'Drag & Drop Source File'}
                  </p>
                  {!sourceFile && <p className="text-xs text-slate-500">Supported formats depend on module</p>}
                </div>
                <input 
                  type="file" 
                  className="hidden" 
                  onChange={(e) => setSourceFile(e.target.files[0])}
                />
              </label>
            </div>

            {/* Target Data Upload */}
            <div className="space-y-2">
              <div className="flex justify-between items-center px-1">
                <span className="text-sm font-medium text-slate-300">Target Data</span>
                {targetFile && <span className="text-xs text-indigo-400 font-medium flex items-center gap-1"><CheckCircle className="w-3 h-3"/> Uploaded</span>}
              </div>
              <label className={`flex flex-col items-center justify-center w-full h-48 border-2 border-dashed rounded-2xl cursor-pointer transition-all duration-200 ${targetFile ? 'border-indigo-500/50 bg-indigo-500/5' : 'border-white/10 hover:border-indigo-500/30 hover:bg-white/5 bg-[#0B0F19]'}`}>
                <div className="flex flex-col items-center justify-center pt-5 pb-6 text-center px-4">
                  <UploadCloud className={`w-10 h-10 mb-3 ${targetFile ? 'text-indigo-400' : 'text-slate-500'}`} />
                  <p className="mb-2 text-sm text-slate-300 font-medium">
                    {targetFile ? targetFile.name : 'Drag & Drop Target File'}
                  </p>
                  {!targetFile && <p className="text-xs text-slate-500">Supported formats depend on module</p>}
                </div>
                <input 
                  type="file" 
                  className="hidden" 
                  onChange={(e) => setTargetFile(e.target.files[0])}
                />
              </label>
            </div>

          </div>

          {/* Action Area */}
          <div className="pt-4 border-t border-white/5 flex justify-end">
            <button
              onClick={handleCompare}
              disabled={!sourceFile || !targetFile || isComparing}
              className={`flex items-center gap-2 px-6 py-3 rounded-xl font-medium transition-all ${(!sourceFile || !targetFile || isComparing) ? 'bg-white/5 text-slate-500 cursor-not-allowed' : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-500/20'}`}
            >
              {isComparing ? (
                <>
                  <RefreshCw className="w-5 h-5 animate-spin" />
                  Comparing...
                </>
              ) : (
                <>
                  <FileSpreadsheet className="w-5 h-5" />
                  Start Comparison
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Results Section */}
      {results && (
        <div className="bg-[#131B2C] border border-white/5 rounded-2xl overflow-hidden shadow-xl animate-fade-in">
          <div className="p-6 border-b border-white/5 bg-white/[0.02]">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <FileText className="w-5 h-5 text-indigo-400" />
              Comparison Results
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="text-xs text-slate-400 uppercase bg-black/20 border-b border-white/5">
                <tr>
                  <th className="px-6 py-4 font-semibold">Cell/Field</th>
                  <th className="px-6 py-4 font-semibold">Source Value</th>
                  <th className="px-6 py-4 font-semibold">Target Value</th>
                  <th className="px-6 py-4 font-semibold">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {results.map((row, idx) => (
                  <tr key={idx} className="hover:bg-white/[0.02] transition-colors">
                    <td className="px-6 py-4 font-medium text-slate-300">{row.cell}</td>
                    <td className="px-6 py-4 text-slate-400">{row.sourceValue}</td>
                    <td className="px-6 py-4 text-slate-400">{row.targetValue}</td>
                    <td className="px-6 py-4">
                      {row.status === 'Match' ? (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                          <CheckCircle className="w-3 h-3" />
                          Match
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20">
                          <AlertCircle className="w-3 h-3" />
                          Mismatch
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
