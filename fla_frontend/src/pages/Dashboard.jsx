import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { FileText, Clock, CheckCircle, AlertCircle, Plus, FileDiff, Zap, Target, Activity, PieChart as PieIcon } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line, PieChart, Pie, Cell } from 'recharts';

export default function Dashboard() {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    fetchTasks();
  }, []);

  const fetchTasks = async () => {
    try {
      const res = await axios.get('http://localhost:8000/api/tasks');
      setTasks(res.data);
    } catch (error) {
      console.error("Error fetching tasks:", error);
    } finally {
      setLoading(false);
    }
  };

  const StatusBadge = ({ status }) => {
    const styles = {
      pending: "bg-slate-100 text-slate-700",
      processing: "bg-blue-100 text-blue-700 animate-pulse",
      review_needed: "bg-amber-100 text-amber-700",
      completed: "bg-green-100 text-green-700",
      error: "bg-red-100 text-red-700"
    };
    
    return (
      <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${styles[status] || styles.pending}`}>
        {status.replace('_', ' ').toUpperCase()}
      </span>
    );
  };

  // Mock Data for Charts
  const extractionData = [
    { name: 'Mon', extractions: 4 },
    { name: 'Tue', extractions: 7 },
    { name: 'Wed', extractions: 5 },
    { name: 'Thu', extractions: 12 },
    { name: 'Fri', extractions: tasks.length > 0 ? tasks.length + 8 : 9 },
    { name: 'Sat', extractions: 2 },
    { name: 'Sun', extractions: 0 },
  ];

  const mismatchData = [
    { name: 'Mon', mismatches: 12 },
    { name: 'Tue', mismatches: 8 },
    { name: 'Wed', mismatches: 15 },
    { name: 'Thu', mismatches: 3 },
    { name: 'Fri', mismatches: 5 },
    { name: 'Sat', mismatches: 1 },
    { name: 'Sun', mismatches: 0 },
  ];

  const moduleUsageData = [
    { name: 'FLA Module', value: 75 },
    { name: 'AOC Module', value: 25 }
  ];
  const COLORS = ['#818cf8', '#34d399'];

  const recentComparisons = [
    { id: 1, module: 'FLA Comparison', date: new Date().toISOString(), matchRate: 98 },
    { id: 2, module: 'AOC Comparison', date: new Date(Date.now() - 86400000).toISOString(), matchRate: 85 },
    { id: 3, module: 'FLA Comparison', date: new Date(Date.now() - 172800000).toISOString(), matchRate: 100 },
  ];

  return (
    <div className="pb-10">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold text-white">Dashboard</h1>
        
        {/* Quick Actions */}
        <div className="flex gap-4">
          <button onClick={() => navigate('/upload')} className="flex items-center gap-2 bg-white/5 hover:bg-white/10 text-white border border-white/10 px-4 py-2 rounded-xl transition-all font-medium text-sm shadow-lg">
            <Plus className="w-4 h-4" /> New Extraction
          </button>
          <button onClick={() => navigate('/compare')} className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-xl transition-all font-medium text-sm shadow-lg shadow-indigo-500/20">
            <FileDiff className="w-4 h-4" /> Run Comparison
          </button>
        </div>
      </div>
      
      {/* Top Stats Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-white/10 p-5 shadow-xl hover:-translate-y-1 transition-transform">
          <div className="flex items-center justify-between mb-4">
            <div className="bg-primary-500/20 p-2.5 rounded-lg"><FileText className="text-primary-400 w-5 h-5" /></div>
            <span className="text-xs font-medium text-emerald-400 bg-emerald-400/10 px-2 py-1 rounded-full">+12%</span>
          </div>
          <p className="text-xs text-slate-400 font-semibold tracking-wide uppercase">Total Extractions</p>
          <p className="text-2xl font-extrabold text-white mt-1">{tasks.length}</p>
        </div>
        
        <div className="bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-white/10 p-5 shadow-xl hover:-translate-y-1 transition-transform">
          <div className="flex items-center justify-between mb-4">
            <div className="bg-indigo-500/20 p-2.5 rounded-lg"><FileDiff className="text-indigo-400 w-5 h-5" /></div>
            <span className="text-xs font-medium text-emerald-400 bg-emerald-400/10 px-2 py-1 rounded-full">+34%</span>
          </div>
          <p className="text-xs text-slate-400 font-semibold tracking-wide uppercase">Total Comparisons</p>
          <p className="text-2xl font-extrabold text-white mt-1">142</p>
        </div>

        <div className="bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-white/10 p-5 shadow-xl hover:-translate-y-1 transition-transform">
          <div className="flex items-center justify-between mb-4">
            <div className="bg-emerald-500/20 p-2.5 rounded-lg"><Target className="text-emerald-400 w-5 h-5" /></div>
            <span className="text-xs font-medium text-slate-400 bg-white/5 px-2 py-1 rounded-full">Avg</span>
          </div>
          <p className="text-xs text-slate-400 font-semibold tracking-wide uppercase">Avg Match Rate</p>
          <p className="text-2xl font-extrabold text-white mt-1">94.2%</p>
        </div>

        <div className="bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-white/10 p-5 shadow-xl hover:-translate-y-1 transition-transform">
          <div className="flex items-center justify-between mb-4">
            <div className="bg-amber-500/20 p-2.5 rounded-lg"><Clock className="text-amber-400 w-5 h-5" /></div>
          </div>
          <p className="text-xs text-slate-400 font-semibold tracking-wide uppercase">Pending Review</p>
          <p className="text-2xl font-extrabold text-white mt-1">{tasks.filter(t => t.status === 'review_needed').length}</p>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        {/* Extraction Volume */}
        <div className="lg:col-span-2 bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-white/10 p-6 shadow-xl">
          <h2 className="text-sm font-semibold text-slate-300 mb-6 flex items-center gap-2 uppercase tracking-wider">
            <Activity className="w-4 h-4 text-indigo-400" /> Extraction Volume
          </h2>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={extractionData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorExtractions" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#818cf8" stopOpacity={0.8}/>
                    <stop offset="95%" stopColor="#818cf8" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                <XAxis dataKey="name" stroke="#64748b" tick={{fill: '#64748b', fontSize: 12}} axisLine={false} tickLine={false} />
                <YAxis stroke="#64748b" tick={{fill: '#64748b', fontSize: 12}} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '0.5rem', color: '#fff' }} />
                <Area type="monotone" dataKey="extractions" stroke="#818cf8" strokeWidth={3} fillOpacity={1} fill="url(#colorExtractions)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Mismatch Trend */}
        <div className="bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-white/10 p-6 shadow-xl flex flex-col">
          <h2 className="text-sm font-semibold text-slate-300 mb-6 flex items-center gap-2 uppercase tracking-wider">
            <AlertCircle className="w-4 h-4 text-rose-400" /> Mismatch Trend (previous year FLA)
          </h2>
          <div className="h-32 w-full mb-6">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={mismatchData}>
                <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: 'none', borderRadius: '0.5rem', color: '#fff' }} />
                <Line type="monotone" dataKey="mismatches" stroke="#fb7185" strokeWidth={3} dot={{ fill: '#fb7185', r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Module Usage Breakdown */}
          <div className="mt-auto border-t border-white/10 pt-4">
             <h2 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2 uppercase tracking-wider">
              <PieIcon className="w-4 h-4 text-emerald-400" /> Module Usage
            </h2>
            <div className="flex items-center justify-between">
              <div className="w-24 h-24">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={moduleUsageData} innerRadius={25} outerRadius={40} paddingAngle={5} dataKey="value" stroke="none">
                      {moduleUsageData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="space-y-2">
                {moduleUsageData.map((entry, index) => (
                  <div key={index} className="flex items-center gap-2 text-xs text-slate-400">
                    <span className="w-2 h-2 rounded-full" style={{ backgroundColor: COLORS[index % COLORS.length] }}></span>
                    {entry.name} ({entry.value}%)
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Tables Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Recent Extractions Table */}
        <div className="bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-white/10 shadow-xl overflow-hidden flex flex-col h-full">
          <div className="px-6 py-4 border-b border-white/10 bg-white/[0.02]">
            <h2 className="text-sm font-semibold text-white uppercase tracking-wider">Recent Extractions</h2>
          </div>
          <div className="overflow-x-auto flex-1">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-black/20 text-slate-400 text-xs uppercase tracking-wider border-b border-white/5">
                  <th className="px-6 py-3 font-medium">Company Name</th>
                  <th className="px-6 py-3 font-medium">Date</th>
                  <th className="px-6 py-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {loading ? (
                  <tr><td colSpan="3" className="px-6 py-8 text-center text-slate-400 text-sm">Loading tasks...</td></tr>
                ) : tasks.length === 0 ? (
                  <tr><td colSpan="3" className="px-6 py-8 text-center text-slate-400 text-sm">No extractions yet.</td></tr>
                ) : tasks.slice(0, 5).map((task) => (
                  <tr key={task.id} className="hover:bg-white/[0.02] transition-colors">
                    <td className="px-6 py-4 font-medium text-slate-200 text-sm">{task.company_name}</td>
                    <td className="px-6 py-4 text-slate-400 text-xs">{new Date(task.created_at).toLocaleDateString()}</td>
                    <td className="px-6 py-4"><StatusBadge status={task.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="p-4 border-t border-white/10 bg-white/[0.01]">
            <button className="text-indigo-400 text-xs font-semibold w-full text-center hover:text-indigo-300">View All Extractions &rarr;</button>
          </div>
        </div>

        {/* Recent Comparisons Table */}
        <div className="bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-white/10 shadow-xl overflow-hidden flex flex-col h-full">
          <div className="px-6 py-4 border-b border-white/10 bg-white/[0.02]">
            <h2 className="text-sm font-semibold text-white uppercase tracking-wider">Recent Comparisons</h2>
          </div>
          <div className="overflow-x-auto flex-1">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-black/20 text-slate-400 text-xs uppercase tracking-wider border-b border-white/5">
                  <th className="px-6 py-3 font-medium">Module Used</th>
                  <th className="px-6 py-3 font-medium">Date</th>
                  <th className="px-6 py-3 font-medium">Match Rate</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {recentComparisons.map((comp) => (
                  <tr key={comp.id} className="hover:bg-white/[0.02] transition-colors">
                    <td className="px-6 py-4 font-medium text-slate-200 text-sm flex items-center gap-2">
                      <FileDiff className="w-4 h-4 text-indigo-400" />
                      {comp.module}
                    </td>
                    <td className="px-6 py-4 text-slate-400 text-xs">{new Date(comp.date).toLocaleDateString()}</td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <div className="w-full bg-white/10 rounded-full h-1.5 max-w-[60px]">
                          <div className={`h-1.5 rounded-full ${comp.matchRate > 90 ? 'bg-emerald-400' : 'bg-amber-400'}`} style={{ width: `${comp.matchRate}%` }}></div>
                        </div>
                        <span className="text-xs font-medium text-slate-300">{comp.matchRate}%</span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="p-4 border-t border-white/10 bg-white/[0.01]">
            <button className="text-indigo-400 text-xs font-semibold w-full text-center hover:text-indigo-300" onClick={() => navigate('/compare')}>Go to Platform &rarr;</button>
          </div>
        </div>

      </div>
    </div>
  );
}
