with open("/Users/apple/Desktop/FLA/fla_frontend/src/pages/Dashboard.jsx", "r") as f:
    content = f.read()

# Replace Stats Cards
old_stats = """      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
          <div className="flex items-center gap-4">
            <div className="bg-primary-100 p-3 rounded-lg"><FileText className="text-primary-600" /></div>
            <div>
              <p className="text-sm text-slate-500 font-medium">Total Extractions</p>
              <p className="text-2xl font-bold text-slate-900">{tasks.length}</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
          <div className="flex items-center gap-4">
            <div className="bg-amber-100 p-3 rounded-lg"><Clock className="text-amber-600" /></div>
            <div>
              <p className="text-sm text-slate-500 font-medium">Pending Review</p>
              <p className="text-2xl font-bold text-slate-900">{tasks.filter(t => t.status === 'review_needed').length}</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
          <div className="flex items-center gap-4">
            <div className="bg-green-100 p-3 rounded-lg"><CheckCircle className="text-green-600" /></div>
            <div>
              <p className="text-sm text-slate-500 font-medium">Completed</p>
              <p className="text-2xl font-bold text-slate-900">{tasks.filter(t => t.status === 'completed').length}</p>
            </div>
          </div>
        </div>
      </div>"""

new_stats = """      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
        <div className="bg-white/80 backdrop-blur-md rounded-2xl border border-white/50 p-6 shadow-xl shadow-slate-200/50 hover:-translate-y-1 hover:shadow-2xl transition-all duration-300 group">
          <div className="flex items-center gap-5">
            <div className="bg-gradient-to-br from-primary-400 to-primary-600 p-4 rounded-xl shadow-lg shadow-primary-500/30 group-hover:scale-110 transition-transform"><FileText className="text-white w-6 h-6" /></div>
            <div>
              <p className="text-sm text-slate-500 font-semibold tracking-wide uppercase">Total Extractions</p>
              <p className="text-3xl font-extrabold text-slate-900 mt-1">{tasks.length}</p>
            </div>
          </div>
        </div>
        <div className="bg-white/80 backdrop-blur-md rounded-2xl border border-white/50 p-6 shadow-xl shadow-slate-200/50 hover:-translate-y-1 hover:shadow-2xl transition-all duration-300 group">
          <div className="flex items-center gap-5">
            <div className="bg-gradient-to-br from-amber-400 to-amber-600 p-4 rounded-xl shadow-lg shadow-amber-500/30 group-hover:scale-110 transition-transform"><Clock className="text-white w-6 h-6" /></div>
            <div>
              <p className="text-sm text-slate-500 font-semibold tracking-wide uppercase">Pending Review</p>
              <p className="text-3xl font-extrabold text-slate-900 mt-1">{tasks.filter(t => t.status === 'review_needed').length}</p>
            </div>
          </div>
        </div>
        <div className="bg-white/80 backdrop-blur-md rounded-2xl border border-white/50 p-6 shadow-xl shadow-slate-200/50 hover:-translate-y-1 hover:shadow-2xl transition-all duration-300 group">
          <div className="flex items-center gap-5">
            <div className="bg-gradient-to-br from-emerald-400 to-emerald-600 p-4 rounded-xl shadow-lg shadow-emerald-500/30 group-hover:scale-110 transition-transform"><CheckCircle className="text-white w-6 h-6" /></div>
            <div>
              <p className="text-sm text-slate-500 font-semibold tracking-wide uppercase">Completed</p>
              <p className="text-3xl font-extrabold text-slate-900 mt-1">{tasks.filter(t => t.status === 'completed').length}</p>
            </div>
          </div>
        </div>
      </div>"""

content = content.replace(old_stats, new_stats)

old_table = """<div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">"""
new_table = """<div className="bg-white/80 backdrop-blur-md rounded-2xl border border-white/50 shadow-xl shadow-slate-200/50 overflow-hidden">"""
content = content.replace(old_table, new_table)

with open("/Users/apple/Desktop/FLA/fla_frontend/src/pages/Dashboard.jsx", "w") as f:
    f.write(content)
