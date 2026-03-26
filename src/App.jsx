import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import LogView from './pages/LogView';
import Chatting from './pages/Chatting';

function App() {
  return (
    <BrowserRouter>
      <div style={{ display: 'flex', height: '100vh', width: '100vw', margin: 0, padding: 0 }}>
        <Sidebar />
        <main style={{ flex: 1, padding: '30px', backgroundColor: '#f4f7fc', overflowY: 'auto' }}>
          <Routes>
            {/* 컴포넌트들이 각 경로에 맞게 렌더링됩니다 */}
            <Route path="/" element={<Dashboard />} />
            <Route path="/logs" element={<LogView />} />
            <Route path="/chat" element={<Chatting />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;