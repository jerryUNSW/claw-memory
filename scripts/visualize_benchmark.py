#!/usr/bin/env python3
"""
Visualize RRF vs Interleaved Benchmark Results

Creates comparison charts for latency, efficiency, and effectiveness.

Usage:
    python3 scripts/visualize_benchmark.py
"""

import json
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# Load benchmark results
results_file = Path(__file__).parent.parent / "benchmark_results.json"

with open(results_file, 'r') as f:
    data = json.load(f)

queries = data['queries']
metrics = data['metrics']
summary = data['summary']

# Separate RRF and Interleaved metrics
rrf_metrics = [m for m in metrics if m['method'] == 'RRF']
interleaved_metrics = [m for m in metrics if m['method'] == 'Interleaved']

# Create figure with subplots
fig = plt.figure(figsize=(16, 10))

# ============================================================================
# 1. Latency Comparison (Bar Chart)
# ============================================================================
ax1 = plt.subplot(2, 3, 1)

rrf_latencies = [m['latency_ms'] for m in rrf_metrics]
interleaved_latencies = [m['latency_ms'] for m in interleaved_metrics]

x = np.arange(len(queries))
width = 0.35

bars1 = ax1.bar(x - width/2, rrf_latencies, width, label='RRF', color='#e74c3c', alpha=0.8)
bars2 = ax1.bar(x + width/2, interleaved_latencies, width, label='Interleaved', color='#3498db', alpha=0.8)

ax1.set_xlabel('Query', fontsize=10)
ax1.set_ylabel('Latency (ms)', fontsize=10)
ax1.set_title('Latency Comparison by Query', fontsize=12, fontweight='bold')
ax1.set_xticks(x)
ax1.set_xticklabels([f'Q{i+1}' for i in range(len(queries))], fontsize=8)
ax1.legend()
ax1.grid(axis='y', alpha=0.3)

# ============================================================================
# 2. Speedup Factor (Bar Chart)
# ============================================================================
ax2 = plt.subplot(2, 3, 2)

speedups = [rrf_latencies[i] / interleaved_latencies[i] for i in range(len(queries))]

bars = ax2.bar(x, speedups, color='#2ecc71', alpha=0.8)
ax2.axhline(y=1.0, color='red', linestyle='--', linewidth=1, label='No improvement')
ax2.axhline(y=summary['speedup'], color='orange', linestyle='--', linewidth=2, label=f'Avg: {summary["speedup"]:.2f}x')

ax2.set_xlabel('Query', fontsize=10)
ax2.set_ylabel('Speedup Factor', fontsize=10)
ax2.set_title('Interleaved Speedup vs RRF', fontsize=12, fontweight='bold')
ax2.set_xticks(x)
ax2.set_xticklabels([f'Q{i+1}' for i in range(len(queries))], fontsize=8)
ax2.legend()
ax2.grid(axis='y', alpha=0.3)

# Add value labels on bars
for i, bar in enumerate(bars):
    height = bar.get_height()
    ax2.text(bar.get_x() + bar.get_width()/2., height,
             f'{height:.1f}x',
             ha='center', va='bottom', fontsize=8)

# ============================================================================
# 3. Results Fetched Comparison (Bar Chart)
# ============================================================================
ax3 = plt.subplot(2, 3, 3)

rrf_fetched = [m['results_fetched'] for m in rrf_metrics]
interleaved_fetched = [m['results_fetched'] for m in interleaved_metrics]

bars1 = ax3.bar(x - width/2, rrf_fetched, width, label='RRF', color='#e74c3c', alpha=0.8)
bars2 = ax3.bar(x + width/2, interleaved_fetched, width, label='Interleaved', color='#3498db', alpha=0.8)

ax3.set_xlabel('Query', fontsize=10)
ax3.set_ylabel('Results Fetched', fontsize=10)
ax3.set_title('Efficiency: Results Fetched', fontsize=12, fontweight='bold')
ax3.set_xticks(x)
ax3.set_xticklabels([f'Q{i+1}' for i in range(len(queries))], fontsize=8)
ax3.legend()
ax3.grid(axis='y', alpha=0.3)

