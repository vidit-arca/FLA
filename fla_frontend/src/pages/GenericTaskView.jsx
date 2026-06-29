import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { AlertCircle } from 'lucide-react';
import { MODULES_SCHEMA } from '../config/modulesSchema';
import TaskView from './TaskView';
import AOC4TaskView from './AOC4TaskView';

export default function GenericTaskView() {
  const { moduleId, taskId } = useParams();
  const navigate = useNavigate();

  const moduleConfig = MODULES_SCHEMA[moduleId];

  if (!moduleConfig) {
    return (
      <div className="flex flex-col items-center justify-center h-[calc(100vh-140px)]">
        <AlertCircle className="w-16 h-16 text-rose-500 mb-4" />
        <h2 className="text-2xl font-bold text-white mb-2">Module Not Found</h2>
        <p className="text-slate-400">The module "{moduleId}" does not exist in the schema.</p>
        <button onClick={() => navigate('/')} className="mt-6 px-6 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl transition-colors font-semibold">
          Go Home
        </button>
      </div>
    );
  }

  // Act as a router/factory for the different UI Engines
  if (moduleConfig.uiEngine === 'wizard') {
    return <AOC4TaskView moduleId={moduleId} taskId={taskId} />;
  }

  if (moduleConfig.uiEngine === 'excel-viewer') {
    return <TaskView moduleId={moduleId} taskId={taskId} />;
  }

  return (
    <div className="flex flex-col items-center justify-center h-[calc(100vh-140px)]">
      <AlertCircle className="w-16 h-16 text-amber-500 mb-4" />
      <h2 className="text-2xl font-bold text-white mb-2">Unknown UI Engine</h2>
      <p className="text-slate-400">The engine "{moduleConfig.uiEngine}" is not supported.</p>
    </div>
  );
}
