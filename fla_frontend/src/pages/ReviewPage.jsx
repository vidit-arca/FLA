import React, { useState } from 'react';
import { 
  CheckCircle2, 
  Clock, 
  AlertCircle, 
  Search, 
  Filter, 
  MoreVertical, 
  Eye, 
  ShieldAlert, 
  FileText,
  ClipboardCheck,
  ChevronRight,
  LayoutGrid
} from 'lucide-react';

// --- Dummy Data ---
const dummyTasks = [
  {
    id: 'TSK-9901',
    company: 'Reliance Industries Ltd.',
    module: 'FLA',
    confidence: 82,
    status: 'urgent',
    date: '2026-06-22',
    flaggedFields: 3
  },
  {
    id: 'TSK-9902',
    company: 'Tata Consultancy Services',
    module: 'FLA',
    confidence: 94,
    status: 'pending',
    date: '2026-06-22',
    flaggedFields: 1
  },
  {
    id: 'TSK-9884',
    company: 'HDFC Bank',
    module: 'AOC',
    confidence: 76,
    status: 'urgent',
    date: '2026-06-21',
    flaggedFields: 5
  },
  {
    id: 'TSK-9880',
    company: 'Infosys Limited',
    module: 'FLA',
    confidence: 89,
    status: 'pending',
    date: '2026-06-21',
    flaggedFields: 2
  },
  {
    id: 'TSK-9875',
    company: 'Wipro Enterprises',
    module: 'AOC',
    confidence: 98,
    status: 'completed',
    date: '2026-06-20',
    flaggedFields: 0
  }
];

const StatCard = ({ title, value, icon: Icon, iconColor, iconBg }) => (
  <div className="bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-white/10 p-5 shadow-xl hover:-translate-y-1 transition-transform">
    <div className="flex items-center justify-between mb-4">
      <div className={`${iconBg} p-2.5 rounded-lg`}>
        <Icon className={`${iconColor} w-5 h-5`} />
      </div>
    </div>
    <p className="text-xs text-slate-400 font-semibold tracking-wide uppercase">{title}</p>
    <p className="text-2xl font-extrabold text-white mt-1">{value}</p>
  </div>
);

