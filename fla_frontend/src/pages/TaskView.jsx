import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Loader2, CheckCircle, Download, FileSpreadsheet, ArrowLeft } from 'lucide-react';
import ExcelViewer from '../components/ExcelViewer';

export default function TaskView() {
  const { taskId } = useParams();
  const navigate = useNavigate();
  const [task, setTask] = useState(null);
  const [logs, setLogs] = useState('');
  const [error, setError] = useState('');
  const logsEndRef = useRef(null);

  useEffect(() => {
    let interval = null;
    
    const fetchTask = async () => {
      try {
        const res = await axios.get(`http://localhost:8000/api/tasks/${taskId}`);
        setTask(res.data);
        setLogs(res.data.logs || '');
        
        if (res.data.status === 'completed' || res.data.status === 'error' || res.data.status === 'review_needed') {
          clearInterval(interval);
        }
      } catch (err) {
        console.error(err);
        setError("Failed to fetch task status.");
        clearInterval(interval);
      }
    };

    fetchTask();
    interval = setInterval(fetchTask, 2000);
    
    return () => clearInterval(interval);
  }, [taskId]);

  useEffect(() => {
    // Auto-scroll logs
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  const handleExport = async (editedData) => {
    try {
      const res = await axios.post(`http://localhost:8000/api/export/${taskId}`, editedData);
      // Wait a moment then fetch task again to get download URL
      setTimeout(async () => {
        const tRes = await axios.get(`http://localhost:8000/api/tasks/${taskId}`);
        setTask(tRes.data);
      }, 1000);
    } catch (err) {
      console.error(err);
      alert("Failed to export Excel.");
    }
  };

  const handleDownload = () => {
    window.location.href = `http://localhost:8000/api/download/${taskId}`;
  };

  if (error) return <div className="text-red-500 font-medium p-8">{error}</div>;
  if (!task) return <div className="flex items-center justify-center p-20"><Loader2 className="w-8 h-8 animate-spin text-primary-500" /></div>;

  const isProcessing = task.status === 'uploaded' || task.status === 'processing' || task.status === 'exporting';
  const isReview = task.status === 'review_needed';
  const isCompleted = task.status === 'completed';

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-4">
          <button onClick={() => navigate('/fla')} className="bg-white/5 hover:bg-white/10 p-2.5 rounded-xl transition-colors border border-white/10 text-slate-400 hover:text-white shadow-sm">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-3xl font-bold text-white">{task.company_name}</h1>
            <p className="text-slate-400 mt-1">Task ID: {task.id}</p>
          </div>
        </div>
        <div>
          <span className={`px-4 py-2 rounded-full text-sm font-bold uppercase tracking-wide
            ${isProcessing ? 'bg-blue-100 text-blue-700 animate-pulse' : ''}
            ${isReview ? 'bg-amber-100 text-amber-700' : ''}
            ${isCompleted ? 'bg-green-100 text-green-700' : ''}
            ${task.status === 'error' ? 'bg-red-100 text-red-700' : ''}
          `}>
            {task.status.replace('_', ' ')}
          </span>
        </div>
      </div>

      {isProcessing && (
        <div className="bg-slate-900 rounded-xl border border-slate-800 p-6 shadow-xl overflow-hidden font-mono text-sm">
          <div className="flex items-center gap-3 text-slate-400 mb-4 pb-4 border-b border-slate-800">
            <Loader2 className="w-5 h-5 animate-spin text-primary-400" />
            <span>Engine is processing documents...</span>
          </div>
          <div className="h-96 overflow-y-auto whitespace-pre-wrap text-emerald-400">
            {logs}
            <div ref={logsEndRef} />
          </div>
        </div>
      )}

      {isCompleted && (
        <div className="relative overflow-hidden bg-gradient-to-r from-emerald-50 to-teal-50 rounded-2xl border border-emerald-200 p-8 shadow-xl shadow-emerald-500/10 flex items-center justify-between mb-10 animate-fade-in">
          <div className="absolute -right-20 -top-20 w-64 h-64 bg-emerald-400/20 rounded-full blur-3xl"></div>
          <div className="flex items-center gap-6 relative z-10">
            <div className="bg-[#1A2235] p-3 border border-white/10 rounded-full shadow-md">
              <CheckCircle className="w-12 h-12 text-emerald-500" />
            </div>
            <div>
              <h2 className="text-3xl font-extrabold text-slate-900 mb-2 tracking-tight">Excel Generated Successfully!</h2>
              <p className="text-slate-600 font-medium">The FLA Return has been fully populated and validated by the AI.</p>
            </div>
          </div>
          <button 
            onClick={handleDownload}
            className="relative z-10 inline-flex items-center gap-3 bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white px-8 py-4 rounded-xl font-bold text-lg shadow-lg shadow-emerald-500/30 hover:shadow-xl hover:shadow-emerald-500/40 hover:-translate-y-1 transition-all duration-300"
          >
            <FileSpreadsheet className="w-6 h-6" />
            Download Excel
          </button>
        </div>
      )}

      {isCompleted && (
        <div className="mt-8 mb-8">
            <h2 className="text-xl font-bold text-slate-200 mb-4">Live Excel Editor</h2>
            <ExcelViewer taskId={taskId} />
        </div>
      )}
      
      {task.status === 'error' && (
        <div className="bg-red-50 rounded-xl border border-red-200 p-6 text-red-700 font-mono whitespace-pre-wrap">
          {logs}
        </div>
      )}

    </div>
  );
}
