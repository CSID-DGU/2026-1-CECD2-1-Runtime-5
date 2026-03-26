import React, { useState, useEffect } from 'react';
import { socAPI } from '../api/axiosInstance';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { PiWarningOctagonBold, PiShieldCheckBold, PiSkullBold, PiBroadcastBold, PiXBold } from "react-icons/pi";
import './Dashboard.css';

const Dashboard = () => {
  // 백엔드 연결 전 UI 확인을 위한 기본 더미 데이터 
  const [summary, setSummary] = useState({ total: 24, critical: 5, medium: 2, resolved: 3 });
  const [timeline, setTimeline] = useState([
    { time: '10:00', count: 2 }, { time: '11:00', count: 5 }, { time: '12:00', count: 1 }
  ]);
  const [events, setEvents] = useState([
    { id: 'EV-1029', level: 'CRITICAL', severity: 'CRITICAL', title: 'Falco: Shell detected inside container', timestamp: '2026-03-26 14:02:11', status: 'PENDING' },
    { id: 'EV-1028', level: 'HIGH', severity: 'HIGH', title: 'Unexpected outbound connection', timestamp: '2026-03-26 14:01:55', status: 'AUTO_ACTIONED' }
  ]);
  
  // 상세 조회 모달 상태
  const [selectedEventId, setSelectedEventId] = useState(null);
  const [eventDetail, setEventDetail] = useState(null);
  const [playbook, setPlaybook] = useState(null);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      const [summaryRes, timelineRes, eventsRes] = await Promise.all([
        socAPI.getDashboardSummary(),
        socAPI.getDashboardTimeline(),
        socAPI.getEvents()
      ]);
      // API 통신 성공 시 실제 데이터로 교체 (실패하면 catch로 빠져서 위의 더미데이터가 유지됨)
      if (summaryRes.data) setSummary(summaryRes.data);
      if (timelineRes.data) setTimeline(timelineRes.data);
      if (eventsRes.data) setEvents(eventsRes.data);
    } catch (error) {
      console.error("백엔드 연결 대기 중... (현재 더미 데이터 표시 중):", error);
    }
  };

  // 상세 모달 열기
  const openDetailModal = async (eventId) => {
    setSelectedEventId(eventId);
    try {
      const [detailRes, playbookRes] = await Promise.all([
        socAPI.getEventDetail(eventId),
        socAPI.getPlaybook ? socAPI.getPlaybook(eventId) : Promise.resolve({ data: { actionPlan: "격리 조치 후 프로세스 분석 수행" } })
      ]);
      setEventDetail(detailRes.data || { attackType: 'RCE 시도', aiInsight: '비정상적인 쉘 실행이 탐지되었습니다.' });
      setPlaybook(playbookRes.data);
    } catch (error) {
      console.error("상세 데이터 통신 실패. 더미 데이터 표시", error);
      setEventDetail({ attackType: 'RCE 시도', aiInsight: '비정상적인 쉘 실행이 탐지되었습니다.' });
      setPlaybook({ actionPlan: "1. 해당 Pod 격리\n2. 관리자 알림 발송" });
    }
  };

  const closeModal = () => {
    setSelectedEventId(null);
    setEventDetail(null);
    setPlaybook(null);
  };

  const handleDecision = async (eventId, decisionType) => {
    try {
      await socAPI.patchEventDecision(eventId, decisionType);
      alert(`[${eventId}] 조치가 ${decisionType} 처리되었습니다.`);
      fetchDashboardData();
    } catch (error) {
      alert("백엔드 API 통신 실패 (서버가 켜져 있는지 확인해주세요).");
    }
  };

  return (
    <div className="dashboard-container">
      <header className="page-header">
        <h1>보안 운영 센터 (SOC)</h1>
        <p>통합 런타임 위협 탐지 및 대응 현황</p>
      </header>
      
      {/* 1. 통계 요약 */}
      <div className="stats-grid">
        <div className="stat-card">
          <PiBroadcastBold className="icon" />
          <div className="info"><span className="label">Total Detection</span><span className="value">{summary.total}</span></div>
        </div>
        <div className="stat-card critical">
          <PiSkullBold className="icon alert" />
          <div className="info"><span className="label">High / Critical</span><span className="value">{summary.critical}</span></div>
        </div>
        <div className="stat-card warning">
          <PiWarningOctagonBold className="icon warning" />
          <div className="info"><span className="label">Medium</span><span className="value">{summary.medium}</span></div>
        </div>
        <div className="stat-card success">
          <PiShieldCheckBold className="icon success" />
          <div className="info"><span className="label">Auto/Manual Resolved</span><span className="value">{summary.resolved}</span></div>
        </div>
      </div>

      {/* 2. 보안 이벤트 타임라인 */}
      <div className="panel" style={{ marginBottom: '24px', height: '350px' }}>
        <div className="panel-header"><h2>보안 이벤트 타임라인</h2></div>
        <ResponsiveContainer width="100%" height="80%">
          <LineChart data={timeline} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="time" />
            <YAxis />
            <Tooltip />
            <Line type="monotone" dataKey="count" stroke="#6366f1" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 8 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* 3. 위협 이벤트 리스트 및 상태 제어 */}
      <div className="panel">
        <div className="panel-header"><h2>실시간 위협 탐지 및 대응 제어</h2></div>
        {events.map(event => (
          <div key={event.id} className={`event-card ${event.severity?.toLowerCase()}`}>
            <div className="event-main" onClick={() => openDetailModal(event.id)} style={{ cursor: 'pointer', flex: 1 }}>
              <span className="severity-dot"></span>
              <div className="event-info">
                <h3>{event.title} <span className="status-badge">{event.status}</span></h3>
                <p className="meta">ID: {event.id} | 시간: {event.timestamp} | 🔍 상세 보기</p>
              </div>
            </div>
            
            <div className="event-actions">
              {event.status === 'PENDING' && <span className="waiting-text">대기 중</span>}
              {event.status === 'ANALYZING' && <span className="waiting-text">AI 분석 중...</span>}
              {event.status === 'AUTO_ACTIONED' && (
                <>
                  <button className="action-btn confirm" onClick={(e) => { e.stopPropagation(); handleDecision(event.id, 'CONFIRMED'); }}>조치 승인</button>
                  <button className="action-btn rollback" onClick={(e) => { e.stopPropagation(); handleDecision(event.id, 'ROLLED_BACK'); }}>원상 복구</button>
                </>
              )}
            </div>
          </div>
        ))}
        {events.length === 0 && <p style={{ textAlign: 'center', color: '#94a3b8', padding: '20px' }}>현재 탐지된 위협 이벤트가 없습니다.</p>}
      </div>

      {/* 4. 단일 위협 상세 조회 모달 창 */}
      {selectedEventId && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <button className="close-btn" onClick={closeModal}><PiXBold size={24} /></button>
            <h2 style={{ marginTop: 0 }}>위협 상세 분석 리포트 [{selectedEventId}]</h2>
            
            {eventDetail ? (
              <div className="detail-body">
                <p><strong>공격 유형:</strong> {eventDetail.attackType}</p>
                <p><strong>AI 인사이트:</strong> {eventDetail.aiInsight}</p>
                
                {playbook && (
                  <div className="playbook-box">
                    <h3 style={{ margin: '0 0 10px 0', color: '#4f46e5' }}>대응 Playbook</h3>
                    <p style={{ whiteSpace: 'pre-line', margin: 0 }}>{playbook.actionPlan}</p>
                  </div>
                )}
              </div>
            ) : (
              <p>데이터를 불러오는 중입니다...</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard;