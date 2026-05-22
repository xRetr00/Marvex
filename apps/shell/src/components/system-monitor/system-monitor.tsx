import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Cpu, HardDrive, Wifi, Zap, Activity } from "lucide-react";

interface DataPoint { value: number; timestamp: number; isSpike?: boolean; }

interface ResourceData {
  cpu: DataPoint[]; gpu: DataPoint[]; vram: DataPoint[]; network: DataPoint[]; memory: DataPoint[];
}

const generateDataPoint = (baseValue: number, variance: number, spikeChance = 0.05): DataPoint => {
  const isSpike = Math.random() < spikeChance;
  const multiplier = isSpike ? 1.5 + Math.random() * 0.5 : 1;
  const value = Math.max(0, Math.min(100, baseValue + (Math.random() - 0.5) * variance * multiplier));
  return { value, timestamp: Date.now(), isSpike: isSpike && value > 70 };
};

const Sparkline = ({ data, color = "#3b82f6", spikeColor = "#ef4444", width = 60, height = 20 }: { data: DataPoint[]; color?: string; spikeColor?: string; width?: number; height?: number }) => {
  const points = data.map((point, index) => ({ x: data.length > 1 ? (index / (data.length - 1)) * width : 0, y: height - (point.value / 100) * height, isSpike: point.isSpike }));
  const path = points.reduce((acc, point, index) => index === 0 ? `M ${point.x} ${point.y}` : `${acc} L ${point.x} ${point.y}`, "");
  const hasSpikes = points.some((p) => p.isSpike);
  return (
    <svg width={width} height={height} className="overflow-visible">
      <path d={`${path} L ${width} ${height} L 0 ${height} Z`} fill={hasSpikes ? `${spikeColor}30` : `${color}30`} />
      <path d={path} fill="none" stroke={hasSpikes ? spikeColor : color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
};

const ResourceCard = ({ icon: Icon, label, value, data, color, unit = "%" }: { icon: React.ComponentType<{ className?: string }>; label: string; value: number; data: DataPoint[]; color: string; unit?: string }) => {
  const hasSpikes = data.some((d) => d.isSpike);
  return (
    <div className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-muted/50">
      <div className={`flex items-center justify-center w-7 h-7 rounded-md bg-muted ${hasSpikes ? "!bg-red-50" : ""}`}>
        <Icon className={`w-4 h-4 ${hasSpikes ? "text-red-500" : "text-muted-foreground"}`} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs font-medium text-muted-foreground">{label}</span>
          <span className={`text-xs font-mono ${hasSpikes ? "text-red-500" : "text-foreground"}`}>{value.toFixed(1)} {unit}</span>
        </div>
        <Sparkline data={data} color={color} />
      </div>
    </div>
  );
};

function lastValue(arr: DataPoint[]): number {
  return arr[arr.length - 1]?.value ?? 0;
}

function hasSpike(arr: DataPoint[]): boolean {
  return arr[arr.length - 1]?.isSpike === true;
}

export default function SystemMonitor() {
  const [resourceData, setResourceData] = useState<ResourceData>({ cpu: [], gpu: [], vram: [], network: [], memory: [] });
  const [isExpanded, setIsExpanded] = useState(false);

  // Check only the newest point per channel — spikes are flagged on generation
  const hasAnySpikes = hasSpike(resourceData.cpu) || hasSpike(resourceData.gpu) ||
    hasSpike(resourceData.vram) || hasSpike(resourceData.network) || hasSpike(resourceData.memory);

  useEffect(() => {
    const interval = setInterval(() => {
      setResourceData((prev) => ({
        cpu: [...prev.cpu, generateDataPoint(45, 30, 0.08)].slice(-20),
        gpu: [...prev.gpu, generateDataPoint(35, 25, 0.06)].slice(-20),
        vram: [...prev.vram, generateDataPoint(60, 20, 0.05)].slice(-20),
        network: [...prev.network, generateDataPoint(25, 40, 0.1)].slice(-20),
        memory: [...prev.memory, generateDataPoint(70, 15, 0.04)].slice(-20),
      }));
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const currentCpu = lastValue(resourceData.cpu);
  const currentGpu = lastValue(resourceData.gpu);
  const currentVram = lastValue(resourceData.vram);
  const currentNetwork = lastValue(resourceData.network);
  const currentMemory = lastValue(resourceData.memory);

  return (
    <Card className="w-full bg-background/95 backdrop-blur-sm border shadow-lg">
      <div className="p-3 cursor-pointer" onClick={() => setIsExpanded(!isExpanded)}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Activity className={`w-4 h-4 ${hasAnySpikes ? "text-red-500" : "text-muted-foreground"}`} />
            <span className="text-sm font-medium">System Monitor</span>
            {hasAnySpikes && <Badge variant="destructive" className="text-xs text-white px-1.5 py-0.5">Spike</Badge>}
          </div>
          <motion.div animate={{ rotate: isExpanded ? 180 : 0 }} className="text-muted-foreground text-xs">▼</motion.div>
        </div>
        <div className="grid grid-cols-2 gap-1.5">
          <ResourceCard icon={Cpu} label="CPU" value={currentCpu} data={resourceData.cpu} color="#3b82f6" />
          <ResourceCard icon={Zap} label="GPU" value={currentGpu} data={resourceData.gpu} color="#10b981" />
          <ResourceCard icon={HardDrive} label="VRAM" value={currentVram} data={resourceData.vram} color="#f59e0b" />
          <ResourceCard icon={Wifi} label="Network" value={currentNetwork} data={resourceData.network} color="#8b5cf6" unit="MB/s" />
        </div>
      </div>
      <AnimatePresence>
        {isExpanded && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
            <div className="px-3 pb-3 border-t">
              <div className="mt-3">
                <ResourceCard icon={HardDrive} label="System Memory" value={currentMemory} data={resourceData.memory} color="#ef4444" unit="GB" />
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  );
}
