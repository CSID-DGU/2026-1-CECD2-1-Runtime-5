import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import argparse
import os

def visualize_ablation(csv_path: str, out_path: str):
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found.")
        return

    # CSV 데이터 로드
    df = pd.read_csv(csv_path)
    
    # LLM이 호출된 데이터만 필터링
    df_llm = df[df['llm_called'] == 1].copy()
    
    if df_llm.empty:
        print("Error: No LLM calls found in the dataset.")
        return

    # prompt_version을 구분하기 위해 experiment_mode 활용
    # baseline_a_v1, baseline_a_v2 등으로 저장되어 있다고 가정
    summary = df_llm.groupby('experiment_mode').agg(
        avg_prompt_tokens=('prompt_tokens', 'mean'),
        avg_completion_tokens=('completion_tokens', 'mean'),
        avg_latency=('latency_ms', 'mean')
    ).reset_index()

    # 폰트 및 스타일 설정
    sns.set_theme(style="whitegrid")
    fig, ax1 = plt.subplots(figsize=(10, 6))

    # X축 범주
    modes = summary['experiment_mode']
    x = range(len(modes))
    width = 0.35

    # 막대 그래프: 평균 프롬프트 토큰 수
    bars1 = ax1.bar([i - width/2 for i in x], summary['avg_prompt_tokens'], width, label='Prompt Tokens', color='#4C72B0')
    # 막대 그래프: 평균 응답 토큰 수
    bars2 = ax1.bar([i + width/2 for i in x], summary['avg_completion_tokens'], width, label='Completion Tokens', color='#55A868')

    ax1.set_xlabel('Prompt Version (Experiment Mode)', fontsize=12)
    ax1.set_ylabel('Average Tokens per Request', fontsize=12)
    ax1.set_title('Prompt Compression Token Efficiency (V1 vs V2)', fontsize=14, fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(modes)

    # 데이터 레이블 추가
    for bar in bars1:
        yval = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2, yval + 2, f'{int(yval)}', ha='center', va='bottom', fontsize=10)
    for bar in bars2:
        yval = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2, yval + 2, f'{int(yval)}', ha='center', va='bottom', fontsize=10)

    # 지연 시간(Latency) 꺾은선 그래프 (오른쪽 Y축)
    ax2 = ax1.twinx()
    line = ax2.plot(x, summary['avg_latency'], color='#C44E52', marker='o', linestyle='-', linewidth=2, markersize=8, label='Avg Latency (ms)')
    ax2.set_ylabel('Average Latency (ms)', fontsize=12)
    ax2.grid(False)

    # 지연 시간 레이블 추가
    for i, val in enumerate(summary['avg_latency']):
        ax2.text(i, val + (val*0.05), f'{int(val)}ms', color='#C44E52', ha='center', va='bottom', fontsize=10, fontweight='bold')

    # 범례 합치기
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper right')

    # 저장
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    plt.tight_layout()
    plt.savefig(out_path, dpi=300)
    print(f"\n✅ Graph successfully saved to: {out_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visualize Token Reduction")
    parser.add_argument("--csv", default="bridge_data/security_stats.csv", help="Path to input CSV")
    parser.add_argument("--out", default="datasets/results/token_compression_graph.png", help="Path to output PNG")
    args = parser.parse_args()
    
    visualize_ablation(args.csv, args.out)