import React, { useState, useEffect } from 'react';
import { 
  Briefcase, CheckSquare, Calendar, FileText, Plus, 
  Trash2, CheckCircle2, Clock, Users 
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

interface Task {
  id: string;
  title: string;
  completed: boolean;
  priority: 'High' | 'Medium' | 'Low';
  due: string;
}

export const ProductivityWorkspaceView: React.FC = () => {
  const { user } = useAuth();
  const storageKey = user ? `super_ai_workspace_tasks_${user.id}` : 'super_ai_workspace_tasks_guest';

  const [tasks, setTasks] = useState<Task[]>(() => {
    try {
      const saved = localStorage.getItem(storageKey);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  // Switch tasks when user account changes or on login/logout
  useEffect(() => {
    try {
      const saved = localStorage.getItem(storageKey);
      setTasks(saved ? JSON.parse(saved) : []);
    } catch {
      setTasks([]);
    }
  }, [storageKey]);

  const [newTaskTitle, setNewTaskTitle] = useState('');

  // Persist tasks locally for the current isolated user account
  const updateTasks = (newTasks: Task[]) => {
    setTasks(newTasks);
    try {
      localStorage.setItem(storageKey, JSON.stringify(newTasks));
    } catch (e) {
      console.warn('Failed to save workspace tasks to localStorage:', e);
    }
  };

  const toggleTask = (id: string) => {
    const updated = tasks.map((t) => (t.id === id ? { ...t, completed: !t.completed } : t));
    updateTasks(updated);
  };

  const deleteTask = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    const updated = tasks.filter((t) => t.id !== id);
    updateTasks(updated);
  };

  const handleAddTask = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTaskTitle.trim()) return;

    const newTask: Task = {
      id: String(Date.now()),
      title: newTaskTitle.trim(),
      completed: false,
      priority: 'Medium',
      due: 'Today',
    };
    updateTasks([newTask, ...tasks]);
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
            className="px-4 py-2.5 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 text-white rounded-xl text-xs font-semibold transition flex items-center gap-1.5"
          >
            <Plus className="w-3.5 h-3.5" />
            Add Task
          </button>
        </form>

        <div className="space-y-2 pt-2">
          {tasks.length === 0 ? (
            <div className="p-8 text-center rounded-xl bg-slate-800/20 border border-white/5 space-y-2">
              <CheckSquare className="w-8 h-8 text-slate-600 mx-auto" />
              <p className="text-xs text-slate-400 font-medium">No tasks yet</p>
              <p className="text-[11px] text-slate-500">Add your first deliverable above to begin tracking your work.</p>
            </div>
          ) : (
            tasks.map((task) => (
              <div
                key={task.id}
                onClick={() => toggleTask(task.id)}
                className="p-3.5 rounded-xl bg-slate-800/40 hover:bg-slate-800/70 border border-white/5 cursor-pointer flex items-center justify-between text-xs transition group"
              >
                <div className="flex items-center space-x-3 flex-1 min-w-0 pr-3">
                  <CheckCircle2
                    className={`w-4 h-4 shrink-0 transition ${
                      task.completed ? 'text-emerald-400' : 'text-slate-600'
                    }`}
                  />
                  <span className={`font-medium truncate ${task.completed ? 'line-through text-slate-500' : 'text-slate-200'}`}>
                    {task.title}
                  </span>
                </div>
                <div className="flex items-center space-x-2 text-[10px] shrink-0">
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
                  <button
                    onClick={(e) => deleteTask(e, task.id)}
                    className="p-1 rounded text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition"
                    title="Delete task"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
