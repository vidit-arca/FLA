with open("/Users/apple/Desktop/FLA/fla_frontend/src/pages/Dashboard.jsx", "r") as f:
    content = f.read()

# Add imports
imports = """import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { FileText, Clock, CheckCircle, AlertCircle } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';"""

content = content.replace("import { FileText, Clock, CheckCircle, AlertCircle } from 'lucide-react';", imports.split('\n')[-2] + '\n' + imports.split('\n')[-1])

# Create dummy chart data based on tasks
chart_logic = """
  const chartData = [
    { name: 'Mon', extractions: 4 },
    { name: 'Tue', extractions: 7 },
    { name: 'Wed', extractions: 5 },
    { name: 'Thu', extractions: 12 },
    { name: 'Fri', extractions: tasks.length > 0 ? tasks.length + 8 : 9 },
    { name: 'Sat', extractions: 2 },
    { name: 'Sun', extractions: 0 },
  ];
"""
content = content.replace("return (", chart_logic + "\n  return (")

chart_ui = """
      <div className="bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-white/10 p-6 shadow-2xl shadow-indigo-900/20 mb-10">
        <h2 className="text-lg font-semibold text-white mb-6">Extraction Volume (Last 7 Days)</h2>
        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="colorExtractions" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#818cf8" stopOpacity={0.8}/>
                  <stop offset="95%" stopColor="#818cf8" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
              <XAxis dataKey="name" stroke="#94a3b8" tick={{fill: '#94a3b8'}} axisLine={false} tickLine={false} />
              <YAxis stroke="#94a3b8" tick={{fill: '#94a3b8'}} axisLine={false} tickLine={false} />
              <Tooltip 
                contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '0.5rem', color: '#fff' }}
                itemStyle={{ color: '#a5b4fc' }}
              />
              <Area type="monotone" dataKey="extractions" stroke="#818cf8" strokeWidth={3} fillOpacity={1} fill="url(#colorExtractions)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Tasks Table */}
"""
content = content.replace("{/* Tasks Table */}", chart_ui)

with open("/Users/apple/Desktop/FLA/fla_frontend/src/pages/Dashboard.jsx", "w") as f:
    f.write(content)
