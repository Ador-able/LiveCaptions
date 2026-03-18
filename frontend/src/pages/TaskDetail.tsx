import { useEffect, useState, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { toast } from 'sonner';
import {
    ArrowLeft, Play, Pause, RotateCcw, Download,
    CheckCircle2, Circle, Terminal
} from 'lucide-react';
import { format } from 'date-fns';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { taskApi, Task, Log } from '@/lib/api';
import { cn, getStatusColor, getStatusIcon, getStatusLabel } from '@/lib/utils';

import { useWebSocket } from '@/contexts/WebSocketContext';

export default function TaskDetail() {
    const { taskId } = useParams<{ taskId: string }>();
    const [task, setTask] = useState<Task | null>(null);
    const [logs, setLogs] = useState<Log[]>([]);
    const [selectedFormat, setSelectedFormat] = useState<string>('srt');
    const logsEndRef = useRef<HTMLDivElement>(null);
    const { connected, subscribe } = useWebSocket();

    // Unified data management
    useEffect(() => {
        if (!taskId) return;

        const currentTaskId = taskId.toLowerCase();
        console.log(`[TaskDetail] Initializing for ${currentTaskId}`);

        // 1. Subscribe FIRST to avoid missing updates during initial fetch
        const unsubscribe = subscribe((message) => {
            const msgTaskId = message.task_id?.toLowerCase();
            if (msgTaskId !== currentTaskId) return;

            console.log(`[TaskDetail] WS Update:`, message.type);

            if (message.type === 'status') {
                const newTask = message.data;
                setTask(prev => {
                    // Avoid overwriting with older data if possible (using updated_at)
                    if (prev && prev.updated_at && newTask.updated_at) {
                        if (new Date(newTask.updated_at) < new Date(prev.updated_at)) {
                            console.warn('[TaskDetail] Ignored older status update');
                            return prev;
                        }
                    }
                    return prev ? { ...prev, ...newTask } : newTask;
                });

                if (newTask.logs) {
                    setLogs(prev => {
                        const isReset = (newTask.status === 'PENDING' || newTask.status === 'PROCESSING') && newTask.logs.length === 0;
                        if (newTask.logs.length >= prev.length || isReset) {
                            return newTask.logs;
                        }
                        return prev;
                    });
                }
            } else if (message.type === 'log') {
                setLogs(prev => {
                    const exists = prev.some(l => l.timestamp === message.data.timestamp && l.message === message.data.message);
                    if (exists) return prev;
                    return [...prev, message.data];
                });
            }
        });

        // 2. Fetch initial data
        const fetchTask = async () => {
            try {
                const data = await taskApi.get(taskId);
                setTask(data);
                if (data.logs) {
                    setLogs(data.logs);
                }
            } catch (error) {
                toast.error('无法加载任务详情');
            }
        };
        fetchTask();

        return () => {
            console.log(`[TaskDetail] Cleaning up for ${currentTaskId}`);
            unsubscribe();
        };
    }, [taskId, subscribe]);

    // Scroll logs to bottom
    useEffect(() => {
        if (logsEndRef.current) {
            const timer = setTimeout(() => {
                logsEndRef.current?.scrollIntoView({ behavior: 'auto', block: 'end' });
            }, 50); // Slightly longer delay to ensure DOM is ready
            return () => clearTimeout(timer);
        }
    }, [logs]);

    const handleAction = async (action: 'pause' | 'resume') => {
        if (!taskId) return;
        try {
            await taskApi.action(taskId, action);
            toast.success(action === 'pause' ? '任务已暂停' : '任务已恢复');
        } catch (error) {
            toast.error('操作失败');
        }
    };

    const handleRetry = async () => {
        if (!taskId) return;
        try {
            await taskApi.retry(taskId);
            toast.success('任务已重试');
        } catch (error) {
            toast.error('重试失败');
        }
    }

    const handleRestartFromStep = async (step: number, stepName: string) => {
        if (!taskId) return;
        const confirmed = window.confirm(`确定要从步骤 ${step}「${stepName}」重新开始执行吗？\n\n该步骤及之后的所有结果将被清除并重新处理。`);
        if (!confirmed) return;
        try {
            await taskApi.restartFromStep(taskId, step);
            toast.success(`任务将从步骤 ${step}「${stepName}」重新开始`);
        } catch (error: any) {
            const detail = error?.response?.data?.detail || '操作失败';
            toast.error(detail);
        }
    }

    if (!task) {
        return <div className="p-8 text-center text-muted-foreground">加载中...</div>;
    }

    const steps = [
        { id: 1, name: '音频提取' },
        { id: 2, name: '人声分离' },
        { id: 3, name: '语音识别 (ASR)' },
        { id: 4, name: '合规检查' },
        { id: 5, name: '智能翻译' },
        { id: 6, name: '清理工作区' },
    ];

    return (
        <div className="space-y-6 h-[calc(100vh-100px)] flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between shrink-0">
                <div className="flex items-center gap-4">
                    <Link to="/">
                        <Button variant="ghost" size="icon">
                            <ArrowLeft className="h-4 w-4" />
                        </Button>
                    </Link>
                    <div>
                        <h2 className="text-xl font-bold tracking-tight flex items-center gap-2">
                            {(task.original_filename || task.video_path || 'Unknown File').split(/[\\/]/).pop()}
                            <Badge variant="outline" className={cn("text-xs font-normal", getStatusColor(task.status))}>
                                {getStatusIcon(task.status)}
                                {getStatusLabel(task.status)}
                            </Badge>
                        </h2>
                        <p className="text-xs text-muted-foreground flex items-center gap-2">
                            ID: {task.id} • Created {format(new Date(task.created_at), 'yyyy-MM-dd HH:mm')}
                            {connected && <span className="text-green-500 flex items-center gap-1">• <Circle className="w-2 h-2 fill-green-500" /> Live</span>}
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    {task.status === 'PENDING' && (
                        <Button variant="default" size="sm" onClick={() => handleAction('resume')}>
                            <Play className="mr-2 h-4 w-4" /> 开始任务
                        </Button>
                    )}
                    {task.status === 'PROCESSING' && (
                        <Button variant="secondary" size="sm" onClick={() => handleAction('pause')}>
                            <Pause className="mr-2 h-4 w-4" /> 暂停
                        </Button>
                    )}
                    {task.status === 'PAUSED' && (
                        <Button variant="default" size="sm" onClick={() => handleAction('resume')}>
                            <Play className="mr-2 h-4 w-4" /> 恢复
                        </Button>
                    )}
                    {(task.status === 'FAILED' || task.status === 'COMPLETED') && (
                        <Button variant="outline" size="sm" onClick={handleRetry}>
                            <RotateCcw className="mr-2 h-4 w-4" /> 重试任务
                        </Button>
                    )}
                    {task.status === 'COMPLETED' && (
                        <div className="flex items-center gap-1">
                            <Select value={selectedFormat} onValueChange={setSelectedFormat}>
                                <SelectTrigger className="h-9 w-24">
                                    <SelectValue placeholder="格式" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="srt">SRT</SelectItem>
                                    <SelectItem value="vtt">VTT</SelectItem>
                                    <SelectItem value="ass">ASS</SelectItem>
                                </SelectContent>
                            </Select>
                            <a href={`${import.meta.env.VITE_API_URL || 'http://localhost:8000/api'}/download/tasks/${task.id}/download/${selectedFormat}`} target="_blank" rel="noreferrer">
                                <Button size="sm" variant="default">
                                    <Download className="mr-2 h-4 w-4" /> 下载字幕
                                </Button>
                            </a>
                        </div>
                    )}
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 flex-1 min-h-0">
                {/* Left: Timeline */}
                <Card className="lg:col-span-1 flex flex-col min-h-0 bg-card/50">
                    <CardHeader className="py-4">
                        <CardTitle className="text-sm font-medium">任务进度</CardTitle>
                        {task.status === 'PROCESSING' && <Progress value={task.progress} className="h-1 mt-2" />}
                    </CardHeader>
                    <ScrollArea className="flex-1">
                        <CardContent className="space-y-6">
                            <div className="relative border-l ml-3 pl-6 space-y-6 py-2">
                                {steps.map((step) => {
                                    const isCompleted = (task.completed_step || 0) >= step.id;
                                    const isCurrent = (task.completed_step || 0) + 1 === step.id && task.status === 'PROCESSING';
                                    const isPending = !isCompleted && !isCurrent;
                                    const canRestart = isCompleted && task.status !== 'PROCESSING';

                                    return (
                                        <div key={step.id} className="relative group">
                                            <span className={cn(
                                                "absolute -left-[30px] flex h-6 w-6 items-center justify-center rounded-full border bg-background text-xs font-semibold ring-4 ring-background transition-colors",
                                                isCompleted ? "border-primary bg-primary text-primary-foreground" :
                                                    isCurrent ? "border-primary text-primary animate-pulse" : "text-muted-foreground"
                                            )}>
                                                {isCompleted ? <CheckCircle2 className="h-3.5 w-3.5" /> : step.id}
                                            </span>
                                            <div className="flex items-center justify-between gap-1">
                                                <div className="flex flex-col gap-0.5">
                                                    <span className={cn(
                                                        "text-sm font-medium leading-none",
                                                        isPending && "text-muted-foreground"
                                                    )}>
                                                        {step.name}
                                                    </span>
                                                    {isCurrent && (
                                                        <span className="text-xs text-primary animate-pulse">进行中...</span>
                                                    )}
                                                </div>
                                                {canRestart && (
                                                    <button
                                                        onClick={() => handleRestartFromStep(step.id, step.name)}
                                                        className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-muted text-muted-foreground hover:text-primary"
                                                        title={`从「${step.name}」重新开始`}
                                                    >
                                                        <RotateCcw className="h-3.5 w-3.5" />
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </CardContent>
                    </ScrollArea>
                </Card>

                {/* Right: Tabs (Logs, Files) */}
                <Card className="lg:col-span-3 flex flex-col min-h-0 overflow-hidden">
                    <Tabs defaultValue="logs" className="flex-1 flex flex-col min-h-0">
                        <div className="px-6 py-3 border-b flex items-center justify-between bg-muted/30">
                            <TabsList className="h-9">
                                <TabsTrigger value="logs" className="text-xs"><Terminal className="mr-2 h-3.5 w-3.5" />实时日志</TabsTrigger>
                            </TabsList>
                        </div>

                        <TabsContent value="logs" className="flex-1 min-h-0 p-0 m-0 data-[state=active]:flex flex-col">
                            <ScrollArea className="flex-1 bg-black/90 text-green-400 font-mono text-xs p-4">
                                {logs.map((log, i) => (
                                    <div key={i} className="mb-1 flex gap-2">
                                        <span className="text-muted-foreground shrink-0">
                                            [{log.timestamp ? format(new Date(log.timestamp), 'HH:mm:ss') : '--:--:--'}]
                                        </span>
                                        {/* Note: log.timestamp might be server time string, we can format it if needed */}
                                        <span className={cn(
                                            log.level === 'ERROR' ? 'text-red-500 font-bold' :
                                                log.level === 'WARNING' ? 'text-yellow-500' :
                                                    log.level === 'SUCCESS' ? 'text-green-400 font-bold' : 'text-foreground/80'
                                        )}>
                                            [{log.level}]
                                        </span>
                                        <span className="break-all whitespace-pre-wrap">{log.message}</span>
                                    </div>
                                ))}
                                <div ref={logsEndRef} />
                            </ScrollArea>
                        </TabsContent>
                    </Tabs>
                </Card>
            </div>
        </div>
    );
}
