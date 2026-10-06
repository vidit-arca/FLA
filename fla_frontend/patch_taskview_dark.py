with open("/Users/apple/Desktop/FLA/fla_frontend/src/pages/TaskView.jsx", "r") as f:
    tv = f.read()

tv = tv.replace('text-slate-900', 'text-white')
tv = tv.replace('text-slate-800', 'text-slate-200')
tv = tv.replace(
    'bg-white rounded-xl border border-slate-200',
    'bg-[#1A2235]/60 backdrop-blur-xl rounded-xl border border-white/10 shadow-2xl shadow-indigo-900/20'
)
tv = tv.replace('bg-slate-50', 'bg-[#131B2C]/80')
tv = tv.replace('border-slate-200', 'border-white/10')
tv = tv.replace('text-slate-500', 'text-slate-400')
tv = tv.replace('text-slate-700', 'text-slate-300')
tv = tv.replace('bg-white p-3', 'bg-[#1A2235] p-3 border border-white/10')

with open("/Users/apple/Desktop/FLA/fla_frontend/src/pages/TaskView.jsx", "w") as f:
    f.write(tv)

with open("/Users/apple/Desktop/FLA/fla_frontend/src/components/ExcelViewer.jsx", "r") as f:
    ev = f.read()

ev = ev.replace('bg-white', 'bg-[#1A2235]')
ev = ev.replace('bg-slate-50', 'bg-[#131B2C]')
ev = ev.replace('bg-slate-100', 'bg-[#1e293b]')
ev = ev.replace('text-slate-800', 'text-slate-200')
ev = ev.replace('text-slate-500', 'text-slate-400')
ev = ev.replace('text-slate-700', 'text-slate-300')
ev = ev.replace('border-slate-200', 'border-slate-700')
ev = ev.replace('border-slate-300', 'border-slate-700')
ev = ev.replace('bg-amber-50 text-amber-900', 'bg-indigo-900/40 text-indigo-300')
ev = ev.replace('bg-primary-600', 'bg-indigo-600')
ev = ev.replace('hover:bg-primary-700', 'hover:bg-indigo-500')
ev = ev.replace('text-primary-500', 'text-indigo-400')
ev = ev.replace('text-primary-700', 'text-indigo-300')
ev = ev.replace('border-primary-600', 'border-indigo-500')

with open("/Users/apple/Desktop/FLA/fla_frontend/src/components/ExcelViewer.jsx", "w") as f:
    f.write(ev)
