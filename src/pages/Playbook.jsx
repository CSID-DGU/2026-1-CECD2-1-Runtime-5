import React, { useEffect, useMemo, useState } from 'react';
import { socAPI } from '../api/axiosInstance';
import { PiBookOpenBold, PiShieldCheckBold } from 'react-icons/pi';

const badgeStyles = {
  stop: { background: '#fee2e2', color: '#991b1b', border: '1px solid #fecaca' },
  alert: { background: '#fef3c7', color: '#92400e', border: '1px solid #fde68a' },
};

const getActionBadgeStyle = (action) => ({
  display: 'inline-flex',
  alignItems: 'center',
  height: '24px',
  padding: '0 9px',
  borderRadius: '6px',
  fontSize: '11px',
  fontWeight: 800,
  textTransform: 'uppercase',
  whiteSpace: 'nowrap',
  ...(badgeStyles[(action || '').toLowerCase()] || {
    background: '#e0f2fe',
    color: '#075985',
    border: '1px solid #bae6fd',
  }),
});

const formatDate = (value) => {
  if (!value) return '-';

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return date.toLocaleString('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const PlaybookSection = ({ title, icon, items, emptyText }) => (
  <section style={{ marginTop: '26px' }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
      {icon}
      <h2 style={{ margin: 0, fontSize: '18px', fontWeight: 800, color: '#111827' }}>{title}</h2>
      <span style={{ color: '#64748b', fontSize: '13px', fontWeight: 700 }}>{items.length}</span>
    </div>

    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '12px' }}>
      {items.map((item) => (
        <article
          key={`${item.approved_by}-${item.rule_name}`}
          style={{
            background: '#ffffff',
            border: '1px solid #e5e7eb',
            borderRadius: '8px',
            padding: '16px',
            minHeight: '146px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '12px', marginBottom: '10px' }}>
              <h3 style={{ margin: 0, color: '#111827', fontSize: '15px', lineHeight: 1.4, fontWeight: 800 }}>
                {item.rule_name}
              </h3>
              <span style={getActionBadgeStyle(item.action)}>{item.action}</span>
            </div>
            <p style={{ margin: 0, color: '#4b5563', fontSize: '13px', lineHeight: 1.6 }}>
              {item.insight || '등록된 인사이트가 없습니다.'}
            </p>
          </div>
          <time style={{ display: 'block', marginTop: '16px', color: '#9ca3af', fontSize: '12px' }}>
            {formatDate(item.created_at)}
          </time>
        </article>
      ))}
    </div>

    {items.length === 0 && (
      <div style={{ padding: '26px', textAlign: 'center', color: '#94a3b8', background: '#fff', border: '1px solid #e5e7eb', borderRadius: '8px' }}>
        {emptyText}
      </div>
    )}
  </section>
);

const Playbook = () => {
  const [playbooks, setPlaybooks] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchPlaybooks = async () => {
      try {
        const res = await socAPI.getPlaybooks();
        setPlaybooks(res.data || []);
      } catch (err) {
        console.error('플레이북 데이터를 불러오지 못했습니다:', err);
      } finally {
        setLoading(false);
      }
    };

    void fetchPlaybooks();
  }, []);

  const systemPlaybooks = useMemo(
    () => playbooks.filter((item) => item.approved_by === 'system').slice(0, 5),
    [playbooks]
  );

  const engineerPlaybooks = useMemo(
    () => playbooks.filter((item) => item.approved_by === 'security_engineer'),
    [playbooks]
  );

  return (
    <div>
      <header>
        <h1 style={{ margin: 0, fontSize: '26px', fontWeight: 800, color: '#111827' }}>Playbook</h1>
        <p style={{ margin: '8px 0 0 0', color: '#6b7280' }}>자동 대응 정책과 승인된 분석 인사이트</p>
      </header>

      {loading ? (
        <div style={{ marginTop: '28px', padding: '28px', textAlign: 'center', color: '#94a3b8', background: '#fff', border: '1px solid #e5e7eb', borderRadius: '8px' }}>
          플레이북을 불러오는 중입니다.
        </div>
      ) : (
        <>
          <PlaybookSection
            title="System 기본 Playbook"
            icon={<PiBookOpenBold size={22} color="#4f46e5" />}
            items={systemPlaybooks}
            emptyText="등록된 기본 플레이북이 없습니다."
          />
          <PlaybookSection
            title="Security Engineer 승인 Playbook"
            icon={<PiShieldCheckBold size={22} color="#059669" />}
            items={engineerPlaybooks}
            emptyText="보안 엔지니어가 승인한 플레이북이 없습니다."
          />
        </>
      )}
    </div>
  );
};

export default Playbook;
