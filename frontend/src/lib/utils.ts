import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"
import { CheckCircle2, AlertCircle, Clock, Loader2, Circle } from 'lucide-react';
import React from 'react';

export function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs))
}

export const getStatusColor = (status: string) => {
    switch (status?.toUpperCase()) {
        case 'COMPLETED': return 'bg-green-500/10 text-green-500 hover:bg-green-500/20 shadow-none border-green-500/20';
        case 'FAILED': return 'bg-destructive/10 text-destructive hover:bg-destructive/20 shadow-none border-destructive/20';
        case 'PROCESSING': return 'bg-amber-500/10 text-amber-500 hover:bg-amber-500/20 shadow-none border-amber-500/20';
        case 'PAUSED': return 'bg-blue-500/10 text-blue-500 hover:bg-blue-500/20 shadow-none border-blue-500/20';
        case 'PENDING': return 'bg-slate-500/10 text-slate-500 hover:bg-slate-500/20 shadow-none border-slate-500/20';
        default: return 'bg-secondary/50 text-secondary-foreground shadow-none';
    }
};

export const getStatusIcon = (status: string) => {
    const className = "w-3 h-3 mr-1";
    switch (status?.toUpperCase()) {
        case 'COMPLETED': return React.createElement(CheckCircle2, { className: cn(className, "text-green-500") });
        case 'FAILED': return React.createElement(AlertCircle, { className: cn(className, "text-destructive") });
        case 'PROCESSING': return React.createElement(Loader2, { className: cn(className, "animate-spin text-amber-500") });
        case 'PAUSED': return React.createElement(Circle, { className: cn(className, "fill-current text-blue-500") });
        default: return React.createElement(Clock, { className: className });
    }
};

export const getStatusLabel = (status: string) => {
    switch (status?.toUpperCase()) {
        case 'COMPLETED': return '已完成';
        case 'FAILED': return '已失败';
        case 'PROCESSING': return '处理中';
        case 'PAUSED': return '已暂停';
        case 'PENDING': return '排队中';
        default: return status || '未知';
    }
};
