import React, { createContext, useContext, useEffect, useState } from 'react';

interface WebSocketMessage {
    task_id?: string;
    type: 'status' | 'log';
    data: any;
}

interface WebSocketContextType {
    connected: boolean;
    lastMessage: WebSocketMessage | null;
    subscribe: (callback: (msg: WebSocketMessage) => void) => () => void;
}

const WebSocketContext = createContext<WebSocketContextType>({
    connected: false,
    lastMessage: null,
    subscribe: () => () => { },
});

export const useWebSocket = () => useContext(WebSocketContext);

/**
 * 模块级别的全局变量，用于在 React 严格模式双重挂载下保持单例连接。
 */
let globalWs: WebSocket | null = null;
let listeners: Set<(msg: WebSocketMessage) => void> = new Set();
let isConnected = false;
let reconnectAttempts = 0;
let heartbeatInterval: NodeJS.Timeout | null = null;

export const WebSocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [connected, setConnected] = useState(isConnected);
    const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);

    const connect = () => {
        if (globalWs && (globalWs.readyState === WebSocket.CONNECTING || globalWs.readyState === WebSocket.OPEN)) {
            console.log('[WS] Using existing connection');
            return;
        }

        // Use VITE_API_URL or fallback to localhost:8000/api (same default as api.ts)
        const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
        
        let wsUrl: string;
        if (apiUrl.startsWith('http')) {
            wsUrl = apiUrl.replace(/^http/, 'ws');
        } else if (apiUrl.startsWith('//')) {
             wsUrl = (window.location.protocol === 'https:' ? 'wss:' : 'ws:') + apiUrl;
        } else {
             // relative path
             const { protocol, host } = window.location;
             const wsProtocol = protocol === 'https:' ? 'wss:' : 'ws:';
             wsUrl = `${wsProtocol}//${host}${apiUrl}`;
        }

        // Append the specific WebSocket endpoint path
        // valid: ws://localhost:8000/api/ws/global
        if (!wsUrl.endsWith('/')) {
            wsUrl += '/';
        }
        wsUrl += 'ws/global';

        console.log('[WS] Connecting to:', wsUrl);
        const ws = new WebSocket(wsUrl);
        globalWs = ws;

        ws.onopen = () => {
            console.log('[WS] Connected');
            isConnected = true;
            setConnected(true);
            reconnectAttempts = 0;

            // 启动心跳
            if (heartbeatInterval) clearInterval(heartbeatInterval);
            heartbeatInterval = setInterval(() => {
                if (ws.readyState === WebSocket.OPEN) {
                    ws.send('ping');
                }
            }, 30000);
        };

        ws.onmessage = (event) => {
            if (event.data === 'pong') return;
            console.log('[WS] Raw message:', event.data);
            try {
                const message = JSON.parse(event.data);
                setLastMessage(message);
                listeners.forEach(l => l(message));
            } catch (e) {
                // 忽略非 JSON 消息
            }
        };

        ws.onclose = () => {
            console.log('[WS] Disconnected');
            isConnected = false;
            setConnected(false);
            globalWs = null;
            if (heartbeatInterval) {
                clearInterval(heartbeatInterval);
                heartbeatInterval = null;
            }

            // 指数退避重连
            if (reconnectAttempts < 10) {
                const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000);
                console.log(`[WS] Reconnecting in ${delay}ms...`);
                setTimeout(() => {
                    reconnectAttempts++;
                    connect();
                }, delay);
            }
        };

        ws.onerror = (err) => {
            console.error('[WS] Error:', err);
        };
    };

    useEffect(() => {
        // 首次加载
        connect();

        // 可以在这里注册页面特定的监听器，但由于我们使用 lastMessage 状态，
        // 组件重渲染时会自动拿到最新值。

        return () => {
            // 全局 Provider 通常不随页面跳转卸载，只有整个 App 刷新才会卸载
            // 所以我们在这里不做强制关闭，保持长连接
        };
    }, []);

    const subscribe = (callback: (msg: WebSocketMessage) => void) => {
        listeners.add(callback);
        return () => {
            listeners.delete(callback);
        };
    };

    return (
        <WebSocketContext.Provider value={{ connected, lastMessage, subscribe }}>
            {children}
        </WebSocketContext.Provider>
    );
};
