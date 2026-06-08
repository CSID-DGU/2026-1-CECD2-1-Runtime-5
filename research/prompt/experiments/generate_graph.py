import matplotlib.pyplot as plt
import numpy as np

# 데이터 설정 (V2가 V3보다 지연 시간이 낮다는 실험 결과 반영)
labels = ['Baseline (V1)', 'Prompt Opt (V2)', 'Combined (V2 + Cache)']
tokens = [380, 120, 12]      # 1건당 평균 토큰 사용량 (V2는 V3보다 약간 많음)
latency = [8500, 6200, 580]  # 1건당 평균 지연 시간 (ms) (V2가 V3보다 빠름)

x = np.arange(len(labels))
width = 0.35

fig, ax1 = plt.subplots(figsize=(10, 6))

# 1. 토큰 감소량 (막대 그래프)
color_tokens = '#3498db'
bars = ax1.bar(x - width/2, tokens, width, label='Avg Tokens', color=color_tokens, alpha=0.8)
ax1.set_ylabel('Tokens (count)', color=color_tokens, fontsize=12, fontweight='bold')
ax1.tick_params(axis='y', labelcolor=color_tokens)
ax1.set_ylim(0, 450)

# 2. 지연 시간 단축 (꺾은선 그래프)
ax2 = ax1.twinx()
color_latency = '#e74c3c'
line = ax2.plot(x + width/2, latency, color=color_latency, marker='o', 
                linewidth=3, markersize=10, label='Avg Latency (ms)')
ax2.set_ylabel('Latency (ms)', color=color_latency, fontsize=12, fontweight='bold')
ax2.tick_params(axis='y', labelcolor=color_latency)
ax2.set_ylim(0, 10000)

# 스타일 및 라벨
plt.title('Security Pipeline Optimization Performance', fontsize=16, pad=20, fontweight='bold')
ax1.set_xticks(x)
ax1.set_xticklabels(labels, fontsize=11, fontweight='bold')

# 수치 표시 (Data Labels)
for i, v in enumerate(tokens):
    ax1.text(i - width/2, v + 5, f'{v}', ha='center', color=color_tokens, fontweight='bold')
for i, v in enumerate(latency):
    ax2.text(i + width/2, v + 200, f'{v}ms', ha='center', color=color_latency, fontweight='bold')

# 격자 및 레이아웃
ax1.grid(axis='y', linestyle='--', alpha=0.5)
fig.tight_layout()

# 저장
plt.savefig('final_performance_graph.png', dpi=300)
print("그래프가 'final_performance_graph.png'로 저장되었습니다.")
