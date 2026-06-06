import React, { useState, useEffect, useCallback } from 'react';
import { socAPI } from '../api/axiosInstance';
import { PiTableBold, PiDownloadSimpleBold } from "react-icons/pi";
import './LogView.css';

const LogView = () => {
  const [logs, setLogs] = useState([]);

  const fetchLogs = useCallback(async () => {
    try {
      const res = await socAPI.getEvents();
      setLogs(res.data || []);
    } catch (err) {
      console.error("로그 데이터를 불러오지 못했습니다:", err);
    }
  }, []);

  useEffect(() => {
    // 페이지 진입 시 즉시 최신 로그를 가져오고, 이후 3초마다 state만 갱신합니다.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchLogs();

    const intervalId = setInterval(() => {
      void fetchLogs();
    }, 3000);

    return () => {
      clearInterval(intervalId);
    };
  }, [fetchLogs]);

  const getBarColor = (priority, status) => {
    if (status === 'CONFIRMED') return '#10b981';
    switch ((priority || '').toUpperCase()) {
      case 'CRITICAL': return '#ef4444';
      case 'HIGH':     return '#f97316';
      case 'WARNING':  return '#f59e0b';
      default:         return '#3b82f6';
    }
  };

  const getBadgeStyle = (status) => {
    const base = { fontSize: '11px', fontWeight: '600', padding: '2px 8px', borderRadius: '4px', whiteSpace: 'nowrap' };
    switch ((status || '').toUpperCase()) {
      case 'AUTO_ACTIONED': return { ...base, background: '#fed7aa', color: '#9a3412' };
      case 'CONFIRMED':     return { ...base, background: '#bbf7d0', color: '#14532d' };
      case 'ROLLED_BACK':   return { ...base, background: '#e5e7eb', color: '#374151' };
      case 'PENDING':       return { ...base, background: '#fecaca', color: '#7f1d1d' };
      default:              return { ...base, background: '#e5e7eb', color: '#374151' };
    }
  };

  // 리포트 내보내기 버튼 이벤트
  const handleExport = async () => {
    try {
      const response = await socAPI.exportReport();
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'security_report.csv');
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch {
      alert("리포트 다운로드에 실패했습니다. 백엔드 상태를 확인해주세요.");
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
            <div key={log.id} style={{ display: 'flex', alignItems: 'stretch', background: '#ffffff', border: '1px solid #e5e7eb', borderRadius: '8px', marginBottom: '8px', overflow: 'hidden' }}>
              <div style={{ width: '4px', flexShrink: 0, background: getBarColor(log.priority, log.status) }} />
              <div style={{ flex: 1, padding: '12px 16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                  <span style={{ fontWeight: '700', fontSize: '14px', color: '#111827' }}>{log.rule_name}</span>
                  <span style={getBadgeStyle(log.status)}>{log.status}</span>
                </div>
                <div style={{ color: '#6b7280', fontSize: '13px', marginBottom: '4px' }}>{log.llm_insight}</div>
                <div style={{ color: '#9ca3af', fontSize: '11px' }}>{log.timestamp} · {log.id}</div>
              </div>
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
