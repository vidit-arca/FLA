import React from 'react';
import { Database, Loader2 } from 'lucide-react';

export default function ExtractedDataSidebar({ extractedData, isExtracting, selectedExtractedData, setSelectedExtractedData, rules }) {
  
  // Get a list of extracted keys that are already mapped
  const mappedKeys = rules.map(r => r.extracted_key);

  return (
    <div className="w-80 h-full bg-white dark:bg-[#1A2234] border-l border-slate-200 dark:border-white/10 flex flex-col shrink-0">
      <div className="p-5 border-b border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5">
        <div className="flex items-center gap-2 mb-2">
            <Database className="w-5 h-5 text-indigo-500" />
            <h2 className="text-lg font-bold text-slate-800 dark:text-white">PDF Data</h2>
        </div>
        <p className="text-xs text-slate-500">Auto-extracted values from the document. Select one to map it.</p>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {isExtracting ? (
            <div className="flex flex-col items-center justify-center h-full text-slate-400 gap-3">
                <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
                <p className="text-sm font-medium">Extracting data from PDF...</p>
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
                        onClick={() => {
                            if (!isMapped) setSelectedExtractedData(isSelected ? null : item);
                        }}
                        className={`p-3 rounded-lg border transition-all ${
                            isMapped 
                                ? 'bg-slate-100 dark:bg-white/5 border-slate-200 dark:border-white/10 opacity-60 cursor-not-allowed'
                                : isSelected 
                                    ? 'bg-indigo-600 border-indigo-600 shadow-md text-white' 
                                    : 'bg-white dark:bg-transparent border-slate-200 dark:border-white/10 cursor-pointer hover:border-indigo-300 dark:hover:border-indigo-500/50 hover:shadow-sm'
                        }`}
                    >
                        <div className="flex flex-col gap-1.5">
                            <div className="flex justify-between items-start">
                                <span className={`text-xs font-bold uppercase ${isSelected ? 'text-indigo-100' : 'text-slate-500'}`}>{item.key}</span>
                                {isMapped && <span className="text-[10px] font-bold bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-300 px-1.5 py-0.5 rounded">MAPPED</span>}
                            </div>
                            <span className={`text-lg font-bold tracking-tight ${isSelected ? 'text-white' : 'text-slate-800 dark:text-white'}`}>{item.value}</span>
                        </div>
                    </div>
                );
            })
        )}
      </div>
    </div>
  );
}
