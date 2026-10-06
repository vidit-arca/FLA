import { useState, useEffect, useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import axios from 'axios';
import { FileText, Clock, AlertCircle, Plus, FileDiff, Activity, CheckCircle, Loader2 } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line, PieChart, Pie, Cell, BarChart, Bar, Legend } from 'recharts';
import { MODULES_SCHEMA } from '../config/modulesSchema';
import AOC4HubExtensions from '../components/AOC4HubExtensions';

export default function GenericHub() {
  const { moduleId } = useParams();
  const navigate = useNavigate();
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);

  const moduleConfig = MODULES_SCHEMA[moduleId];

  useEffect(() => {
    if (moduleConfig) {
      fetchTasks();
    }
  }, [moduleId, moduleConfig]);

  if (!moduleConfig) {
    return (
      <div className="flex flex-col items-center justify-center h-[calc(100vh-140px)]">
        <AlertCircle className="w-16 h-16 text-rose-500 mb-4" />
        <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">Module Not Found</h2>
        <p className="text-slate-600 dark:text-slate-400">The module "{moduleId}" does not exist in the schema.</p>
        <button onClick={() => navigate('/')} className="mt-6 px-6 py-2 bg-indigo-600 hover:bg-indigo-500 text-slate-900 dark:text-white rounded-xl transition-colors font-semibold">
          Go Home
        </button>
      </div>
    );
  }

  const fetchTasks = async () => {
    try {
      setLoading(true);
      const res = await axios.get('http://localhost:8000/api/tasks');
      setTasks(res.data.filter(t => t.module_type === moduleConfig.apiType || (!t.module_type && moduleConfig.apiType === 'fla')));
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

  const activeTasks = tasks.filter(t => ['uploaded', 'processing', 'exporting'].includes(t.status)).length;
  const completedTasks = tasks.filter(t => t.status === 'completed').length;
  const successRate = tasks.length > 0 ? Math.round((completedTasks / tasks.length) * 100) : 0;
  
  const statusData = [
    { name: 'Completed', value: completedTasks, color: '#34d399' },
    { name: 'Pending Review', value: tasks.filter(t => t.status === 'review_needed').length, color: '#fbbf24' },
    { name: 'Processing', value: activeTasks, color: '#60a5fa' },
    { name: 'Failed', value: tasks.filter(t => t.status === 'error').length, color: '#f87171' }
  ].filter(d => d.value > 0);
  
  if (statusData.length === 0) statusData.push({ name: 'No Data', value: 1, color: '#334155' });

  return (
    <div className="pb-10">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white flex items-center gap-3">
            {moduleConfig.name} Hub
            <span className={`text-xs font-semibold bg-${moduleConfig.themeColor}-500/20 text-${moduleConfig.themeColor}-400 px-3 py-1 rounded-full border border-${moduleConfig.themeColor}-500/30`}>Active</span>
          </h1>
          <p className="text-slate-600 dark:text-slate-400 text-sm mt-1">{moduleConfig.description}</p>
        </div>
        
        {/* Quick Actions */}
        <div className="flex gap-4">
          <button onClick={() => navigate(`/m/${moduleId}/upload`)} className="flex items-center gap-2 bg-slate-900/5 dark:bg-white/5 hover:bg-slate-900/10 dark:bg-white/10 text-slate-900 dark:text-white border border-slate-200 dark:border-white/10 px-4 py-2 rounded-xl transition-all font-medium text-sm shadow-lg">
            <Plus className="w-4 h-4" /> New Extraction
          </button>

        {moduleConfig.features.hasPreviousYearComparison && (
            <button onClick={() => navigate('/compare')} className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-slate-900 dark:text-white px-4 py-2 rounded-xl transition-all font-medium text-sm shadow-lg shadow-indigo-500/20">
              <FileDiff className="w-4 h-4" /> Run Comparison
            </button>
          )}
        </div>
      </div>
      
      

      {/* Top Stats Row */}
      <div className={`grid grid-cols-1 md:grid-cols-2 ${moduleConfig.features.hasPreviousYearComparison ? 'lg:grid-cols-5' : 'lg:grid-cols-4'} gap-6 mb-8`}>
        <div className="bg-white dark:bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-slate-200 dark:border-white/10 p-5 shadow-xl hover:-translate-y-1 transition-transform">
          <div className="flex items-center justify-between mb-4">
            <div className={`bg-${moduleConfig.themeColor}-500/20 p-2.5 rounded-lg`}><FileText className={`text-${moduleConfig.themeColor}-400 w-5 h-5`} /></div>
          </div>
          <p className="text-xs text-slate-600 dark:text-slate-400 font-semibold tracking-wide uppercase">Total Documents</p>
          <p className="text-2xl font-extrabold text-slate-900 dark:text-white mt-1">{tasks.length}</p>
        </div>
        
        <div className="bg-white dark:bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-slate-200 dark:border-white/10 p-5 shadow-xl hover:-translate-y-1 transition-transform">
          <div className="flex items-center justify-between mb-4">
            <div className="bg-amber-500/20 p-2.5 rounded-lg"><Clock className="text-amber-400 w-5 h-5" /></div>
          </div>
          <p className="text-xs text-slate-600 dark:text-slate-400 font-semibold tracking-wide uppercase">Pending Review</p>
          <p className="text-2xl font-extrabold text-slate-900 dark:text-white mt-1">{tasks.filter(t => t.status === 'review_needed').length}</p>
        </div>

        
        <div className="bg-white dark:bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-slate-200 dark:border-white/10 p-5 shadow-xl hover:-translate-y-1 transition-transform">
          <div className="flex items-center justify-between mb-4">
            <div className="bg-blue-500/20 p-2.5 rounded-lg"><Loader2 className="text-blue-400 w-5 h-5 animate-spin-slow" /></div>
          </div>
          <p className="text-xs text-slate-600 dark:text-slate-400 font-semibold tracking-wide uppercase">Active Processing</p>
          <p className="text-2xl font-extrabold text-slate-900 dark:text-white mt-1">{activeTasks}</p>
        </div>
        
        <div className="bg-white dark:bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-slate-200 dark:border-white/10 p-5 shadow-xl hover:-translate-y-1 transition-transform">
          <div className="flex items-center justify-between mb-4">
            <div className="bg-emerald-500/20 p-2.5 rounded-lg"><CheckCircle className="text-emerald-400 w-5 h-5" /></div>
          </div>
          <p className="text-xs text-slate-600 dark:text-slate-400 font-semibold tracking-wide uppercase">Success Rate</p>
          <p className="text-2xl font-extrabold text-slate-900 dark:text-white mt-1">{successRate}%</p>
        </div>

        {moduleConfig.features.hasPreviousYearComparison && (
          <div className="bg-white dark:bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-slate-200 dark:border-white/10 p-5 shadow-xl hover:-translate-y-1 transition-transform">
             <div className="flex items-center justify-between mb-4">
              <div className="bg-emerald-500/20 p-2.5 rounded-lg"><FileDiff className="text-emerald-400 w-5 h-5" /></div>
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-400 font-semibold tracking-wide uppercase">Completed Comparisons</p>
            <p className="text-2xl font-extrabold text-slate-900 dark:text-white mt-1">142</p>
          </div>
        )}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <div className="lg:col-span-2 bg-white dark:bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-slate-200 dark:border-white/10 p-6 shadow-xl flex flex-col h-[350px]">
          <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-6 flex items-center gap-2 uppercase tracking-wider">
            <Activity className={`w-4 h-4 text-${moduleConfig.themeColor}-400`} /> Processing Volume
          </h2>
          <div className="flex-1 w-full min-h-0">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={extractionData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
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
                  contentStyle={{ backgroundColor: 'rgba(15, 23, 42, 0.9)', backdropFilter: 'blur(12px)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '12px', color: '#fff' }} 
                  itemStyle={{ color: '#e0e7ff', fontWeight: 'bold' }}
                />
                <Area type="monotone" dataKey="extractions" stroke="url(#lineGradient)" strokeWidth={4} fillOpacity={1} fill="url(#colorExtractions)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-white dark:bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-slate-200 dark:border-white/10 p-6 shadow-xl flex flex-col h-[350px]">
          <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2 flex items-center gap-2 uppercase tracking-wider">
            <CheckCircle className="w-4 h-4 text-emerald-400" /> Task Status Distribution
          </h2>
          <div className="flex-1 w-full min-h-0 relative">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={statusData} cx="50%" cy="50%" innerRadius={60} outerRadius={90} paddingAngle={5} dataKey="value" stroke="none">
                  {statusData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ backgroundColor: 'rgba(15, 23, 42, 0.9)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', color: '#fff' }} />
                <Legend verticalAlign="bottom" height={36} iconType="circle" wrapperStyle={{ fontSize: '12px', color: '#94a3b8' }}/>
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
      
      {moduleConfig.features.hasPreviousYearComparison && (
        <div className="grid grid-cols-1 mb-8">
           <div className="bg-white dark:bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-slate-200 dark:border-white/10 p-6 shadow-xl flex flex-col h-[300px]">
             <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-6 flex items-center gap-2 uppercase tracking-wider">
               <AlertCircle className="w-4 h-4 text-rose-400" /> Mismatch Trend Analysis
             </h2>
             <div className="flex-1 w-full min-h-0">
               <ResponsiveContainer width="100%" height="100%">
                 <AreaChart data={mismatchData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                   <defs>
                     <linearGradient id="colorMismatches" x1="0" y1="0" x2="0" y2="1">
                       <stop offset="0%" stopColor="#fb7185" stopOpacity={0.4}/>
                       <stop offset="50%" stopColor="#fb7185" stopOpacity={0.1}/>
                       <stop offset="100%" stopColor="#fb7185" stopOpacity={0}/>
                     </linearGradient>
                   </defs>
                   <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                   <XAxis dataKey="name" stroke="#64748b" tick={{fill: '#94a3b8', fontSize: 12}} axisLine={false} tickLine={false} />
                   <YAxis stroke="#64748b" tick={{fill: '#94a3b8', fontSize: 12}} axisLine={false} tickLine={false} />
                   <Tooltip cursor={{fill: 'rgba(255,255,255,0.05)'}} contentStyle={{ backgroundColor: 'rgba(15, 23, 42, 0.9)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', color: '#fff' }} />
                   <Area type="monotone" dataKey="mismatches" stroke="#fb7185" strokeWidth={3} fillOpacity={1} fill="url(#colorMismatches)" dot={{ fill: '#fb7185', r: 4, strokeWidth: 2, stroke: '#1e293b' }} activeDot={{ r: 6, strokeWidth: 0 }} />
                 </AreaChart>
               </ResponsiveContainer>
             </div>
           </div>
        </div>
      )}

      {moduleId === 'aoc4' && <AOC4HubExtensions />}

      {/* Tables Row */}
      <div className="bg-white dark:bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-slate-200 dark:border-white/10 shadow-xl overflow-hidden flex flex-col h-full">
        <div className="px-6 py-4 border-b border-slate-200 dark:border-white/10 bg-slate-900/[0.02] dark:bg-white/[0.02]">
          <h2 className="text-sm font-semibold text-slate-900 dark:text-white uppercase tracking-wider">Recent Tasks</h2>
        </div>
        <div className="overflow-x-auto flex-1">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-black/20 text-slate-600 dark:text-slate-400 text-xs uppercase tracking-wider border-b border-slate-200 dark:border-white/5">
                <th className="px-6 py-3 font-medium">Company Name</th>
                <th className="px-6 py-3 font-medium">Date</th>
                <th className="px-6 py-3 font-medium">Status</th>
                <th className="px-6 py-3 font-medium text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {loading ? (
                <tr><td colSpan="4" className="px-6 py-8 text-center text-slate-600 dark:text-slate-400 text-sm">Loading tasks...</td></tr>
              ) : tasks.length === 0 ? (
                <tr><td colSpan="4" className="px-6 py-8 text-center text-slate-600 dark:text-slate-400 text-sm">No extractions yet.</td></tr>
              ) : tasks.slice(0, 10).map((task) => (
                <tr key={task.id} className="hover:bg-slate-900/[0.02] dark:bg-white/[0.02] transition-colors cursor-pointer" onClick={() => navigate(`/m/${moduleId}/task/${task.id}`)}>
                  <td className="px-6 py-4 font-medium text-slate-800 dark:text-slate-200 text-sm">{task.company_name}</td>
                  <td className="px-6 py-4 text-slate-600 dark:text-slate-400 text-xs">{new Date(task.created_at).toLocaleDateString()}</td>
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