const ReviewPage = () => {
  const [searchTerm, setSearchTerm] = useState('');
  const [activeTab, setActiveTab] = useState('All');

  const tabs = ['All', 'FLA Module', 'AOC Module'];

  const filteredTasks = dummyTasks.filter(task => {
    const matchesSearch = task.company.toLowerCase().includes(searchTerm.toLowerCase()) || task.id.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesTab = activeTab === 'All' || task.module.toLowerCase() === activeTab.replace(' Module', '').toLowerCase();
    return matchesSearch && matchesTab;
  });

  return (
    <div className="pb-10 animate-fade-in">
      
      {/* Header Area */}
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Human Review Console</h1>
          <p className="text-slate-400 text-sm mt-1">Review and validate data extracted by the AI engine.</p>
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <StatCard 
          title="Pending Reviews" 
          value={filteredTasks.filter(t => t.status === 'pending' || t.status === 'urgent').length} 
          icon={Clock} 
          iconColor="text-amber-400"
          iconBg="bg-amber-500/20"
        />
        <StatCard 
          title="Urgent / Flagged" 
          value={filteredTasks.filter(t => t.status === 'urgent').length} 
          icon={ShieldAlert} 
          iconColor="text-rose-400"
          iconBg="bg-rose-500/20"
        />
        <StatCard 
          title="Completed Today" 
          value={filteredTasks.filter(t => t.status === 'completed').length} 
          icon={CheckCircle2} 
          iconColor="text-emerald-400"
          iconBg="bg-emerald-500/20"
        />
      </div>

      {/* Main Table Container */}
      <div className="bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-white/10 shadow-xl overflow-hidden flex flex-col">
        
        {/* Table Header / Toolbar */}
        <div className="p-5 border-b border-white/10 flex flex-col xl:flex-row items-start xl:items-center justify-between gap-5">
          
          {/* Left Side: Title & Tabs */}
          <div className="flex flex-col md:flex-row md:items-center gap-4 w-full xl:w-auto">
            <h2 className="text-sm font-semibold text-slate-300 flex items-center gap-2 uppercase tracking-wider whitespace-nowrap">
              <ClipboardCheck className="w-4 h-4 text-indigo-400" /> Pending Task Queue
            </h2>
            
            <div className="hidden md:block w-px h-6 bg-white/10"></div> {/* Vertical Divider */}

            {/* Minimalist Tabs */}
            <div className="flex items-center gap-2 self-start overflow-x-auto hide-scrollbar">
              {tabs.map(tab => {
                const isActive = activeTab === tab;
                const Icon = tab === 'All' ? LayoutGrid : FileText;
                return (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`
                      flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200 whitespace-nowrap
                      ${isActive 
                        ? 'bg-indigo-500/20 text-indigo-300' 
                        : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.02]'}
                    `}
                  >
                    <Icon className="w-4 h-4 opacity-70" />
                    {tab}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Right Side: Search & Filter */}
          <div className="flex items-center gap-3 w-full xl:w-auto mt-2 xl:mt-0">
            <div className="relative w-full sm:w-64" style={{ position: 'relative' }}>
              <Search 
                className="w-4 h-4 text-slate-500" 
                style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }} 
              />
              <input 
                type="text" 
                placeholder="Search tasks..." 
                className="w-full bg-black/20 border border-white/10 rounded-lg py-2 pr-4 text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-indigo-500/50 transition-all"
                style={{ paddingLeft: '36px' }}
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            <button className="flex items-center justify-center gap-2 px-3 py-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg text-sm font-medium text-slate-300 transition-colors">
              <Filter className="w-4 h-4" />
              <span className="hidden sm:inline">Filter</span>
            </button>
          </div>
        </div>

        {/* Data Table */}
        <div className="overflow-x-auto p-2">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="text-xs uppercase tracking-wider font-semibold text-slate-400 border-b border-white/5">
                <th className="px-6 py-4">Task ID</th>
                <th className="px-6 py-4">Entity Name</th>
                <th className="px-6 py-4">Module</th>
                <th className="px-6 py-4">AI Confidence</th>
                <th className="px-6 py-4">Status</th>
                <th className="px-6 py-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {filteredTasks.length === 0 ? (
                <tr>
                  <td colSpan="6" className="px-6 py-12 text-center text-slate-500 text-sm">
                    No tasks found matching your filters.
                  </td>
                </tr>
              ) : (
                filteredTasks.map((task) => (
                <tr key={task.id} className="hover:bg-white/[0.02] transition-colors group cursor-default">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className="text-sm font-medium text-indigo-400 font-mono">
                      {task.id}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-lg bg-indigo-500/10 border border-indigo-500/20">
                        <FileText className="w-4 h-4 text-indigo-400" />
                      </div>
                      <div className="flex flex-col">
                        <span className="text-sm font-semibold text-slate-200">{task.company}</span>
                        <span className="text-xs text-slate-500 mt-0.5">{task.date}</span>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className="text-xs font-semibold text-slate-300 bg-black/30 px-2.5 py-1 rounded-md border border-white/5">
                      {task.module}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center gap-3">
                      <div className="w-24 bg-white/5 rounded-full h-1.5 overflow-hidden">
                        <div 
                          className={`h-1.5 rounded-full shadow-[0_0_8px_rgba(255,255,255,0.2)] ${task.confidence < 80 ? 'bg-rose-400' : task.confidence < 90 ? 'bg-amber-400' : 'bg-emerald-400'}`}
                          style={{ width: `${task.confidence}%` }}
                        />
                      </div>
                      <span className={`text-xs font-bold ${task.confidence < 80 ? 'text-rose-400' : task.confidence < 90 ? 'text-amber-400' : 'text-emerald-400'}`}>{task.confidence}%</span>
                    </div>
                    {task.flaggedFields > 0 && (
                      <p className="text-[10px] text-rose-400 mt-1.5 flex items-center gap-1">
                        <AlertCircle className="w-3 h-3" /> {task.flaggedFields} flagged fields
                      </p>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {task.status === 'urgent' && (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-rose-500/10 text-rose-400 border border-rose-500/20 text-xs font-semibold">
                        <AlertCircle className="w-3.5 h-3.5" /> Action Req
                      </span>
                    )}
                    {task.status === 'pending' && (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-amber-500/10 text-amber-400 border border-amber-500/20 text-xs font-semibold">
                        <Clock className="w-3.5 h-3.5" /> Pending
                      </span>
                    )}
                    {task.status === 'completed' && (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs font-semibold">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Validated
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right">
                    <button 
                      onClick={() => window.location.href = `/review/${task.id}`}
                      className="inline-flex items-center justify-center p-2 bg-indigo-500/20 hover:bg-indigo-500/30 text-indigo-400 rounded-lg transition-colors mr-2 cursor-pointer"
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              )))}
            </tbody>
          </table>
        </div>

      </div>
    </div>
  );
};

export default ReviewPage;
