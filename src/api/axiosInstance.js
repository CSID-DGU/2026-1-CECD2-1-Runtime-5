import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8080', // 백엔드 서버 주소 (필요시 변경)
  headers: {
    'Content-Type': 'application/json',
  },
});

export const socAPI = {
  // 1. 대시보드 통계 
  getDashboardSummary: () => api.get('/api/v1/dashboard/summary'),
  
  // 2. 대시보드 타임라인 
  getDashboardTimeline: () => api.get('/api/v1/dashboard/timeline'),
  
  // 3. 위협 이벤트 리스트 조회 
  getEvents: () => api.get('/api/v1/events'),
  
  // 4. 단일 위협 상세 조회 
  getEventDetail: (id) => api.get(`/api/v1/events/${id}`),
  
  // 5. 관리자 사후 승인 및 명령 하달 (Human-in-the-loop) [cite: 158, 165]
  patchEventDecision: (id, decision) => api.patch(`/api/v1/events/${id}/decision`, { decision }),
  
  // 6. 챗봇 질의 
  postChat: (message) => api.post('/api/v1/copilot/chat', { message }),
  
  // 7. 리포트 내보내기 
  exportReport: () => api.get('/api/v1/reports/export', { responseType: 'blob' })
};

export default api;