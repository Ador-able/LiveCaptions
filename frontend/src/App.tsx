import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Header from './components/layout/Header';
import Footer from './components/layout/Footer';
import Dashboard from './pages/Dashboard';
import NewTask from './pages/NewTask';
import TaskDetail from './pages/TaskDetail';

const App: React.FC = () => {
    return (
        <Router>
            <div className="min-h-screen bg-gray-50 flex flex-col font-sans">
                {/* 顶部导航栏 */}
                <Header />

                {/* 主要内容区域 */}
                <main className="flex-grow container mx-auto px-4 sm:px-6 lg:px-8 py-8">
                    <Routes>
                        <Route path="/" element={<Dashboard />} />
                        <Route path="/new" element={<NewTask />} />
                        <Route path="/tasks/:taskId" element={<TaskDetail />} />
                    </Routes>
                </main>

                {/* 页脚 */}
                <Footer />
            </div>
        </Router>
    );
};

export default App;
