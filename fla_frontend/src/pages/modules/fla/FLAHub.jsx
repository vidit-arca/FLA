import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { FileText, Clock, AlertCircle, Plus, FileDiff, Activity } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts';

export default function FLAHub() {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    fetchTasks();
  }, []);

  const fetchTasks = async () => {
    try {
      const res = await axios.get('http://localhost:8000/api/tasks');
      setTasks(res.data.filter(t => t.module_type === 'fla' || !t.module_type));
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

  const extractionData = useMemo(() => {
    const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    const data = [
      { name: 'Mon', extractions: 0 },
      { name: 'Tue', extractions: 0 },
      { name: 'Wed', extractions: 0 },
      { name: 'Thu', extractions: 0 },
      { name: 'Fri', extractions: 0 },
      { name: 'Sat', extractions: 0 },
      { name: 'Sun', extractions: 0 },
    ];
    
    tasks.forEach(task => {
      if (task.created_at) {
        const date = new Date(task.created_at);
        const dayName = days[date.getDay()];
        const targetDay = data.find(d => d.name === dayName);
        if (targetDay) {
          targetDay.extractions += 1;
        }
      }
    });
    
    return data;
  }, [tasks]);

  const mismatchData = [
    { name: 'Mon', mismatches: 12 },
    { name: 'Tue', mismatches: 8 },
    { name: 'Wed', mismatches: 15 },
    { name: 'Thu', mismatches: 3 },
    { name: 'Fri', mismatches: 5 },
    { name: 'Sat', mismatches: 1 },
    { name: 'Sun', mismatches: 0 },
  ];

  return (
    <div className="pb-10">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            FLA Extraction Hub
            <span className="text-xs font-semibold bg-indigo-500/20 text-indigo-400 px-3 py-1 rounded-full border border-indigo-500/30">Active</span>
          </h1>
          <p className="text-slate-400 text-sm mt-1">Manage, extract, and compare Foreign Liabilities and Assets reports.</p>
        </div>
        
        {/* Quick Actions */}
        <div className="flex gap-4">
          <button onClick={() => navigate('/fla/upload')} className="flex items-center gap-2 bg-white/5 hover:bg-white/10 text-white border border-white/10 px-4 py-2 rounded-xl transition-all font-medium text-sm shadow-lg">
            <Plus className="w-4 h-4" /> New Extraction
          </button>
          <button onClick={() => navigate('/compare')} className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-xl transition-all font-medium text-sm shadow-lg shadow-indigo-500/20">
            <FileDiff className="w-4 h-4" /> Run Comparison
          </button>
        </div>
      </div>
      
      {/* Top Stats Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
        <div className="bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-white/10 p-5 shadow-xl hover:-translate-y-1 transition-transform">
          <div className="flex items-center justify-between mb-4">
            <div className="bg-primary-500/20 p-2.5 rounded-lg"><FileText className="text-primary-400 w-5 h-5" /></div>
          </div>
          <p className="text-xs text-slate-400 font-semibold tracking-wide uppercase">Total FLA Documents</p>
          <p className="text-2xl font-extrabold text-white mt-1">{tasks.length}</p>
        </div>
        
        <div className="bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-white/10 p-5 shadow-xl hover:-translate-y-1 transition-transform">
          <div className="flex items-center justify-between mb-4">
            <div className="bg-amber-500/20 p-2.5 rounded-lg"><Clock className="text-amber-400 w-5 h-5" /></div>
          </div>
          <p className="text-xs text-slate-400 font-semibold tracking-wide uppercase">Pending Review</p>
          <p className="text-2xl font-extrabold text-white mt-1">{tasks.filter(t => t.status === 'review_needed').length}</p>
        </div>

        <div className="bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-white/10 p-5 shadow-xl hover:-translate-y-1 transition-transform">
           <div className="flex items-center justify-between mb-4">
            <div className="bg-emerald-500/20 p-2.5 rounded-lg"><FileDiff className="text-emerald-400 w-5 h-5" /></div>
          </div>
          <p className="text-xs text-slate-400 font-semibold tracking-wide uppercase">Completed Comparisons</p>
          <p className="text-2xl font-extrabold text-white mt-1">142</p>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <div className="lg:col-span-2 bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-white/10 p-6 shadow-xl">
          <h2 className="text-sm font-semibold text-slate-300 mb-6 flex items-center gap-2 uppercase tracking-wider">
            <Activity className="w-4 h-4 text-indigo-400" /> FLA Processing Volume
          </h2>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={extractionData} margin={{ top: 20, right: 20, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorExtractions" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#818cf8" stopOpacity={0.5}/>
                    <stop offset="50%" stopColor="#c084fc" stopOpacity={0.2}/>
                    <stop offset="100%" stopColor="#1e1b4b" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="lineGradient" x1="0" y1="0" x2="1" y2="0">
                     <stop offset="0%" stopColor="#818cf8" />
                     <stop offset="100%" stopColor="#c084fc" />
                   </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="4 4" stroke="rgba(255,255,255,0.06)" vertical={false} />
                <XAxis dataKey="name" stroke="#64748b" tick={{fill: '#94a3b8', fontSize: 12, fontWeight: 500}} axisLine={false} tickLine={false} tickMargin={10} />
                <YAxis stroke="#64748b" tick={{fill: '#94a3b8', fontSize: 12, fontWeight: 500}} axisLine={false} tickLine={false} tickMargin={10} allowDecimals={false} />
                <Tooltip 
                  contentStyle={{ backgroundColor: 'rgba(15, 23, 42, 0.8)', backdropFilter: 'blur(12px)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '12px', color: '#fff' }} 
                  itemStyle={{ color: '#e0e7ff', fontWeight: 'bold' }}
                />
                <Area 
                  type="monotone" 
                  dataKey="extractions" 
                  stroke="url(#lineGradient)" 
                  strokeWidth={4} 
                  fillOpacity={1} 
                  fill="url(#colorExtractions)" 
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-white/10 p-6 shadow-xl flex flex-col">
          <h2 className="text-sm font-semibold text-slate-300 mb-6 flex items-center gap-2 uppercase tracking-wider">
            <AlertCircle className="w-4 h-4 text-rose-400" /> FLA Mismatch Trend
          </h2>
          <div className="h-48 w-full mb-6">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={mismatchData}>
                <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: 'none', borderRadius: '0.5rem', color: '#fff' }} />
                <Line type="monotone" dataKey="mismatches" stroke="#fb7185" strokeWidth={3} dot={{ fill: '#fb7185', r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Tables Row */}
      <div className="bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-white/10 shadow-xl overflow-hidden flex flex-col h-full">
        <div className="px-6 py-4 border-b border-white/10 bg-white/[0.02]">
          <h2 className="text-sm font-semibold text-white uppercase tracking-wider">Recent FLA Tasks</h2>
        </div>
        <div className="overflow-x-auto flex-1">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-black/20 text-slate-400 text-xs uppercase tracking-wider border-b border-white/5">
                <th className="px-6 py-3 font-medium">Company Name</th>
                <th className="px-6 py-3 font-medium">Date</th>
                <th className="px-6 py-3 font-medium">Status</th>
                <th className="px-6 py-3 font-medium text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {loading ? (
                <tr><td colSpan="4" className="px-6 py-8 text-center text-slate-400 text-sm">Loading tasks...</td></tr>
              ) : tasks.length === 0 ? (
                <tr><td colSpan="4" className="px-6 py-8 text-center text-slate-400 text-sm">No extractions yet.</td></tr>
              ) : tasks.slice(0, 10).map((task) => (
                <tr key={task.id} className="hover:bg-white/[0.02] transition-colors cursor-pointer" onClick={() => navigate(`/fla/task/${task.id}`)}>
                  <td className="px-6 py-4 font-medium text-slate-200 text-sm">{task.company_name}</td>
                  <td className="px-6 py-4 text-slate-400 text-xs">{new Date(task.created_at).toLocaleDateString()}</td>
                  <td className="px-6 py-4"><StatusBadge status={task.status} /></td>
                  <td className="px-6 py-4 text-right">
                    <button className="text-indigo-400 text-xs font-semibold hover:text-indigo-300 transition-colors">Review</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
