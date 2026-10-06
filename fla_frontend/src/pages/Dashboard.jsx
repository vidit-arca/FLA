import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { 
  LayoutDashboard, Package, Zap, Users, Settings, Activity, 
  ArrowRight, ShieldCheck, FileText, Cpu, Database, Clock, 
  Server, CheckCircle, AlertCircle, ClipboardCheck, ShieldAlert,
  Wand2, Sliders, ExternalLink, Sparkles, Layers, CheckCircle2
} from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { MODULES_SCHEMA } from '../config/modulesSchema';

export default function Dashboard() {
  const navigate = useNavigate();
  const [totalDocs, setTotalDocs] = useState(0);
  const [templateCount, setTemplateCount] = useState(0);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const [tasksRes, templatesRes] = await Promise.all([
          axios.get('http://localhost:8000/api/tasks').catch(() => ({ data: [] })),
          axios.get('http://localhost:8000/api/idp/templates').catch(() => ({ data: [] }))
        ]);
        if (Array.isArray(tasksRes.data)) {
          setTotalDocs(tasksRes.data.length);
        }
        if (Array.isArray(templatesRes.data)) {
          setTemplateCount(templatesRes.data.length);
        }
      } catch (err) {
        console.error("Failed to fetch real-time dashboard stats:", err);
      }
    };

    fetchStats();
    const interval = setInterval(fetchStats, 5000);
    return () => clearInterval(interval);
  }, []);

  const moduleDistribution = [
    { name: 'FLA Return Module', value: 45, color: '#818cf8', bg: 'bg-indigo-500/20' },
    { name: 'IDP Batch Extractor', value: 25, color: '#38bdf8', bg: 'bg-sky-500/20' },
    { name: 'IDP Studio & Builder', value: 18, color: '#c084fc', bg: 'bg-purple-500/20' },
    { name: 'AOC 4 (MCA) Module', value: 12, color: '#34d399', bg: 'bg-emerald-500/20' }
  ];
  const COLORS = ['#818cf8', '#38bdf8', '#c084fc', '#34d399'];

  const activityFeed = [
    { id: 1, text: "Admin mapped 11 fields for 'Karomi_2025' in IDP Studio", time: "2 mins ago", icon: Sliders, color: "text-purple-400", bg: "bg-purple-500/20" },
    { id: 2, text: "IDP Batch Extractor reconciled 2 documents against RBI Rule Engine", time: "14 mins ago", icon: Wand2, color: "text-sky-400", bg: "bg-sky-500/20" },
    { id: 3, text: "Admin uploaded 5 files to FLA Return Module", time: "28 mins ago", icon: FileText, color: "text-indigo-400", bg: "bg-indigo-500/20" },
    { id: 4, text: "System verified PAN & closing dates via IDP-to-FLA Bridge", time: "1 hour ago", icon: CheckCircle2, color: "text-emerald-400", bg: "bg-emerald-500/20" },
    { id: 5, text: "Admin ran Comparison Manager on 'Reliance_FY23'", time: "3 hours ago", icon: Activity, color: "text-amber-400", bg: "bg-amber-500/20" },
  ];

  return (
    <div className="pb-12 animate-in fade-in duration-300">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">Platform Overview</h1>
            <span className="flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400 border border-emerald-500/30">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
              All 4 Systems Operational
            </span>
          </div>
          <p className="text-slate-600 dark:text-slate-400 text-sm mt-1">
            Enterprise AI Extraction, Rule-Engine Reconciliation, and Visual Document Processing Ecosystem.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <a
            href="/idp-studio"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold bg-purple-600 hover:bg-purple-700 text-white shadow-lg shadow-purple-500/20 transition-all hover:-translate-y-0.5"
          >
            <Sliders className="w-4 h-4" />
            Open IDP Studio
          </a>
          <a
            href="/idp-extract"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold bg-indigo-600 hover:bg-indigo-700 text-white shadow-lg shadow-indigo-500/20 transition-all hover:-translate-y-0.5"
          >
            <Wand2 className="w-4 h-4" />
            Launch Extractor
          </a>
        </div>
      </div>
      
      {/* Top Stats Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-10">
        <div className="bg-white dark:bg-[#1A2235]/80 backdrop-blur-xl rounded-2xl border border-slate-200 dark:border-white/10 p-5 shadow-xl hover:-translate-y-1 transition-transform">
          <div className="flex items-center justify-between mb-4">
            <div className="bg-indigo-500/20 p-2.5 rounded-xl"><Package className="text-indigo-400 w-5 h-5" /></div>
            <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400 bg-emerald-100 dark:bg-emerald-500/20 px-2.5 py-0.5 rounded-full">100% Uptime</span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 font-bold tracking-wide uppercase">Active Enterprise Modules</p>
          <p className="text-3xl font-extrabold text-slate-900 dark:text-white mt-1">4<span className="text-xs font-normal text-slate-500 ml-1">Suites</span></p>
        </div>
        
        <div className="bg-white dark:bg-[#1A2235]/80 backdrop-blur-xl rounded-2xl border border-slate-200 dark:border-white/10 p-5 shadow-xl hover:-translate-y-1 transition-transform">
          <div className="flex items-center justify-between mb-4">
            <div className="bg-sky-500/20 p-2.5 rounded-xl"><Zap className="text-sky-400 w-5 h-5" /></div>
            <span className="flex items-center gap-1 text-xs font-bold text-sky-600 dark:text-sky-400 bg-sky-100 dark:bg-sky-500/20 px-2.5 py-0.5 rounded-full">
              <span className="w-1.5 h-1.5 rounded-full bg-sky-500 animate-pulse"></span>
              Live
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 font-bold tracking-wide uppercase">Documents Processed (30d)</p>
          <p className="text-3xl font-extrabold text-slate-900 dark:text-white mt-1">{totalDocs}</p>
        </div>

        <div className="bg-white dark:bg-[#1A2235]/80 backdrop-blur-xl rounded-2xl border border-slate-200 dark:border-white/10 p-5 shadow-xl hover:-translate-y-1 transition-transform">
          <div className="flex items-center justify-between mb-4">
            <div className="bg-purple-500/20 p-2.5 rounded-xl"><Sliders className="text-purple-400 w-5 h-5" /></div>
            <span className="flex items-center gap-1 text-xs font-bold text-purple-600 dark:text-purple-400 bg-purple-100 dark:bg-purple-500/20 px-2.5 py-0.5 rounded-full">
              <span className="w-1.5 h-1.5 rounded-full bg-purple-500 animate-pulse"></span>
              Live
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 font-bold tracking-wide uppercase">IDP Form Templates</p>
          <p className="text-3xl font-extrabold text-slate-900 dark:text-white mt-1">{templateCount}<span className="text-xs font-normal text-slate-500 ml-1">Active</span></p>
        </div>

        <div 
          onClick={() => navigate('/review')}
          className="bg-white dark:bg-[#1A2235]/80 backdrop-blur-xl rounded-2xl border border-amber-500/30 p-5 shadow-[0_0_25px_rgba(245,158,11,0.08)] hover:border-amber-500/60 hover:-translate-y-1 transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between mb-4">
            <div className="bg-amber-500/20 p-2.5 rounded-xl group-hover:bg-amber-500/30 transition-colors"><ClipboardCheck className="text-amber-400 w-5 h-5" /></div>
            <span className="text-[10px] font-bold text-amber-500 dark:text-amber-400 bg-amber-100 dark:bg-amber-500/20 border border-amber-400/20 px-2.5 py-0.5 rounded-full uppercase tracking-wider animate-pulse">Action Required</span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 font-bold tracking-wide uppercase group-hover:text-amber-500 dark:group-hover:text-amber-300 transition-colors">Tasks Awaiting Review</p>
          <p className="text-3xl font-extrabold text-amber-500 dark:text-amber-400 mt-1">5</p>
        </div>
      </div>

      {/* Enterprise Core Modules Grid (4 Modules) */}
      <div className="mb-10">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-sm font-extrabold text-slate-700 dark:text-slate-300 uppercase tracking-wider flex items-center gap-2">
            <Layers className="w-4 h-4 text-indigo-500" /> Enterprise Core Modules & IDP Suites
          </h2>
          <span className="text-xs font-semibold text-slate-500">4 standalone AI systems installed & configured</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {/* 1. IDP Batch Extractor */}
          <div className="bg-gradient-to-br from-white to-sky-50/40 dark:from-[#161F33] dark:to-[#111827] border border-sky-500/30 hover:border-sky-500/60 rounded-2xl p-6 shadow-xl flex flex-col justify-between group transition-all duration-300 hover:-translate-y-1">
            <div>
              <div className="flex items-center justify-between mb-4">
                <div className="w-12 h-12 rounded-xl bg-sky-500/20 flex items-center justify-center group-hover:scale-105 transition-transform">
                  <Wand2 className="w-6 h-6 text-sky-500 dark:text-sky-400" />
                </div>
                <span className="text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-full bg-sky-500/10 text-sky-600 dark:text-sky-400 border border-sky-500/20">
                  Batch Extraction
                </span>
              </div>
              <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-2">IDP Batch Extractor</h3>
              <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                DOM-first batch PDF/Excel extraction with digital text layer + Qwen LLM fallback, inline confidence inspection, and 100% deterministic RBI packet export.
              </p>
            </div>
            <div className="mt-6 pt-4 border-t border-slate-200 dark:border-white/10 flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-500">Standalone App</span>
              <a
                href="/idp-extract"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-bold bg-sky-500 hover:bg-sky-600 text-white shadow-sm transition-colors"
              >
                Launch Extractor <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          </div>

          {/* 2. IDP Studio & Form Builder */}
          <div className="bg-gradient-to-br from-white to-purple-50/40 dark:from-[#1A1C35] dark:to-[#111827] border border-purple-500/30 hover:border-purple-500/60 rounded-2xl p-6 shadow-xl flex flex-col justify-between group transition-all duration-300 hover:-translate-y-1">
            <div>
              <div className="flex items-center justify-between mb-4">
                <div className="w-12 h-12 rounded-xl bg-purple-500/20 flex items-center justify-center group-hover:scale-105 transition-transform">
                  <Sliders className="w-6 h-6 text-purple-500 dark:text-purple-400" />
                </div>
                <span className="text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-full bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20">
                  Visual Studio
                </span>
              </div>
              <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-2">IDP Studio & Builder</h3>
              <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                Visual bounding-box template builder, Phase 0 semantic alias normalizer, custom JSON schema mappings, and live rule-engine bridge adapter.
              </p>
            </div>
            <div className="mt-6 pt-4 border-t border-slate-200 dark:border-white/10 flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-500">Standalone App</span>
              <a
                href="/idp-studio"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-bold bg-purple-600 hover:bg-purple-700 text-white shadow-sm transition-colors"
              >
                Open Studio <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          </div>

          {/* 3. FLA Return Automation */}
          <div className="bg-gradient-to-br from-white to-indigo-50/40 dark:from-[#1A2038] dark:to-[#111827] border border-indigo-500/30 hover:border-indigo-500/60 rounded-2xl p-6 shadow-xl flex flex-col justify-between group transition-all duration-300 hover:-translate-y-1">
            <div>
              <div className="flex items-center justify-between mb-4">
                <div className="w-12 h-12 rounded-xl bg-indigo-500/20 flex items-center justify-center group-hover:scale-105 transition-transform">
                  <FileText className="w-6 h-6 text-indigo-500 dark:text-indigo-400" />
                </div>
                <span className="text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-full bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20">
                  RBI Compliance
                </span>
              </div>
              <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-2">FLA Return Module</h3>
              <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                Foreign Liabilities and Assets return automation with RBI compliance checks, Section I-IV mathematical reconciliation, and PY/FY comparison.
              </p>
            </div>
            <div className="mt-6 pt-4 border-t border-slate-200 dark:border-white/10 flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-500">Core Module</span>
              <button
                onClick={() => navigate('/m/fla')}
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-bold bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm transition-colors"
              >
                Open Workspace <ArrowRight className="w-3 h-3" />
              </button>
            </div>
          </div>

          {/* 4. AOC 4 (MCA) Manager */}
          <div className="bg-gradient-to-br from-white to-emerald-50/40 dark:from-[#15272B] dark:to-[#111827] border border-emerald-500/30 hover:border-emerald-500/60 rounded-2xl p-6 shadow-xl flex flex-col justify-between group transition-all duration-300 hover:-translate-y-1">
            <div>
              <div className="flex items-center justify-between mb-4">
                <div className="w-12 h-12 rounded-xl bg-emerald-500/20 flex items-center justify-center group-hover:scale-105 transition-transform">
                  <ShieldAlert className="w-6 h-6 text-emerald-500 dark:text-emerald-400" />
                </div>
                <span className="text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                  MCA Filing
                </span>
              </div>
              <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-2">AOC 4 (MCA) Module</h3>
              <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                Manage, extract, and review MCA AOC 4 financial statements, auditor report cross-checking, and statutory disclosure validation.
              </p>
            </div>
            <div className="mt-6 pt-4 border-t border-slate-200 dark:border-white/10 flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-500">Core Module</span>
              <button
                onClick={() => navigate('/m/aoc4')}
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm transition-colors"
              >
                Open Workspace <ArrowRight className="w-3 h-3" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* System Metrics & Activity + Module Traffic Donut */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-10">
        
        {/* System & Hardware Metrics */}
        <div className="lg:col-span-2 bg-white dark:bg-[#1A2235]/80 backdrop-blur-xl rounded-2xl border border-slate-200 dark:border-white/10 p-6 shadow-xl">
          <h2 className="text-sm font-extrabold text-slate-700 dark:text-slate-300 mb-6 flex items-center gap-2 uppercase tracking-wider">
            <Server className="w-4 h-4 text-indigo-400" /> System Performance & Extraction Accuracy
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-slate-50 dark:bg-black/20 rounded-xl p-5 border border-slate-200 dark:border-white/5">
              <div className="flex items-center gap-3 mb-2">
                <Clock className="w-5 h-5 text-amber-500 dark:text-amber-400" />
                <h3 className="text-xs font-bold uppercase text-slate-500 dark:text-slate-400">Avg Processing Speed</h3>
              </div>
              <p className="text-2xl font-extrabold text-slate-900 dark:text-white">2.4<span className="text-sm font-normal text-slate-500 ml-1">sec / page</span></p>
              <div className="w-full bg-slate-200 dark:bg-white/5 rounded-full h-1.5 mt-3">
                <div className="bg-amber-500 dark:bg-amber-400 h-1.5 rounded-full" style={{ width: '85%' }}></div>
              </div>
            </div>

            <div className="bg-slate-50 dark:bg-black/20 rounded-xl p-5 border border-slate-200 dark:border-white/5">
              <div className="flex items-center gap-3 mb-2">
                <Cpu className="w-5 h-5 text-emerald-500 dark:text-emerald-400" />
                <h3 className="text-xs font-bold uppercase text-slate-500 dark:text-slate-400">DOM Match Rate</h3>
              </div>
              <p className="text-2xl font-extrabold text-emerald-600 dark:text-emerald-400">98.4%</p>
              <div className="w-full bg-slate-200 dark:bg-white/5 rounded-full h-1.5 mt-3">
                <div className="bg-emerald-500 dark:bg-emerald-400 h-1.5 rounded-full shadow-[0_0_10px_rgba(52,211,153,0.4)]" style={{ width: '98.4%' }}></div>
              </div>
            </div>

            <div className="bg-slate-50 dark:bg-black/20 rounded-xl p-5 border border-slate-200 dark:border-white/5">
              <div className="flex items-center gap-3 mb-2">
                <Database className="w-5 h-5 text-purple-500 dark:text-purple-400" />
                <h3 className="text-xs font-bold uppercase text-slate-500 dark:text-slate-400">Bridge Reconciliation</h3>
              </div>
              <p className="text-2xl font-extrabold text-slate-900 dark:text-white">100%<span className="text-sm font-normal text-slate-500 ml-1">Protected</span></p>
              <div className="w-full bg-slate-200 dark:bg-white/5 rounded-full h-1.5 mt-3">
                <div className="bg-purple-500 dark:bg-purple-400 h-1.5 rounded-full" style={{ width: '100%' }}></div>
              </div>
            </div>
          </div>
        </div>

        {/* Module Traffic Donut */}
        <div className="bg-white dark:bg-[#1A2235]/80 backdrop-blur-xl rounded-2xl border border-slate-200 dark:border-white/10 p-6 shadow-xl flex flex-col">
          <h2 className="text-sm font-extrabold text-slate-700 dark:text-slate-300 mb-4 flex items-center gap-2 uppercase tracking-wider">
            <Package className="w-4 h-4 text-emerald-400" /> 4-Module Traffic Distribution
          </h2>
          <div className="flex-1 flex flex-col items-center justify-center">
            <div className="h-44 w-full mb-3">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={moduleDistribution} innerRadius={55} outerRadius={75} paddingAngle={4} dataKey="value" stroke="none">
                    {moduleDistribution.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '0.5rem', color: '#fff', fontSize: '12px', fontWeight: 'bold' }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="space-y-2.5 w-full px-2">
              {moduleDistribution.map((entry, index) => (
                <div key={index} className="flex items-center justify-between text-xs text-slate-600 dark:text-slate-400 w-full">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: COLORS[index % COLORS.length] }}></span>
                    <span className="font-bold text-slate-700 dark:text-slate-300">{entry.name}</span>
                  </div>
                  <span className="font-extrabold text-slate-900 dark:text-white">{entry.value}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Global Activity Feed */}
      <div className="bg-white dark:bg-[#1A2235]/80 backdrop-blur-xl rounded-2xl border border-slate-200 dark:border-white/10 shadow-xl overflow-hidden flex flex-col">
        <div className="p-6 border-b border-slate-200 dark:border-white/10 flex items-center justify-between">
          <h2 className="text-sm font-extrabold text-slate-700 dark:text-slate-300 flex items-center gap-2 uppercase tracking-wider">
            <Activity className="w-4 h-4 text-indigo-400" /> Global Activity & IDP Reconciliation Log
          </h2>
          <span className="text-xs font-bold text-slate-400">Real-time enterprise audit trail</span>
        </div>
        <div className="p-4 flex-1">
          <div className="space-y-3">
            {activityFeed.map((activity) => (
              <div key={activity.id} className="flex items-center gap-4 p-3.5 rounded-xl hover:bg-slate-50 dark:hover:bg-white/[0.04] transition-colors group cursor-default border border-transparent hover:border-slate-200 dark:hover:border-white/5">
                <div className={`p-2.5 rounded-xl h-fit ${activity.bg}`}>
                  <activity.icon className={`w-4 h-4 ${activity.color}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-bold text-slate-900 dark:text-white truncate">{activity.text}</p>
                  <p className="text-xs text-slate-500 mt-0.5">{activity.time}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
