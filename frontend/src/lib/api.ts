import axios from 'axios';

// 创建 axios 实例
const api = axios.create({
    // In Docker/Production with 'serve', there is no proxy. Point directly to backend.
    // Assuming backend is exposed on port 8000 on the same host.
    baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api',
    headers: {
        'Content-Type': 'application/json',
    },
    timeout: 600000, // 10 minutes for large uploads
});

// 响应拦截器：处理通用错误
api.interceptors.response.use(
    (response) => {
        return response.data;
    },
    (error) => {
        // 统一错误处理
        const message = error.response?.data?.detail || error.message || 'Unknown error';
        console.error('API Error:', message);
        return Promise.reject(error);
    }
);

export interface Log {
    timestamp: string;
    step: string;
    level: string;
    message: string;
}

export interface Task {
    id: string;
    status: 'PENDING' | 'PROCESSING' | 'PAUSED' | 'COMPLETED' | 'FAILED';
    video_path: string;
    created_at: string;
    updated_at: string;
    progress: number;
    current_step: string;
    completed_step: number;
    error_message?: string;
    result_files?: any;
    logs?: Log[];
    source_language?: string;
    target_language?: string;
    original_filename?: string;
}

export const taskApi = {
    createString: (data: FormData) => api.post<any, Task>('/tasks/', data, {
        headers: { 'Content-Type': 'multipart/form-data' }
    }),
    create: (data: any) => {
        if (data instanceof FormData) {
            return api.post<any, Task>('/tasks/', data, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });
        }
        return api.post<any, Task>('/tasks/', data);
    }, // For JSON or FormData
    list: (skip = 0, limit = 100) => api.get<any, Task[]>(`/tasks/?skip=${skip}&limit=${limit}`),
    get: (taskId: string) => api.get<any, Task>(`/tasks/${taskId}`),
    delete: (taskId: string) => api.delete(`/tasks/${taskId}`),
    retry: (taskId: string) => api.post(`/tasks/${taskId}/retry`),
    action: (taskId: string, action: 'pause' | 'resume') => api.post(`/tasks/${taskId}/action?action=${action}`),
    restartFromStep: (taskId: string, step: number) => api.post(`/tasks/${taskId}/restart-from-step?step=${step}`),
};

export default api;
