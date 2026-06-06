# Runtime Security Management Dashboard

본 프론트엔드 서비스는 컨테이너 런타임 보안 이벤트를 실시간으로 시각화하고, AI의 분석 결과를 관리자가 직접 제어할 수 있는 관리 대시보드입니다.

---

## ✨ 주요 기능

1. **Dashboard**: 실시간 보안 이벤트 발생 현황, 위험도별 통계, 최근 로그 타임라인 시각화.
2. **Log View**: 상세 보안 이벤트 로그 목록 조회 및 각 이벤트에 대한 AI 인사이트(발생 원인, 권장 조치) 확인.
3. **Chatting (AI Assistant)**: 보안 어시스턴트 챗봇을 통해 탐지된 이벤트에 대해 질문하거나 특정 이벤트를 처리하도록 명령.
4. **Playbook Management**: 자동 대응 규칙 목록 조회 및 관리.
5. **Real-time Interaction**: 탐지된 위협에 대해 즉시 승인, 롤백 또는 대응 방식 변경 지원.

---

## 🛠 기술 스택

- **Framework**: React (Vite 기반)
- **Styling**: Vanilla CSS, Styled-components
- **State Management**: React Hooks (useState, useEffect)
- **API Client**: Axios
- **Iconography**: React Icons

---

## 🚀 시작하기

### 1. 의존성 설치

```bash
npm install
```

### 2. 로컬 실행

```bash
npm run dev
```

기본적으로 `http://localhost:5173`에서 실행됩니다.

---

## 🔗 백엔드 연결 설정

백엔드 API 주소는 `src/api/axiosInstance.js` 파일에서 설정할 수 있습니다.

```javascript
// src/api/axiosInstance.js
const axiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1',
  timeout: 5000,
});
```

---

## 📂 폴더 구조

- `src/api`: Axios 인스턴스 및 백엔드 통신 로직.
- `src/components`: Sidebar, Header 등 공용 컴포넌트.
- `src/pages`: Dashboard, LogView, Chatting, Playbook 등 개별 페이지 화면.
- `src/assets`: 이미지 및 정적 자산.