# ============================================================================
# 4. Fetch Reduction Percentage (Bar Chart)
# ============================================================================
ax4 = plt.subplot(2, 3, 4)

fetch_reductions = [((rrf_fetched[i] - interleaved_fetched[i]) / rrf_fetched[i] * 100) 
                    for i in range(len(queries))]

bars = ax4.bar(x, fetch_reductions, color='#9b59b6', alpha=0.8)
ax4.axhline(y=summary['fetch_reduction_pct'], color='orange', linestyle='--', 
            linewidth=2, label=f'Avg: {summary["fetch_reduction_pct"]:.1f}%')

ax4.set_xlabel('Query', fontsize=10)
ax4.set_ylabel('Fetch Reduction (%)', fontsize=10)
ax4.set_title('Efficiency Gain: Fewer Fetches', fontsize=12, fontweight='bold')
ax4.set_xticks(x)
ax4.set_xticklabels([f'Q{i+1}' for i in range(len(queries))], fontsize=8)
ax4.legend()
ax4.grid(axis='y', alpha=0.3)

# ============================================================================
# 5. Summary Statistics (Table)
# ============================================================================
ax5 = plt.subplot(2, 3, 5)
ax5.axis('off')

summary_data = [
    ['Metric', 'RRF', 'Interleaved', 'Improvement'],
    ['Avg Latency', f"{summary['rrf_avg_latency']:.2f}ms", 
     f"{summary['interleaved_avg_latency']:.2f}ms", 
     f"{summary['speedup']:.2f}x"],
    ['Avg Fetches', f"{summary['rrf_avg_fetched']:.1f}", 
     f"{summary['interleaved_avg_fetched']:.1f}", 
     f"{summary['fetch_reduction_pct']:.1f}%↓"],
    ['Top-1 Match', '—', '—', f"{summary['top1_match_rate']*100:.0f}%"],
    ['Overlap', '—', '—', f"{summary['avg_overlap_pct']:.1f}%"],
]

table = ax5.table(cellText=summary_data, cellLoc='center', loc='center',
                  colWidths=[0.3, 0.2, 0.25, 0.25])
table.auto_set_font_size(False)
table.set_fontsize(9)
table.scale(1, 2)

# Style header row
for i in range(4):
    table[(0, i)].set_facecolor('#34495e')
    table[(0, i)].set_text_props(weight='bold', color='white')

# Style data rows
for i in range(1, 5):
    for j in range(4):
        if i % 2 == 0:
            table[(i, j)].set_facecolor('#ecf0f1')

ax5.set_title('Performance Summary', fontsize=12, fontweight='bold', pad=20)

# ============================================================================
# 6. Latency Distribution (Box Plot)
# ============================================================================
ax6 = plt.subplot(2, 3, 6)

box_data = [rrf_latencies, interleaved_latencies]
bp = ax6.boxplot(box_data, labels=['RRF', 'Interleaved'], patch_artist=True)

bp['boxes'][0].set_facecolor('#e74c3c')
bp['boxes'][0].set_alpha(0.6)
bp['boxes'][1].set_facecolor('#3498db')
bp['boxes'][1].set_alpha(0.6)

ax6.set_ylabel('Latency (ms)', fontsize=10)
ax6.set_title('Latency Distribution', fontsize=12, fontweight='bold')
ax6.grid(axis='y', alpha=0.3)

# Add mean markers
means = [np.mean(rrf_latencies), np.mean(interleaved_latencies)]
ax6.plot([1, 2], means, 'D', color='orange', markersize=8, label='Mean')
ax6.legend()

# ============================================================================
# Overall title and layout
# ============================================================================
fig.suptitle('RRF vs Interleaved Retrieval: Comprehensive Benchmark Results', 
             fontsize=16, fontweight='bold', y=0.98)

plt.tight_layout(rect=[0, 0, 1, 0.96])

# Save figure
output_file = Path(__file__).parent.parent / "benchmark_comparison.png"
plt.savefig(output_file, dpi=300, bbox_inches='tight')
print(f"✅ Visualization saved to: {output_file}")

plt.show()
