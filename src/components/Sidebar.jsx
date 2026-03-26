import React from 'react';
import { NavLink } from 'react-router-dom';
// 전문적인 느낌의 Phosphor 아이콘 사용
import { PiChartPieSliceBold, PiListBulletsBold, PiChatCircleDotsBold, PiPlayBold, PiArrowsCounterClockwiseBold } from "react-icons/pi";

const Sidebar = () => {
  // B2B SaaS 스타일의 차분한 네이비/그레이 스타일
  const navStyle = ({ isActive }) => ({
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '12px 18px',
    textDecoration: 'none',
    color: isActive ? '#fff' : '#94a3b8', // 비활성화는 그레이, 활성화는 화이트
    backgroundColor: isActive ? 'rgba(99, 102, 241, 0.15)' : 'transparent', // 활성화 시 살짝 비치는 배경
    borderRadius: '10px',
    marginBottom: '8px',
    fontWeight: isActive ? '600' : '400',
    transition: 'all 0.2s ease',
  });

  return (
    <div style={{ width: '260px', backgroundColor: '#111827', padding: '30px 20px', display: 'flex', flexDirection: 'column', color: '#fff' }}>
      {/* 와이어프레임 로고 위치 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '50px' }}>
        <div style={{ width: '12px', height: '24px', backgroundColor: '#6366f1', borderRadius: '4px' }}></div>
        <h1 style={{ fontSize: '22px', fontWeight: '800', letterSpacing: '-1px', margin: 0, color: '#fff' }}>RUNTIME</h1>
      </div>

      <nav style={{ flex: 1 }}>
        <NavLink to="/" style={navStyle}>
          <PiChartPieSliceBold size={20} /> 대시보드
        </NavLink>
        <NavLink to="/logs" style={navStyle}>
          <PiListBulletsBold size={20} /> 로그 모니터링
        </NavLink>
        <NavLink to="/chat" style={navStyle}>
          <PiChatCircleDotsBold size={20} /> 보안 어시스턴트
        </NavLink>
      </nav>
      
      {/* 하단 컨트롤 영역 - 와이어프레임 반영 */}
      <div style={{ borderTop: '1px solid #1f2937', paddingTop: '25px', marginTop: '20px' }}>
        <p style={{ fontSize: '12px', color: '#64748b', fontWeight: '600', marginBottom: '15px', letterSpacing: '0.5px' }}>SYSTEM CONTROLS</p>
        <button style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', padding: '12px', backgroundColor: '#d1d5db', color: '#1f2937', border: 'none', borderRadius: '8px', marginBottom: '10px', cursor: 'pointer', fontWeight: '700', fontSize: '14px' }}>
          <PiPlayBold /> 로그 분석 실행
        </button>
        <button style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', padding: '12px', backgroundColor: 'transparent', color: '#94a3b8', border: '1px solid #374151', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', fontSize: '14px' }}>
          <PiArrowsCounterClockwiseBold /> 초기화
        </button>
      </div>
    </div>
  );
};

export default Sidebar;