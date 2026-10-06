import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { AlertTriangle, ShieldCheck, Users, FileWarning, Search, ChevronRight } from 'lucide-react';

export default function AOC4HubExtensions() {
  // Mock Data for Top Common Errors
  const commonErrorsData = [
    { name: 'Audit Trail Missing', count: 42, color: '#818cf8' },
    { name: 'Shareholding Mismatch', count: 28, color: '#6366f1' },
    { name: 'Schedule III Format', count: 19, color: '#4f46e5' },
    { name: 'CARO Section Missing', count: 14, color: '#4338ca' },
    { name: 'EPS Calculation Error', count: 8, color: '#3730a3' }
  ];

  // Mock Data for Missing Sources
  const missingSources = [
    { client: 'TechNova Solutions Pvt Ltd', missing: 'Notes to Accounts', days: 2 },
    { client: 'Global Horizons LLP', missing: 'Audit Report', days: 5 },
    { client: 'Apex Dynamics India', missing: 'Input Sheet', days: 1 }
  ];

  return (
    <div className="mt-8 mb-8 flex flex-col gap-6">

      {/* AOC4 Header Section */}
      <div className="flex items-center gap-3 pb-2 border-b border-indigo-500/20">
        <Search className="w-5 h-5 text-indigo-400" />
        <h2 className="text-lg font-bold text-slate-900 dark:text-white tracking-wide">AOC4 Extraction Insights</h2>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Left Panel: Common Errors Bar Chart (Takes up 2 columns) */}
        <div className="lg:col-span-2 bg-white dark:bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-slate-200 dark:border-white/10 p-6 shadow-xl flex flex-col h-[350px]">
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-6 flex items-center gap-2 uppercase tracking-wider">
            <AlertTriangle className="w-4 h-4 text-amber-400" /> Top Common Rule Failures
          </h3>
          <div className="flex-1 w-full min-h-0">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart layout="vertical" data={commonErrorsData} margin={{ top: 0, right: 30, left: 40, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" horizontal={true} vertical={false} />
                <XAxis type="number" stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis dataKey="name" type="category" stroke="#64748b" tick={{ fill: '#cbd5e1', fontSize: 11, fontWeight: 500 }} axisLine={false} tickLine={false} />
                <Tooltip
                  cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                  contentStyle={{ backgroundColor: 'rgba(15, 23, 42, 0.9)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', color: '#fff' }}
                />
                <Bar dataKey="count" radius={[0, 4, 4, 0]} barSize={24}>
                  {commonErrorsData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Right Panel: KPI Stack */}
        <div className="flex flex-col gap-6">

          {/* Audit Trail KPI */}
          <div className="bg-white dark:bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-slate-200 dark:border-white/10 p-5 shadow-xl flex flex-col justify-center flex-1 relative overflow-hidden group">
            <div className="absolute -right-10 -top-10 w-32 h-32 bg-emerald-500/10 rounded-full blur-2xl group-hover:bg-emerald-500/20 transition-all"></div>
            <div className="flex items-center gap-4 relative z-10">
              <div className="bg-emerald-500/20 p-3 rounded-xl border border-emerald-500/30">
                <ShieldCheck className="w-8 h-8 text-emerald-400" />
              </div>
              <div>
                <p className="text-[10px] text-slate-600 dark:text-slate-400 font-bold tracking-widest uppercase mb-1">Audit Trail Compliance</p>
                <div className="flex items-end gap-2">
                  <p className="text-3xl font-extrabold text-slate-900 dark:text-white leading-none">68%</p>
                  <p className="text-xs font-semibold text-emerald-400 mb-0.5">Passed</p>
                </div>
              </div>
            </div>
            <div className="mt-4 w-full h-1.5 bg-slate-800 rounded-full overflow-hidden relative z-10">
              <div className="h-full bg-emerald-500 rounded-full" style={{ width: '68%' }}></div>
            </div>
          </div>

          {/* Manual Backlog KPI */}
          <div className="bg-white dark:bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-slate-200 dark:border-white/10 p-5 shadow-xl flex flex-col justify-center flex-1 relative overflow-hidden group">
            <div className="absolute -right-10 -top-10 w-32 h-32 bg-indigo-500/10 rounded-full blur-2xl group-hover:bg-indigo-500/20 transition-all"></div>
            <div className="flex items-center gap-4 relative z-10">
              <div className="bg-indigo-500/20 p-3 rounded-xl border border-indigo-500/30">
                <Users className="w-8 h-8 text-indigo-400" />
              </div>
              <div>
                <p className="text-[10px] text-slate-600 dark:text-slate-400 font-bold tracking-widest uppercase mb-1">Manual Verifications</p>
                <div className="flex items-end gap-2">
                  <p className="text-3xl font-extrabold text-slate-900 dark:text-white leading-none">24</p>
                  <p className="text-xs font-semibold text-indigo-400 mb-0.5">Tasks Waiting</p>
                </div>
              </div>
            </div>
            <p className="text-xs text-slate-500 mt-3 font-medium relative z-10">Pending calls with client for Board Resolutions.</p>
          </div>

        </div>
      </div>

      {/* Bottom Panel: Missing Sources Tracker */}
      <div className="bg-white dark:bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-slate-200 dark:border-white/10 shadow-xl overflow-hidden flex flex-col">
        <div className="px-6 py-4 border-b border-slate-200 dark:border-white/10 bg-rose-500/5 flex items-center justify-between">
          <h2 className="text-sm font-bold text-rose-400 uppercase tracking-wider flex items-center gap-2">
            <FileWarning className="w-4 h-4" /> Missing Source Documents Alert
          </h2>
          <span className="bg-rose-500/20 text-rose-400 text-xs font-bold px-2 py-0.5 rounded-md border border-rose-500/20">
            {missingSources.length} Issues
          </span>
        </div>
        <div className="p-2">
          {missingSources.map((item, idx) => (
            <div key={idx} className="flex items-center justify-between p-4 hover:bg-slate-900/[0.02] dark:bg-white/[0.02] rounded-xl transition-colors border border-transparent hover:border-slate-200 dark:border-white/5">
              <div className="flex flex-col">
                <p className="text-sm font-bold text-slate-800 dark:text-slate-200">{item.client}</p>
                <p className="text-xs text-slate-500 font-medium mt-0.5">AOC4 Return Processing Stalled</p>
              </div>
              <div className="flex items-center gap-6">
                <div className="text-right">
                  <p className="text-[10px] text-slate-600 dark:text-slate-400 font-bold uppercase tracking-widest">Missing Document</p>
                  <p className="text-sm font-bold text-amber-400">{item.missing}</p>
                </div>
                <div className="text-right w-20">
                  <p className="text-[10px] text-slate-600 dark:text-slate-400 font-bold uppercase tracking-widest">Delay</p>
                  <p className="text-sm font-bold text-rose-400">{item.days} Days</p>
                </div>
                <button className="w-8 h-8 rounded-full bg-slate-800 hover:bg-slate-700 flex items-center justify-center transition-colors border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300">
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
}
