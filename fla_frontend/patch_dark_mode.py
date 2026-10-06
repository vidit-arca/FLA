import re

# App.jsx
with open("/Users/apple/Desktop/FLA/fla_frontend/src/App.jsx", "r") as f:
    app_content = f.read()

app_content = app_content.replace(
    'min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex font-sans',
    'min-h-screen bg-[#0B0F19] flex font-sans text-slate-200'
)
app_content = app_content.replace(
    'w-72 bg-white/70 backdrop-blur-xl border-r border-slate-200/60 flex flex-col shadow-[4px_0_24px_-12px_rgba(0,0,0,0.1)] z-10',
    'w-72 bg-[#131B2C]/60 backdrop-blur-2xl border-r border-white/5 flex flex-col shadow-[4px_0_24px_-12px_rgba(0,0,0,0.5)] z-10'
)
app_content = app_content.replace(
    'text-3xl font-extrabold bg-clip-text text-transparent bg-gradient-to-r from-slate-900 to-slate-700',
    'text-3xl font-extrabold bg-clip-text text-transparent bg-gradient-to-r from-indigo-400 to-purple-400'
)
app_content = app_content.replace(
    'text-sm text-slate-500 font-medium ml-13',
    'text-sm text-slate-400 font-medium ml-13'
)
app_content = app_content.replace(
    'text-slate-600 hover:text-primary-700 hover:bg-primary-50/80',
    'text-slate-300 hover:text-indigo-400 hover:bg-indigo-500/10'
)
app_content = app_content.replace(
    'group-hover:text-primary-600',
    'group-hover:text-indigo-400'
)
app_content = app_content.replace(
    'bg-primary-200/20 blur-3xl',
    'bg-indigo-600/20 blur-[100px]'
)
app_content = app_content.replace(
    'bg-blue-200/20 blur-3xl',
    'bg-purple-600/20 blur-[100px]'
)
app_content = app_content.replace(
    'from-primary-500 to-primary-700',
    'from-indigo-500 to-purple-600'
)

with open("/Users/apple/Desktop/FLA/fla_frontend/src/App.jsx", "w") as f:
    f.write(app_content)

# Dashboard.jsx
with open("/Users/apple/Desktop/FLA/fla_frontend/src/pages/Dashboard.jsx", "r") as f:
    dash_content = f.read()

dash_content = dash_content.replace('text-slate-900', 'text-white')
dash_content = dash_content.replace(
    'bg-white/80 backdrop-blur-md rounded-2xl border border-white/50 p-6 shadow-xl shadow-slate-200/50',
    'bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-white/10 p-6 shadow-2xl shadow-indigo-900/20'
)
dash_content = dash_content.replace(
    'bg-white/80 backdrop-blur-md rounded-2xl border border-white/50 shadow-xl shadow-slate-200/50',
    'bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-white/10 shadow-2xl shadow-indigo-900/20'
)
dash_content = dash_content.replace('bg-slate-50/50', 'bg-[#131B2C]/80')
dash_content = dash_content.replace('bg-slate-50', 'bg-[#131B2C]/80')
dash_content = dash_content.replace('border-slate-200', 'border-white/10')
dash_content = dash_content.replace('text-slate-800', 'text-slate-200')
dash_content = dash_content.replace('text-slate-500', 'text-slate-400')
dash_content = dash_content.replace('hover:bg-slate-50', 'hover:bg-white/5')
dash_content = dash_content.replace('text-primary-600 hover:text-primary-700', 'text-indigo-400 hover:text-indigo-300')

with open("/Users/apple/Desktop/FLA/fla_frontend/src/pages/Dashboard.jsx", "w") as f:
    f.write(dash_content)

# Upload.jsx
with open("/Users/apple/Desktop/FLA/fla_frontend/src/pages/Upload.jsx", "r") as f:
    up_content = f.read()

up_content = up_content.replace('text-slate-900', 'text-white')
up_content = up_content.replace(
    'bg-white/80 backdrop-blur-md rounded-2xl border border-white/50 p-10 shadow-xl shadow-slate-200/50',
    'bg-[#1A2235]/60 backdrop-blur-xl rounded-2xl border border-white/10 p-10 shadow-2xl shadow-purple-900/20'
)
up_content = up_content.replace('text-slate-700', 'text-slate-300')
up_content = up_content.replace(
    'bg-white/50 border border-slate-200',
    'bg-[#131B2C]/80 border border-white/10 text-white'
)
up_content = up_content.replace(
    'bg-slate-50/50 hover:bg-primary-50 hover:border-primary-400 border-slate-300',
    'bg-[#131B2C]/50 hover:bg-indigo-900/20 hover:border-indigo-500/50 border-white/10'
)
up_content = up_content.replace('text-slate-400', 'text-slate-400')
up_content = up_content.replace(
    'bg-gradient-to-r from-primary-600 to-primary-700 hover:from-primary-500 hover:to-primary-600',
    'bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-400 hover:to-purple-500'
)
up_content = up_content.replace('bg-white p-4', 'bg-[#1A2235] p-4 border border-white/10')
up_content = up_content.replace('text-primary-500', 'text-indigo-400')

with open("/Users/apple/Desktop/FLA/fla_frontend/src/pages/Upload.jsx", "w") as f:
    f.write(up_content)

