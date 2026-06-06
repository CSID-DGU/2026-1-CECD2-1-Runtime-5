import React from 'react';
import { NavLink } from 'react-router-dom';
// 전문적인 느낌의 Phosphor 아이콘 사용
import { PiChartPieSliceBold, PiListBulletsBold, PiChatCircleDotsBold, PiBookOpenBold } from "react-icons/pi";

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
        <NavLink to="/playbook" style={navStyle}>
          <PiBookOpenBold size={20} /> Playbook
        </NavLink>
        <NavLink to="/chat" style={navStyle}>
          <PiChatCircleDotsBold size={20} /> 보안 어시스턴트
        </NavLink>
      </nav>
    </div>
  );
};

export default Sidebar;
