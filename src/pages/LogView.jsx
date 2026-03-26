import React, { useState, useEffect } from 'react';
import { socAPI } from '../api/axiosInstance';
import { PiTableBold, PiDownloadSimpleBold, PiWarningCircleBold, PiSkullBold, PiInfoBold } from "react-icons/pi";
import './LogView.css';

const LogView = () => {
  // 💡 백엔드 연결 전 UI 확인용 임시 더미 데이터 추가!
  const [logs, setLogs] = useState([
    { id: 'EV-1029', timestamp: '2026-03-26 14:02:11', severity: 'CRITICAL', status: 'PENDING', title: 'Falco: Shell detected inside container' },
    { id: 'EV-1028', timestamp: '2026-03-26 14:01:55', severity: 'HIGH', status: 'AUTO_ACTIONED', title: 'Unexpected outbound connection' },
    { id: 'EV-1027', timestamp: '2026-03-26 13:50:03', severity: 'INFO', status: 'RESOLVED_MANUAL', title: 'Pod scaled out: backend' },
    { id: 'EV-1026', timestamp: '2026-03-26 13:45:12', severity: 'MEDIUM', status: 'CONFIRMED', title: 'Suspicious Ping Command' }
  ]);

  useEffect(() => {
    // 실제 API 연동 로직 (통신 성공 시 진짜 데이터로 덮어씌움)
    socAPI.getEvents()
      .then(res => {
        if (res.data && res.data.length > 0) setLogs(res.data);
      })
      .catch(err => {
        console.error("백엔드 연결 대기 중... (현재 더미 데이터 표시 중):", err);
      });
  }, []);

  // 심각도(Severity)에 따라 아이콘을 다르게 보여주는 함수
  const getSeverityIcon = (sev) => {
    if (!sev) return <PiInfoBold className="sev-icon info" />;
    switch(sev.toUpperCase()) {
      case 'CRITICAL': return <PiSkullBold className="sev-icon critical" />;
      case 'HIGH': return <PiWarningCircleBold className="sev-icon high" />;
      default: return <PiInfoBold className="sev-icon info" />;
    }
  }

  // 리포트 내보내기 버튼 이벤트
  const handleExport = async () => {
    try {
      const response = await socAPI.exportReport();
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'security_report.pdf');
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      alert("백엔드 통신 실패. (리포트 다운로드 기능은 백엔드 서버가 켜져야 작동합니다!)");
    }
  };

  return (
    <div className="log-container">
      <header className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '26px', fontWeight: '800' }}>런타임 로그 모니터링</h1>
          <p style={{ margin: '8px 0 0 0', color: '#6b7280' }}>모든 위협 탐지 및 대응 이력</p>
        </div>
        <button onClick={handleExport} className="export-btn">
          <PiDownloadSimpleBold size={18} /> 리포트 내보내기
        </button>
      </header>

      <div className="log-list-panel">
        <div className="panel-header">
          <h2 style={{ margin: 0 }}>보안 로그</h2>
          <PiTableBold size={20} className="header-icon" />
        </div>
        <div className="log-items">
          {logs.map(log => (
            <div key={log.id} className={`log-item ${log.severity?.toLowerCase()}`}>
              <div className="log-meta">
                {getSeverityIcon(log.severity)}
                <span className="timestamp">{log.timestamp}</span>
              </div>
              <span className="message">[{log.status}] {log.title}</span>
              <span className="log-id">ID: {log.id}</span>
            </div>
          ))}
          {/* 로그가 0개일 때 보여줄 메시지 */}
          {logs.length === 0 && <p style={{ padding: '20px', textAlign: 'center', color: '#94a3b8' }}>기록된 로그가 없습니다.</p>}
        </div>
      </div>
    </div>
  );
};

export default LogView;