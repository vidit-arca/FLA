import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { LayoutDashboard, Package, Zap, Users, Settings, Activity, ArrowRight, ShieldCheck, FileText, Cpu, Database, Clock, Server, CheckCircle, AlertCircle, ClipboardCheck } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

export default function Dashboard() {
  const navigate = useNavigate();
  const [totalDocs, setTotalDocs] = useState(0);

  useEffect(() => {
    // Fetch actual total documents processed from the backend
    axios.get('http://localhost:8000/api/tasks')
      .then(res => setTotalDocs(res.data.length))
      .catch(err => console.error("Failed to fetch task count:", err));
  }, []);

  const moduleDistribution = [
    { name: 'FLA Module', value: 80 },
    { name: 'AOC Module', value: 20 }
  ];
  const COLORS = ['#818cf8', '#34d399'];

  const activityFeed = [
    { id: 1, text: "Admin uploaded 5 files to FLA Module", time: "2 mins ago", icon: FileText, color: "text-indigo-400", bg: "bg-indigo-400/20" },
    { id: 2, text: "Admin ran Comparison Manager on 'Reliance_FY23'", time: "15 mins ago", icon: Activity, color: "text-emerald-400", bg: "bg-emerald-400/20" },
    { id: 3, text: "System completed processing 'Tata_AOC'", time: "1 hour ago", icon: CheckCircle, color: "text-emerald-400", bg: "bg-emerald-400/20" },
    { id: 4, text: "Admin exported data from FLA Module", time: "3 hours ago", icon: Package, color: "text-indigo-400", bg: "bg-indigo-400/20" },
    { id: 5, text: "System flagged 'Wipro_FLA' for manual review", time: "5 hours ago", icon: AlertCircle, color: "text-rose-400", bg: "bg-rose-400/20" },
  ];

  return (
    <div className="pb-10">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Platform Overview</h1>
          <p className="text-slate-400 text-sm mt-1">Global statistics across all AI extraction modules.</p>
        </div>
      </div>
      
      {/* Top Stats Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-white/10 p-5 shadow-xl hover:-translate-y-1 transition-transform">
          <div className="flex items-center justify-between mb-4">
            <div className="bg-indigo-500/20 p-2.5 rounded-lg"><Package className="text-indigo-400 w-5 h-5" /></div>
            <span className="text-xs font-medium text-emerald-400 bg-emerald-400/10 px-2 py-1 rounded-full">Live</span>
          </div>
          <p className="text-xs text-slate-400 font-semibold tracking-wide uppercase">Active Modules</p>
          <p className="text-2xl font-extrabold text-white mt-1">1</p>
        </div>
        
        <div className="bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-white/10 p-5 shadow-xl hover:-translate-y-1 transition-transform">
          <div className="flex items-center justify-between mb-4">
            <div className="bg-primary-500/20 p-2.5 rounded-lg"><Zap className="text-primary-400 w-5 h-5" /></div>
          </div>
          <p className="text-xs text-slate-400 font-semibold tracking-wide uppercase">Documents Processed (30d)</p>
          <p className="text-2xl font-extrabold text-white mt-1">{totalDocs}</p>
        </div>

        <div 
          onClick={() => navigate('/review')}
          className="bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-amber-500/30 p-5 shadow-[0_0_20px_rgba(245,158,11,0.05)] hover:border-amber-500/50 hover:-translate-y-1 transition-all cursor-pointer group"
        >
           <div className="flex items-center justify-between mb-4">
            <div className="bg-amber-500/20 p-2.5 rounded-lg group-hover:bg-amber-500/30 transition-colors"><ClipboardCheck className="text-amber-400 w-5 h-5" /></div>
            <span className="text-[10px] font-bold text-amber-400 bg-amber-400/10 border border-amber-400/20 px-2 py-1 rounded-full uppercase tracking-wider animate-pulse">Action Required</span>
          </div>
          <p className="text-xs text-slate-400 font-semibold tracking-wide uppercase group-hover:text-amber-200/70 transition-colors">Tasks Awaiting Review</p>
          <p className="text-2xl font-extrabold text-amber-400 mt-1">5</p>
        </div>

        <div className="bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-white/10 p-5 shadow-xl hover:-translate-y-1 transition-transform">
           <div className="flex items-center justify-between mb-4">
            <div className="bg-emerald-500/20 p-2.5 rounded-lg"><Users className="text-emerald-400 w-5 h-5" /></div>
          </div>
          <p className="text-xs text-slate-400 font-semibold tracking-wide uppercase">Active Users</p>
          <p className="text-2xl font-extrabold text-white mt-1">12</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        
        {/* System & Hardware Metrics */}
        <div className="lg:col-span-2 bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-white/10 p-6 shadow-xl">
          <h2 className="text-sm font-semibold text-slate-300 mb-6 flex items-center gap-2 uppercase tracking-wider">
            <Server className="w-4 h-4 text-indigo-400" /> System & Hardware Metrics
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-black/20 rounded-xl p-5 border border-white/5">
              <div className="flex items-center gap-3 mb-2">
                <Clock className="w-5 h-5 text-amber-400" />
                <h3 className="text-sm font-medium text-slate-300">Avg Extraction Time</h3>
              </div>
              <p className="text-2xl font-bold text-white">45<span className="text-sm font-normal text-slate-500 ml-1">sec / doc</span></p>
              <div className="w-full bg-white/5 rounded-full h-1.5 mt-3">
                <div className="bg-amber-400 h-1.5 rounded-full" style={{ width: '45%' }}></div>
              </div>
            </div>

            <div className="bg-black/20 rounded-xl p-5 border border-white/5">
              <div className="flex items-center gap-3 mb-2">
                <Cpu className="w-5 h-5 text-emerald-400" />
                <h3 className="text-sm font-medium text-slate-300">Global Confidence Score</h3>
              </div>
              <p className="text-2xl font-bold text-emerald-400">94.2%</p>
              <div className="w-full bg-white/5 rounded-full h-1.5 mt-3">
                <div className="bg-emerald-400 h-1.5 rounded-full shadow-[0_0_10px_rgba(52,211,153,0.5)]" style={{ width: '94.2%' }}></div>
              </div>
            </div>

            <div className="bg-black/20 rounded-xl p-5 border border-white/5">
              <div className="flex items-center gap-3 mb-2">
                <Database className="w-5 h-5 text-primary-400" />
                <h3 className="text-sm font-medium text-slate-300">GPU Storage Used</h3>
              </div>
              <p className="text-2xl font-bold text-white">12<span className="text-sm font-normal text-slate-500 ml-1">GB / 100GB</span></p>
              <div className="w-full bg-white/5 rounded-full h-1.5 mt-3">
                <div className="bg-primary-400 h-1.5 rounded-full" style={{ width: '12%' }}></div>
              </div>
            </div>
          </div>
        </div>

        {/* Module Distribution Donut */}
        <div className="bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-white/10 p-6 shadow-xl flex flex-col">
          <h2 className="text-sm font-semibold text-slate-300 mb-6 flex items-center gap-2 uppercase tracking-wider">
             <Package className="w-4 h-4 text-emerald-400" /> Module Traffic
          </h2>
          <div className="flex-1 flex flex-col items-center justify-center">
            <div className="h-40 w-full mb-4">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={moduleDistribution} innerRadius={50} outerRadius={70} paddingAngle={5} dataKey="value" stroke="none">
                    {moduleDistribution.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '0.5rem', color: '#fff' }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="space-y-2 w-full px-4">
              {moduleDistribution.map((entry, index) => (
                <div key={index} className="flex items-center justify-between text-xs text-slate-400 w-full">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: COLORS[index % COLORS.length] }}></span>
                    <span className="font-medium text-slate-300">{entry.name}</span>
                  </div>
                  <span className="font-bold text-white">{entry.value}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Global Activity Feed (Audit Log) */}
        <div className="lg:col-span-2 bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-white/10 shadow-xl overflow-hidden flex flex-col">
          <div className="p-6 border-b border-white/10">
            <h2 className="text-sm font-semibold text-slate-300 flex items-center gap-2 uppercase tracking-wider">
              <Activity className="w-4 h-4 text-indigo-400" /> Global Activity Feed
            </h2>
          </div>
          <div className="p-4 flex-1">
            <div className="space-y-4">
              {activityFeed.map((activity) => (
                <div key={activity.id} className="flex gap-4 p-3 rounded-xl hover:bg-white/[0.02] transition-colors group cursor-default">
                  <div className={`p-2.5 rounded-lg h-fit ${activity.bg}`}>
                    <activity.icon className={`w-4 h-4 ${activity.color}`} />
                  </div>
                  <div className="flex-1 flex flex-col justify-center">
                    <p className="text-sm font-medium text-slate-200">{activity.text}</p>
                    <p className="text-xs text-slate-500 mt-0.5">{activity.time}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Available Modules List */}
        <div className="bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-white/10 shadow-xl flex flex-col overflow-hidden">
          <div className="p-6 border-b border-white/10">
            <h2 className="text-sm font-semibold text-slate-300 flex items-center gap-2 uppercase tracking-wider">
              <Package className="w-4 h-4 text-emerald-400" /> Installed Modules
            </h2>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {/* FLA Module Card */}
            <div 
              onClick={() => navigate('/fla')}
              className="bg-black/20 border border-indigo-500/30 hover:border-indigo-400/60 p-4 rounded-xl cursor-pointer transition-all hover:bg-indigo-500/10 group"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-indigo-500/20 rounded-lg group-hover:bg-indigo-500/30 transition-colors">
                    <FileText className="w-5 h-5 text-indigo-400" />
                  </div>
                  <h3 className="font-bold text-white">FLA Module</h3>
                </div>
                <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-white transition-colors" />
              </div>
              <p className="text-xs text-slate-400">Foreign Liabilities and Assets OCR & Comparison Platform.</p>
            </div>

            {/* Upcoming Module Placeholder */}
            <div className="bg-white/5 border border-white/5 p-4 rounded-xl opacity-60 cursor-not-allowed">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-white/5 rounded-lg">
                    <Package className="w-5 h-5 text-slate-400" />
                  </div>
                  <h3 className="font-bold text-white">AOC Module <span className="text-[10px] bg-slate-700 px-2 py-0.5 rounded-full ml-2">Coming Soon</span></h3>
                </div>
              </div>
              <p className="text-xs text-slate-500">Automated extraction for Annual Return files.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
