import React, { useState } from "react";
import { CheckCircle2, Circle, CircleAlert, CircleDotDashed, CircleX } from "lucide-react";
import { motion, AnimatePresence, LayoutGroup } from "framer-motion";

interface Subtask {
  id: string;
  title: string;
  description: string;
  status: string;
  priority: string;
  tools?: string[];
}

interface Task {
  id: string;
  title: string;
  description: string;
  status: string;
  priority: string;
  level: number;
  dependencies: string[];
  subtasks: Subtask[];
}

interface AgentPlanProps {
  tasks?: Task[];
}

const defaultTasks: Task[] = [];

function StatusIcon({ status, size }: { status: string; size: "sm" | "md" }) {
  const cls = size === "sm" ? "h-3.5 w-3.5" : "h-4.5 w-4.5";
  switch (status) {
    case "completed": return <CheckCircle2 className={`${cls} text-green-500`} />;
    case "in-progress": return <CircleDotDashed className={`${cls} text-blue-500`} />;
    case "need-help": return <CircleAlert className={`${cls} text-yellow-500`} />;
    case "failed": return <CircleX className={`${cls} text-red-500`} />;
    default: return <Circle className={`${cls} text-muted-foreground`} />;
  }
}

export default function AgentPlan({ tasks: propTasks }: AgentPlanProps) {
  const [tasks, setTasks] = useState<Task[]>(propTasks ?? defaultTasks);
  const [expandedTasks, setExpandedTasks] = useState<string[]>([]);

  const toggleTask = (id: string) =>
    setExpandedTasks((prev) => prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id]);

  return (
    <div className="bg-background text-foreground h-full overflow-auto p-2">
      <motion.div className="bg-card border-border rounded-lg border shadow overflow-hidden"
        initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
        <LayoutGroup>
          <div className="p-4 overflow-hidden">
            {tasks.length === 0 ? (
              <p className="text-muted-foreground text-sm text-center py-4">No tasks yet.</p>
            ) : (
              <ul className="space-y-1 overflow-hidden">
                {tasks.map((task) => {
                  const isExpanded = expandedTasks.includes(task.id);
                  return (
                    <motion.li key={task.id} className="mt-1 pt-2" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                      <div className="group flex items-center px-3 py-1.5 rounded-md hover:bg-muted/30">
                        <div className="mr-2 flex-shrink-0 cursor-pointer" onClick={(e) => { e.stopPropagation(); }}>
                          <StatusIcon status={task.status} size="md" />
                        </div>
                        <div className="flex min-w-0 flex-grow cursor-pointer items-center justify-between" onClick={() => toggleTask(task.id)}>
                          <div className="mr-2 flex-1 truncate">
                            <span className={task.status === "completed" ? "text-muted-foreground line-through" : ""}>{task.title}</span>
                          </div>
                          <span className={`rounded px-1.5 py-0.5 text-xs ${task.status === "completed" ? "bg-green-100 text-green-700" : task.status === "in-progress" ? "bg-blue-100 text-blue-700" : task.status === "need-help" ? "bg-yellow-100 text-yellow-700" : task.status === "failed" ? "bg-red-100 text-red-700" : "bg-muted text-muted-foreground"}`}>
                            {task.status}
                          </span>
                        </div>
                      </div>
                      <AnimatePresence>
                        {isExpanded && task.subtasks.length > 0 && (
                          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                            <ul className="mt-1 mr-2 mb-1.5 ml-3 space-y-0.5">
                              {task.subtasks.map((subtask) => (
                                <li key={subtask.id} className="flex flex-col py-0.5 pl-6">
                                  <div className="flex flex-1 items-center rounded-md p-1 hover:bg-muted/30">
                                    <div className="mr-2 flex-shrink-0"><StatusIcon status={subtask.status} size="sm" /></div>
                                    <span className={`text-sm ${subtask.status === "completed" ? "text-muted-foreground line-through" : ""}`}>{subtask.title}</span>
                                  </div>
                                </li>
                              ))}
                            </ul>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </motion.li>
                  );
                })}
              </ul>
            )}
          </div>
        </LayoutGroup>
      </motion.div>
    </div>
  );
}
