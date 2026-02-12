import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import NewTask from './pages/NewTask';

const App: React.FC = () => {
    return (
        <Router>
            <div className="min-h-screen bg-gray-50 flex flex-col font-sans">
                {/* 顶部导航栏 */}
                <header className="bg-white shadow-sm z-10 sticky top-0">
                    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                        <div className="flex justify-between h-16 items-center">
                            {/* Logo 和标题 */}
                            <div className="flex-shrink-0 flex items-center">
                                <Link to="/" className="text-2xl font-bold text-blue-600 tracking-tight">
                                    LiveCaptions <span className="text-gray-500 text-sm font-medium">Pro</span>
                                </Link>
                            </div>

                            {/* 导航链接 */}
                            <div className="hidden sm:ml-6 sm:flex sm:space-x-8">
                                <Link to="/" className="border-transparent text-gray-500 hover:border-blue-500 hover:text-gray-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium transition-colors">
                                    任务列表
                                </Link>
                                <Link to="/new" className="border-transparent text-gray-500 hover:border-blue-500 hover:text-gray-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium transition-colors">
                                    新建任务
                                </Link>
                                <a href="#" className="border-transparent text-gray-500 hover:border-blue-500 hover:text-gray-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium transition-colors">
                                    配置
                                </a>
                            </div>

                            {/* 用户信息 / 设置 */}
                            <div className="hidden sm:ml-6 sm:flex sm:items-center">
                                <button className="bg-white p-1 rounded-full text-gray-400 hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500">
                                    <span className="sr-only">View notifications</span>
                                    {/* Bell Icon */}
                                    <svg className="h-6 w-6" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                                    </svg>
                                </button>
                            </div>
                        </div>
                    </div>
                </header>

                {/* 主要内容区域 */}
                <main className="flex-grow container mx-auto px-4 sm:px-6 lg:px-8 py-8">
                    <Routes>
                        <Route path="/" element={<Dashboard />} />
                        <Route path="/new" element={<NewTask />} />
                        {/* 更多路由... */}
                    </Routes>
                </main>

                {/* 页脚 */}
                <footer className="bg-white border-t border-gray-200 mt-auto">
                    <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
                        <p className="text-center text-sm text-gray-400">
                            &copy; 2024 LiveCaptions. All rights reserved. Powered by Whisper & LLM.
                        </p>
                    </div>
                </footer>
            </div>
        </Router>
    );
};

export default App;
