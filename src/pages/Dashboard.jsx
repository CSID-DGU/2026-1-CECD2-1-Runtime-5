import React, { useState, useEffect, useCallback } from 'react';
import api, { socAPI } from '../api/axiosInstance';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { PiWarningOctagonBold, PiShieldCheckBold, PiSkullBold, PiBroadcastBold, PiXBold } from "react-icons/pi";
import './Dashboard.css';

const getPriorityLevel = (priority) => {
  const p = (priority || '').toLowerCase();
  if (p === 'critical' || p === 'high') return 'critical';
  if (p === 'medium' || p === 'warning') return 'medium';
  return 'low';
};

const Dashboard = () => {
  const [summary, setSummary] = useState({ total: 0, critical: 0, medium: 0, resolved: 0 });
  const [timeline, setTimeline] = useState([]);
  const [events, setEvents] = useState([]);
  
  // 상세 조회 모달 상태
  const [selectedEventId, setSelectedEventId] = useState(null);
  const [eventDetail, setEventDetail] = useState(null);
  const [playbook, setPlaybook] = useState(null);
  const [rollbackModal, setRollbackModal] = useState({ eventId: null, action: 'stop' });

  const fetchDashboardData = useCallback(async () => {
    try {
      const [summaryRes, timelineRes, eventsRes] = await Promise.all([
        socAPI.getDashboardSummary(),
        socAPI.getDashboardTimeline(),
        socAPI.getEvents()
      ]);
      if (summaryRes.data) setSummary(summaryRes.data);
      setTimeline(timelineRes.data || []);
      setEvents(eventsRes.data || []);
    } catch (error) {
      console.error("대시보드 데이터를 불러오지 못했습니다:", error);
    }
  }, []);

  useEffect(() => {
    // 페이지 진입 시 즉시 최신 데이터를 가져오고, 이후 3초마다 state만 갱신합니다.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchDashboardData();

    const intervalId = setInterval(() => {
      void fetchDashboardData();
    }, 3000);

    return () => {
      clearInterval(intervalId);
    };
  }, [fetchDashboardData]);

  // 상세 모달 열기
  const openDetailModal = async (eventId) => {
    setSelectedEventId(eventId);
    try {
      const detailRes = await socAPI.getEventDetail(eventId);
      setEventDetail(detailRes.data || { attackType: 'RCE 시도', aiInsight: '비정상적인 쉘 실행이 탐지되었습니다.' });
      setPlaybook(detailRes.data || null);
    } catch (error) {
      console.error("상세 데이터를 불러오지 못했습니다:", error);
      setEventDetail({ attackType: '조회 실패', aiInsight: '상세 데이터를 불러오지 못했습니다.' });
      setPlaybook(null);
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
      await fetchDashboardData();
    } catch {
      alert("백엔드 API 통신 실패 (서버가 켜져 있는지 확인해주세요).");
    }
  };

  const openRollbackModal = (eventId) => {
    setRollbackModal({ eventId, action: 'stop' });
  };

  const closeRollbackModal = () => {
    setRollbackModal({ eventId: null, action: 'stop' });
  };

  const handleRollbackConfirm = async () => {
    if (!rollbackModal.eventId) return;

    try {
      await api.patch(`/api/v1/events/${rollbackModal.eventId}/decision`, {
        decision: 'ROLLED_BACK',
        manual_action: rollbackModal.action,
      });
      alert(`[${rollbackModal.eventId}] 원상 복구 후 ${rollbackModal.action} 조치가 저장되었습니다.`);
      closeRollbackModal();
      await fetchDashboardData();
    } catch {
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
      {(() => {
        const criticalHigh  = summary.critical ?? events.filter(e => getPriorityLevel(e.priority) === 'critical').length;
        const mediumWarning = summary.medium ?? events.filter(e => getPriorityLevel(e.priority) === 'medium').length;
        const lowInfo       = summary.low ?? events.filter(e => getPriorityLevel(e.priority) === 'low').length;
        const autoActioned  = summary.auto_actioned ?? events.filter(e => (e.status || '').toUpperCase() === 'AUTO_ACTIONED').length;
        const confirmed     = summary.resolved ?? events.filter(e => (e.status || '').toUpperCase() === 'CONFIRMED').length;
        const rolledBack    = summary.rolled_back ?? events.filter(e => (e.status || '').toUpperCase() === 'ROLLED_BACK').length;
        const cardStyle = (color) => ({
          background: '#ffffff',
          border: `1px solid ${color}33`,
          borderLeft: `4px solid ${color}`,
          borderRadius: '10px',
          padding: '16px 20px',
        });
        return (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', marginBottom: '12px' }}>
              {[
                { label: 'Critical / High',  value: criticalHigh,  color: '#ef4444' },
                { label: 'Medium / Warning', value: mediumWarning, color: '#f59e0b' },
                { label: 'Low / Info',       value: lowInfo,       color: '#3b82f6' },
              ].map(c => (
                <div key={c.label} style={cardStyle(c.color)}>
                  <div style={{ fontSize: '12px', color: '#374151', marginBottom: '6px' }}>{c.label}</div>
                  <div style={{ fontSize: '28px', fontWeight: '800', color: c.color }}>{c.value}</div>
                </div>
              ))}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', marginBottom: '24px' }}>
              {[
                { label: 'Auto Actioned', value: autoActioned, color: '#f97316' },
                { label: 'Confirmed',     value: confirmed,    color: '#10b981' },
                { label: 'Rolled Back',   value: rolledBack,   color: '#64748b' },
              ].map(c => (
                <div key={c.label} style={cardStyle(c.color)}>
                  <div style={{ fontSize: '12px', color: '#374151', marginBottom: '6px' }}>{c.label}</div>
                  <div style={{ fontSize: '28px', fontWeight: '800', color: c.color }}>{c.value}</div>
                </div>
              ))}
            </div>
          </>
        );
      })()}

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
        {events.map(event => {
          const s = (event.status || '').toUpperCase();
          const badgeStyle = {
            ...(s === 'AUTO_ACTIONED' ? { background: '#fed7aa', color: '#9a3412' }
              : s === 'CONFIRMED'     ? { background: '#bbf7d0', color: '#14532d' }
              : s === 'ROLLED_BACK'   ? { background: '#e5e7eb', color: '#374151' }
              : s === 'PENDING'       ? { background: '#fecaca', color: '#7f1d1d' }
              :                         {}),
          };
          return (
            <div key={event.id} className={`event-card ${(event.priority || event.severity || '').toLowerCase()}`}>
              <div className="event-main" onClick={() => openDetailModal(event.id)} style={{ cursor: 'pointer', flex: 1 }}>
                <span className="severity-dot"></span>
                <div className="event-info">
                  <h3>{event.rule_name || event.title} <span className="status-badge" style={badgeStyle}>{event.status}</span></h3>
                  <p className="meta">ID: {event.id} | 시간: {event.timestamp} | 🔍 상세 보기</p>
                </div>
              </div>
              <div className="event-actions">
                {event.status === 'PENDING'   && <span className="waiting-text">대기 중</span>}
                {event.status === 'ANALYZING' && <span className="waiting-text">AI 분석 중...</span>}
                {event.status === 'AUTO_ACTIONED' && (
                  <>
                    <button className="action-btn confirm"  onClick={(e) => { e.stopPropagation(); handleDecision(event.id, 'CONFIRMED'); }}>조치 승인</button>
                    <button className="action-btn rollback" onClick={(e) => { e.stopPropagation(); openRollbackModal(event.id); }}>원상 복구</button>
                  </>
                )}
              </div>
            </div>
          );
        })}
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
                    <p style={{ margin: '0 0 8px 0' }}><strong>추천 Action:</strong> {playbook.action}</p>
                    <p style={{ whiteSpace: 'pre-line', margin: 0 }}><strong>근거:</strong> {playbook.aiInsight}</p>
                  </div>
                )}
              </div>
            ) : (
              <p>데이터를 불러오는 중입니다...</p>
            )}
          </div>
        </div>
      )}

      {rollbackModal.eventId && (
        <div className="modal-overlay" onClick={closeRollbackModal}>
          <div className="rollback-modal" onClick={(e) => e.stopPropagation()}>
            <button className="close-btn" onClick={closeRollbackModal}><PiXBold size={22} /></button>
            <h2>원상 복구 후 관리자 조치</h2>
            <p className="rollback-event-id">이벤트 ID: {rollbackModal.eventId}</p>

            <div className="rollback-options" role="radiogroup" aria-label="관리자 조치 선택">
              {[
                { value: 'stop', label: 'stop', description: '컨테이너 중지' },
                { value: 'alert', label: 'alert', description: '알림만 발송' },
                { value: 'ignore', label: 'ignore', description: '무시' },
              ].map((option) => (
                <label key={option.value} className="rollback-option">
                  <input
                    type="radio"
                    name="manual_action"
                    value={option.value}
                    checked={rollbackModal.action === option.value}
                    onChange={() => setRollbackModal((prev) => ({ ...prev, action: option.value }))}
                  />
                  <span className="rollback-action">{option.label}</span>
                  <span className="rollback-description">({option.description})</span>
                </label>
              ))}
            </div>

            <div className="rollback-actions">
              <button className="rollback-cancel-btn" onClick={closeRollbackModal}>취소</button>
              <button className="rollback-confirm-btn" onClick={handleRollbackConfirm}>확인</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard;
