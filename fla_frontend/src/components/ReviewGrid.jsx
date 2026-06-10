import { useState } from 'react';
import { Save } from 'lucide-react';

export default function ReviewGrid({ initialData, onExport }) {
  const [data, setData] = useState(initialData);

  const handleInputChange = (key, value) => {
    setData(prev => ({
      ...prev,
      [key]: value
    }));
  };

  const handleSaveAndExport = () => {
    onExport(data);
  };

  // Group fields logically if possible, otherwise list alphabetically
  const keys = Object.keys(data).sort();

  return (
    <div className="flex flex-col h-[600px]">
      <div className="flex-1 overflow-auto">
        <table className="w-full text-left border-collapse">
          <thead className="sticky top-0 bg-white shadow-sm z-10">
            <tr>
              <th className="px-6 py-3 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase tracking-wider w-1/3">Extracted Parameter</th>
              <th className="px-6 py-3 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase tracking-wider w-2/3">Extracted Value</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {keys.map((key) => {
              // Convert value to string for input
              let val = data[key];
              if (val === null || val === undefined) val = "";
              else if (typeof val === 'object') val = JSON.stringify(val);
              else val = String(val);

              return (
                <tr key={key} className="hover:bg-slate-50 transition-colors">
                  <td className="px-6 py-3 font-mono text-sm text-slate-700">
                    {key}
                  </td>
                  <td className="px-6 py-2">
                    <input 
                      type="text"
                      value={val}
                      onChange={(e) => handleInputChange(key, e.target.value)}
                      className="w-full px-3 py-1.5 border border-slate-200 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none text-sm transition-all"
                    />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <div className="p-4 border-t border-slate-200 bg-white flex justify-end">
        <button 
          onClick={handleSaveAndExport}
          className="flex items-center gap-2 bg-primary-600 hover:bg-primary-700 text-white px-6 py-2.5 rounded-lg font-medium transition-colors"
        >
          <Save className="w-5 h-5" />
          Save & Generate Excel
        </button>
      </div>
    </div>
  );
}
