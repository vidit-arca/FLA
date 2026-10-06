import React from 'react';
import { Database, Loader2 } from 'lucide-react';

export default function ExtractedDataSidebar({ extractedData, isExtracting, selectedExtractedData, setSelectedExtractedData, rules }) {
  
  // Get a list of extracted keys that are already mapped
  const mappedKeys = rules.map(r => r.extracted_key);

  return (
    <div className="w-full h-full bg-transparent flex flex-col shrink-0">
      <div className="p-5 border-b border-white/5 bg-white/5">
        <div className="flex items-center gap-2 mb-2">
            <Database className="w-5 h-5 text-indigo-400" />
            <h2 className="text-lg font-bold text-white">PDF Data</h2>
        </div>
        <p className="text-xs text-slate-400 font-medium">Auto-extracted values from the document. Select one to map it.</p>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {isExtracting ? (
            <div className="flex flex-col items-center justify-center h-full text-slate-400">
            <Loader2 className="w-6 h-6 animate-spin text-indigo-400 mb-2" />
            <span className="text-sm font-medium">Processing Document...</span>
          </div>
        ) : extractedData.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-slate-400 text-center px-4">
                <p className="text-sm">Upload a PDF to automatically extract its key-value pairs.</p>
            </div>
        ) : (
            extractedData.map((item, idx) => {
                const isSelected = selectedExtractedData === item;
                const isMapped = mappedKeys.includes(item.key);
                
                return (
                  <div 
                    key={idx} 
                    onClick={() => !isMapped && setSelectedExtractedData(item)}
                    className={`p-4 rounded-xl border transition-all duration-200 ${
                      isMapped 
                        ? 'border-emerald-500/30 bg-emerald-500/5 cursor-default' 
                        : isSelected 
                            ? 'border-indigo-400 bg-indigo-500/10 shadow-[0_0_15px_rgba(99,102,241,0.2)] transform scale-[1.02]'
                            : 'border-white/5 bg-black/10 hover:border-white/10 hover:bg-black/20 cursor-pointer'
                    }`}
                  >
                    <div className="flex flex-col gap-1.5">
                      <span className={`text-[10px] font-bold uppercase tracking-wider block truncate ${
                        isMapped ? 'text-emerald-400' : isSelected ? 'text-indigo-400' : 'text-slate-400'
                      }`} title={item.key}>
                        {item.key}
                      </span>
                      
                      <span className={`text-sm font-medium ${
                        isMapped ? 'text-slate-300' : 'text-white'
                      }`}>
                        {item.value}
                      </span>
                    </div>
                    
                    {isMapped && (
                      <div className="mt-3 flex items-center gap-1.5">
                          <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]"></div>
                          <span className="text-xs text-emerald-400 font-medium">Mapped</span>
                      </div>
                    )}
                  </div>
                );
            })
        )}
      </div>
    </div>
  );
}
