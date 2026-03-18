import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Header } from '@/components/layout/Header';
import { Footer } from '@/components/layout/Footer';
import { Toaster } from 'sonner';

// Lazy load pages
const Dashboard = React.lazy(() => import('@/pages/Dashboard'));
const NewTask = React.lazy(() => import('@/pages/NewTask'));
const TaskDetail = React.lazy(() => import('@/pages/TaskDetail'));

import { WebSocketProvider } from '@/contexts/WebSocketContext';

function App() {
    return (
        <BrowserRouter>
            <WebSocketProvider>
                <div className="relative flex min-h-screen flex-col bg-background font-sans antialiased">
                    <Header />
                    <main className="flex-1 container py-6">
                        <React.Suspense fallback={<div className="flex h-full items-center justify-center p-8 text-muted-foreground">Loading...</div>}>
                            <Routes>
                                <Route path="/" element={<Dashboard />} />
                                <Route path="/new" element={<NewTask />} />
                                <Route path="/tasks/:taskId" element={<TaskDetail />} />
                                <Route path="*" element={<Navigate to="/" replace />} />
                            </Routes>
                        </React.Suspense>
                    </main>
                    <Footer />
                    <Toaster />
                </div>
            </WebSocketProvider>
        </BrowserRouter>
    );
}

export default App;
