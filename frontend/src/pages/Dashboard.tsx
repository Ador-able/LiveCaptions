import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { formatDistanceToNow } from 'date-fns';
import { zhCN } from 'date-fns/locale';
import {
    RotateCcw, Trash2, FileVideo, Play,
    Clock, Loader2
} from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardFooter, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { taskApi, Task } from '@/lib/api';
import { cn, getStatusColor, getStatusIcon, getStatusLabel } from '@/lib/utils';

import { useWebSocket } from '@/contexts/WebSocketContext';

export default function Dashboard() {
    const [tasks, setTasks] = useState<Task[]>([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState<'all' | 'PROCESSING' | 'COMPLETED' | 'FAILED'>('all');
    const { subscribe } = useWebSocket();

    const fetchTasks = async () => {
        try {
            setLoading(true);
            const data = await taskApi.list();
            setTasks(data);
        } catch (error) {
            toast.error('无法加载任务列表');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchTasks();
    }, []);

    // 监听全局 WebSocket 消息，实时更新任务列表中的状态
    useEffect(() => {
        const unsubscribe = subscribe((message) => {
            if (message.type !== 'status') return;

            const updatedTask = message.data;
            const updatedId = updatedTask.id.toLowerCase();
            setTasks(prevTasks =>
                prevTasks.map(task =>
                    task.id.toLowerCase() === updatedId ? { ...task, ...updatedTask } : task
                )
            );
        });

        return unsubscribe;
    }, [subscribe]);

    const handleDelete = async (e: React.MouseEvent, id: string) => {
        e.preventDefault(); // Prevent linking to detail
        e.stopPropagation();
        if (!confirm('确定要删除这个任务吗？')) return;
        try {
            await taskApi.delete(id);
            toast.success('任务已删除');
            fetchTasks();
        } catch (error) {
            toast.error('删除失败');
        }
    };

    const handleRetry = async (e: React.MouseEvent, id: string) => {
        e.preventDefault();
        e.stopPropagation();
        try {
            await taskApi.retry(id);
            toast.success('任务已重试');
            fetchTasks();
        } catch (error) {
            toast.error('重试失败');
        }
    };

    const handleStart = async (e: React.MouseEvent, id: string) => {
        e.preventDefault();
        e.stopPropagation();
        try {
            await taskApi.action(id, 'resume');
            toast.success('任务已启动');
            fetchTasks();
        } catch (error) {
            toast.error('启动失败');
        }
    };

    const filteredTasks = tasks.filter(t => {
        if (filter === 'all') return true;
        return t.status === filter;
    });

    return (
        <div className="space-y-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                    <h2 className="text-2xl font-bold tracking-tight">任务列表</h2>
                    <p className="text-muted-foreground">管理所有的视频字幕生成任务。</p>
                </div>
                <div className="flex items-center gap-2">
                    <Link to="/new">
                        <Button>新建任务</Button>
                    </Link>
                </div>
            </div>

            <div className="flex items-center gap-2 border-b pb-2">
                {(['all', 'PROCESSING', 'COMPLETED', 'FAILED'] as const).map((f) => (
                    <Button
                        key={f}
                        variant={filter === f ? 'secondary' : 'ghost'}
                        size="sm"
                        onClick={() => setFilter(f)}
                        className="capitalize"
                    >
                        {f === 'all' ? '全部' : f === 'PROCESSING' ? '处理中' : f === 'COMPLETED' ? '已完成' : '失败'}
                        <span className="ml-2 rounded-full bg-primary/10 px-1.5 py-0.5 text-xs">
                            {f === 'all' ? tasks.length : tasks.filter(t => t.status === f).length}
                        </span>
                    </Button>
                ))}
            </div>

            {loading && tasks.length === 0 ? (
                <div className="flex h-40 items-center justify-center">
                    <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
            ) : filteredTasks.length === 0 ? (
                <div className="flex h-[400px] flex-col items-center justify-center rounded-md border border-dashed text-center animate-in fade-in-50">
                    <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-secondary/50">
                        <FileVideo className="h-10 w-10 text-muted-foreground" />
                    </div>
                    <h3 className="mt-4 text-lg font-semibold">没有找到任务</h3>
                    <p className="mb-4 text-sm text-muted-foreground">
                        {filter === 'all' ? '当前没有任何任务，请先创建一个。' : '当前筛选条件下没有任务。'}
                    </p>
                    {filter === 'all' && (
                        <Link to="/new">
                            <Button>开始新任务</Button>
                        </Link>
                    )}
                </div>
            ) : (
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {filteredTasks.map((task) => (
                        <Link key={task.id} to={`/tasks/${task.id}`}>
                            <Card className="group relative overflow-hidden transition-all hover:border-primary/50 hover:shadow-md cursor-pointer h-full flex flex-col">
                                <CardHeader className="pb-3">
                                    <div className="flex items-start justify-between gap-2">
                                        <div className="grid gap-1 overflow-hidden">
                                            <CardTitle className="line-clamp-1 text-base leading-tight">
                                                {(task.original_filename || task.video_path || 'Unknown File').split(/[\\/]/).pop()}
                                            </CardTitle>
                                            <CardDescription className="text-xs">
                                                ID: {task.id.substring(0, 8)}
                                            </CardDescription>
                                        </div>
                                        <Badge variant="outline" className={cn(getStatusColor(task.status))}>
                                            {getStatusIcon(task.status)}
                                            {getStatusLabel(task.status)}
                                        </Badge>
                                    </div>
                                </CardHeader>
                                <CardContent className="pb-3 flex-1">
                                    <div className="space-y-4">
                                        <div className="text-xs text-muted-foreground flex items-center gap-2">
                                            <Clock className="h-3.5 w-3.5" />
                                            <span>
                                                {formatDistanceToNow(new Date(task.created_at), { addSuffix: true, locale: zhCN })}
                                            </span>
                                        </div>
                                        {task.status === 'PROCESSING' && (
                                            <div className="space-y-1.5">
                                                <div className="flex justify-between text-[10px] text-muted-foreground">
                                                    <span className="truncate mr-2">{task.current_step || '处理中...'}</span>
                                                    <span>{Math.round(task.progress)}%</span>
                                                </div>
                                                <Progress value={task.progress} className="h-1" />
                                            </div>
                                        )}
                                        {task.status === 'FAILED' && (
                                            <div className="rounded-md bg-destructive/10 p-2 text-[10px] text-destructive line-clamp-2">
                                                {task.error_message || "未知错误"}
                                            </div>
                                        )}
                                    </div>
                                </CardContent>
                                <CardFooter className="pt-0 gap-2 justify-end opacity-0 group-hover:opacity-100 transition-opacity">
                                    {task.status === 'PENDING' && (
                                        <Button variant="outline" size="sm" className="h-7 text-xs" onClick={(e) => handleStart(e, task.id)}>
                                            <Play className="mr-1 h-3 w-3" /> 开始
                                        </Button>
                                    )}
                                    {task.status === 'FAILED' && (
                                        <Button variant="outline" size="sm" className="h-7 text-xs" onClick={(e) => handleRetry(e, task.id)}>
                                            <RotateCcw className="mr-1 h-3 w-3" /> 重试
                                        </Button>
                                    )}
                                    <Button variant="ghost" size="sm" className="h-7 text-xs text-destructive hover:bg-destructive/10 hover:text-destructive" onClick={(e) => handleDelete(e, task.id)}>
                                        <Trash2 className="h-3.5 w-3.5" />
                                    </Button>
                                </CardFooter>
                            </Card>
                        </Link>
                    ))}
                </div>
            )}
        </div>
    );
}
