import React, { useState } from 'react';
import { 
  Briefcase, CheckSquare, Calendar, FileText, Plus, 
  Trash2, CheckCircle2, Clock, Users 
} from 'lucide-react';

interface Task {
  id: string;
  title: string;
  completed: boolean;
  priority: 'High' | 'Medium' | 'Low';
  due: string;
}

export const ProductivityWorkspaceView: React.FC = () => {
  const [tasks, setTasks] = useState<Task[]>([
    { id: '1', title: 'Compile Indic NLP Tokenizer Benchmarks for Tamil & Telugu', completed: true, priority: 'High', due: 'Today' },
    { id: '2', title: 'Review ONDC direct restaurant integration schema', completed: false, priority: 'High', due: 'Tomorrow' },
    { id: '3', title: 'Prepare design system documentation for Mobile App release', completed: false, priority: 'Medium', due: '18 Oct' },
  ]);

  const [newTaskTitle, setNewTaskTitle] = useState('');

  const toggleTask = (id: string) => {
    setTasks((prev) =>
      prev.map((t) => (t.id === id ? { ...t, completed: !t.completed } : t))
    );
  };

  const handleAddTask = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTaskTitle.trim()) return;

    setTasks([
      ...tasks,
      {
        id: String(Date.now()),
        title: newTaskTitle,
        completed: false,
        priority: 'Medium',
        due: 'Today',
      },
    ]);
    setNewTaskTitle('');
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto w-full">
      {/* Workspace Header */}
      <div className="p-6 rounded-3xl bg-slate-900/60 border border-white/10 backdrop-blur-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-violet-400 text-xs font-semibold uppercase tracking-wider">
            <Briefcase className="w-4 h-4" />
            <span>Productivity & Knowledge Engine</span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight mt-1">Unified Team Workspace</h1>
          <p className="text-xs text-slate-400 mt-1">
            Organize roadmaps, sprint tasks, and collaborative research docs seamlessly.
          </p>
        </div>
      </div>

      {/* Task Planner Panel */}
      <div className="p-6 rounded-2xl bg-slate-900/60 border border-white/10 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <CheckSquare className="w-4 h-4 text-violet-400" /> Action Items & Sprint Deliverables
          </h3>
          <span className="text-xs text-slate-400 font-mono">
            {tasks.filter((t) => t.completed).length} / {tasks.length} Done
          </span>
        </div>

        <form onSubmit={handleAddTask} className="flex items-center space-x-2">
          <input
            type="text"
            value={newTaskTitle}
            onChange={(e) => setNewTaskTitle(e.target.value)}
            placeholder="Add a new deliverable or note..."
            className="flex-1 px-3.5 py-2.5 bg-slate-800 border border-white/10 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-violet-500"
          />
          <button
            type="submit"
            disabled={!newTaskTitle.trim()}
            className="px-4 py-2.5 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 text-white rounded-xl text-xs font-semibold transition"
          >
            Add Task
          </button>
        </form>

        <div className="space-y-2 pt-2">
          {tasks.map((task) => (
            <div
              key={task.id}
              onClick={() => toggleTask(task.id)}
              className="p-3.5 rounded-xl bg-slate-800/40 hover:bg-slate-800/70 border border-white/5 cursor-pointer flex items-center justify-between text-xs transition"
            >
              <div className="flex items-center space-x-3">
                <CheckCircle2
                  className={`w-4 h-4 shrink-0 transition ${
                    task.completed ? 'text-emerald-400' : 'text-slate-600'
                  }`}
                />
                <span className={`font-medium ${task.completed ? 'line-through text-slate-500' : 'text-slate-200'}`}>
                  {task.title}
                </span>
              </div>
              <div className="flex items-center space-x-2 text-[10px]">
                <span
                  className={`px-2 py-0.5 rounded font-bold ${
                    task.priority === 'High'
                      ? 'bg-red-500/20 text-red-300'
                      : 'bg-amber-500/20 text-amber-300'
                  }`}
                >
                  {task.priority}
                </span>
                <span className="text-slate-400">{task.due}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
